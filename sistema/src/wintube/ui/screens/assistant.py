"""
ui/screens/assistant.py
------------------------------------------------------------
Assistente IA — conversa com o Gemini sem sair do LibertyTube.

Ajuda a melhorar legendas, criar prompts, pensar títulos e escolher
cortes. Se a chave ainda não estiver conectada, a tela vira um passo a
passo pra pegar a chave grátis do Google.
"""

import tkinter as tk

from ...core import projects, tasks
from ...pipeline import base, script_ai
from ..theme import ESPACO, tema
from ..widgets import Botao, Cabecalho, Cartao, Rolagem, divisor, espaco, rotulo

ATALHOS = [
    ("✍️ Melhorar minha legenda",
     "Melhore esta legenda pra ficar mais chamativa e curta: "),
    ("💡 Ideias de título",
     "Me dê 5 títulos chamativos pra um vídeo curto sobre: "),
    ("🎬 Dicas de corte",
     "Quais trechos de um vídeo motivacional funcionam melhor em Shorts? "
     "Responda em tópicos curtos."),
    ("🧠 Criar um prompt",
     "Crie um prompt pra IA selecionar os melhores momentos de uma "
     "transcrição de filme, com timestamps."),
]

_HISTORICO = []  # sobrevive à troca de tela dentro da mesma sessão


def montar(app, parent):
    if not script_ai.conectado():
        _tela_conectar(app, parent)
        return

    Cabecalho(parent, "Assistente IA",
              "Pergunte o que quiser sobre o seu vídeo — legendas, títulos, "
              "cortes e prompts.").pack(fill="x", pady=(4, ESPACO["md"]))

    # atalhos
    atalhos = tk.Frame(parent, bg=tema.cor("fundo"))
    atalhos.pack(fill="x", pady=(0, ESPACO["md"]))
    for i, (rotulo_botao, texto) in enumerate(ATALHOS):
        Botao(atalhos, rotulo_botao, lambda t=texto: _preencher(estado, t),
              variante="secundario", altura=34, fonte=tema.fonte("micro")
              ).grid(row=0, column=i, padx=(0, 8), sticky="w")

    # conversa
    caixa = tk.Frame(parent, bg=tema.cor("card"), highlightthickness=1,
                     highlightbackground=tema.cor("borda"), height=380)
    caixa.pack(fill="both", expand=True)
    caixa.pack_propagate(False)

    conversa = Rolagem(caixa, bg=tema.cor("card"))
    conversa.pack(fill="both", expand=True)

    # entrada
    barra = tk.Frame(parent, bg=tema.cor("fundo"))
    barra.pack(fill="x", pady=(ESPACO["md"], ESPACO["lg"]))

    campo = tk.Frame(barra, bg=tema.cor("input"), highlightthickness=1,
                     highlightbackground=tema.cor("borda"))
    campo.pack(side="left", fill="x", expand=True)
    entrada = tk.Entry(campo, bg=tema.cor("input"), fg=tema.cor("texto"),
                       relief="flat", bd=0, insertbackground=tema.cor("primario"),
                       font=tema.fonte("corpo"), highlightthickness=0)
    entrada.pack(fill="x", padx=14, pady=13)

    botao = Botao(barra, "Enviar", lambda: _enviar(app, estado), altura=46,
                  icone="➤")
    botao.pack(side="left", padx=(10, 0))

    estado = {"conversa": conversa, "entrada": entrada, "botao": botao,
              "app": app}

    entrada.bind("<Return>", lambda e: _enviar(app, estado))
    entrada.focus_set()

    if not _HISTORICO:
        _bolha(conversa.corpo,
               "Oi! Sou o assistente do LibertyTube. Posso melhorar legendas, "
               "sugerir títulos, criar prompts e dar dicas de corte. "
               "O que você quer fazer?", "ia")
    else:
        for mensagem in _HISTORICO:
            _bolha(conversa.corpo, mensagem["texto"], mensagem["autor"])


# ── conversa ─────────────────────────────────────────────────────────
def _bolha(parent, texto, autor):
    ehu = autor == "user"
    linha = tk.Frame(parent, bg=tema.cor("card"))
    linha.pack(fill="x", padx=16, pady=6)

    balao = tk.Frame(linha, bg=tema.cor("primario") if ehu else tema.cor("elevado"),
                     highlightthickness=0 if ehu else 1,
                     highlightbackground=tema.cor("borda"))
    balao.pack(side="right" if ehu else "left", anchor="e" if ehu else "w")

    tk.Label(balao, text=texto, font=tema.fonte("corpo"),
             bg=balao.cget("bg"),
             fg="#FFFFFF" if ehu else tema.cor("texto"),
             wraplength=560, justify="left", anchor="w"
             ).pack(padx=14, pady=10)
    return linha


def _preencher(estado, texto):
    estado["entrada"].delete(0, "end")
    estado["entrada"].insert(0, texto)
    estado["entrada"].focus_set()
    estado["entrada"].icursor("end")


def _enviar(app, estado):
    mensagem = estado["entrada"].get().strip()
    if not mensagem:
        return

    estado["entrada"].delete(0, "end")
    _HISTORICO.append({"autor": "user", "texto": mensagem})
    _bolha(estado["conversa"].corpo, mensagem, "user")

    pensando = _bolha(estado["conversa"].corpo, "digitando…", "ia")
    estado["botao"].carregando(True, "…")
    app.root.after(60, lambda: estado["conversa"].canvas.yview_moveto(1.0))

    contexto = _contexto_do_projeto()

    def terminou(resposta):
        pensando.destroy()
        estado["botao"].carregando(False)
        _HISTORICO.append({"autor": "ia", "texto": resposta})
        _bolha(estado["conversa"].corpo, resposta, "ia")
        app.root.after(60, lambda: estado["conversa"].canvas.yview_moveto(1.0))

    def falhou(erro):
        pensando.destroy()
        estado["botao"].carregando(False)
        _bolha(estado["conversa"].corpo, f"Não consegui responder: {erro}", "ia")

    tasks.em_thread(
        lambda: script_ai.conversar(mensagem, _HISTORICO[:-1], contexto),
        ao_terminar=terminou, ao_falhar=falhou, root=app.root)


def _contexto_do_projeto():
    proj = projects.atual()
    plataforma = projects.PLATAFORMAS[projects.plataforma()][0]
    return (f"Projeto: {proj.nome}. Plataforma: {plataforma} "
            f"({projects.formato()}). "
            f"{len(base.listar_videos(proj.cenas_baixadas))} cena(s) baixada(s), "
            f"{len(base.listar_videos(proj.cenas_cortadas))} corte(s).")


# ── tela de conectar a IA ────────────────────────────────────────────
def _tela_conectar(app, parent):
    Cabecalho(parent, "Assistente IA",
              "Pra usar o assistente (e o roteiro automático) você precisa de "
              "uma chave do Google Gemini. É grátis, sem cartão."
              ).pack(fill="x", pady=(4, ESPACO["lg"]))

    cartao = Cartao(parent, "Pegue sua chave grátis em 1 minuto",
                    accent=tema.cor("primario"))
    cartao.pack(fill="x")

    passos = [
        "Clique no botão abaixo — ele abre o Google AI Studio.",
        "Entre com sua conta do Google (a mesma do Gmail serve).",
        "Clique em “Create API key” e copie a chave (começa com AIza).",
        "Cole a chave aqui embaixo e clique em Conectar.",
    ]
    for i, texto in enumerate(passos, 1):
        linha = tk.Frame(cartao.corpo, bg=tema.cor("card"))
        linha.pack(fill="x", pady=4)
        tk.Label(linha, text=f" {i} ", font=tema.fonte("micro", peso="bold"),
                 bg=tema.cor("card_hover"), fg=tema.cor("texto"),
                 padx=6, pady=3).pack(side="left", padx=(0, 10))
        tk.Label(linha, text=texto, font=tema.fonte("pequeno"),
                 bg=tema.cor("card"), fg=tema.cor("texto"), anchor="w"
                 ).pack(side="left")

    Botao(cartao.corpo, "Abrir o Google AI Studio",
          lambda: app.abrir_link("https://aistudio.google.com/apikey"),
          icone="🔑", altura=42, variante="secundario"
          ).pack(anchor="w", pady=(ESPACO["md"], 0))

    divisor(cartao.corpo)

    campo = tk.Frame(cartao.corpo, bg=tema.cor("input"), highlightthickness=1,
                     highlightbackground=tema.cor("borda"))
    campo.pack(fill="x")
    entrada = tk.Entry(campo, bg=tema.cor("input"), fg=tema.cor("texto"),
                       relief="flat", bd=0, font=tema.fonte("corpo"),
                       insertbackground=tema.cor("primario"), highlightthickness=0)
    entrada.pack(fill="x", padx=14, pady=12)

    status = rotulo(cartao.corpo, "", "pequeno", "texto2")
    status.configure(bg=tema.cor("card"))
    status.pack(anchor="w", pady=(10, 0))

    botao = Botao(cartao.corpo, "Conectar", lambda: _conectar(), altura=44)
    botao.pack(anchor="w", pady=(ESPACO["md"], 0))

    def _conectar():
        chave = entrada.get().strip()
        if not chave:
            status.configure(text="Cole a chave primeiro.", fg=tema.cor("aviso"))
            return
        botao.carregando(True, "testando…")
        status.configure(text="Conferindo a chave com o Google…",
                         fg=tema.cor("texto2"))

        def terminou(resultado):
            ok, mensagem, modelos = resultado
            botao.carregando(False)
            if ok:
                script_ai.definir_chave(chave)
                if modelos:
                    script_ai.definir_modelo(modelos[0])
                status.configure(text=mensagem, fg=tema.cor("sucesso"))
                app.aviso("IA conectada!", "sucesso")
                app.root.after(700, lambda: app.navegar("assistente"))
            else:
                status.configure(text=mensagem, fg=tema.cor("perigo"))

        tasks.em_thread(lambda: script_ai.testar_chave(chave),
                        ao_terminar=terminou,
                        ao_falhar=lambda e: (botao.carregando(False),
                                             status.configure(text=str(e),
                                                              fg=tema.cor("perigo"))),
                        root=app.root)

    espaco(parent, ESPACO["lg"])
