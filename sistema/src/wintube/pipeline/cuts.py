"""
pipeline/cuts.py
------------------------------------------------------------
Etapa 3 — separar os melhores momentos.

    cortar()      corta as cenas nos tempos que estão no roteiro.txt
    gerar_broll() gera clipes curtos aleatórios pra dar movimento

Os cortes já saem no formato da plataforma escolhida (9:16, 1:1 ou 16:9)
e com keyframe a cada 1 s — é isso que evita o vídeo "congelar" quando a
montagem intercala os B-Rolls.
"""

import os
import random
import re

from ..core import projects, runtime, timeline
from .base import EXTENSOES_VIDEO, listar_videos, normalizar

PADRAO_TEMPO = r"\[\s*([0-9:]+)\s*-->\s*([0-9:]+)\s*\]"
MIN_DURACAO_CORTE = 60.0

# parâmetros de qualidade usados nos dois cortes
_QUALIDADE = ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
              "-pix_fmt", "yuv420p",
              "-force_key_frames", "expr:gte(t,n_forced*1)",
              "-g", "30", "-keyint_min", "30", "-sc_threshold", "0",
              "-c:a", "aac", "-b:a", "192k", "-ar", "44100"]


class ErroCorte(Exception):
    pass


def _segundos(marca):
    """"0:01:23" → 83.0 — pra saber o tamanho do corte e mostrar a barra
    andando enquanto o ffmpeg grava."""
    try:
        partes = [float(p) for p in str(marca).split(":")]
    except ValueError:
        return 0.0
    total = 0.0
    for parte in partes:
        total = total * 60 + parte
    return total


def _intervalo_minimo(inicio, fim, duracao_video):
    """Aumenta o trecho para pelo menos um minuto sem passar do original."""
    inicio_s = max(0.0, _segundos(inicio))
    fim_s = max(inicio_s, _segundos(fim))

    if duracao_video <= 0:
        return inicio_s, fim_s
    if duracao_video < MIN_DURACAO_CORTE:
        return 0.0, duracao_video

    fim_s = min(fim_s, duracao_video)
    if fim_s - inicio_s >= MIN_DURACAO_CORTE:
        return inicio_s, fim_s

    fim_estendido = min(duracao_video, inicio_s + MIN_DURACAO_CORTE)
    if fim_estendido - inicio_s >= MIN_DURACAO_CORTE:
        return inicio_s, fim_estendido

    inicio_ajustado = max(0.0, duracao_video - MIN_DURACAO_CORTE)
    return inicio_ajustado, duracao_video


def ler_roteiro():
    proj = projects.atual()
    if not os.path.exists(proj.arquivo_roteiro):
        return ""
    try:
        with open(proj.arquivo_roteiro, encoding="utf-8-sig") as f:
            return f.read()
    except Exception:
        return ""


def salvar_roteiro(texto):
    proj = projects.atual().criar_pastas()
    with open(proj.arquivo_roteiro, "w", encoding="utf-8") as f:
        f.write(texto or "")
    return proj.arquivo_roteiro


def contar_blocos(texto=None):
    """Quantos trechos com timestamp o roteiro tem."""
    return len(re.findall(PADRAO_TEMPO, texto if texto is not None else ler_roteiro()))


def cortar(log=None, progresso=None, ctx=None):
    """Corta as cenas conforme o roteiro. Devolve quantos cortes saíram."""
    log, progresso = normalizar(log, progresso)
    proj = projects.atual().criar_pastas()

    if not os.path.exists(proj.arquivo_roteiro):
        raise ErroCorte("Não achei o roteiro deste projeto.\n"
                        "Cole o roteiro da IA no passo 3 e salve antes de cortar.")

    with open(proj.arquivo_roteiro, encoding="utf-8-sig") as f:
        linhas = [l.strip() for l in f if l.strip()]

    blocos = [l for l in linhas if re.search(PADRAO_TEMPO, l)]
    if not blocos:
        raise ErroCorte(
            "O roteiro não tem nenhum trecho com tempo.\n\n"
            "Cada trecho precisa estar assim:\n"
            "cena_01.mp4\n[0:00:12 --> 0:00:21] a fala escolhida")

    fmt = projects.formato()
    enq = projects.enquadramento()
    largura, altura = projects.FORMATOS[fmt]
    log(f"{len(blocos)} trecho(s) — formato {fmt}, enquadramento {enq}.")

    video_atual, numero, gerados = None, 0, 0
    gerados_nomes = set()
    for linha in linhas:
        if ctx is not None:
            ctx.checar()

        if linha.lower().endswith(EXTENSOES_VIDEO):
            video_atual = linha
            continue

        m = re.search(PADRAO_TEMPO, linha)
        if not (m and video_atual):
            continue

        inicio, fim = m.groups()
        numero += 1
        # cada corte ocupa a sua fatia da barra, e dentro dela o ffmpeg
        # reporta o andamento de verdade
        faixa = ((numero - 1) / len(blocos) * 100, numero / len(blocos) * 100)
        entrada = os.path.join(proj.cenas_baixadas, video_atual)
        if not os.path.exists(entrada):
            log(f"  pulei: {video_atual} não está na pasta de cenas.", "aviso")
            continue

        duracao_video = runtime.duracao(entrada)
        inicio_s, fim_s = _intervalo_minimo(inicio, fim, duracao_video)
        tamanho = max(0.0, fim_s - inicio_s)
        inicio_ffmpeg = f"{inicio_s:.3f}"
        progresso(f"Cortando {numero} de {len(blocos)}…", int(faixa[0]))

        if tamanho < MIN_DURACAO_CORTE and duracao_video:
            log(f"  {video_atual} tem menos de 1 minuto; usando o vídeo inteiro.",
                "aviso")
        elif tamanho > max(0.0, _segundos(fim) - _segundos(inicio)) + 0.5:
            log(f"  cena {numero} estendida para pelo menos 1 minuto.")

        saida = os.path.join(proj.cenas_cortadas, f"corte_cena_{numero:02d}.mp4")

        # "Seguir rosto" só faz sentido no vertical; se falhar, cai no central
        if fmt == "9:16" and enq == "seguir":
            if _tentar_seguir_rosto(entrada, inicio_ffmpeg,
                                    f"{fim_s:.3f}", saida, numero,
                                    largura, altura, log, ctx) == "pronto":
                gerados += 1
                gerados_nomes.add(os.path.basename(saida))
                continue

        filtro = projects.filtro_escala(fmt, "centro" if enq == "seguir" else enq)

        try:
            runtime.rodar_ffmpeg(["-i", entrada, "-ss", inicio_ffmpeg,
                                  "-t", f"{tamanho:.3f}",
                                  "-vf", filtro] + _QUALIDADE + [saida],
                                 ctx=ctx, progresso=progresso,
                                 duracao_total=tamanho,
                                 rotulo=f"Corte {numero} de {len(blocos)}",
                                 faixa=faixa)
            gerados += 1
            gerados_nomes.add(os.path.basename(saida))
            log(f"  ✓ corte_cena_{numero:02d}.mp4")
        except runtime.ErroFFmpeg as e:
            log(f"  erro no corte {numero}: {e}", "erro")

    if not gerados:
        raise ErroCorte("Nenhum corte foi gerado. Confira se os nomes das cenas "
                        "no roteiro batem com os arquivos baixados.")

    for antigo in listar_videos(proj.cenas_cortadas):
        if antigo not in gerados_nomes:
            try:
                os.remove(os.path.join(proj.cenas_cortadas, antigo))
            except OSError:
                log(f"  não consegui limpar o corte antigo {antigo}.", "aviso")

    timeline.resetar(proj)
    progresso(f"{gerados} corte(s) prontos!", 100)
    log(f"{gerados} corte(s) em 3_cortes/cenas_cortadas.", "ok")
    return gerados


def _tentar_seguir_rosto(entrada, inicio, fim, saida, numero,
                          largura, altura, log, ctx):
    """Corta o trecho, rastreia o rosto nele e regrava seguindo a pessoa.
    Devolve "pronto" se conseguiu, ou None pra cair no corte central."""
    from . import face_track

    temporario = saida.replace(".mp4", "_tmp.mp4")
    try:
        tamanho = max(0.0, _segundos(fim) - _segundos(inicio))
        runtime.rodar_ffmpeg(["-i", entrada, "-ss", inicio,
                              "-t", f"{tamanho:.3f}",
                              "-c:v", "libx264", "-c:a", "aac", temporario], ctx=ctx)
        filtro = face_track.filtro_seguindo_rosto(temporario, largura, altura, log=log)
        if not filtro:
            return None
        runtime.rodar_ffmpeg(["-i", temporario, "-vf", filtro] + _QUALIDADE + [saida],
                             ctx=ctx)
        log(f"  ✓ corte_cena_{numero:02d}.mp4 (seguindo o rosto)")
        return "pronto"
    except Exception as e:
        log(f"  rastreio falhou no corte {numero} ({e}); usando corte central.", "aviso")
        return None
    finally:
        try:
            os.remove(temporario)
        except Exception:
            pass


def gerar_broll(clipes_por_cena=10, duracao_clipe=5.0,
                log=None, progresso=None, ctx=None):
    """Gera clipes curtos aleatórios de cada cena, pra intercalar na
    montagem e dar movimento ao vídeo."""
    log, progresso = normalizar(log, progresso)
    proj = projects.atual().criar_pastas()

    cenas = listar_videos(proj.cenas_baixadas)
    if not cenas:
        raise ErroCorte("Não há cenas baixadas neste projeto.")

    total = 0
    for i, arquivo in enumerate(cenas):
        if ctx is not None:
            ctx.checar()

        entrada = os.path.join(proj.cenas_baixadas, arquivo)
        duracao = runtime.duracao(entrada)
        if duracao <= duracao_clipe:
            log(f"  {arquivo}: curto demais, pulei.", "aviso")
            continue

        base = os.path.splitext(arquivo)[0]
        for n in range(1, clipes_por_cena + 1):
            if ctx is not None:
                ctx.checar()
            progresso(f"B-Roll da cena {i + 1} de {len(cenas)} ({n}/{clipes_por_cena})",
                      int(((i + n / clipes_por_cena) / len(cenas)) * 100))
            comeco = random.uniform(0, duracao - duracao_clipe)
            saida = os.path.join(proj.broll, f"{base}_broll_{n:02d}.mp4")
            try:
                runtime.rodar_ffmpeg(
                    ["-ss", f"{comeco:.2f}", "-i", entrada, "-t", str(duracao_clipe),
                     "-c:v", "libx264",
                     "-force_key_frames", "expr:gte(t,n_forced*1)",
                     "-g", "30", "-keyint_min", "30", "-sc_threshold", "0",
                     "-c:a", "aac", "-b:a", "192k", saida], ctx=ctx)
                total += 1
            except runtime.ErroFFmpeg:
                pass
        log(f"  ✓ {arquivo}: {clipes_por_cena} B-Rolls")

    if not total:
        raise ErroCorte("Não consegui gerar B-Rolls (as cenas são curtas demais?).")

    progresso(f"{total} B-Roll(s) prontos!", 100)
    log(f"{total} B-Roll(s) em 3_cortes/cenas_broll.", "ok")
    return total
