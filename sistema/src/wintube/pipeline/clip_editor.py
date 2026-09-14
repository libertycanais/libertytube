"""Edicao destrutiva controlada de um corte da timeline."""

import os

from ..core import runtime


_QUALIDADE = [
    "-c:v", "libx264", "-preset", "medium", "-crf", "18",
    "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k",
    "-movflags", "+faststart",
]


class ErroEdicao(Exception):
    pass


def _numero(valor, nome):
    try:
        numero = float(valor)
    except (TypeError, ValueError):
        raise ErroEdicao(f"O valor de {nome} precisa ser um número.")
    if numero < 0:
        raise ErroEdicao(f"O valor de {nome} não pode ser negativo.")
    return numero


def aparar(caminho, inicio, fim, log=None, progresso=None, ctx=None):
    """Cria um novo arquivo com o intervalo aparado, sem sobrescrever a origem."""
    if not caminho or not os.path.exists(caminho):
        raise ErroEdicao("O corte selecionado não existe mais.")
    inicio = _numero(inicio, "início")
    fim = _numero(fim, "fim")
    if fim <= inicio:
        raise ErroEdicao("O fim precisa ser maior que o início.")

    raiz, extensao = os.path.splitext(caminho)
    saida = raiz + "_editado" + extensao
    indice = 2
    while os.path.exists(saida):
        saida = raiz + f"_editado_{indice}" + extensao
        indice += 1
    temporario = saida + ".tmp.mp4"
    try:
        runtime.rodar_ffmpeg(
            ["-ss", f"{inicio:.3f}", "-i", caminho, "-t", f"{fim - inicio:.3f}"
             ] + _QUALIDADE + [temporario],
            ctx=ctx, progresso=progresso, duracao_total=fim - inicio,
            rotulo="Aparando o corte", faixa=(0, 100))
        if not os.path.exists(temporario):
            raise ErroEdicao("O FFmpeg não criou o corte editado.")
        os.replace(temporario, saida)
        if log:
            log(f"Corte ajustado: {os.path.basename(saida)}", "ok")
        return saida
    finally:
        try:
            os.remove(temporario)
        except OSError:
            pass


def dividir(caminho, ponto, log=None, progresso=None, ctx=None):
    """Divide um corte em duas partes e devolve os novos caminhos."""
    if not caminho or not os.path.exists(caminho):
        raise ErroEdicao("O corte selecionado não existe mais.")
    ponto = _numero(ponto, "divisão")
    duracao = runtime.duracao(caminho)
    if ponto <= 0 or ponto >= duracao:
        raise ErroEdicao("A divisão precisa ficar dentro da duração do corte.")

    raiz, extensao = os.path.splitext(caminho)
    primeira = raiz + "_a" + extensao
    segunda = raiz + "_b" + extensao
    temporarios = [primeira + ".tmp.mp4", segunda + ".tmp.mp4"]
    try:
        runtime.rodar_ffmpeg(
            ["-i", caminho, "-t", f"{ponto:.3f}"] + _QUALIDADE + [temporarios[0]],
            ctx=ctx, progresso=progresso, duracao_total=ponto,
            rotulo="Dividindo o corte (parte 1)", faixa=(0, 50))
        runtime.rodar_ffmpeg(
            ["-ss", f"{ponto:.3f}", "-i", caminho,
             "-t", f"{duracao - ponto:.3f}"] + _QUALIDADE + [temporarios[1]],
            ctx=ctx, progresso=progresso, duracao_total=duracao - ponto,
            rotulo="Dividindo o corte (parte 2)", faixa=(50, 100))
        for temporario in temporarios:
            if not os.path.exists(temporario):
                raise ErroEdicao("O FFmpeg não criou uma das partes do corte.")
        os.replace(temporarios[0], primeira)
        os.replace(temporarios[1], segunda)
        os.remove(caminho)
        if log:
            log(f"Corte dividido em {os.path.basename(primeira)} e "
                f"{os.path.basename(segunda)}", "ok")
        return [primeira, segunda]
    finally:
        for temporario in temporarios:
            try:
                os.remove(temporario)
            except OSError:
                pass
