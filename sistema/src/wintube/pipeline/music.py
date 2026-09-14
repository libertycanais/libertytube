"""
pipeline/music.py
------------------------------------------------------------
Trilha sonora: baixa as músicas e mixa por baixo do vídeo montado.

A trilha entra baixinha (15%), com fade de entrada e saída, pra não
cobrir a fala.
"""

import os
import random

from ..core import projects, runtime
from .base import extrair_links, listar_audios, normalizar


class ErroTrilha(Exception):
    pass


def ler_links_trilhas():
    proj = projects.atual()
    if not os.path.exists(proj.arquivo_trilhas):
        return ""
    try:
        with open(proj.arquivo_trilhas, encoding="utf-8-sig") as f:
            return f.read()
    except Exception:
        return ""


def salvar_links_trilhas(texto):
    proj = projects.atual().criar_pastas()
    with open(proj.arquivo_trilhas, "w", encoding="utf-8") as f:
        f.write(texto or "")
    return proj.arquivo_trilhas


def baixar_trilhas(texto=None, log=None, progresso=None, ctx=None):
    """Baixa em MP3 as músicas dos links informados."""
    log, progresso = normalizar(log, progresso)
    proj = projects.atual().criar_pastas()

    links = extrair_links(texto if texto is not None else ler_links_trilhas())
    if not links:
        raise ErroTrilha("Cole pelo menos um link de música (YouTube) antes de baixar.")

    try:
        import yt_dlp
    except ImportError:
        raise ErroTrilha("O componente de download não está instalado. "
                         "Rode o instalador do LibertyTube de novo.")

    opcoes = {
        "format": "bestaudio/best",
        "outtmpl": os.path.join(proj.trilhas_baixadas, "%(title)s.%(ext)s"),
        "ignoreerrors": True,
        "retries": 5,
        "socket_timeout": 30,
        "quiet": True,
        "no_warnings": True,
        "postprocessors": [{"key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3", "preferredquality": "192"}],
    }

    baixadas = 0
    with yt_dlp.YoutubeDL(opcoes) as ydl:
        for i, link in enumerate(links, 1):
            if ctx is not None:
                ctx.checar()
            progresso(f"Baixando música {i} de {len(links)}…",
                      int(i / len(links) * 100))
            try:
                ydl.download([link])
                baixadas += 1
                log(f"  ✓ música {i}")
            except Exception as e:
                log(f"  não consegui baixar {link}: {e}", "erro")

    total = len(listar_audios(proj.trilhas_baixadas))
    if not total:
        raise ErroTrilha("Nenhuma música foi baixada. Confira os links.")

    progresso(f"{total} música(s) na pasta.", 100)
    log(f"{total} trilha(s) em 5_trilhas/trilhas_baixadas.", "ok")
    return total


def sonorizar(trilha=None, volume=0.15, log=None, progresso=None, ctx=None):
    """Mixa uma trilha por baixo do vídeo montado.
    Devolve o caminho de 5_trilhas/montagem_sonorizada.mp4."""
    log, progresso = normalizar(log, progresso)
    proj = projects.atual().criar_pastas()

    video = proj.video_montado
    if not os.path.exists(video):
        raise ErroTrilha("O vídeo montado ainda não existe.\n"
                         "Faça o passo 4 (Montar Vídeo) antes de sonorizar.")

    disponiveis = [os.path.join(proj.trilhas_baixadas, f)
                   for f in listar_audios(proj.trilhas_baixadas)]
    if not disponiveis:
        raise ErroTrilha("Você ainda não baixou nenhuma música.\n"
                         "Cole os links e clique em Baixar Trilhas.")

    duracao_video = runtime.duracao(video)
    if trilha and os.path.exists(trilha):
        escolhida = trilha
    else:
        # prefere uma trilha que cubra o vídeo inteiro
        compativeis = [t for t in disponiveis if runtime.duracao(t) >= duracao_video]
        escolhida = random.choice(compativeis or disponiveis)

    precisa_repetir = runtime.duracao(escolhida) < duracao_video
    log(f"Trilha: {os.path.basename(escolhida)}"
        + (" (vai repetir pra cobrir o vídeo)" if precisa_repetir else ""))
    progresso("Mixando a trilha…", 5)

    entrada_fade, saida_fade = 2.0, 3.0
    inicio_saida = duracao_video - saida_fade
    if inicio_saida < entrada_fade:
        inicio_saida = duracao_video * 0.8
        saida_fade = max(0.2, duracao_video * 0.2)

    filtro = (f"[1:a]volume={volume}[v];[v]afade=t=in:st=0:d={entrada_fade}[fi];"
              f"[fi]afade=t=out:st={inicio_saida:.2f}:d={saida_fade:.2f}[bg];"
              f"[0:a][bg]amix=inputs=2:duration=first[mx];[mx]volume=2[aout]")
    saida_temporaria = proj.video_sonorizado + ".tmp.mp4"

    args = ["-i", video]
    if precisa_repetir:
        args += ["-stream_loop", "-1"]
    args += ["-i", escolhida, "-filter_complex", filtro,
             "-map", "0:v", "-map", "[aout]",
             "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             saida_temporaria]

    try:
        runtime.rodar_ffmpeg(args, ctx=ctx, progresso=progresso,
                             duracao_total=duracao_video,
                             rotulo="Mixando a trilha", faixa=(5, 99))
        os.replace(saida_temporaria, proj.video_sonorizado)
    finally:
        try:
            os.remove(saida_temporaria)
        except OSError:
            pass
    progresso("Trilha aplicada!", 100)
    log("Vídeo com trilha em 5_trilhas/montagem_sonorizada.mp4", "ok")
    return proj.video_sonorizado
