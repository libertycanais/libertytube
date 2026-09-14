"""
core/projects.py
------------------------------------------------------------
Sistema de projetos: cada vídeo é uma pasta separada dentro de
    <pasta de trabalho>/projetos/<nome do projeto>/
com as etapas do pipeline dentro dela:

    1_cenas/cenas_baixadas      vídeos baixados do YouTube
    2_transcricao               Transcricao.txt
    3_cortes                    roteiro.txt, cenas_cortadas/, cenas_broll/
    4_montagem                  montagem_final.mp4
    5_trilhas                   trilhas_baixadas/, sonorizado, legendado

Diferente da 2.48, aqui NÃO existem variáveis globais de pasta: quem
precisa de um caminho chama `projeto_atual().cortes` na hora. Era isso
que causava o bug de "baixou mas não achou" quando o projeto mudava.
"""

import os
import re

from . import paths, settings

# proporções suportadas (largura, altura)
FORMATOS = {
    "9:16": (1080, 1920),
    "1:1": (1080, 1080),
    "16:9": (1920, 1080),
}

# rede social -> formato de saída
PLATAFORMAS = {
    "tiktok": ("TikTok", "9:16"),
    "reels": ("Instagram Reels", "9:16"),
    "shorts": ("YouTube Shorts", "9:16"),
    "kwai": ("Kwai", "9:16"),
    "feed": ("Feed do Instagram", "1:1"),
    "youtube": ("YouTube", "16:9"),
    "facebook": ("Facebook", "16:9"),
}

ENQUADRAMENTOS = ("centro", "esquerda", "direita", "inteiro", "seguir")


class Projeto:
    """Os caminhos de um projeto. É só um objeto de caminhos — criar não
    escreve nada em disco enquanto você não chamar `criar_pastas()`."""

    def __init__(self, nome, raiz):
        self.nome = nome
        self.raiz = raiz

    # etapa 1
    @property
    def cenas(self):
        return os.path.join(self.raiz, "1_cenas")

    @property
    def cenas_baixadas(self):
        return os.path.join(self.cenas, "cenas_baixadas")

    @property
    def arquivo_links(self):
        return os.path.join(self.cenas, "links.txt")

    # etapa 2
    @property
    def transcricao(self):
        return os.path.join(self.raiz, "2_transcricao")

    @property
    def arquivo_transcricao(self):
        return os.path.join(self.transcricao, "Transcricao.txt")

    # etapa 3
    @property
    def cortes(self):
        return os.path.join(self.raiz, "3_cortes")

    @property
    def arquivo_roteiro(self):
        return os.path.join(self.cortes, "roteiro.txt")

    @property
    def arquivo_timeline(self):
        return os.path.join(self.cortes, "timeline.json")

    @property
    def cenas_cortadas(self):
        return os.path.join(self.cortes, "cenas_cortadas")

    @property
    def broll(self):
        return os.path.join(self.cortes, "cenas_broll")

    # etapa 4
    @property
    def montagem(self):
        return os.path.join(self.raiz, "4_montagem")

    @property
    def video_montado(self):
        return os.path.join(self.montagem, "montagem_final.mp4")

    # etapa 5
    @property
    def trilhas(self):
        return os.path.join(self.raiz, "5_trilhas")

    @property
    def trilhas_baixadas(self):
        return os.path.join(self.trilhas, "trilhas_baixadas")

    @property
    def arquivo_trilhas(self):
        return os.path.join(self.trilhas, "trilhas.txt")

    @property
    def video_sonorizado(self):
        return os.path.join(self.trilhas, "montagem_sonorizada.mp4")

    @property
    def video_legendado(self):
        return os.path.join(self.trilhas, "video_final_legendado.mp4")

    def todas_as_pastas(self):
        return (self.cenas, self.cenas_baixadas, self.transcricao, self.cortes,
                self.cenas_cortadas, self.broll, self.montagem, self.trilhas,
                self.trilhas_baixadas)

    def criar_pastas(self):
        for pasta in self.todas_as_pastas():
            os.makedirs(pasta, exist_ok=True)
        return self

    def video_final(self):
        """O vídeo mais "avançado" que existe: legendado > sonorizado >
        montado. É o que a etapa 5 usa como entrada."""
        for c in (self.video_legendado, self.video_sonorizado, self.video_montado):
            if os.path.exists(c):
                return c
        return None

    def video_base(self):
        """Vídeo sem legenda, usado como entrada para gerar a saída final."""
        for c in (self.video_sonorizado, self.video_montado):
            if os.path.exists(c):
                return c
        return None

    def __repr__(self):
        return f"<Projeto {self.nome!r}>"


# ── Lista / criação / troca ──────────────────────────────────────────
def pasta_projetos():
    p = os.path.join(paths.work_dir(), "projetos")
    os.makedirs(p, exist_ok=True)
    return p


def _sanitizar(nome):
    nome = (nome or "").strip()
    nome = re.sub(r"[^\w\s-]", "_", nome, flags=re.UNICODE)
    nome = re.sub(r"\s+", "_", nome).strip("_")
    return nome or "projeto"


def listar():
    base = pasta_projetos()
    try:
        return sorted(d for d in os.listdir(base)
                      if os.path.isdir(os.path.join(base, d)))
    except Exception:
        return []


def criar(nome):
    """Cria um projeto novo (sem sobrescrever outro com o mesmo nome) e
    já deixa ele ativo."""
    nome = _sanitizar(nome)
    base = pasta_projetos()
    final, i = nome, 2
    while os.path.isdir(os.path.join(base, final)):
        final = f"{nome}_{i}"
        i += 1
    proj = Projeto(final, os.path.join(base, final))
    proj.criar_pastas()
    definir_ativo(final)
    return proj


def definir_ativo(nome):
    nome = _sanitizar(nome)
    os.makedirs(os.path.join(pasta_projetos(), nome), exist_ok=True)
    settings.set("projeto_ativo", nome)
    return atual()


def atual():
    """Projeto ativo. Se não houver nenhum, cria "Meu primeiro projeto"."""
    nome = settings.get("projeto_ativo", "")
    base = pasta_projetos()
    if nome and os.path.isdir(os.path.join(base, nome)):
        return Projeto(nome, os.path.join(base, nome))
    existentes = listar()
    if existentes:
        settings.set("projeto_ativo", existentes[0])
        return Projeto(existentes[0], os.path.join(base, existentes[0]))
    return criar("Meu primeiro projeto")


def excluir(nome):
    """Apaga a pasta do projeto inteiro. Só devolve True se apagou."""
    import shutil
    alvo = os.path.join(pasta_projetos(), _sanitizar(nome))
    if not os.path.isdir(alvo):
        return False
    try:
        shutil.rmtree(alvo)
    except Exception:
        return False
    if settings.get("projeto_ativo") == nome:
        settings.set("projeto_ativo", "")
    return True


def resumo(nome):
    """Quantos arquivos cada etapa do projeto já tem — usado nos cards
    da tela Meus Projetos."""
    proj = Projeto(nome, os.path.join(pasta_projetos(), nome))

    def conta(pasta, exts):
        try:
            return len([f for f in os.listdir(pasta) if f.lower().endswith(exts)])
        except Exception:
            return 0

    videos = (".mp4", ".mkv", ".mov", ".avi", ".webm")
    return {
        "cenas": conta(proj.cenas_baixadas, videos),
        "cortes": conta(proj.cenas_cortadas, videos),
        "broll": conta(proj.broll, videos),
        "montagens": conta(proj.montagem, videos),
        "tem_transcricao": os.path.exists(proj.arquivo_transcricao),
        "tem_roteiro": os.path.exists(proj.arquivo_roteiro),
    }


# ── Formato / enquadramento ──────────────────────────────────────────
def formato():
    f = settings.get("formato", "9:16")
    return f if f in FORMATOS else "9:16"


def definir_formato(valor):
    return settings.set("formato", valor if valor in FORMATOS else "9:16")


def plataforma():
    p = settings.get("plataforma", "tiktok")
    return p if p in PLATAFORMAS else "tiktok"


def definir_plataforma(valor):
    """Escolher a rede social já ajusta o formato do vídeo."""
    if valor not in PLATAFORMAS:
        valor = "tiktok"
    settings.set("plataforma", valor)
    definir_formato(PLATAFORMAS[valor][1])
    return valor


def enquadramento():
    e = settings.get("enquadramento", "centro")
    return e if e in ENQUADRAMENTOS else "centro"


def definir_enquadramento(valor):
    return settings.set("enquadramento",
                        valor if valor in ENQUADRAMENTOS else "centro")


def filtro_escala(fmt=None, enq=None):
    """Filtro -vf do ffmpeg pra encaixar o vídeo no formato escolhido.

    "inteiro" põe o vídeo inteiro com barras pretas; os outros preenchem
    o quadro e cortam pela esquerda/centro/direita.
    """
    fmt = fmt or formato()
    enq = enq or enquadramento()
    largura, altura = FORMATOS.get(fmt, FORMATOS["9:16"])

    if enq == "inteiro":
        return (f"scale={largura}:{altura}:force_original_aspect_ratio=decrease,"
                f"pad={largura}:{altura}:(ow-iw)/2:(oh-ih)/2:color=black")

    base = f"scale={largura}:{altura}:force_original_aspect_ratio=increase"
    if enq == "esquerda":
        x = "0"
    elif enq == "direita":
        x = "(iw-ow)"
    else:
        x = "(iw-ow)/2"
    return f"{base},crop={largura}:{altura}:{x}:(ih-oh)/2"
