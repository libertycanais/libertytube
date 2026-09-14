"""
ui/screens/first_password.py
------------------------------------------------------------
"Crie sua senha" — aparece no primeiro acesso, quando o cliente entrou
com a senha temporária que recebeu por email.

Usa a mesma moldura da tela de entrar (cartão arredondado à esquerda,
marca à direita), pra não parecer que o app trocou de cara no meio do
caminho.

Tem barra de força da senha, conferência das duas em tempo real e a
troca rodando em thread.
"""

import tkinter as tk

from ...backend import auth
from ...core import tasks
from ..theme import tema
from ..widgets import Botao, CampoRedondo
from . import login


def montar(app, root):
    login.moldura(app, root, lambda pai, fundo: _formulario(app, pai, fundo))


def _formulario(app, pai, fundo):
    tk.Label(pai, text="Crie sua senha", font=tema.fonte("display", 21),
             bg=fundo, fg=tema.cor("texto"), anchor="w").pack(fill="x")
    tk.Label(pai,
             text="Você entrou com a senha temporária do email. Escolha uma "
                  "senha só sua para os próximos acessos.",
             font=tema.fonte("pequeno"), bg=fundo, fg=tema.cor("texto2"),
             anchor="w", justify="left", wraplength=login.FORMULARIO_L
             ).pack(fill="x", pady=(6, 18))

    campo_nova = CampoRedondo(pai, rotulo="NOVA SENHA",
                              placeholder="mínimo 8 caracteres", senha=True,
                              fundo=fundo, largura=login.FORMULARIO_L)
    campo_nova.pack(fill="x")

    # barra de força
    medidor = tk.Frame(pai, bg=fundo)
    medidor.pack(fill="x", pady=(10, 0))
    blocos = []
    for _ in range(4):
        bloco = tk.Frame(medidor, bg=tema.cor("borda"), height=4,
                         width=(login.FORMULARIO_L - 18) // 4)
        bloco.pack(side="left", padx=(0, 6))
        blocos.append(bloco)

    dica = tk.Label(pai, text="", font=tema.fonte("micro"), bg=fundo,
                    fg=tema.cor("muted"), anchor="w")
    dica.pack(fill="x", pady=(6, 0))

    tk.Frame(pai, bg=fundo, height=10).pack()

    campo_conf = CampoRedondo(pai, rotulo="CONFIRMAR A SENHA",
                              placeholder="digite de novo", senha=True,
                              fundo=fundo, largura=login.FORMULARIO_L)
    campo_conf.pack(fill="x")

    status = tk.Label(pai, text="", font=tema.fonte("pequeno"), bg=fundo,
                      fg=tema.cor("texto2"), wraplength=login.FORMULARIO_L,
                      justify="left", anchor="w")
    status.pack(fill="x", pady=(12, 0))

    botao = Botao(pai, "Salvar e entrar", lambda: _salvar(app, estado),
                  icone="→", altura=50, largura=login.FORMULARIO_L, raio=14,
                  fundo=fundo, fonte=tema.fonte("corpo_forte", 12))
    botao.pack(pady=(12, 0))

    estado = {"nova": campo_nova, "conf": campo_conf, "status": status,
              "botao": botao}

    def avaliar(_=None):
        senha = campo_nova.entrada.get()
        nota, texto = auth.forca_senha(senha)
        cores = [tema.cor("perigo"), tema.cor("aviso"),
                 tema.cor("info"), tema.cor("sucesso")]
        for i, bloco in enumerate(blocos):
            bloco.configure(bg=cores[min(nota, 4) - 1] if senha and i < nota
                            else tema.cor("borda"))
        dica.configure(text=texto if senha else "",
                       fg=tema.cor("sucesso") if nota >= 3 else tema.cor("muted"))

    def conferir(_=None):
        if (campo_conf.entrada.get()
                and campo_nova.entrada.get() != campo_conf.entrada.get()):
            campo_conf.mostrar_aviso("As duas senhas ainda estão diferentes.")
        else:
            campo_conf.mostrar_aviso("")

    campo_nova.entrada.bind("<KeyRelease>",
                            lambda e: (campo_nova._digitou(e), avaliar(),
                                       conferir()))
    campo_conf.entrada.bind("<KeyRelease>",
                            lambda e: (campo_conf._digitou(e), conferir()))
    campo_nova.entrada.bind("<Return>", lambda e: campo_conf.focar())
    campo_conf.entrada.bind("<Return>", lambda e: _salvar(app, estado))
    campo_nova.focar()


def _salvar(app, estado):
    nova = estado["nova"].entrada.get()
    conf = estado["conf"].entrada.get()

    if not nova or not conf:
        estado["status"].configure(text="Preencha os dois campos.",
                                   fg=tema.cor("aviso"))
        return
    if nova != conf:
        estado["status"].configure(text="As duas senhas não são iguais.",
                                   fg=tema.cor("perigo"))
        return

    estado["botao"].carregando(True, "salvando…")
    estado["status"].configure(text="Atualizando no servidor…",
                               fg=tema.cor("texto2"))

    def terminou(resultado):
        if resultado.ok:
            estado["status"].configure(text="Senha salva! Abrindo o LibertyTube…",
                                       fg=tema.cor("sucesso"))
            app.sessao = resultado.sessao
            app.root.after(500, app.abrir_painel)
        else:
            estado["botao"].carregando(False)
            estado["status"].configure(text=resultado.motivo,
                                       fg=tema.cor("perigo"))

    tasks.em_thread(lambda: auth.definir_senha(nova, conf),
                    ao_terminar=terminou,
                    ao_falhar=lambda e: (estado["botao"].carregando(False),
                                         estado["status"].configure(
                                             text=str(e), fg=tema.cor("perigo"))),
                    root=app.root)
