"""
ui/screens/assembly.py
------------------------------------------------------------
Etapa 4 — montar o vídeo e colocar a trilha.

Junta os cortes, intercala os B-Rolls, aplica os fades e, na mesma tela,
baixa e mixa a música de fundo.
"""

import os
import tkinter as tk

from ...core import projects, settings
from ...pipeline import assembly, base, music
from ..media import Galeria, cabecalho_galeria
from ..theme import ESPACO, tema
from ..widgets import (Banner, Botao, Cabecalho, Cartao, Chave, Seletor,
                       divisor, espaco, rotulo)

FORMATOS_UI = [
    ("9:16", "Vertical 9:16"),
    ("1:1", "Quadrado 1:1"),
    ("16:9", "Horizontal 16:9"),
]

ONDE_USAR = {
    "9:16": "TikTok, Reels, Shorts e Stories",
    "1:1": "Feed do Instagram e Facebook",
    "16:9": "YouTube e Facebook",
}


def _montagens_do_projeto():
    """O vídeo montado (com trilha, se já tiver)."""
    proj = projects.atual()
    arquivos = [os.path.join(proj.montagem, a)
                for a in base.listar_videos(proj.montagem)]
    if os.path.exists(proj.video_sonorizado):
        arquivos.insert(0, proj.video_sonorizado)
    return arquivos


def montar(app, parent):
    proj = app.projeto
    cortes = base.listar_videos(proj.cenas_cortadas)
    montagens = base.listar_videos(proj.montagem)
    trilhas = base.listar_audios(proj.trilhas_baixadas)

    Cabecalho(parent, "Montar vídeo",
              "Junta os cortes num vídeo só, no formato da rede escolhida, "
              "e coloca a trilha por baixo.", etapa=4).pack(fill="x",
                                                            pady=(4, ESPACO["lg"]))

    if not cortes:
        Banner(parent, "Este projeto ainda não tem cortes pra montar.",
               tipo="aviso", icone="!",
               acao=("Ir para o passo 3 →", lambda: app.navegar("cortar"))
               ).pack(fill="x")
        return

    # ── formato ──
    cartao_formato = Cartao(parent, "1. Formato do vídeo final",
                            f"{len(cortes)} corte(s) neste projeto.",
                            accent=tema.etapa(4))
    cartao_formato.pack(fill="x")

    dica = rotulo(cartao_formato.corpo, "", "pequeno", "texto2")
    dica.configure(bg=tema.cor("card"))

    def escolher_formato(chave):
        projects.definir_formato(chave)
        dica.configure(text=f"✓  {ONDE_USAR.get(chave, '')}")

    Seletor(cartao_formato.corpo, FORMATOS_UI, valor=projects.formato(),
            ao_mudar=escolher_formato, colunas=3).pack(anchor="w",
                                                       pady=(ESPACO["sm"], 0))
    dica.configure(text=f"✓  {ONDE_USAR.get(projects.formato(), '')}")
    dica.pack(anchor="w", pady=(6, 0))

    divisor(cartao_formato.corpo)

    opcoes = tk.Frame(cartao_formato.corpo, bg=tema.cor("card"))
    opcoes.pack(fill="x")

    brolls = base.listar_videos(proj.broll)

    usar_broll = Chave(
        opcoes, "Intercalar os B-Rolls",
        f"{len(brolls)} clipe(s) prontos — entram a cada 5 s pra dar movimento"
        if brolls else "nenhum B-Roll neste projeto (gere no passo 3)",
        valor=bool(brolls) and bool(settings.get("usar_broll", False)),
        ao_mudar=lambda v: settings.set("usar_broll", v))
    usar_broll.pack(fill="x", pady=(0, 4))
    if not brolls:
        usar_broll.bloquear("nenhum B-Roll neste projeto (gere no passo 3)")

    divisor(opcoes, pady=6)

    usar_letterbox = Chave(
        opcoes, "Faixas pretas de cinema",
        "só faz efeito no formato 16:9",
        valor=bool(settings.get("letterbox", True)),
        ao_mudar=lambda v: settings.set("letterbox", v))
    usar_letterbox.pack(fill="x")

    def montar_video():
        app.rodar(lambda log, prog, ctx: assembly.montar(
            usar_broll=usar_broll.ligada(),
            usar_letterbox=usar_letterbox.ligada(),
            log=log, progresso=prog, ctx=ctx),
            nome="Montando o vídeo", recarregar=True,
            prontos=lambda: _montagens_do_projeto())

    Botao(cartao_formato.corpo, "Gerar vídeo montado", montar_video,
          icone="🎬", altura=46).pack(anchor="w", pady=(ESPACO["md"], 0))

    espaco(parent, ESPACO["md"])

    # ── trilha ──
    cartao_trilha = Cartao(parent, "2. Trilha sonora (opcional)",
                           "Cole links de músicas do YouTube, um por linha. "
                           "A trilha entra baixinha, sem cobrir a fala.",
                           accent=tema.etapa(4))
    cartao_trilha.pack(fill="x")

    editor = tk.Text(cartao_trilha.corpo, height=3, bg=tema.cor("input"),
                     fg=tema.cor("texto"), insertbackground=tema.cor("primario"),
                     relief="flat", bd=0, wrap="word", font=tema.fonte("corpo"),
                     padx=12, pady=10, highlightthickness=1,
                     highlightbackground=tema.cor("borda"))
    editor.pack(fill="x", pady=(ESPACO["sm"], 0))
    salvos = music.ler_links_trilhas()
    if salvos:
        editor.insert("1.0", salvos)

    linha = tk.Frame(cartao_trilha.corpo, bg=tema.cor("card"))
    linha.pack(fill="x", pady=(ESPACO["md"], 0))

    def baixar_trilhas():
        texto = editor.get("1.0", "end").strip()
        music.salvar_links_trilhas(texto)
        app.rodar(lambda log, prog, ctx: music.baixar_trilhas(texto, log, prog, ctx),
                  nome="Baixando as trilhas", recarregar=True)

    def sonorizar():
        app.rodar(lambda log, prog, ctx: music.sonorizar(
            log=log, progresso=prog, ctx=ctx),
            nome="Colocando a trilha", recarregar=True)

    Botao(linha, "Baixar trilhas", baixar_trilhas, icone="🎵",
          variante="secundario", altura=42).pack(side="left")
    Botao(linha, "Aplicar trilha no vídeo", sonorizar, icone="🔊", altura=42
          ).pack(side="left", padx=(10, 0))

    if trilhas:
        rotulo(cartao_trilha.corpo,
               f"{len(trilhas)} música(s) baixada(s): "
               + ", ".join(os.path.splitext(t)[0][:24] for t in trilhas[:3])
               + ("…" if len(trilhas) > 3 else ""),
               "pequeno", "texto2").pack(anchor="w", pady=(10, 0))

    espaco(parent, ESPACO["md"])

    # ── resultado ──
    if os.path.exists(proj.video_sonorizado):
        Banner(parent, "Vídeo montado e com trilha! Agora é só colocar a "
                       "legenda e a sua marca.",
               tipo="sucesso",
               acao=("Ir para legenda →", lambda: app.navegar("legenda"))
               ).pack(fill="x", pady=(0, ESPACO["md"]))
    elif os.path.exists(proj.video_montado):
        Banner(parent, "Vídeo montado! Coloque uma trilha ou siga direto pra "
                       "legenda.",
               tipo="sucesso",
               acao=("Ir para legenda →", lambda: app.navegar("legenda"))
               ).pack(fill="x", pady=(0, ESPACO["md"]))

    arquivos = [os.path.join(proj.montagem, m) for m in montagens]
    if os.path.exists(proj.video_sonorizado):
        arquivos.insert(0, proj.video_sonorizado)

    cabecalho_galeria(parent, "Vídeos montados", len(arquivos), proj.montagem,
                      ao_atualizar=app.recarregar).pack(fill="x", pady=(0, 8))
    Galeria(parent, arquivos, colunas=3, ao_atualizar=app.recarregar,
            vazio="Nenhuma montagem ainda. Clique em Gerar vídeo montado."
            ).pack(fill="x", pady=(0, ESPACO["lg"]))
