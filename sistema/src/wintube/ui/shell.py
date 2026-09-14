"""
ui/shell.py
------------------------------------------------------------
A janela do LibertyTube: o esqueleto que segura tudo.

    +------------------------------------------------------+
    |  logo        |  topo: projeto ativo · tema · conta    |
    |  menu        |------------------------------------- |
    |  (etapas,    |  conteúdo da tela                     |
    |  conteúdo)   |                                       |
    |  suporte     |---------------------------------------|
    |  config      |  console (log + progresso)            |
    +------------------------------------------------------+

Ordem de abertura (o que mudou em relação à 2.48):
    1. a janela aparece IMEDIATAMENTE, com um "carregando"
    2. a checagem de login roda em thread
    3. o app só monta o painel quando o login é confirmado

Antes, o app fazia a checagem de licença e a busca de atualização antes
de desenhar qualquer coisa — em internet ruim dava até 20 s de janela
congelada.
"""

import os
import time
import tkinter as tk
import webbrowser

from ..backend import auth, content, session
from ..core import projects, settings, tasks
from ..version import TITULO_JANELA, VERSAO
from ..backend import config as backend_config
from . import media
from .theme import ESPACO, mesclar, tema
from .widgets import Botao, Console, PainelProgresso, Rolagem, Toast

# de quanto em quanto tempo o app confere se o login de 15 dias venceu
# enquanto a janela fica aberta (o cliente pode deixar o app dias ligado)
INTERVALO_VIGIA_MS = 30 * 60 * 1000

try:
    from PIL import Image, ImageTk
    TEM_PIL = True
except ImportError:
    TEM_PIL = False


# menu: (chave, ícone, rótulo, grupo)
MENU = [
    ("inicio", "1", "Baixar vídeos", "FLUXO DO VÍDEO"),
    ("transcrever", "2", "Transcrever", "FLUXO DO VÍDEO"),
    ("cortar", "3", "Cortar cenas", "FLUXO DO VÍDEO"),
    ("editor", "E", "Editor de vídeo", "FLUXO DO VÍDEO"),
    ("montar", "4", "Montar vídeo", "FLUXO DO VÍDEO"),
    ("legenda", "5", "Legenda e marca", "FLUXO DO VÍDEO"),
    ("assistente", "🤖", "Assistente IA", "FERRAMENTAS"),
    ("projetos", "📁", "Meus projetos", "FERRAMENTAS"),
    ("aulas", "🎓", "Crie seu canal", "CONTEÚDO"),
    ("como_usar", "▶️", "Como usar o app", "CONTEÚDO"),
    ("bonus", "🎁", "Bônus", "CONTEÚDO"),
    ("vip", "👑", "Material VIP", "CONTEÚDO"),
    ("networking", "🔥", "Networking", "CONTEÚDO"),
]

# todo emoji que o app desenha — a primeira aparição de cada um custa
# caro no Windows, então eles são preparados antes (_aquecer_icones)
ICONES = [icone for _, icone, _, _ in MENU] + [
    "⚙️", "🗑", "🎬", "☀️", "🌙", "✆", "📁", "⚡", "✓",
]


class LibertyTubeApp:
    """Controla a janela inteira e a navegação entre telas."""

    def __init__(self, root):
        self.root = root
        self.sessao = None
        self.executor = tasks.Executor(root)
        self.pagina = "inicio"
        self.console = None
        self.painel_progresso = None
        self._itens_menu = {}
        self._logos = {}
        self._vigia = None

        root.title(TITULO_JANELA)
        root.configure(bg=tema.cor("fundo"))
        self._dimensionar()
        self._icone()
        tema.aplicar_ttk(root)
        self._carregar_logos()

        root.protocol("WM_DELETE_WINDOW", self._fechar)

        # 1) janela na tela na hora
        self._tela_carregando()
        # 2) login conferido em segundo plano
        root.after(60, self._verificar_acesso)
        # 3) emojis do menu preparados aos poucos, enquanto o cliente
        #    espera ou digita a senha (ver _aquecer_icones)
        root.after(400, self._aquecer_icones)

    # ══ janela ═══════════════════════════════════════════════════════
    def _dimensionar(self):
        self.root.update_idletasks()
        tela_l = self.root.winfo_screenwidth()
        tela_a = self.root.winfo_screenheight()

        if tela_l >= 3000:
            ideal = 1600
        elif tela_l >= 2400:
            ideal = 1480
        elif tela_l >= 1600:
            ideal = 1320
        elif tela_l >= 1200:
            ideal = 1180
        else:
            ideal = tela_l - 40

        largura = min(ideal, max(820, tela_l - 40))
        altura = min(int(ideal * 0.63), max(560, tela_a - 90))
        self.sidebar_largura = 244 if largura >= 1180 else 188

        self.root.minsize(820, 560)
        x = (tela_l // 2) - (largura // 2)
        y = max(0, (tela_a // 2) - (altura // 2) - 20)
        self.root.geometry(f"{largura}x{altura}+{x}+{y}")

    def _icone(self):
        from ..core import paths
        try:
            if self.root.tk.call("tk", "windowingsystem") == "win32":
                self.root.iconbitmap(paths.asset("libertytube.ico"))
        except Exception:
            pass

    def _carregar_logos(self):
        from ..core import paths
        if not TEM_PIL:
            return
        try:
            base = Image.open(paths.asset("libertytube.png")).convert("RGBA")
            caixa = base.getbbox()
            if caixa:
                base = base.crop(caixa)
            pequeno = base.copy()
            pequeno.thumbnail((150, 42))
            grande = base.copy()
            grande.thumbnail((250, 82))
            self._logos = {"menu": ImageTk.PhotoImage(pequeno),
                           "hero": ImageTk.PhotoImage(grande)}
        except Exception:
            self._logos = {}

    def logo(self, tamanho="menu"):
        return self._logos.get(tamanho)

    def _fechar(self):
        """O X da janela: fecha direto (só avisa se tem tarefa rodando)."""
        if self.executor.ocupado():
            from . import dialogs
            if not dialogs.confirmar(
                    self, "Fechar o LibertyTube",
                    "Tem uma tarefa rodando agora. Se você fechar, ela é "
                    "cancelada e o que já foi feito continua salvo.\n\n"
                    "Fechar mesmo assim?",
                    sim="Fechar", nao="Continuar", icone="!", perigoso=True):
                return
            self.executor.cancelar()
        self.root.destroy()

    def _limpar_janela(self):
        for widget in self.root.winfo_children():
            widget.destroy()

    # ══ emojis: o custo escondido da primeira montagem ════════════════
    def _aquecer_icones(self, indice=0):
        """Desenha cada emoji uma vez, um por vez, antes da hora.

        O Windows leva ~60 ms pra resolver e rasterizar cada emoji na
        PRIMEIRA vez que ele aparece. O menu tem vinte: se essa conta
        toda cair de uma vez na montagem do painel, o app fica quase um
        segundo sem responder — bem no momento em que o cliente entra, e
        foi exatamente isso que ele sentiu como "travou ao sair do login".

        Aqui a conta é paga em pedacinhos (um ícone por vez), enquanto a
        tela está parada esperando o login. Depois disso a montagem do
        painel cai de ~650 ms pra ~160 ms.
        """
        if getattr(self, "container", None) is not None:
            return                       # o painel já está montado: tarde demais
        if indice >= len(ICONES):
            return
        try:
            caixa = tk.Frame(self.root)
            for tamanho in (10, 11, 13, 22, 24):
                tk.Label(caixa, text=ICONES[indice],
                         font=(tema.familia, tamanho)).pack()
            caixa.update_idletasks()
            caixa.destroy()
            self.root.after(40, lambda: self._aquecer_icones(indice + 1))
        except Exception:
            pass                         # aquecer é bônus: nunca derruba o app

    # ══ boot ═════════════════════════════════════════════════════════
    def _tela_carregando(self, mensagem="Abrindo o LibertyTube…"):
        self._limpar_janela()
        self.console = None
        self.painel_progresso = None
        fundo = tk.Frame(self.root, bg=tema.cor("fundo"))
        fundo.pack(fill="both", expand=True)

        centro = tk.Frame(fundo, bg=tema.cor("fundo"))
        centro.place(relx=0.5, rely=0.5, anchor="center")

        if self.logo("hero"):
            tk.Label(centro, image=self.logo("hero"),
                     bg=tema.cor("fundo")).pack(pady=(0, 18))
        else:
            tk.Label(centro, text="LibertyTube", font=tema.fonte("display", 26),
                     bg=tema.cor("fundo"), fg=tema.cor("texto")).pack(pady=(0, 18))

        self._rotulo_carregando = tk.Label(
            centro, text=mensagem, font=tema.fonte("corpo"),
            bg=tema.cor("fundo"), fg=tema.cor("texto2"))
        self._rotulo_carregando.pack()

        from tkinter import ttk
        barra = ttk.Progressbar(centro, style="WT.Horizontal.TProgressbar",
                                mode="indeterminate", length=220)
        barra.pack(pady=(18, 0))
        barra.start(14)

    def _verificar_acesso(self):
        tasks.em_thread(auth.verificar, ao_terminar=self._acesso_conferido,
                        ao_falhar=self._acesso_falhou, root=self.root)

    def _acesso_falhou(self, erro):
        # falha fechada: sem confirmar o acesso, o app não abre
        self.mostrar_login(f"Não consegui verificar seu acesso: {erro}")

    def _acesso_conferido(self, resultado):
        status = (resultado or {}).get("status")
        if status == "ok":
            self.sessao = resultado.get("sessao")
            if auth.precisa_criar_senha(self.sessao):
                self.mostrar_primeira_senha()
                return
            self.abrir_painel(aviso=resultado.get("mensagem"),
                              offline=resultado.get("offline"))
        else:
            self.mostrar_login((resultado or {}).get("mensagem", ""))

    # ══ telas de conta ═══════════════════════════════════════════════
    def mostrar_login(self, mensagem=""):
        from .screens import login
        self._parar_vigia()
        self._limpar_janela()
        self.sessao = None
        self.console = None
        self.painel_progresso = None
        login.montar(self, self.root, mensagem)

    def mostrar_primeira_senha(self):
        from .screens import first_password
        self._limpar_janela()
        self.console = None
        self.painel_progresso = None
        first_password.montar(self, self.root)

    def entrar_com(self, sessao):
        """Chamado pela tela de login quando o servidor aceita."""
        self.sessao = sessao
        if auth.precisa_criar_senha(sessao):
            self.mostrar_primeira_senha()
        else:
            self.abrir_painel()

    def sair_da_conta(self):
        from . import dialogs
        if not dialogs.confirmar(
                self, "Sair da conta",
                "Sair da sua conta neste computador?\n\n"
                "Você vai precisar do email e da senha pra entrar de novo.",
                sim="Sair da conta", nao="Ficar", icone="🔓"):
            return
        if self.executor.ocupado():
            self.executor.cancelar()
        auth.sair()
        content.limpar_cache()
        self.mostrar_login("Sessão encerrada. Entre de novo pra continuar.")

    # ══ prazo do login (15 dias) ═════════════════════════════════════
    def _vigiar_sessao(self):
        """O app pode ficar dias aberto. Aqui ele confere de tempos em
        tempos se o prazo do login venceu e desloga na hora certa."""
        self._vigia = None
        if not self.sessao:
            return

        if not auth.sessao_vencida(self.sessao):
            self._agendar_vigia(INTERVALO_VIGIA_MS)
            return

        if self.executor.ocupado():
            # não derruba o cliente no meio de uma renderização de 40 min
            self.log("O prazo do login venceu — vou pedir a senha assim que "
                     "esta tarefa terminar.", "aviso")
            self._agendar_vigia(5 * 60 * 1000)
            return

        auth.sair()
        content.limpar_cache()
        self.mostrar_login(
            auth.MSG_PRAZO.format(dias=backend_config.MAX_DIAS_SESSAO))

    def _agendar_vigia(self, atraso_ms):
        self._parar_vigia()
        try:
            self._vigia = self.root.after(atraso_ms, self._vigiar_sessao)
        except Exception:
            self._vigia = None

    def _parar_vigia(self):
        if self._vigia:
            try:
                self.root.after_cancel(self._vigia)
            except Exception:
                pass
            self._vigia = None

    # ══ painel principal ═════════════════════════════════════════════
    def abrir_painel(self, aviso=None, offline=False):
        self._limpar_janela()
        self._montar_layout()
        self.navegar("inicio")

        self.log(f"LibertyTube {VERSAO} pronto.", "sistema")
        self.log(f"Projeto ativo: {projects.atual().nome}", "info")
        if offline:
            self.log("Sem internet — usando a última sessão válida.", "aviso")
        elif aviso:
            self.log(aviso, "aviso")

        faltam = auth.dias_restantes(self.sessao)
        if self.sessao and faltam <= 3:
            self.log(f"Seu login vale por mais {faltam} dia(s) — depois o "
                     "LibertyTube pede email e senha de novo.", "aviso")

        self._agendar_vigia(INTERVALO_VIGIA_MS)
        self.root.after(500, self._novidades)
        self.root.after(1500, self._checar_atualizacao)

    def _montar_layout(self):
        self.container = tk.Frame(self.root, bg=tema.cor("fundo"))
        self.container.pack(fill="both", expand=True)

        self._montar_menu()

        direita = tk.Frame(self.container, bg=tema.cor("fundo"))
        direita.pack(side="left", fill="both", expand=True)

        self._montar_topo(direita)

        self.area = tk.Frame(direita, bg=tema.cor("fundo"))
        self.area.pack(fill="both", expand=True, padx=ESPACO["lg"],
                       pady=(ESPACO["sm"], 0))

        # a faixa de progresso fica ACIMA do conteúdo (e some quando não
        # tem nada rodando): é a resposta pro "o app travou?"
        self.painel_progresso = PainelProgresso(
            direita, ao_cancelar=self.cancelar_tarefa,
            pack_opcoes={"fill": "x", "padx": ESPACO["lg"],
                         "pady": (ESPACO["sm"], 0), "before": self.area})

        self.console = Console(direita, ao_cancelar=self.cancelar_tarefa)
        self.console.pack(fill="x", padx=ESPACO["lg"],
                          pady=(ESPACO["sm"], ESPACO["md"]))

    # ── menu lateral ──
    def _montar_menu(self):
        self.menu = tk.Frame(self.container, bg=tema.cor("sidebar"),
                             width=self.sidebar_largura)
        self.menu.pack(side="left", fill="y")
        self.menu.pack_propagate(False)

        topo = tk.Frame(self.menu, bg=tema.cor("sidebar"))
        topo.pack(fill="x", pady=(18, 10), padx=18)
        if self.logo("menu"):
            tk.Label(topo, image=self.logo("menu"),
                     bg=tema.cor("sidebar")).pack(anchor="w")
        else:
            tk.Label(topo, text="LibertyTube", font=tema.fonte("titulo", 18),
                     bg=tema.cor("sidebar"), fg=tema.cor("texto")).pack(anchor="w")
        tk.Label(topo, text=f"versão {VERSAO}", font=tema.fonte("micro"),
                 bg=tema.cor("sidebar"), fg=tema.cor("muted")).pack(anchor="w")

        # o rodapé é empacotado ANTES da lista: em janela baixa o Tk aperta
        # o último a entrar, e é a lista que deve encolher (ela rola) —
        # nunca o "Configurações", que só existe aqui embaixo
        rodape = tk.Frame(self.menu, bg=tema.cor("sidebar"))
        rodape.pack(side="bottom", fill="x", pady=(6, 12))
        self._rodape_menu = rodape

        tk.Frame(rodape, bg=tema.cor("borda_suave"), height=1).pack(
            fill="x", padx=18, pady=(0, 8))
        self._item_menu(rodape, "config", "⚙️", "Configurações")

        rolagem = Rolagem(self.menu, bg=tema.cor("sidebar"))
        rolagem.pack(fill="both", expand=True)
        lista = rolagem.corpo

        grupo_atual = None
        for chave, icone, rotulo_texto, grupo in MENU:
            if grupo != grupo_atual:
                grupo_atual = grupo
                tk.Label(lista, text=grupo, font=tema.fonte("micro", peso="bold"),
                         bg=tema.cor("sidebar"), fg=tema.cor("muted"), anchor="w"
                         ).pack(fill="x", padx=22, pady=(12, 4))
            self._itens_menu[chave] = self._item_menu(lista, chave, icone,
                                                      rotulo_texto)

        # botão de suporte: buscado no servidor, sem travar a tela
        tasks.em_thread(lambda: content.config_app("whatsapp_suporte"),
                        ao_terminar=self._criar_botao_suporte, root=self.root)

    def _item_menu(self, parent, chave, icone, texto):
        linha = tk.Frame(parent, bg=tema.cor("sidebar"), cursor="hand2")
        linha.pack(fill="x", padx=10, pady=1)

        indicador = tk.Frame(linha, bg=tema.cor("sidebar"), width=3)
        indicador.pack(side="left", fill="y")

        etiqueta = tk.Label(linha, text=f"  {icone}   {texto}",
                            font=tema.fonte("corpo"), bg=tema.cor("sidebar"),
                            fg=tema.cor("texto2"), anchor="w", padx=8, pady=7)
        etiqueta.pack(side="left", fill="both", expand=True)

        def entrar(_=None):
            if self.pagina != chave:
                linha.configure(bg=tema.cor("card_hover"))
                etiqueta.configure(bg=tema.cor("card_hover"), fg=tema.cor("texto"))

        def sair(_=None):
            if self.pagina != chave:
                linha.configure(bg=tema.cor("sidebar"))
                etiqueta.configure(bg=tema.cor("sidebar"), fg=tema.cor("texto2"))

        for widget in (linha, indicador, etiqueta):
            widget.bind("<Enter>", entrar)
            widget.bind("<Leave>", sair)
            widget.bind("<Button-1>", lambda e, c=chave: self.navegar(c))

        item = {"linha": linha, "indicador": indicador, "etiqueta": etiqueta}
        self._itens_menu[chave] = item
        return item

    def _marcar_menu(self, chave):
        for c, item in self._itens_menu.items():
            ativo = (c == chave)
            cor_fundo = tema.cor("card_hover") if ativo else tema.cor("sidebar")
            item["linha"].configure(bg=cor_fundo)
            item["etiqueta"].configure(
                bg=cor_fundo,
                fg=tema.cor("texto") if ativo else tema.cor("texto2"),
                font=tema.fonte("corpo_forte" if ativo else "corpo"))
            item["indicador"].configure(
                bg=tema.cor("primario") if ativo else cor_fundo)

    def _criar_botao_suporte(self, url):
        if not url or not isinstance(url, str) or not url.strip():
            return
        if not hasattr(self, "_rodape_menu") or not self._rodape_menu.winfo_exists():
            return
        caixa = tk.Frame(self._rodape_menu, bg=tema.cor("sidebar"))
        caixa.pack(fill="x", padx=14, pady=(0, 8),
                   before=self._rodape_menu.winfo_children()[0])
        Botao(caixa, "Falar com suporte", lambda: webbrowser.open(url.strip()),
              variante="whatsapp", icone="✆", altura=38, expandir=True
              ).pack(fill="x")

    # ── topo ──
    def _montar_topo(self, parent):
        topo = tk.Frame(parent, bg=tema.cor("fundo"))
        topo.pack(fill="x", padx=ESPACO["lg"], pady=(ESPACO["md"], 0))

        # projeto ativo
        projeto = tk.Frame(topo, bg=tema.cor("card"), highlightthickness=1,
                           highlightbackground=tema.cor("borda"), cursor="hand2")
        projeto.pack(side="left")
        etiqueta = tk.Label(projeto,
                            text=f"  📁  {projects.atual().nome}   ▾  ",
                            font=tema.fonte("pequeno_forte"), bg=tema.cor("card"),
                            fg=tema.cor("texto"), padx=6, pady=7)
        etiqueta.pack()
        for widget in (projeto, etiqueta):
            widget.bind("<Button-1>", lambda e: self.navegar("projetos"))

        plataforma, formato = projects.PLATAFORMAS[projects.plataforma()]
        tk.Label(topo, text=f"   {plataforma} · {formato}",
                 font=tema.fonte("pequeno"), bg=tema.cor("fundo"),
                 fg=tema.cor("muted")).pack(side="left")

        # conta
        conta = tk.Label(topo, text=f"  {auth.email_do(self.sessao) or 'conta'}  ",
                         font=tema.fonte("micro"), bg=tema.cor("fundo"),
                         fg=tema.cor("muted"))
        conta.pack(side="right", padx=(10, 0))

        # aviso do relogin obrigatório — só aparece quando está perto
        faltam = auth.dias_restantes(self.sessao)
        if self.sessao and faltam <= 5:
            from .widgets import Chip
            Chip(topo,
                 "login vence hoje" if faltam == 0
                 else f"login vence em {faltam} dia(s)",
                 cor=mesclar(tema.cor("aviso"), tema.cor("fundo"), 0.75),
                 cor_texto=tema.cor("aviso")).pack(side="right", padx=(10, 0))

        Botao(topo, "Modo claro" if tema.escuro else "Modo escuro",
              self.alternar_tema, variante="secundario", altura=34,
              icone="☀️" if tema.escuro else "🌙",
              fonte=tema.fonte("micro")).pack(side="right")

    # ══ navegação ════════════════════════════════════════════════════
    def navegar(self, chave):
        from .screens import (assistant, assembly, captions, cuts, editor, home,
                              library, projects_screen, settings_screen,
                              transcribe_screen)

        telas = {
            "inicio": home.montar,
            "transcrever": transcribe_screen.montar,
            "cortar": cuts.montar,
            "editor": editor.montar,
            "montar": assembly.montar,
            "legenda": captions.montar,
            "assistente": assistant.montar,
            "projetos": projects_screen.montar,
            "aulas": library.montar_aulas,
            "como_usar": library.montar_como_usar,
            "bonus": library.montar_bonus,
            "vip": library.montar_vip,
            "networking": library.montar_networking,
            "config": settings_screen.montar,
        }

        montar = telas.get(chave)
        if not montar:
            return

        self.pagina = chave
        self._marcar_menu(chave)

        for widget in self.area.winfo_children():
            widget.destroy()

        rolagem = Rolagem(self.area)
        rolagem.pack(fill="both", expand=True)
        try:
            montar(self, rolagem.corpo)
        except Exception as e:  # noqa: BLE001 — tela quebrada não derruba o app
            self.log(f"Erro ao abrir a tela: {e}", "erro")
            tk.Label(rolagem.corpo,
                     text=f"Não consegui abrir esta tela.\n\n{e}",
                     font=tema.fonte("corpo"), bg=tema.cor("fundo"),
                     fg=tema.cor("perigo"), justify="left").pack(anchor="w", pady=20)

    def recarregar(self):
        self.navegar(self.pagina)

    def alternar_tema(self):
        tema.alternar()
        tema.aplicar_ttk(self.root)
        pagina = self.pagina
        self.root.configure(bg=tema.cor("fundo"))
        self._limpar_janela()
        self._itens_menu = {}
        self._montar_layout()
        self.navegar(pagina)
        self.log(f"LibertyTube {VERSAO} — modo {tema.modo}.", "sistema")
        self.log(f"Projeto ativo: {projects.atual().nome}", "info")

    # ══ console e tarefas ════════════════════════════════════════════
    def log(self, mensagem, nivel="info"):
        if self.console:
            self.console.escrever(mensagem, nivel)

    def aviso(self, mensagem, tipo="sucesso"):
        Toast(self.root, mensagem, tipo)

    def cancelar_tarefa(self):
        self.executor.cancelar()
        self.log("Cancelando… (pode levar alguns segundos)", "aviso")

    def rodar(self, funcao, nome="Processando", ao_terminar=None,
              ao_falhar=None, recarregar=False, prontos=None):
        """Roda uma etapa do pipeline mostrando log, progresso e o botão
        de cancelar. `funcao` recebe (log, progresso, ctx).

        `prontos` é uma função que devolve os vídeos que a etapa gerou.
        Quando ela termina, esses vídeos abrem no player do LibertyTube, no
        formato da rede escolhida — é o que o cliente quer ver na hora,
        em vez de ir caçar arquivo na pasta.
        """
        if self.executor.ocupado():
            self.aviso("Espere a tarefa atual terminar.", "aviso")
            return

        comeco = time.time()
        self.console.ocupado(True, nome.lower())
        self.log(f"▶ {nome}", "sistema")
        if self.painel_progresso:
            self.painel_progresso.iniciar(nome)

        def progrediu(texto, pct=None):
            self.console.progresso(texto, pct)
            if self.painel_progresso:
                self.painel_progresso.atualizar(texto, pct)

        def terminou(resultado):
            self.log(f"✔ {nome} — concluído.", "ok")
            if self.painel_progresso:
                self.painel_progresso.finalizar("ok")
            self.aviso(f"{nome} concluído!", "sucesso")
            if ao_terminar:
                ao_terminar(resultado)
            if recarregar:
                self.recarregar()
            if prontos:
                # depois de redesenhar a tela: modal nascendo junto com a
                # remontagem fica atrás do app
                self.root.after(
                    500, lambda: self._mostrar_prontos(prontos, comeco))

        def falhou(problema):
            from . import dialogs
            self.log(f"✖ {nome} — {problema}", "erro")
            if self.painel_progresso:
                self.painel_progresso.finalizar("erro",
                                                str(problema).split("\n")[0])
            dialogs.erro(self, nome, str(problema))
            if ao_falhar:
                ao_falhar(problema)

        def cancelou():
            self.log(f"■ {nome} — cancelado por você.", "aviso")
            if self.painel_progresso:
                self.painel_progresso.finalizar("cancelado")

        self.executor.rodar(
            funcao, nome=nome,
            ao_log=self.log,
            ao_progresso=progrediu,
            ao_terminar=terminou, ao_falhar=falhou, ao_cancelar=cancelou,
            ao_fim=lambda: self.console.ocupado(False))

    def _mostrar_prontos(self, prontos, comeco):
        """Abre no player o que a etapa acabou de gerar.

        Só entra o que foi criado DEPOIS que a etapa começou: senão o
        modo automático abriria o vídeo da semana passada quando o
        cliente mandasse só baixar cenas.
        """
        from . import player
        try:
            arquivos = [a for a in (prontos() or [])
                        if os.path.exists(a)
                        and os.path.getmtime(a) >= comeco - 5]
        except Exception:
            return
        if arquivos:
            player.abrir(self, arquivos, 0)

    # ══ novidades e atualização ══════════════════════════════════════
    def _novidades(self):
        from .screens import whats_new
        try:
            whats_new.mostrar_se_novo(self)
        except Exception:
            pass

    def _checar_atualizacao(self):
        from ..backend import updates
        from . import dialogs

        def achou(dados):
            if not dados:
                return
            versao = dados.get("versao")
            self.log(f"Existe uma versão nova do LibertyTube ({versao}).", "sistema")
            dialogs.atualizacao(self, dados,
                                lambda: self._aplicar_atualizacao(dados))

        tasks.em_thread(updates.checar, ao_terminar=achou, root=self.root)

    def _aplicar_atualizacao(self, dados):
        from ..backend import updates
        from . import dialogs

        def trabalho(log, progresso, ctx):
            return updates.aplicar(dados, progresso=progresso)

        def pronto(_):
            dialogs.aviso(
                self, "Atualização instalada",
                 f"O LibertyTube {dados.get('versao', '')} já está no seu "
                "computador.\n\nPra começar a usar a versão nova, ele "
                "precisa abrir de novo — leva 2 segundos.",
                botao="Reiniciar agora", acao=updates.reiniciar,
                icone="✓", cor="sucesso",
                botao_secundario=("Depois", None))

        self.rodar(trabalho, nome="Atualizando o LibertyTube", ao_terminar=pronto)

    # ══ atalhos usados pelas telas ═══════════════════════════════════
    @property
    def projeto(self):
        return projects.atual()

    def abrir_link(self, url):
        if url:
            webbrowser.open(url)

    def preferencia(self, chave, valor=None):
        if valor is None:
            return settings.get(chave)
        return settings.set(chave, valor)

    def usuario(self):
        return auth.usuario(self.sessao or session.carregar())
