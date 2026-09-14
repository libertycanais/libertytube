"""
pipeline/assembly.py
------------------------------------------------------------
Etapa 4 — a montagem final.

    1. junta todos os cortes em um vídeo só
    2. intercala os B-Rolls a cada 5 s (se existirem e o usuário quiser)
    3. aplica letterbox (só no 16:9) e os fades de entrada/saída

Tudo no formato da plataforma escolhida.
"""

import os
import random

from ..core import paths, projects, runtime, timeline
from .base import EXTENSOES_VIDEO, chave_natural, normalizar


class ErroMontagem(Exception):
    pass


PERFIS_EDICAO = {
    "viral": {"transicao": "smoothleft", "duracao": 0.35,
              "visual": "eq=contrast=1.06:saturation=1.12:brightness=0.01,"
                        "unsharp=5:5:0.25:5:5:0"},
    "podcast": {"transicao": "fade", "duracao": 0.25,
                "visual": "eq=contrast=1.02:saturation=1.04"},
    "cinematico": {"transicao": "fadeblack", "duracao": 0.8,
                   "visual": "eq=contrast=1.08:saturation=0.90:brightness=-0.02"},
}
MAX_CORTES_XFADE = 8


def perfil_edicao(chave):
    return PERFIS_EDICAO.get(chave, PERFIS_EDICAO["viral"])


def filtro_movimento(chave, largura, altura):
    if chave == "zoom_suave":
        return (f"zoompan=z='min(zoom+0.0012,1.08)':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d=1:s={largura}x{altura}:fps=30")
    if chave == "pan_suave":
        return (f"zoompan=z='1.05':"
                f"x='(iw-iw/zoom)*(0.5+0.5*sin(on/90))':"
                f"y='ih/2-(ih/zoom/2)':d=1:s={largura}x{altura}:fps=30")
    return ""


def montar(usar_broll=True, usar_letterbox=True, formato=None,
           estilo="viral", movimento="zoom_suave", log=None, progresso=None,
           ctx=None):
    """Gera 4_montagem/montagem_final.mp4 e devolve o caminho."""
    log, progresso = normalizar(log, progresso)
    proj = projects.atual().criar_pastas()

    formato = formato or projects.formato()
    largura, altura = projects.FORMATOS.get(formato, projects.FORMATOS["9:16"])
    escala = (f"scale={largura}:{altura}:force_original_aspect_ratio=increase,"
              f"crop={largura}:{altura}")
    perfil = perfil_edicao(estilo)
    escala_visual = f"{escala},{perfil['visual']}"
    movimento_filtro = filtro_movimento(movimento, largura, altura)
    if movimento_filtro:
        escala_visual = f"{escala_visual},{movimento_filtro}"

    cortes = timeline.listar(proj)
    if not cortes:
        raise ErroMontagem("Não há cortes neste projeto.\n"
                           "Faça o passo 3 (Cortar Cenas) antes de montar.")

    log(f"{len(cortes)} corte(s) — formato {formato} ({largura}x{altura}).")

    # quanto vídeo vai ser gravado — é o que faz a barra andar de verdade
    # em vez de pular de 20 pra 55 e parecer travada
    segundos_totais = sum(runtime.duracao(os.path.join(proj.cenas_cortadas, c))
                          for c in cortes)
    if segundos_totais:
        log(f"São {segundos_totais / 60:.1f} minuto(s) de vídeo pra gravar.")

    tem_broll = bool(usar_broll and os.path.isdir(proj.broll)
                     and [f for f in os.listdir(proj.broll)
                          if f.lower().endswith(EXTENSOES_VIDEO)])
    faixa_juntar = (2, 40) if tem_broll else (2, 55)

    # ── 1. junta os cortes ──
    progresso("Juntando os cortes…", 2)
    lista = os.path.join(proj.montagem, "_lista.txt")
    base = os.path.join(proj.montagem, "montagem_base.mp4")
    base_temporaria = base + ".tmp.mp4"
    with open(lista, "w", encoding="utf-8") as f:
        for corte in cortes:
            caminho = os.path.relpath(os.path.join(proj.cenas_cortadas, corte),
                                      proj.montagem).replace("\\", "/")
            f.write(f"file '{caminho}'\n")

    try:
        if 1 < len(cortes) <= MAX_CORTES_XFADE:
            try:
                _juntar_com_transicoes(
                    proj, cortes, base_temporaria, escala_visual, perfil, ctx,
                    progresso=progresso, faixa=faixa_juntar)
                log(f"Transições {estilo} aplicadas entre os cortes.")
            except runtime.ErroFFmpeg:
                log("As transições não puderam ser aplicadas; usando cortes "
                    "contínuos.", "aviso")
                _juntar_continuo(
                    proj, cortes, base_temporaria, escala_visual, ctx, progresso,
                    segundos_totais, faixa_juntar)
        else:
            if len(cortes) > MAX_CORTES_XFADE:
                log("Muitos cortes para transições simultâneas; usando "
                    "montagem contínua estável.", "aviso")
            _juntar_continuo(
                proj, cortes, base_temporaria, escala_visual, ctx, progresso,
                segundos_totais, faixa_juntar)
        os.replace(base_temporaria, base)
    finally:
        try:
            os.remove(lista)
        except Exception:
            pass
        try:
            os.remove(base_temporaria)
        except Exception:
            pass

    atual = base

    # ── 2. intercala os B-Rolls ──
    brolls = []
    if usar_broll and os.path.isdir(proj.broll):
        brolls = [f for f in os.listdir(proj.broll)
                  if f.lower().endswith(EXTENSOES_VIDEO)]

    if brolls:
        if ctx is not None:
            ctx.checar()
        progresso("Intercalando os B-Rolls…", faixa_juntar[1])
        log(f"Intercalando {len(brolls)} B-Roll(s) a cada 5 s.")
        atual = _intercalar_broll(proj, base, brolls, escala_visual, ctx,
                                  progresso=progresso, faixa=(40, 68))

    # ── 3. letterbox + fades ──
    if ctx is not None:
        ctx.checar()
    final = proj.video_montado
    final_temporario = final + ".tmp.mp4"
    letterbox = paths.asset("letterbox.png")
    duracao = runtime.duracao(atual)
    fade = 1.0
    saida_fade = max(0.1, duracao - fade)
    faixa_final = (68 if brolls else 55, 99)

    if usar_letterbox and formato == "16:9" and os.path.exists(letterbox):
        progresso("Aplicando letterbox e fades…", faixa_final[0])
        filtro = (f"[0:v][1:v]overlay=0:0[ov];"
                  f"[ov]fade=t=in:st=0:d={fade},"
                  f"fade=t=out:st={saida_fade:.2f}:d={fade}[vout]")
        try:
            runtime.rodar_ffmpeg(
                ["-i", atual, "-i", letterbox, "-filter_complex", filtro,
                 "-af", f"afade=t=in:st=0:d={fade},"
                        f"afade=t=out:st={saida_fade:.2f}:d={fade}",
                 "-map", "[vout]", "-map", "0:a?",
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                 "-c:a", "aac", "-b:a", "192k", final_temporario],
                ctx=ctx, progresso=progresso, duracao_total=duracao,
                rotulo="Gravando o vídeo final", faixa=faixa_final)
            os.replace(final_temporario, final)
        finally:
            try:
                os.remove(final_temporario)
            except OSError:
                pass
    else:
        progresso("Aplicando os fades…", faixa_final[0])
        try:
            runtime.rodar_ffmpeg(
                ["-i", atual,
                 "-vf", f"fade=t=in:st=0:d={fade},"
                        f"fade=t=out:st={saida_fade:.2f}:d={fade}",
                 "-af", f"afade=t=in:st=0:d={fade},"
                        f"afade=t=out:st={saida_fade:.2f}:d={fade}",
                  "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                 "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                  "-c:a", "aac", "-b:a", "192k", final_temporario],
                 ctx=ctx, progresso=progresso, duracao_total=duracao,
                 rotulo="Gravando o vídeo final", faixa=faixa_final)
            os.replace(final_temporario, final)
        except runtime.ErroFFmpeg:
            import shutil
            shutil.copy2(atual, final_temporario)  # sem fades, mas entrega o vídeo
            os.replace(final_temporario, final)
        finally:
            try:
                os.remove(final_temporario)
            except OSError:
                pass

    progresso("Montagem pronta!", 100)
    log("Vídeo montado em 4_montagem/montagem_final.mp4", "ok")
    return final


def _juntar_continuo(proj, cortes, saida, filtro, ctx, progresso,
                     duracao_total, faixa):
    """Concatena audio e video pelo filtro concat, sem copiar streams.

    O concat demuxer pode preservar timestamps incompatíveis entre arquivos
    criados em máquinas diferentes. Normalizar cada entrada aqui evita MP4
    com video e audio em duracoes diferentes.
    """
    entradas, filtros = [], []
    pares = []
    for i, corte in enumerate(cortes):
        entradas += ["-i", os.path.join(proj.cenas_cortadas, corte)]
        filtros.append(
            f"[{i}:v]setpts=PTS-STARTPTS,{filtro},fps=30,format=yuv420p[v{i}];"
            f"[{i}:a]aresample=44100,asetpts=PTS-STARTPTS[a{i}]"
        )
        pares.append(f"[v{i}][a{i}]")
    filtros.append("".join(pares) +
                   f"concat=n={len(cortes)}:v=1:a=1[vout][aout]")
    runtime.rodar_ffmpeg(
        entradas + ["-filter_complex", ";".join(filtros),
                    "-map", "[vout]", "-map", "[aout]",
                    "-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                    "-force_key_frames", "expr:gte(t,n_forced*1)",
                    "-g", "30", "-keyint_min", "30", "-sc_threshold", "0",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", saida],
        ctx=ctx, progresso=progresso, duracao_total=duracao_total,
        rotulo="Juntando os cortes", faixa=faixa)


def _juntar_com_transicoes(proj, cortes, saida, filtro, perfil, ctx,
                           progresso=None, faixa=None):
    """Junta cortes com xfade/acrossfade e efeitos visuais do preset."""
    duracoes = [runtime.duracao(os.path.join(proj.cenas_cortadas, corte))
                for corte in cortes]
    if any(d <= 0 for d in duracoes):
        raise runtime.ErroFFmpeg("Não consegui medir a duração dos cortes.")

    transicao = min(perfil["duracao"], max(0.1, min(duracoes) / 3))
    entradas, filtros = [], []
    for i, corte in enumerate(cortes):
        caminho = os.path.join(proj.cenas_cortadas, corte)
        entradas += ["-i", caminho]
        filtros.append(
            f"[{i}:v]setpts=PTS-STARTPTS,{filtro},fps=30,format=yuv420p[v{i}];"
            f"[{i}:a]asetpts=PTS-STARTPTS,aresample=48000[a{i}]"
        )

    video_atual = "v0"
    audio_atual = "a0"
    acumulado = duracoes[0]
    for i in range(1, len(cortes)):
        video_novo = f"vx{i}"
        audio_novo = f"ax{i}"
        offset = max(0.0, acumulado - transicao)
        filtros.append(
            f"[{video_atual}][v{i}]xfade=transition={perfil['transicao']}"
            f":duration={transicao:.3f}:offset={offset:.3f}[{video_novo}];"
            f"[{audio_atual}][a{i}]acrossfade=d={transicao:.3f}:"
            f"c1=tri:c2=tri[{audio_novo}]"
        )
        video_atual = video_novo
        audio_atual = audio_novo
        acumulado += duracoes[i] - transicao

    filtros_texto = ";".join(filtros)
    runtime.rodar_ffmpeg(
        entradas + ["-filter_complex", filtros_texto,
                    "-map", f"[{video_atual}]", "-map", f"[{audio_atual}]",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", "-shortest", saida],
        ctx=ctx, progresso=progresso, duracao_total=sum(duracoes),
        rotulo="Aplicando transições e efeitos", faixa=faixa)


def _intercalar_broll(proj, base, brolls, escala, ctx, progresso=None,
                      faixa=None):
    """Monta a lista alternando 5 s de fala e 5 s de B-Roll."""
    duracao = runtime.duracao(base)
    sorteio = brolls.copy()
    random.shuffle(sorteio)

    lista = os.path.join(proj.montagem, "_inter.txt")
    saida = os.path.join(proj.montagem, "montagem_broll.mp4")
    saida_temporaria = saida + ".tmp.mp4"

    with open(lista, "w", encoding="utf-8") as f:
        tempo, vez_do_broll = 0.0, True
        while tempo < duracao:
            fim = min(tempo + 5.0, duracao)
            pedaco = fim - tempo
            if vez_do_broll:
                if not sorteio:
                    sorteio = brolls.copy()
                    random.shuffle(sorteio)
                caminho = os.path.relpath(os.path.join(proj.broll, sorteio.pop(0)),
                                          proj.montagem).replace("\\", "/")
                f.write(f"file '{caminho}'\n")
                # limita SEMPRE ao tamanho do pedaço, senão áudio e vídeo
                # saem de sincronia quando o B-Roll não tem exatos 5 s
                f.write(f"outpoint {pedaco:.2f}\n")
            else:
                caminho = os.path.relpath(base, proj.montagem).replace("\\", "/")
                f.write(f"file '{caminho}'\n")
                f.write(f"inpoint {tempo:.2f}\n")
                f.write(f"outpoint {fim:.2f}\n")
            tempo += 5.0
            vez_do_broll = not vez_do_broll

    try:
        runtime.rodar_ffmpeg(
            ["-f", "concat", "-safe", "0", "-i", lista, "-i", base,
             "-map", "0:v", "-map", "1:a?", "-vf", escala,
             "-c:v", "libx264", "-preset", "fast", "-crf", "18",
              "-c:a", "aac", "-b:a", "192k", "-shortest", saida_temporaria],
            ctx=ctx, progresso=progresso, duracao_total=duracao,
            rotulo="Intercalando os B-Rolls", faixa=faixa)
        os.replace(saida_temporaria, saida)
    finally:
        try:
            os.remove(lista)
        except Exception:
            pass
        try:
            os.remove(saida_temporaria)
        except OSError:
            pass
    return saida


def listar_montagens():
    """Vídeos já montados neste projeto (pra galeria da tela)."""
    proj = projects.atual()
    if not os.path.isdir(proj.montagem):
        return []
    return [os.path.join(proj.montagem, f)
            for f in sorted(os.listdir(proj.montagem), key=chave_natural)
            if f.lower().endswith(EXTENSOES_VIDEO)]
