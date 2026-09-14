"""
pipeline/download.py
------------------------------------------------------------
Etapa 1 — baixa os vídeos (ou a playlist inteira) do YouTube.

Qualidade: pega o melhor disponível até 4K e junta vídeo+áudio em MP4.
Velocidade: baixa vários pedaços ao mesmo tempo.
"""

import os

from ..core import projects
from .base import (EXTENSOES_VIDEO, extrair_links, falta_espaco, formatar_mb,
                   normalizar, proximo_numero)


class ErroDownload(Exception):
    pass


_MSG_DISCO = ("O disco encheu no meio do download.\n\n"
              "Libere espaço no computador ou mande os vídeos pra outro "
              "disco em Configurações → Onde os vídeos são salvos.")


def _e_disco_cheio(erro):
    """O yt-dlp embrulha o erro do sistema, então sobra olhar o texto."""
    texto = str(erro).lower()
    return ("no space left" in texto or "espaço" in texto
            or "disk full" in texto or "errno 28" in texto
            or "error 112" in texto or "winerror 112" in texto)


def baixar(links=None, log=None, progresso=None, ctx=None):
    """Baixa os links no projeto ativo. Devolve quantas cenas existem
    na pasta depois do download."""
    log, progresso = normalizar(log, progresso)
    proj = projects.atual().criar_pastas()

    if links is None:
        if os.path.exists(proj.arquivo_links):
            with open(proj.arquivo_links, encoding="utf-8-sig") as f:
                links = extrair_links(f.read())
        else:
            links = []
    elif isinstance(links, str):
        links = extrair_links(links)

    if not links:
        raise ErroDownload("Cole pelo menos um link do YouTube antes de baixar.")

    # disco cheio é o motivo nº 1 de "não baixou": confere ANTES de gastar
    # o tempo do cliente e de espalhar arquivos pela metade
    sem_espaco = falta_espaco(proj.cenas_baixadas)
    if sem_espaco:
        raise ErroDownload(sem_espaco)

    try:
        import yt_dlp
    except ImportError:
        raise ErroDownload(
            "O componente de download (yt-dlp) não está instalado.\n"
            "Rode o instalador do LibertyTube de novo pra reparar.")

    # guarda os links do projeto pra próxima vez
    try:
        with open(proj.arquivo_links, "w", encoding="utf-8") as f:
            f.write("\n".join(links))
    except Exception:
        pass

    antes = len([f for f in os.listdir(proj.cenas_baixadas)
                 if f.lower().endswith(EXTENSOES_VIDEO)])
    log(f"{len(links)} link(s) na fila. Playlists são expandidas automaticamente.")

    estado = {"ultimo": "", "prontos": 0}

    def hook(d):
        if ctx is not None and ctx.abortado():
            raise ErroDownload("cancelado")
        if d.get("status") == "downloading":
            total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
            baixado = d.get("downloaded_bytes") or 0
            nome = os.path.basename(d.get("filename", ""))
            velocidade = d.get("speed") or 0
            # a velocidade e o "cena 2 de 5" são o que responde a pergunta
            # do cliente: "isso vai demorar?"
            extra = f" · {velocidade / 1048576:.1f} MB/s" if velocidade else ""
            fila = f"vídeo {estado['prontos'] + 1}: " if estado["prontos"] else ""
            if total:
                pct = int(baixado / total * 100)
                progresso(f"{fila}{nome} — {formatar_mb(baixado)} de "
                          f"{formatar_mb(total)}{extra}", pct)
            else:
                progresso(f"{fila}{nome} — {formatar_mb(baixado)} baixados{extra}",
                          None)
        elif d.get("status") == "finished":
            nome = os.path.basename(d.get("filename", ""))
            if nome != estado["ultimo"]:
                estado["ultimo"] = nome
                estado["prontos"] += 1
                log(f"✓ {nome}")
                progresso(f"{nome} baixado — juntando vídeo e áudio…", None)

    opcoes = {
        # melhor qualidade até 4K; cai pro que existir se não achar
        "format": ("bestvideo[height<=2160][ext=mp4]+bestaudio[ext=m4a]/"
                   "bestvideo[height<=2160]+bestaudio/"
                   "best[ext=mp4]/best"),
        "merge_output_format": "mp4",
        "outtmpl": os.path.join(proj.cenas_baixadas, "cena_%(autonumber)02d.%(ext)s"),
        "autonumber_start": proximo_numero(proj.cenas_baixadas),
        "ignoreerrors": True,          # uma cena falha, as outras continuam
        "noplaylist": False,           # playlist inteira
        "concurrent_fragment_downloads": 8,
        "retries": 5,
        "fragment_retries": 5,
        "socket_timeout": 30,
        "quiet": True,
        "no_warnings": True,
        "progress_hooks": [hook],
    }

    progresso("Preparando o download…", 2)
    try:
        with yt_dlp.YoutubeDL(opcoes) as ydl:
            ydl.download(links)
    except ErroDownload:
        raise
    except Exception as e:
        if ctx is not None and ctx.abortado():
            raise
        # o disco pode ter enchido DURANTE o download
        sem_espaco = falta_espaco(proj.cenas_baixadas)
        if sem_espaco or _e_disco_cheio(e):
            raise ErroDownload(sem_espaco or _MSG_DISCO)
        raise ErroDownload(
            "Não consegui baixar. Confira se o link está certo e se o vídeo "
            f"é público.\n\nDetalhe: {e}")

    depois = len([f for f in os.listdir(proj.cenas_baixadas)
                  if f.lower().endswith(EXTENSOES_VIDEO)])
    novas = max(0, depois - antes)
    if not depois:
        raise ErroDownload(falta_espaco(proj.cenas_baixadas) or
                           "Nenhuma cena foi baixada. Confira os links.")
    if not novas:
        # baixou zero mas já tinha cena na pasta: quase sempre é disco cheio
        sem_espaco = falta_espaco(proj.cenas_baixadas)
        if sem_espaco:
            raise ErroDownload(sem_espaco)
        if estado["prontos"] == 0:
            raise ErroDownload(
                "Nenhum dos links desta solicitação foi baixado. "
                "Confira se os vídeos são públicos e se os links estão corretos.")

    progresso(f"{novas} cena(s) baixada(s).", 100)
    log(f"{novas} cena(s) nova(s). Total no projeto: {depois}.", "ok")
    return depois
