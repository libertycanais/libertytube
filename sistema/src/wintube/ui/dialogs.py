"""
ui/dialogs.py
------------------------------------------------------------
As janelas de aviso do LibertyTube — com a cara do app, não com a cara do
Windows.

Antes o app usava `messagebox` pra avisar de atualização e um Toplevel
cru pras novidades: moldura cinza do Windows, fonte do sistema, botão
"Sim/Não". Parecia outro programa aparecendo por cima do LibertyTube.

Aqui a janela é desenhada por nós: sem moldura do sistema, topo em
degradê, conteúdo rolável e botões do próprio app. Arrasta pelo topo,
Esc fecha, e ela nasce centralizada em cima da janela principal.

    Modal        a janela em si (topo, corpo, rodapé)
    novidades    "o que há de novo nesta versão"
    atualizacao  "saiu a versão X — atualizar agora?"
    aviso        mensagem simples com um botão
"""

import re
import tkinter as tk

from ..version import VERSAO
from .theme import ESPACO, escurecer, mesclar, tema
from .widgets import Botao, Rolagem, degrade


class Modal(tk.Toplevel):
    """Janela de aviso sem moldura do Windows.

    Use `.corpo` pra colocar o conteúdo e `.rodape` pros botões.
    """

    def __init__(self, app, titulo, subtitulo="", icone="✨",
                 largura=600, altura=520, cor="primario"):
        # `app` pode ser o LibertyTubeApp ou qualquer widget — assim as
        # funções soltas (media.py) também conseguem abrir a janela
        self.raiz = getattr(app, "root", app)
        super().__init__(self.raiz, bg=tema.cor("fundo"))
        self.app = app
        self._fechada = False

        self.overrideredirect(True)          # tira a barra do Windows
        self.transient(self.raiz.winfo_toplevel())
        # SEM ISTO O APP TRAVA. Janela sem moldura não entra na ordem de
        # empilhamento do Windows como janela normal: ela nascia ATRÁS do
        # app. Como ela prende o clique (grab_set), o cliente clicava em
        # tudo e nada respondia — sem ver janela nenhuma na tela. Era o
        # "aperto em sair e o app não faz nada".
        self.attributes("-topmost", True)
        self.configure(highlightthickness=1,
                       highlightbackground=tema.cor("borda"),
                       highlightcolor=tema.cor("borda"))

        self._centralizar(largura, altura)

        # ── topo em degradê ──
        self.topo = tk.Canvas(self, height=86, highlightthickness=0, bd=0,
                              bg=tema.cor(cor))
        self.topo.pack(fill="x")
        self._cor_topo = cor
        self._titulo = titulo
        self._subtitulo = subtitulo
        self._icone = icone
        self.topo.bind("<Configure>", lambda e: self._pintar_topo())

        # arrastar a janela pelo topo
        self._arraste = {"x": 0, "y": 0}
        self.topo.bind("<Button-1>", self._pegar)
        self.topo.bind("<B1-Motion>", self._arrastar)

        # ── corpo ──
        self.corpo = tk.Frame(self, bg=tema.cor("fundo"))
        self.corpo.pack(fill="both", expand=True, padx=ESPACO["lg"],
                        pady=(ESPACO["lg"], 0))

        # ── rodapé ──
        self.rodape = tk.Frame(self, bg=tema.cor("fundo"))
        self.rodape.pack(fill="x", padx=ESPACO["lg"],
                         pady=(ESPACO["md"], ESPACO["lg"]))

        self.bind("<Escape>", lambda e: self.fechar())
        self.protocol("WM_DELETE_WINDOW", self.fechar)

        # sem moldura do sistema, o Tk não dá foco sozinho
        self.attributes("-alpha", 0.0)
        self.after(10, self._aparecer)

    # ── aparência ────────────────────────────────────────────────────
    def _pintar_topo(self):
        self.topo.delete("all")
        base = tema.cor(self._cor_topo)
        degrade(self.topo, mesclar(base, "#FFFFFF", 0.18), escurecer(base, 0.35),
                faixas=50, horizontal=True)

        largura = self.topo.winfo_width()
        brilho = mesclar(base, "#FFFFFF", 0.12)
        self.topo.create_oval(-160, -120, largura * 0.45, 90,
                              fill=brilho, outline=brilho)

        self.topo.create_text(30, 34, anchor="w", text=self._icone,
                              font=(tema.familia, 17), fill="#FFFFFF")
        self.topo.create_text(66, 33, anchor="w", text=self._titulo,
                              font=tema.fonte("titulo", 15), fill="#FFFFFF")
        if self._subtitulo:
            self.topo.create_text(66, 57, anchor="w", text=self._subtitulo,
                                  font=tema.fonte("pequeno"),
                                  fill=mesclar("#FFFFFF", base, 0.3))

        # ✕ de fechar, com área de clique própria
        fechar = self.topo.create_text(largura - 26, 30, text="✕",
                                       font=(tema.familia, 12), fill="#E7E1FF")
        self.topo.tag_bind(fechar, "<Button-1>", lambda e: self.fechar())
        self.topo.tag_bind(fechar, "<Enter>",
                           lambda e: (self.topo.itemconfigure(fechar, fill="#FFFFFF"),
                                      self.topo.configure(cursor="hand2")))
        self.topo.tag_bind(fechar, "<Leave>",
                           lambda e: (self.topo.itemconfigure(fechar, fill="#E7E1FF"),
                                      self.topo.configure(cursor="")))

    def _centralizar(self, largura, altura):
        raiz = self.raiz.winfo_toplevel()
        raiz.update_idletasks()
        x = raiz.winfo_rootx() + (raiz.winfo_width() // 2) - largura // 2
        y = raiz.winfo_rooty() + (raiz.winfo_height() // 2) - altura // 2
        self.geometry(f"{largura}x{altura}+{max(0, x)}+{max(0, y)}")

    def _aparecer(self, passo=0):
        """Aparece suave: janela que surge seca parece erro do sistema."""
        if self._fechada or not self.winfo_exists():
            return
        if passo == 0:
            try:
                self.lift()
                self.grab_set()
                self.focus_force()
                # se o cliente clicar na janela do app (ou no ícone da
                # barra de tarefas), o Windows joga o app pra frente e
                # esconde esta janela; aqui ela sobe de novo
                self.raiz.winfo_toplevel().bind("<FocusIn>", self._subir,
                                                add="+")
            except Exception:
                pass
        alpha = min(1.0, (passo + 1) / 6)
        try:
            self.attributes("-alpha", alpha)
        except Exception:
            return
        if alpha < 1.0:
            self.after(16, lambda: self._aparecer(passo + 1))

    def _subir(self, _=None):
        """Traz esta janela de volta pra frente do app."""
        if self._fechada or not self.winfo_exists():
            return
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass

    # ── arrastar ─────────────────────────────────────────────────────
    def _pegar(self, evento):
        self._arraste = {"x": evento.x_root - self.winfo_x(),
                         "y": evento.y_root - self.winfo_y()}

    def _arrastar(self, evento):
        self.geometry(f"+{evento.x_root - self._arraste['x']}"
                      f"+{evento.y_root - self._arraste['y']}")

    # ── ciclo de vida ────────────────────────────────────────────────
    def ao_fechar(self, funcao):
        self._ao_fechar = funcao

    def fechar(self):
        if self._fechada:
            return
        self._fechada = True
        funcao = getattr(self, "_ao_fechar", None)
        try:
            self.grab_release()
        except Exception:
            pass
        try:
            self.destroy()
        except Exception:
            pass
        if funcao:
            funcao()


# ── conteúdo em blocos "título + explicação" ─────────────────────────
def blocos_de_texto(pai, texto, cor_marca="primario"):
    """Desenha um texto no formato do NOVIDADES.txt: a primeira linha de
    cada bloco é o título, o resto é a explicação."""
    for bloco in re.split(r"\n\s*\n", (texto or "").strip()):
        linhas = [l.strip() for l in bloco.splitlines() if l.strip()]
        if not linhas:
            continue

        item = tk.Frame(pai, bg=tema.cor("fundo"))
        item.pack(fill="x", pady=(0, 14))

        tk.Label(item, text="●", font=(tema.familia, 8), bg=tema.cor("fundo"),
                 fg=tema.cor(cor_marca)).pack(side="left", anchor="n", pady=4)

        textos = tk.Frame(item, bg=tema.cor("fundo"))
        textos.pack(side="left", fill="x", expand=True, padx=(10, 0))

        tk.Label(textos, text=linhas[0], font=tema.fonte("corpo_forte"),
                 bg=tema.cor("fundo"), fg=tema.cor("texto"), anchor="w",
                 justify="left", wraplength=470).pack(fill="x")

        if len(linhas) > 1:
            tk.Label(textos, text=" ".join(linhas[1:]), font=tema.fonte("corpo"),
                     bg=tema.cor("fundo"), fg=tema.cor("texto2"), anchor="w",
                     justify="left", wraplength=470).pack(fill="x", pady=(3, 0))


# ── janelas prontas ──────────────────────────────────────────────────
def novidades(app, lista, ao_fechar=None):
    """lista: [(versão, texto), …] — o que veio do NOVIDADES.txt."""
    versao = lista[0][0] if lista else ""
    janela = Modal(app, "Novidades desta versão",
                    f"LibertyTube {versao}" if versao else "", icone="✨",
                   largura=620, altura=560)

    rolagem = Rolagem(janela.corpo)
    rolagem.pack(fill="both", expand=True)

    for i, (v, texto) in enumerate(lista):
        if i:
            tk.Frame(rolagem.corpo, bg=tema.cor("borda_suave"), height=1
                     ).pack(fill="x", pady=(6, 16))
        tk.Label(rolagem.corpo, text=f"Versão {v}", font=tema.fonte("subtitulo"),
                 bg=tema.cor("fundo"), fg=tema.cor("primario"), anchor="w"
                 ).pack(fill="x", pady=(0, 12))
        blocos_de_texto(rolagem.corpo, texto)

    if ao_fechar:
        janela.ao_fechar(ao_fechar)
    Botao(janela.rodape, "Entendi!", janela.fechar, altura=44, largura=170
          ).pack(side="right")
    return janela


def atualizacao(app, dados, ao_atualizar):
    """"Saiu a versão X" — com as notas e dois botões."""
    versao = dados.get("versao", "")
    janela = Modal(app, "Atualização disponível",
                    f"LibertyTube {versao} — a sua é a {VERSAO}",
                   icone="⬇", largura=620, altura=520, cor="info")

    tk.Label(janela.corpo,
             text="Baixa só o que mudou, leva alguns segundos e o LibertyTube "
                  "reinicia sozinho. Seus projetos não são tocados.",
             font=tema.fonte("corpo"), bg=tema.cor("fundo"),
             fg=tema.cor("texto2"), anchor="w", justify="left",
             wraplength=520).pack(fill="x", pady=(0, ESPACO["md"]))

    rolagem = Rolagem(janela.corpo)
    rolagem.pack(fill="both", expand=True)
    blocos_de_texto(rolagem.corpo, dados.get("notas") or
                    "Melhorias e correções nesta versão.", cor_marca="info")

    def agora():
        janela.fechar()
        ao_atualizar()

    Botao(janela.rodape, "Atualizar agora", agora, icone="⬇", altura=44,
          largura=200).pack(side="right")
    Botao(janela.rodape, "Depois", janela.fechar, variante="fantasma",
          altura=44, largura=120).pack(side="right", padx=(0, 10))
    return janela


def confirmar(app, titulo, texto, sim="Sim", nao="Cancelar", icone="?",
              cor="aviso", perigoso=False):
    """Pergunta de sim/não. Devolve True/False — dá pra usar no lugar do
    `messagebox.askyesno` sem mudar o jeito de escrever o código:

        if not dialogs.confirmar(app, "Apagar?", "..."): return
    """
    janela = Modal(app, titulo, "", icone=icone, largura=560, altura=310,
                   cor=cor)
    resposta = {"ok": False}

    tk.Label(janela.corpo, text=texto, font=tema.fonte("corpo"),
             bg=tema.cor("fundo"), fg=tema.cor("texto2"), anchor="w",
             justify="left", wraplength=490).pack(fill="both", expand=True)

    def responder(valor):
        resposta["ok"] = valor
        janela.fechar()

    Botao(janela.rodape, sim, lambda: responder(True),
          variante="perigo" if perigoso else "primario",
          altura=44, largura=170).pack(side="right")
    Botao(janela.rodape, nao, lambda: responder(False), variante="fantasma",
          altura=44, largura=140).pack(side="right", padx=(0, 10))

    janela.raiz.wait_window(janela)
    return resposta["ok"]


def perguntar_texto(app, titulo, rotulo, placeholder="", valor="",
                    botao="Criar", icone="✎", subtitulo=""):
    """Pede um texto (nome do projeto, por exemplo). Devolve a resposta ou
    None se a pessoa cancelar. Substitui o `simpledialog.askstring`, que
    abre uma caixinha cinza com cara de Windows 98."""
    from .widgets import Campo

    janela = Modal(app, titulo, subtitulo, icone=icone, largura=540,
                   altura=300, cor="primario")
    resposta = {"texto": None}

    campo = Campo(janela.corpo, rotulo=rotulo, placeholder=placeholder,
                  largura=34, valor=valor)
    campo.pack(fill="x")

    def confirmar_texto():
        texto = campo.valor()
        if not texto:
            campo.mostrar_aviso("Escreva um nome antes de continuar.")
            campo.focar()
            return
        resposta["texto"] = texto
        janela.fechar()

    campo.entrada.bind("<Return>", lambda e: confirmar_texto())

    Botao(janela.rodape, botao, confirmar_texto, altura=44, largura=170
          ).pack(side="right")
    Botao(janela.rodape, "Cancelar", janela.fechar, variante="fantasma",
          altura=44, largura=130).pack(side="right", padx=(0, 10))

    janela.after(80, campo.focar)
    janela.raiz.wait_window(janela)
    return resposta["texto"]


def erro(app, titulo, texto):
    """A etapa falhou. Mostra o motivo com a cara do app (o
    `messagebox.showerror` do Windows destoava de tudo)."""
    texto = (texto or "").strip()
    if len(texto) > 900:                 # traceback gigante não ajuda ninguém
        texto = texto[:900] + "…"
    return aviso(app, titulo, texto, botao="Entendi", icone="!",
                 cor="perigo")


def aviso(app, titulo, texto, botao="Entendi", acao=None, icone="✓",
          cor="sucesso", botao_secundario=None):
    """Mensagem simples, no lugar do messagebox do Windows."""
    janela = Modal(app, titulo, "", icone=icone, largura=560, altura=300,
                   cor=cor)

    tk.Label(janela.corpo, text=texto, font=tema.fonte("corpo"),
             bg=tema.cor("fundo"), fg=tema.cor("texto2"), anchor="w",
             justify="left", wraplength=490).pack(fill="both", expand=True)

    def confirmar():
        janela.fechar()
        if acao:
            acao()

    Botao(janela.rodape, botao, confirmar, altura=44, largura=170
          ).pack(side="right")
    if botao_secundario:
        rotulo, funcao = botao_secundario

        def secundario():
            janela.fechar()
            if funcao:
                funcao()

        Botao(janela.rodape, rotulo, secundario, variante="fantasma",
              altura=44, largura=130).pack(side="right", padx=(0, 10))
    return janela
