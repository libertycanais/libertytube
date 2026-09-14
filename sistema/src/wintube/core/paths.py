"""
core/paths.py
------------------------------------------------------------
Onde cada coisa mora no disco.

Três pastas, com papéis bem separados (na 2.48 isso era tudo misturado
na pasta do programa):

    APP_DIR      código do LibertyTube (somente leitura)
    ASSETS_DIR   identidade visual, letterbox, prompts, NOVIDADES.txt
    CONFIG_DIR   sessão, preferências e cache do usuário
                 Windows: %LOCALAPPDATA%\\LibertyTube
                 macOS:   ~/Library/Application Support/LibertyTube
                 Linux:   ~/.config/libertytube
    WORK_DIR     projetos do usuário (vídeos, cortes, montagens)
                 padrão: ~/Documents/LibertyTube

Nada é gravado dentro da pasta do programa — isso quebrava quando o app
ficava em "Program Files" e era a causa do bug do BOM na 2.4x.
"""

import os
import sys
import platform

# ── 1. Pasta do programa ─────────────────────────────────────────────
if getattr(sys, "frozen", False):
    # empacotado (PyInstaller)
    APP_DIR = os.path.dirname(sys.executable)
    _RES_DIR = getattr(sys, "_MEIPASS", APP_DIR)
else:
    # src/wintube/core/paths.py  ->  src/
    APP_DIR = os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__))))
    _RES_DIR = APP_DIR


def _achar_assets():
    """assets/ pode estar ao lado de src/ (repositório) ou dentro do
    pacote empacotado. Procura nos dois lugares."""
    candidatos = [
        os.path.join(os.path.dirname(APP_DIR), "assets"),  # repo: raiz/assets
        os.path.join(APP_DIR, "assets"),                   # empacotado
        os.path.join(_RES_DIR, "assets"),
    ]
    for c in candidatos:
        if os.path.isdir(c):
            return c
    return candidatos[0]


ASSETS_DIR = _achar_assets()
PROMPTS_DIR = os.path.join(ASSETS_DIR, "prompts")


def asset(nome):
    """Caminho de um arquivo em assets/ (identidade visual, letterbox…)."""
    return os.path.join(ASSETS_DIR, nome)


def prompt(nome):
    """Caminho de um prompt em assets/prompts/ (timesmap.txt…)."""
    return os.path.join(PROMPTS_DIR, nome)


# ── 2. Pasta de configuração (sessão, preferências) ──────────────────
def _pasta_config():
    sistema = platform.system()
    if sistema == "Windows":
        base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
        return os.path.join(base, "LibertyTube")
    if sistema == "Darwin":
        return os.path.expanduser("~/Library/Application Support/LibertyTube")
    return os.path.expanduser("~/.config/libertytube")


CONFIG_DIR = _pasta_config()
os.makedirs(CONFIG_DIR, exist_ok=True)

ARQ_PREFERENCIAS = os.path.join(CONFIG_DIR, "preferencias.json")
ARQ_SESSAO = os.path.join(CONFIG_DIR, "sessao.json")
ARQ_LOG = os.path.join(CONFIG_DIR, "libertytube.log")


# ── 3. Pasta de trabalho (projetos do usuário) ───────────────────────
def _limpar_caminho(texto):
    """Tira BOM, aspas e espaços de um caminho lido de arquivo.

    O instalador do Windows escreve UTF-8 com BOM; sem isso o caminho
    virava "﻿C:\\Users\\..." e deixava de ser absoluto.
    """
    if not texto:
        return ""
    texto = texto.replace("﻿", "").replace("​", "")
    return texto.strip().strip('"').strip("'").strip()


def _padrao_work_dir():
    return os.path.join(os.path.expanduser("~"), "Documents", "LibertyTube")


def work_dir():
    """Pasta onde ficam os projetos. O usuário pode trocar nas
    Configurações (fica salvo em preferencias.json)."""
    from . import settings  # import tardio: settings usa paths
    escolhido = _limpar_caminho(settings.get("pasta_projetos", ""))
    if escolhido and os.path.isabs(escolhido):
        try:
            os.makedirs(escolhido, exist_ok=True)
            return escolhido
        except Exception:
            pass
    padrao = _padrao_work_dir()
    os.makedirs(padrao, exist_ok=True)
    return padrao


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


def discos_do_computador():
    """Discos onde dá pra guardar vídeo, com o espaço livre de cada um.

    Serve pro cliente mandar os vídeos pro HD grande em vez do SSD do
    Windows, que vive cheio. Devolve [{unidade, raiz, livre_gb}, …].
    """
    encontrados = []
    if platform.system() == "Windows":
        import string
        import ctypes
        try:
            mascara = ctypes.windll.kernel32.GetLogicalDrives()
        except Exception:
            mascara = 0
        for i, letra in enumerate(string.ascii_uppercase):
            if not (mascara >> i) & 1:
                continue
            raiz = f"{letra}:\\"
            try:
                # 3 = disco fixo (pendrive e rede ficam de fora)
                if ctypes.windll.kernel32.GetDriveTypeW(raiz) != 3:
                    continue
            except Exception:
                continue
            livre = espaco_livre_gb(raiz)
            if livre is None:
                continue
            encontrados.append({"unidade": f"{letra}:", "raiz": raiz,
                                "livre_gb": livre})
    else:
        for raiz in ("/", os.path.expanduser("~")):
            livre = espaco_livre_gb(raiz)
            if livre is not None:
                encontrados.append({"unidade": raiz, "raiz": raiz,
                                    "livre_gb": livre})
    return encontrados


def definir_work_dir(caminho):
    """Troca a pasta de projetos. Devolve o caminho aplicado."""
    from . import settings
    caminho = _limpar_caminho(caminho)
    if caminho and os.path.isabs(caminho):
        os.makedirs(caminho, exist_ok=True)
        settings.set("pasta_projetos", caminho)
    return work_dir()


def abrir_no_explorador(caminho):
    """Abre uma pasta no Explorer / Finder / gerenciador do Linux."""
    import subprocess
    if not caminho or not os.path.exists(caminho):
        return False
    try:
        if sys.platform == "win32":
            os.startfile(caminho)  # noqa: S606
        elif sys.platform == "darwin":
            subprocess.Popen(["open", caminho])
        else:
            subprocess.Popen(["xdg-open", caminho])
        return True
    except Exception:
        return False
