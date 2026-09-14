"""
pipeline/transcribe.py
------------------------------------------------------------
Etapa 2 — a IA ouve as cenas e escreve tudo com os tempos.

Gera 2_transcricao/Transcricao.txt no formato que o prompt do roteiro
espera:

    cena_01.mp4
    [0:00:03 --> 0:00:09] a fala que apareceu aqui
"""

import os
from datetime import timedelta

from ..core import projects
from . import whisper_engine
from .base import listar_videos, normalizar


class ErroTranscricao(Exception):
    pass


def _tempo(segundos):
    return str(timedelta(seconds=int(segundos or 0)))


def transcrever(log=None, progresso=None, ctx=None):
    """Transcreve todas as cenas do projeto ativo. Devolve o caminho do
    arquivo de transcrição."""
    log, progresso = normalizar(log, progresso)
    proj = projects.atual().criar_pastas()

    videos = listar_videos(proj.cenas_baixadas)
    if not videos:
        raise ErroTranscricao(
            "Não há cenas baixadas neste projeto.\n"
            "Volte no passo 1 e baixe os vídeos primeiro.")

    progresso("Carregando a IA de transcrição (na primeira vez ela é "
              "baixada)…", None)
    log("Carregando a IA de transcrição (na primeira vez ela é baixada).")
    whisper_engine.carregar("small")

    linhas_totais = 0
    temporario = proj.arquivo_transcricao + ".tmp"
    try:
        with open(temporario, "w", encoding="utf-8") as saida:
            for i, video in enumerate(videos):
                if ctx is not None:
                    ctx.checar()
                inicio_faixa = 5 + (i / len(videos)) * 90
                fim_faixa = 5 + ((i + 1) / len(videos)) * 90
                progresso(f"Transcrevendo {i + 1} de {len(videos)} — {video}",
                          int(inicio_faixa))
                log(f"[{i + 1}/{len(videos)}] {video}")

                def avancou(ouvidos, total, _i=i, _v=video,
                            _a=inicio_faixa, _b=fim_faixa):
                    pct = _a + (_b - _a) * (ouvidos / total if total else 0)
                    progresso(f"Transcrevendo {_i + 1} de {len(videos)} — {_v} "
                              f"({ouvidos / 60:.1f} de {total / 60:.1f} min)",
                              int(pct))

                try:
                    resultado = whisper_engine.transcrever_arquivo(
                        os.path.join(proj.cenas_baixadas, video),
                        ao_avancar=avancou)
                except Exception as e:
                    log(f"  não consegui transcrever {video}: {e}", "erro")
                    continue

                saida.write(f"{video}\n")
                for seg in resultado["segmentos"]:
                    saida.write(f"[{_tempo(seg['inicio'])} --> {_tempo(seg['fim'])}] "
                                f"{seg['texto']}\n")
                    linhas_totais += 1
                saida.write("\n" + "-" * 50 + "\n\n")
                log(f"  ✓ {len(resultado['segmentos'])} fala(s)")

        if linhas_totais == 0:
            raise ErroTranscricao(
                "A transcrição saiu vazia.\n\n"
                "Quase sempre isso quer dizer que as cenas baixaram SEM ÁUDIO. "
                "Baixe de novo ou escolha outro vídeo.")
        os.replace(temporario, proj.arquivo_transcricao)
    except Exception:
        try:
            os.remove(temporario)
        except OSError:
            pass
        raise

    progresso("Transcrição pronta!", 100)
    log(f"Transcrição salva com {linhas_totais} falas.", "ok")
    return proj.arquivo_transcricao


def ler_transcricao():
    """Texto da transcrição do projeto ativo (ou "" se não existe)."""
    proj = projects.atual()
    if not os.path.exists(proj.arquivo_transcricao):
        return ""
    try:
        with open(proj.arquivo_transcricao, encoding="utf-8-sig") as f:
            return f.read()
    except Exception:
        return ""
