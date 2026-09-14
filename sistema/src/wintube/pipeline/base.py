"""
pipeline/base.py
------------------------------------------------------------
Coisinhas que todas as etapas usam.
"""

import os
import re

EXTENSOES_VIDEO = (".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm")
EXTENSOES_AUDIO = (".mp3", ".wav", ".m4a", ".aac", ".ogg")


def sem_log(texto, nivel="info"):
    pass


def sem_progresso(texto, pct=None):
    pass


def normalizar(log, progresso):
    return (log or sem_log), (progresso or sem_progresso)


def listar_videos(pasta):
    """Vídeos de uma pasta, em ordem natural (cena_2 antes de cena_10)."""
    if not os.path.isdir(pasta):
        return []
    arquivos = [f for f in os.listdir(pasta) if f.lower().endswith(EXTENSOES_VIDEO)]
    return sorted(arquivos, key=chave_natural)


def listar_audios(pasta):
    if not os.path.isdir(pasta):
        return []
    return sorted((f for f in os.listdir(pasta)
                   if f.lower().endswith(EXTENSOES_AUDIO)), key=chave_natural)


def chave_natural(nome):
    """Ordena cena_2 antes de cena_10 (ordem "humana")."""
    partes = re.split(r"(\d+)", nome)
    return [int(p) if p.isdigit() else p.lower() for p in partes]


def extrair_links(texto):
    """Pega todos os links de um texto colado, sem repetir."""
    achados = re.findall(r'https?://[^\s,;"\'<>\]\)]+', texto or "")
    limpos, vistos = [], set()
    for link in achados:
        link = link.rstrip('.,;:)]>')
        if link and link not in vistos:
            vistos.add(link)
            limpos.append(link)
    return limpos


def proximo_numero(pasta, prefixo="cena_"):
    """Próximo número livre pra não sobrescrever o que já foi baixado."""
    maior = 0
    if os.path.isdir(pasta):
        for arquivo in os.listdir(pasta):
            m = re.match(rf"{prefixo}(\d+)", arquivo)
            if m:
                maior = max(maior, int(m.group(1)))
    return maior + 1


def formatar_mb(bytes_):
    return f"{(bytes_ or 0) / 1048576:.0f} MB"


# quanto o LibertyTube precisa ter livre pra trabalhar sem sufoco
ESPACO_MINIMO_GB = 2.0


def espaco_livre_gb(pasta):
    """Quantos GB sobram no disco desta pasta (None se não der pra ler)."""
    import shutil
    alvo = pasta
    while alvo and not os.path.isdir(alvo):
        pai = os.path.dirname(alvo)
        if pai == alvo:
            return None
        alvo = pai
    try:
        return shutil.disk_usage(alvo).free / (1024 ** 3)
    except Exception:
        return None


def falta_espaco(pasta, minimo_gb=ESPACO_MINIMO_GB):
    """Mensagem pronta se o disco estiver cheio; None se estiver tudo bem.

    Existe porque disco cheio é o motivo mais comum de "não baixou" — e o
    erro que chegava no cliente era "confira se o link está certo", que
    manda ele procurar no lugar errado. O yt-dlp e o FFmpeg param no meio
    e deixam arquivos `.part` pela pasta.
    """
    livre = espaco_livre_gb(pasta)
    if livre is None or livre >= minimo_gb:
        return None
    unidade = os.path.splitdrive(os.path.abspath(pasta))[0] or "o disco"
    quanto = f"{livre * 1024:.0f} MB" if livre < 1 else f"{livre:.1f} GB"
    return (f"O disco {unidade} está sem espaço: sobrou só {quanto}, e o "
            f"LibertyTube precisa de pelo menos {minimo_gb:.0f} GB.\n\n"
            "Libere espaço no computador ou mande os vídeos pra outro "
            "disco em Configurações → Onde os vídeos são salvos.")
