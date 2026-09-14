"""
ui/screens/transcribe_screen.py
------------------------------------------------------------
Etapa 2 — a IA ouve as cenas e escreve tudo com os tempos.

Tem dois caminhos:
  * automático: o LibertyTube manda a transcrição pro Gemini e já traz o
    roteiro pronto (precisa da chave, que é grátis)
  * manual: 4 passos numerados pra copiar o prompt, colar no Gemini ou
    ChatGPT e trazer a resposta de volta
"""

import os
import tkinter as tk

from ...pipeline import base, cuts, script_ai, transcribe
from ..theme import ESPACO, tema
from ..widgets import Banner, Botao, Cabecalho, Cartao, divisor, espaco, rotulo


def montar(app, parent):
    proj = app.projeto
    cenas = base.listar_videos(proj.cenas_baixadas)
    texto_transcricao = transcribe.ler_transcricao()

    Cabecalho(parent, "Transcrever",
              "A IA escuta cada cena e escreve as falas com o tempo exato — "
              "é isso que permite cortar no lugar certo.",
              etapa=2).pack(fill="x", pady=(4, ESPACO["lg"]))

    if not cenas:
        Banner(parent, "Você ainda não baixou nenhuma cena neste projeto.",
               tipo="aviso", icone="!",
               acao=("Ir para o passo 1 →", lambda: app.navegar("inicio"))
               ).pack(fill="x")
        return

    # ── transcrever ──
    cartao = Cartao(parent, "1. Deixe a IA ouvir as cenas",
                    f"{len(cenas)} cena(s) neste projeto. Na primeira vez o "
                    "LibertyTube baixa a IA de transcrição (uns 100 MB).",
                    accent=tema.etapa(2))
    cartao.pack(fill="x")

    linha = tk.Frame(cartao.corpo, bg=tema.cor("card"))
    linha.pack(fill="x", pady=(ESPACO["md"], 0))

    Botao(linha, "Transcrever agora",
          lambda: app.rodar(
              lambda log, prog, ctx: transcribe.transcrever(log, prog, ctx),
              nome="Transcrevendo as cenas", recarregar=True),
          icone="🎧", altura=44).pack(side="left")

    if texto_transcricao:
        rotulo(linha, "  ✓ este projeto já tem transcrição", "pequeno", "sucesso"
               ).pack(side="left", padx=(12, 0))

    espaco(parent, ESPACO["md"])

    if not texto_transcricao:
        return

    # ── roteiro pela IA ──
    cartao_ia = Cartao(parent, "2. Gerar o roteiro com a IA",
                       "O roteiro é a lista dos melhores momentos com os "
                       "tempos de corte.", accent=tema.etapa(2))
    cartao_ia.pack(fill="x")

    if script_ai.conectado():
        rotulo(cartao_ia.corpo, "IA conectada ✓", "pequeno", "sucesso"
               ).pack(anchor="w", pady=(ESPACO["sm"], 0))

        def gerar():
            def trabalho(log, progresso, ctx):
                roteiro = script_ai.gerar_roteiro(texto_transcricao, log=log,
                                                  progresso=progresso, ctx=ctx)
                cuts.salvar_roteiro(roteiro)
                log(f"Roteiro salvo com {cuts.contar_blocos(roteiro)} trecho(s).",
                    "ok")
                return roteiro

            app.rodar(trabalho, nome="Gerando o roteiro",
                      ao_terminar=lambda _: app.navegar("cortar"))

        Botao(cartao_ia.corpo, "Gerar roteiro automático", gerar, icone="✨",
              altura=44).pack(anchor="w", pady=(ESPACO["md"], 0))
    else:
        rotulo(cartao_ia.corpo,
               "A IA ainda não está conectada. A chave do Gemini é grátis e "
               "leva 1 minuto pra pegar.", "pequeno", "texto2"
               ).pack(anchor="w", pady=(ESPACO["sm"], 0))
        Botao(cartao_ia.corpo, "Conectar a IA (grátis)",
              lambda: app.navegar("config"), icone="🔑", altura=42,
              variante="secundario").pack(anchor="w", pady=(ESPACO["md"], 0))

    divisor(cartao_ia.corpo)

    rotulo(cartao_ia.corpo, "Prefere fazer no Gemini ou no ChatGPT? "
                            "Siga estes 4 passos:", "corpo_forte").pack(anchor="w")

    passos = tk.Frame(cartao_ia.corpo, bg=tema.cor("card"))
    passos.pack(fill="x", pady=(ESPACO["sm"], 0))

    def copiar_tudo():
        prompt = script_ai.ler_prompt("timesmap")
        app.root.clipboard_clear()
        app.root.clipboard_append(f"{prompt}\n\n===== TRANSCRIÇÃO =====\n"
                                  f"{texto_transcricao}")
        app.aviso("Prompt + transcrição copiados! Agora é só colar na IA.", "sucesso")

    _passo(passos, 1, "Copiar o prompt + a transcrição juntos",
           [("Copiar tudo", copiar_tudo, "primario")])
    _passo(passos, 2, "Abrir a IA e colar",
           [("Abrir Gemini", lambda: app.abrir_link("https://gemini.google.com"),
             "secundario"),
            ("Abrir ChatGPT", lambda: app.abrir_link("https://chat.openai.com"),
             "secundario")])
    _passo(passos, 3, "Copiar a resposta que a IA gerar", [])
    _passo(passos, 4, "Colar no passo 3 (Cortar cenas) e salvar",
           [("Ir para o passo 3 →", lambda: app.navegar("cortar"), "secundario")])

    espaco(parent, ESPACO["md"])

    # ── texto da transcrição ──
    cartao_texto = Cartao(parent, "Transcrição deste projeto",
                          os.path.basename(proj.arquivo_transcricao))
    cartao_texto.pack(fill="x")

    visor = tk.Text(cartao_texto.corpo, height=12, bg=tema.cor("input"),
                    fg=tema.cor("texto2"), relief="flat", bd=0, wrap="word",
                    font=tema.fonte_mono(9), padx=12, pady=10,
                    highlightthickness=1,
                    highlightbackground=tema.cor("borda"))
    visor.pack(fill="x", pady=(ESPACO["sm"], 0))
    visor.insert("1.0", texto_transcricao)
    visor.configure(state="disabled")

    Banner(parent, "Com o roteiro em mãos, vá para o passo 3 e separe os "
                   "melhores momentos.",
           tipo="info", icone="→",
           acao=("Ir para cortar cenas →", lambda: app.navegar("cortar"))
           ).pack(fill="x", pady=(ESPACO["md"], ESPACO["lg"]))


def _passo(parent, numero, texto, botoes):
    linha = tk.Frame(parent, bg=tema.cor("card"))
    linha.pack(fill="x", pady=(0, 10))

    selo = tk.Label(linha, text=f" {numero} ", font=tema.fonte("micro", peso="bold"),
                    bg=tema.cor("card_hover"), fg=tema.cor("texto"), padx=6, pady=3)
    selo.pack(side="left", padx=(0, 10))

    tk.Label(linha, text=texto, font=tema.fonte("pequeno"), bg=tema.cor("card"),
             fg=tema.cor("texto"), anchor="w").pack(side="left")

    for rotulo_botao, comando, variante in reversed(botoes):
        Botao(linha, rotulo_botao, comando, variante=variante, altura=32,
              fonte=tema.fonte("micro")).pack(side="right", padx=(8, 0))
