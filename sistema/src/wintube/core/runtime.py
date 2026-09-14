"""
core/runtime.py
------------------------------------------------------------
Tudo que é "ambiente": FFmpeg, subprocess sem janela preta, saída
padrão no modo janela e consciência de DPI no Windows.

Também centraliza a execução do FFmpeg — antes cada módulo montava seu
próprio subprocess.run e o erro do FFmpeg sumia no DEVNULL.
"""

import os
import sys
import shutil
import subprocess

from . import paths

NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_STARTUPINFO = None


# ── FFmpeg ───────────────────────────────────────────────────────────
def registrar_ffmpeg():
    """Coloca as pastas onde o FFmpeg pode estar no começo do PATH do
    processo, pra yt-dlp/faster-whisper/ffmpeg acharem sem o usuário
    precisar mexer em variável de ambiente do sistema."""
    candidatos = [
        os.path.join(paths.CONFIG_DIR, "ffmpeg", "bin"),
        os.path.join(paths.CONFIG_DIR, "ffmpeg"),
        os.path.join(paths.APP_DIR, "ffmpeg", "bin"),
        os.path.join(paths.APP_DIR, "ffmpeg"),
        paths.APP_DIR,
    ]
    # o instalador antigo deixava o ffmpeg ao lado da pasta do app
    pai = os.path.dirname(paths.APP_DIR)
    try:
        for item in os.listdir(pai):
            if "ffmpeg" in item.lower():
                alvo = os.path.join(pai, item)
                if os.path.isdir(os.path.join(alvo, "bin")):
                    candidatos.append(os.path.join(alvo, "bin"))
                elif os.path.isdir(alvo):
                    candidatos.append(alvo)
    except Exception:
        pass

    existentes = [c for c in candidatos if os.path.isdir(c)]
    if existentes:
        os.environ["PATH"] = os.pathsep.join(existentes) + os.pathsep + os.environ.get("PATH", "")
    return existentes


def caminho_ffmpeg():
    return shutil.which("ffmpeg")


def ffmpeg_disponivel():
    return bool(shutil.which("ffmpeg")) and bool(shutil.which("ffprobe"))


# ── Subprocess sem janela preta ──────────────────────────────────────
def patch_subprocess():
    """No Windows, cada chamada de ffmpeg abriria uma janelinha preta.
    Aqui aplicamos CREATE_NO_WINDOW por padrão em todo subprocess."""
    global _STARTUPINFO
    if os.name != "nt":
        return

    _STARTUPINFO = subprocess.STARTUPINFO()
    _STARTUPINFO.dwFlags |= subprocess.STARTF_USESHOWWINDOW

    _run = subprocess.run
    _popen_init = subprocess.Popen.__init__

    def _defaults(kwargs):
        kwargs.setdefault("creationflags", NO_WINDOW)
        kwargs.setdefault("startupinfo", _STARTUPINFO)
        if kwargs.get("stdin") is None:
            kwargs["stdin"] = subprocess.DEVNULL
        return kwargs

    def run_patched(*args, **kwargs):
        return _run(*args, **_defaults(kwargs))

    def popen_patched(self, *args, **kwargs):
        return _popen_init(self, *args, **_defaults(kwargs))

    subprocess.run = run_patched
    subprocess.Popen.__init__ = popen_patched


def preparar_saida_padrao():
    """No modo janela (.exe sem console) sys.stdout é None e várias libs
    quebram ao imprimir. Coloca um destino silencioso no lugar."""
    class _Null:
        def write(self, *a, **k):
            pass

        def flush(self):
            pass

        def isatty(self):
            return False

    if sys.stdout is None:
        sys.stdout = _Null()
    if sys.stderr is None:
        sys.stderr = _Null()


def dpi_aware():
    """Sem isso o Windows escala a janela em telas com zoom 125/150% e
    ela pode sair maior que a tela do usuário."""
    if sys.platform != "win32":
        return
    try:
        from ctypes import windll
        try:
            windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def preparar():
    """Chamado uma vez no boot, antes de qualquer coisa."""
    preparar_saida_padrao()
    patch_subprocess()
    registrar_ffmpeg()


# ── Execução de FFmpeg / FFprobe ─────────────────────────────────────
class ErroFFmpeg(Exception):
    """Levantado quando o FFmpeg falha, já com o motivo legível."""


def _segundos_do_progresso(linha):
    """Lê o tempo já processado de uma linha do `-progress` do ffmpeg.

    Usamos `out_time=00:01:23.45` porque é o único campo sem ambiguidade:
    o `out_time_ms` do ffmpeg vem, na verdade, em microssegundos em boa
    parte das versões.
    """
    if not linha.startswith("out_time="):
        return None
    valor = linha.split("=", 1)[1].strip()
    if not valor or valor.startswith("N/A") or valor.startswith("-"):
        return None
    try:
        horas, minutos, segundos = valor.split(":")
        return int(horas) * 3600 + int(minutos) * 60 + float(segundos)
    except Exception:
        return None


def rodar_ffmpeg(args, ctx=None, checar=True, progresso=None,
                 duracao_total=None, rotulo="", faixa=None):
    """Executa o ffmpeg e devolve (codigo, stderr_texto).

    `ctx` é o contexto da tarefa (core.tasks.Contexto): serve pra
    registrar o processo e conseguir cancelar de verdade no meio.

    Progresso de verdade (o cliente vê a barra andando enquanto grava):
        progresso      função(texto, pct) — a mesma que as etapas recebem
        duracao_total  duração em segundos do que vai ser gravado
        rotulo         texto que aparece junto da porcentagem
        faixa          (inicio, fim) — em que pedaço da barra este ffmpeg
                       cabe, quando a etapa faz vários ffmpeg seguidos

    Sem `progresso` e `duracao_total` o comportamento é o mesmo de antes.
    """
    acompanhar = bool(progresso) and bool(duracao_total and duracao_total > 0)
    globais = ["-hide_banner", "-loglevel", "error", "-y"]
    if acompanhar:
        globais += ["-nostats", "-progress", "pipe:1"]

    cmd = ["ffmpeg"] + globais + list(args)
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE if acompanhar else subprocess.DEVNULL,
        stderr=subprocess.PIPE)
    if ctx is not None:
        ctx.registrar_processo(proc)

    if not acompanhar:
        _, err = proc.communicate()
        erro = (err or b"").decode("utf-8", "replace").strip()
        if checar and proc.returncode != 0:
            raise ErroFFmpeg(erro[-600:]
                             or f"ffmpeg terminou com código {proc.returncode}")
        return proc.returncode, erro

    # o stderr precisa ser lido em paralelo, senão o buffer enche e o
    # ffmpeg trava esperando alguém esvaziar
    pedacos = []
    import threading

    def drenar():
        try:
            for bloco in iter(lambda: proc.stderr.read(4096), b""):
                pedacos.append(bloco)
        except Exception:
            pass

    leitor = threading.Thread(target=drenar, daemon=True)
    leitor.start()

    inicio, fim = faixa or (0, 100)
    try:
        for bruta in iter(proc.stdout.readline, b""):
            segundos = _segundos_do_progresso(
                bruta.decode("utf-8", "replace").strip())
            if segundos is None:
                continue
            fracao = max(0.0, min(1.0, segundos / duracao_total))
            pct = inicio + (fim - inicio) * fracao
            faltam = max(0, duracao_total - segundos)
            texto = (f"{rotulo} — {segundos:.0f}s de {duracao_total:.0f}s de vídeo"
                     if rotulo else
                     f"{segundos:.0f}s de {duracao_total:.0f}s de vídeo")
            if faltam <= 0.5:
                texto = f"{rotulo} — finalizando o arquivo…" if rotulo \
                    else "finalizando o arquivo…"
            progresso(texto, int(pct))
    except Exception:
        pass
    finally:
        try:
            proc.stdout.close()
        except Exception:
            pass

    proc.wait()
    leitor.join(timeout=2)
    erro = b"".join(pedacos).decode("utf-8", "replace").strip()
    if checar and proc.returncode != 0:
        raise ErroFFmpeg(erro[-600:]
                         or f"ffmpeg terminou com código {proc.returncode}")
    return proc.returncode, erro


# duração já perguntada ao ffprobe: {(caminho, mtime, tamanho): segundos}.
# Cada chamada custa ~70 ms, e a mesma galeria era remontada a cada etapa
# que terminava — 40 perguntas repetidas sobre os MESMOS arquivos.
_DURACOES = {}


def duracao(caminho):
    """Duração de um vídeo/áudio em segundos (0.0 se não der pra ler).

    Guarda a resposta: a chave leva data e tamanho do arquivo, então
    arquivo trocado é perguntado de novo.
    """
    if not caminho or not os.path.exists(caminho):
        return 0.0
    try:
        info = os.stat(caminho)
        chave = (caminho, info.st_mtime, info.st_size)
    except OSError:
        chave = (caminho, 0, 0)
    if chave in _DURACOES:
        return _DURACOES[chave]
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", caminho],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        segundos = float((r.stdout or "0").strip() or 0)
    except Exception:
        return 0.0
    if len(_DURACOES) > 500:            # sessão longa não vira depósito
        _DURACOES.clear()
    _DURACOES[chave] = segundos
    return segundos


def resolucao(caminho):
    """(largura, altura) de um vídeo, ou (0, 0)."""
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height",
             "-of", "csv=s=x:p=0", caminho],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        w, h = (r.stdout or "0x0").strip().split("x")[:2]
        return int(w), int(h)
    except Exception:
        return 0, 0
