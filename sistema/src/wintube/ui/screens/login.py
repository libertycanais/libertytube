"""
ui/screens/login.py
------------------------------------------------------------
Tela de entrar no LibertyTube.

    +----------------------------+---------------------------+
    |  (painel roxo)             |                           |
    |  LibertyTube               |   Bem-vindo de volta      |
    |  Do link do YouTube ao     |   email                   |
    |  corte pronto pra postar.  |   senha                   |
    |                            |   [ Entrar no LibertyTube ]|
    |  ↓ baixa o vídeo inteiro   |                           |
    |  ♪ a IA ouve e escreve     |   rodapé                  |
    |  ✂ corta e monta sozinho   |                           |
    |  ✦ legenda viral e marca   |                           |
    |  LibertyTube 1.0.0         |                           |
    +----------------------------+---------------------------+

O painel roxo é desenhado num Canvas (degradê + dois círculos suaves);
o formulário são widgets de verdade do lado direito. Em janela estreita
o painel some e o formulário vai pro centro.

Os campos e o botão são desenhados em Canvas porque a borda do Tk só faz
canto reto.

O login roda em thread (a janela não congela), tem aviso de Caps Lock,
"lembrar meu email" e botão de suporte.
"""

import tkinter as tk

from ...backend import auth, config as backend_config, content
from ...core import tasks
from ...core import settings as prefs
from ...version import VERSAO
from ..theme import mesclar, tema
from ..widgets import Botao, CampoRedondo, Chave, degrade, link

# abaixo disto o painel roxo sai de cena e o formulário vai pro centro
LARGURA_MINIMA_PAINEL = 980

FRACAO_PAINEL = 0.44      # quanto da janela o painel roxo ocupa
FORMULARIO_L = 350        # largura do formulário

# (ícone, título, explicação) — o que o app faz, do jeito que o cliente vê
VANTAGENS = [
    ("↓", "Baixa o vídeo inteiro", "playlist, 4K, tudo de uma vez"),
    ("♪", "A IA ouve e escreve", "transcrição com os tempos certinhos"),
    ("✂", "Corta e monta sozinho", "no formato de cada rede social"),
    ("✦", "Legenda viral e sua marca", "sai pronto pra postar"),
]


def montar(app, root, mensagem=""):
    _construir(app, root, lambda pai, fundo: _formulario(app, pai, fundo, mensagem))


def moldura(app, root, montar_conteudo):
    """Mesma moldura da tela de entrar, com outro conteúdo do lado
    direito — é o que a tela de criar senha usa."""
    _construir(app, root, montar_conteudo)


# ── estrutura ────────────────────────────────────────────────────────
def _construir(app, root, montar_conteudo):
    fundo = tk.Frame(root, bg=tema.cor("fundo"))
    fundo.pack(fill="both", expand=True)

    painel = tk.Canvas(fundo, bg=tema.cor("primario"), highlightthickness=0,
                       bd=0)

    # o formulário mora num Frame comum: os campos são widgets de verdade
    formulario = tk.Frame(fundo, bg=tema.cor("fundo"))

    estado = {"largura": 0}

    def desenhar(_=None):
        largura = fundo.winfo_width()
        altura = fundo.winfo_height()
        if largura <= 1 or altura <= 1:
            return

        mostrar_painel = largura >= LARGURA_MINIMA_PAINEL
        painel_l = int(largura * FRACAO_PAINEL) if mostrar_painel else 0

        if mostrar_painel:
            painel.place(x=0, y=0, width=painel_l, relheight=1)
            # só redesenha quando o tamanho muda de verdade: o Configure
            # dispara várias vezes seguidas ao abrir e ao arrastar a borda
            if estado["largura"] != (painel_l, altura):
                estado["largura"] = (painel_l, altura)
                painel.update_idletasks()
                _pintar_painel(painel, painel_l, altura)
        else:
            painel.place_forget()
            estado["largura"] = 0

        sobra = largura - painel_l
        x = painel_l + max(40, (sobra - FORMULARIO_L) / 2)
        formulario.place(x=x, rely=0.5, anchor="w", width=FORMULARIO_L)

    fundo.bind("<Configure>", desenhar)

    montar_conteudo(formulario, tema.cor("fundo"))
    _suporte(app, fundo)

    root.update_idletasks()
    desenhar()


def _pintar_painel(tela, largura, altura):
    """O painel roxo: degradê, dois círculos suaves, marca, promessa e a
    lista do que o app faz."""
    tela.delete("all")
    if largura <= 1 or altura <= 1:
        return

    roxo = tema.cor("primario")
    degrade(tela, mesclar(roxo, "#FFFFFF", 0.20), escurecer_roxo(roxo),
            faixas=70)

    # círculo claro saindo pelo topo e outro, mais escuro, no rodapé:
    # é o que tira a cara de "fundo chapado"
    claro = mesclar(roxo, "#FFFFFF", 0.16)
    raio = largura * 0.62
    tela.create_oval(largura * 0.30, -raio * 1.15,
                     largura * 0.30 + raio * 2, raio * 0.85,
                     fill=claro, outline=claro)
    escuro = mesclar(roxo, "#000000", 0.28)
    raio2 = largura * 0.78
    tela.create_oval(-raio2 * 0.55, altura - raio2 * 0.72,
                     -raio2 * 0.55 + raio2 * 2, altura + raio2 * 1.3,
                     fill=escuro, outline=escuro)

    margem = 52
    largura_texto = largura - margem * 2
    y = altura * 0.30

    tela.create_text(margem, y, anchor="w", text="LibertyTube",
                     font=tema.fonte("display", 30), fill="#FFFFFF")

    y += 52
    tela.create_text(margem, y, anchor="nw", width=largura_texto,
                     text="Do link do YouTube ao corte pronto pra postar.",
                     font=tema.fonte("titulo", 19), fill="#FFFFFF")

    y += 78
    tela.create_text(margem, y, anchor="nw", width=largura_texto,
                      text="O LibertyTube faz o trabalho braçal enquanto você "
                          "cuida do canal.",
                     font=tema.fonte("pequeno"),
                     fill=mesclar("#FFFFFF", roxo, 0.25))

    y += 44
    for icone, titulo, explicacao in VANTAGENS:
        tela.create_text(margem + 6, y + 10, anchor="w", text=icone,
                         font=(tema.familia, 13), fill="#FFFFFF")
        tela.create_text(margem + 32, y + 3, anchor="w", text=titulo,
                         font=tema.fonte("pequeno_forte"), fill="#FFFFFF")
        tela.create_text(margem + 32, y + 19, anchor="w", text=explicacao,
                         font=tema.fonte("micro"),
                         fill=mesclar("#FFFFFF", roxo, 0.35))
        y += 42

    tela.create_text(margem, altura - 26, anchor="w", text=f"LibertyTube {VERSAO}",
                     font=tema.fonte("micro"),
                     fill=mesclar("#FFFFFF", roxo, 0.45))


def escurecer_roxo(cor):
    return mesclar(cor, "#000000", 0.42)


# ── formulário (lado direito) ────────────────────────────────────────
def _formulario(app, pai, fundo, mensagem=""):
    tk.Label(pai, text="Bem-vindo de volta 👋",
             font=tema.fonte("display", 22), bg=fundo,
             fg=tema.cor("texto"), anchor="w").pack(fill="x")
    tk.Label(pai, text="Entre com o email e a senha que você recebeu na compra.",
             font=tema.fonte("pequeno"), bg=fundo, fg=tema.cor("texto2"),
             anchor="w", justify="left", wraplength=FORMULARIO_L
             ).pack(fill="x", pady=(8, 22))

    campo_email = CampoRedondo(pai, rotulo="EMAIL", placeholder="seu@email.com",
                               fundo=fundo, largura=FORMULARIO_L)
    campo_email.pack(fill="x")
    if prefs.get("email_lembrado", ""):
        campo_email.definir(prefs.get("email_lembrado", ""))

    tk.Frame(pai, bg=fundo, height=14).pack()

    campo_senha = CampoRedondo(pai, rotulo="SENHA", placeholder="sua senha",
                               senha=True, fundo=fundo, largura=FORMULARIO_L)
    campo_senha.pack(fill="x")

    linha = tk.Frame(pai, bg=fundo)
    linha.pack(fill="x", pady=(14, 0))

    lembrar = Chave(linha, "Lembrar meu email",
                    valor=bool(prefs.get("lembrar_email", True)), compacto=True)
    lembrar.pack(side="left")

    esqueci = link(linha, "Esqueci minha senha", lambda: _recuperar(app, estado),
                   cor="primario")
    esqueci.configure(bg=fundo)
    esqueci.pack(side="right")

    status = tk.Label(pai, text=mensagem or "", font=tema.fonte("pequeno"),
                      bg=fundo,
                      fg=tema.cor("aviso") if mensagem else tema.cor("texto2"),
                      wraplength=FORMULARIO_L, justify="left", anchor="w")
    status.pack(fill="x", pady=(12, 0))

    botao = Botao(pai, "Entrar no LibertyTube", lambda: _entrar(app, estado),
                  altura=50, largura=FORMULARIO_L, raio=12, fundo=fundo,
                  fonte=tema.fonte("corpo_forte", 12))
    botao.pack(pady=(14, 0))

    tk.Frame(pai, bg=tema.cor("borda_suave"), height=1).pack(fill="x", pady=(20, 0))

    rodape = tk.Label(pai, text="Não tem conta? Fale com o suporte de onde "
                                "você comprou.",
                      font=tema.fonte("micro"), bg=fundo, fg=tema.cor("muted"),
                      wraplength=FORMULARIO_L)
    rodape.pack(pady=(12, 0))

    if not backend_config.configurado():
        tk.Label(pai, text="Servidor não configurado — fale com o suporte.",
                 font=tema.fonte("micro"), bg=fundo,
                 fg=tema.cor("aviso")).pack(pady=(6, 0))

    estado = {"app": app, "email": campo_email, "senha": campo_senha,
              "status": status, "botao": botao, "lembrar": lembrar}

    campo_email.entrada.bind("<Return>", lambda e: campo_senha.focar())
    campo_senha.entrada.bind("<Return>", lambda e: _entrar(app, estado))
    (campo_senha if campo_email.valor() else campo_email).focar()


# ── ações ────────────────────────────────────────────────────────────
def _mostrar(estado, texto, tipo="erro"):
    cores = {"erro": "perigo", "ok": "sucesso", "aviso": "aviso",
             "neutro": "texto2"}
    estado["status"].configure(text=texto, fg=tema.cor(cores.get(tipo, "texto2")))


def _entrar(app, estado):
    email = estado["email"].valor()
    senha = estado["senha"].entrada.get()

    if not email or not senha:
        _mostrar(estado, "Preencha email e senha.", "aviso")
        return

    estado["botao"].carregando(True, "entrando…")
    _mostrar(estado, "Conferindo com o servidor…", "neutro")

    def terminou(resultado):
        if resultado.ok:
            if estado["lembrar"].ligada():
                prefs.update({"email_lembrado": email, "lembrar_email": True})
            else:
                prefs.update({"email_lembrado": "", "lembrar_email": False})
            _mostrar(estado, "Tudo certo! Abrindo o LibertyTube…", "ok")
            app.root.after(400, lambda: app.entrar_com(resultado.sessao))
        else:
            estado["botao"].carregando(False)
            _mostrar(estado, resultado.motivo, "erro")
            estado["senha"].entrada.focus_set()

    def falhou(erro):
        estado["botao"].carregando(False)
        _mostrar(estado, f"Não consegui entrar: {erro}", "erro")

    tasks.em_thread(lambda: auth.entrar(email, senha),
                    ao_terminar=terminou, ao_falhar=falhou, root=app.root)


def _recuperar(app, estado):
    email = estado["email"].valor()
    if not email:
        _mostrar(estado, "Digite seu email primeiro pra receber o link.", "aviso")
        estado["email"].focar()
        return

    _mostrar(estado, "Enviando o email…", "neutro")

    def terminou(resultado):
        _mostrar(estado, resultado.motivo, "ok" if resultado.ok else "erro")

    tasks.em_thread(lambda: auth.recuperar_senha(email),
                    ao_terminar=terminou,
                    ao_falhar=lambda e: _mostrar(estado, str(e), "erro"),
                    root=app.root)


def _suporte(app, parent):
    """Busca o link do suporte no servidor e cria o botão no canto."""
    def criar(url):
        if not url or not isinstance(url, str) or not url.strip():
            return
        if not parent.winfo_exists():
            return
        Botao(parent, "Falar com o suporte",
              lambda: app.abrir_link(url.strip()),
              variante="whatsapp", icone="✆", altura=38, raio=19
              ).place(relx=1.0, y=28, x=-48, anchor="ne")

    tasks.em_thread(lambda: content.config_app("whatsapp_suporte"),
                    ao_terminar=criar, root=app.root)
