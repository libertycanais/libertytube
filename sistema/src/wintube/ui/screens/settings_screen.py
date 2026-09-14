"""
ui/screens/settings_screen.py
------------------------------------------------------------
Configurações: IA, pastas, conta, aparência e atualização.
"""

import os
import tkinter as tk
from tkinter import filedialog

from ...backend import auth, config as backend_config, session, updates
from ...core import paths, runtime, settings, tasks
from ...pipeline import script_ai
from ...version import VERSAO
from ..theme import ESPACO, tema
from ..widgets import Botao, Cabecalho, Cartao, Chave, divisor, espaco, rotulo


def montar(app, parent):
    Cabecalho(parent, "Configurações",
              "Ajustes do app, da sua conta e das pastas.").pack(
        fill="x", pady=(4, ESPACO["lg"]))

    _ia(app, parent)
    espaco(parent, ESPACO["md"])
    _pastas(app, parent)
    espaco(parent, ESPACO["md"])
    _aparencia(app, parent)
    espaco(parent, ESPACO["md"])
    _conta(app, parent)
    espaco(parent, ESPACO["md"])
    _sistema(app, parent)
    espaco(parent, ESPACO["lg"])


# ── IA ───────────────────────────────────────────────────────────────
def _ia(app, parent):
    cartao = Cartao(parent, "Inteligência Artificial",
                    "A chave do Google Gemini é grátis e serve pro roteiro "
                    "automático e pro assistente.", accent=tema.cor("primario"))
    cartao.pack(fill="x")

    chave_atual = script_ai.chave()
    estado = rotulo(cartao.corpo,
                    f"✓  conectado — modelo {script_ai.modelo()}" if chave_atual
                    else "não conectado",
                    "pequeno", "sucesso" if chave_atual else "texto2")
    estado.configure(bg=tema.cor("card"))
    estado.pack(anchor="w", pady=(ESPACO["sm"], ESPACO["sm"]))

    campo = tk.Frame(cartao.corpo, bg=tema.cor("input"), highlightthickness=1,
                     highlightbackground=tema.cor("borda"))
    campo.pack(fill="x")
    entrada = tk.Entry(campo, bg=tema.cor("input"), fg=tema.cor("texto"),
                       relief="flat", bd=0, font=tema.fonte("corpo"),
                       insertbackground=tema.cor("primario"), highlightthickness=0,
                       show="•" if chave_atual else "")
    entrada.pack(fill="x", padx=14, pady=12)
    if chave_atual:
        entrada.insert(0, chave_atual)

    linha = tk.Frame(cartao.corpo, bg=tema.cor("card"))
    linha.pack(fill="x", pady=(ESPACO["md"], 0))

    botao = Botao(linha, "Salvar e testar", lambda: _testar_chave(), altura=42)
    botao.pack(side="left")
    Botao(linha, "Pegar chave grátis",
          lambda: app.abrir_link("https://aistudio.google.com/apikey"),
          variante="secundario", altura=42).pack(side="left", padx=(10, 0))

    def _testar_chave():
        chave = entrada.get().strip()
        if not chave:
            estado.configure(text="Cole a chave primeiro.", fg=tema.cor("aviso"))
            return
        botao.carregando(True, "testando…")

        def terminou(resultado):
            ok, mensagem, modelos = resultado
            botao.carregando(False)
            if ok:
                script_ai.definir_chave(chave)
                if modelos:
                    script_ai.definir_modelo(modelos[0])
                estado.configure(text=f"✓  {mensagem}", fg=tema.cor("sucesso"))
                app.aviso("IA conectada!", "sucesso")
            else:
                estado.configure(text=mensagem, fg=tema.cor("perigo"))

        tasks.em_thread(lambda: script_ai.testar_chave(chave),
                        ao_terminar=terminou, root=app.root)


# ── pastas ───────────────────────────────────────────────────────────
def _pastas(app, parent):
    cartao = Cartao(parent, "Onde os vídeos são salvos",
                    "Cada projeto vira uma pasta dentro deste lugar.")
    cartao.pack(fill="x")

    atual = rotulo(cartao.corpo, paths.work_dir(), "pequeno", "texto2")
    atual.configure(bg=tema.cor("card"))
    atual.pack(anchor="w", pady=(ESPACO["sm"], 2))

    rotulo_espaco = rotulo(cartao.corpo, "", "micro", "muted")
    rotulo_espaco.configure(bg=tema.cor("card"))
    rotulo_espaco.pack(anchor="w", pady=(0, ESPACO["md"]))

    def atualizar_espaco():
        """Mostra o espaço que sobra — vídeo enche disco rápido, e disco
        cheio é o motivo nº 1 de download que morre pela metade."""
        livre = paths.espaco_livre_gb(paths.work_dir())
        if livre is None:
            rotulo_espaco.configure(text="")
            return
        cor = "perigo" if livre < 5 else ("aviso" if livre < 20 else "muted")
        quanto = f"{livre * 1024:.0f} MB" if livre < 1 else f"{livre:.1f} GB"
        recado = f"{quanto} livres neste disco"
        if livre < 5:
            recado += " — quase sem espaço: troque de disco aqui embaixo"
        rotulo_espaco.configure(text=recado, fg=tema.cor(cor))

    atualizar_espaco()

    def aplicar(caminho):
        paths.definir_work_dir(caminho)
        atual.configure(text=paths.work_dir())
        atualizar_espaco()
        app.aviso("Pasta alterada. Os vídeos novos vão pra lá.", "sucesso")
        app.abrir_painel()

    def trocar():
        escolhida = filedialog.askdirectory(title="Escolha a pasta dos vídeos")
        if escolhida:
            aplicar(escolhida)

    linha = tk.Frame(cartao.corpo, bg=tema.cor("card"))
    linha.pack(fill="x")
    Botao(linha, "Abrir pasta", lambda: paths.abrir_no_explorador(paths.work_dir()),
          icone="📂", variante="secundario", altura=40).pack(side="left")
    Botao(linha, "Escolher outra pasta", trocar, variante="fantasma",
          altura=40).pack(side="left", padx=(10, 0))

    # atalho pros discos do computador, com o espaço de cada um: é o que
    # o cliente quer de verdade ("põe no meu HD, o SSD do Windows vive cheio")
    discos = paths.discos_do_computador()
    if len(discos) > 1:
        rotulo(cartao.corpo, "Mandar os vídeos pra outro disco:", "pequeno_forte",
               "texto").pack(anchor="w", pady=(ESPACO["md"], 6))
        grade = tk.Frame(cartao.corpo, bg=tema.cor("card"))
        grade.pack(fill="x")
        atual_unidade = os.path.splitdrive(paths.work_dir())[0].upper()
        for disco in discos:
            texto = f"{disco['unidade']}  ·  {disco['livre_gb']:.0f} GB livres"
            if disco["unidade"].upper() == atual_unidade:
                texto += "  (em uso)"
            Botao(grade, texto,
                   lambda d=disco: aplicar(os.path.join(d["raiz"], "LibertyTube",
                                                       "videos")),
                  variante="secundario" if disco["livre_gb"] >= 20 else "fantasma",
                  altura=38, fonte=tema.fonte("micro")
                  ).pack(side="left", padx=(0, 8), pady=(0, 4))


# ── aparência ────────────────────────────────────────────────────────
def _aparencia(app, parent):
    cartao = Cartao(parent, "Aparência", "Escolha como o LibertyTube fica na tela.")
    cartao.pack(fill="x")

    Chave(cartao.corpo, "Modo escuro",
          "fundo escuro, mais confortável pra editar à noite",
          valor=tema.escuro,
          ao_mudar=lambda _: app.root.after(120, app.alternar_tema)
          ).pack(fill="x", pady=(ESPACO["sm"], 0))


# ── conta ────────────────────────────────────────────────────────────
def _conta(app, parent):
    sessao = app.sessao or session.carregar() or {}
    usuario = auth.usuario(sessao)
    perfil = sessao.get("perfil") or {}

    cartao = Cartao(parent, "Sua conta", accent=tema.cor("info"))
    cartao.pack(fill="x")

    linhas = [f"Email: {usuario.get('email', '—')}"]
    if perfil.get("nome"):
        linhas.insert(0, f"Nome: {perfil['nome']}")
    if perfil.get("expira_em"):
        linhas.append(f"Assinatura válida até: {perfil['expira_em']}")

    faltam = auth.dias_restantes(sessao)
    linhas.append(
        f"Login neste computador: vale por mais {faltam} dia(s). "
        f"A cada {backend_config.MAX_DIAS_SESSAO} dias o LibertyTube pede "
        "email e senha de novo.")
    if perfil.get("material_vip"):
        linhas.append("Material VIP: liberado 👑")
    if sessao.get("demo"):
        linhas.append("(modo demo — servidor de login não configurado)")
    if not backend_config.configurado():
        linhas.append("Servidor: não configurado (backend.json)")

    rotulo(cartao.corpo, "\n".join(linhas), "pequeno", "texto2").pack(
        anchor="w", pady=(ESPACO["sm"], 0))

    divisor(cartao.corpo)

    # o cliente clicava aqui achando que ia fechar o programa: agora a
    # linha embaixo diz o que cada coisa faz (fechar é o "Sair" do menu)
    Botao(cartao.corpo, "Trocar de conta", app.sair_da_conta,
          icone="🔓", variante="secundario", altura=40).pack(anchor="w")
    rotulo(cartao.corpo,
           "Sai da sua conta e volta pra tela de entrar, sem fechar o app. "
           "Pra fechar o LibertyTube, use o “Sair” lá embaixo no menu.",
           "micro", "muted", wraplength=560).pack(anchor="w", pady=(6, 0))


# ── sistema ──────────────────────────────────────────────────────────
def _sistema(app, parent):
    cartao = Cartao(parent, "Sistema")
    cartao.pack(fill="x")

    ffmpeg_ok = runtime.ffmpeg_disponivel()
    itens = [
        (f"LibertyTube {VERSAO}", "sucesso"),
        ("FFmpeg encontrado ✓" if ffmpeg_ok
         else "FFmpeg não encontrado — reinstale o LibertyTube",
         "sucesso" if ffmpeg_ok else "perigo"),
        (f"Configurações: {paths.CONFIG_DIR}", "muted"),
    ]
    for texto, cor in itens:
        rotulo(cartao.corpo, texto, "pequeno", cor).pack(anchor="w", pady=1)

    linha = tk.Frame(cartao.corpo, bg=tema.cor("card"))
    linha.pack(fill="x", pady=(ESPACO["md"], 0))

    def procurar_atualizacao():
        app.log("Procurando atualização…", "sistema")

        def chegou(dados):
            if dados:
                app._aplicar_atualizacao(dados)
            else:
                app.aviso("Você já está na versão mais nova.", "sucesso")

        tasks.em_thread(updates.checar, ao_terminar=chegou, root=app.root)

    Botao(linha, "Procurar atualização", procurar_atualizacao, icone="⬇",
          variante="secundario", altura=40).pack(side="left")
    Botao(linha, "Abrir pasta de configurações",
          lambda: paths.abrir_no_explorador(paths.CONFIG_DIR),
          variante="fantasma", altura=40).pack(side="left", padx=(10, 0))

    if os.path.exists(paths.ARQ_LOG):
        Botao(linha, "Ver log", lambda: paths.abrir_no_explorador(paths.CONFIG_DIR),
              variante="fantasma", altura=40).pack(side="left", padx=(10, 0))
