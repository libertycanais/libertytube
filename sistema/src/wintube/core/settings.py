"""
core/settings.py
------------------------------------------------------------
Preferências locais do usuário, num único JSON.

Na 2.48 cada preferência era um arquivo solto (tema.txt, formato_ativo.txt,
enquadramento.txt, projeto_ativo.txt, config.json, pasta_projetos.txt) e
cada um era lido de um jeito. Agora é um arquivo só, com cache em memória
e escrita atômica.

Chaves usadas hoje:
    tema              "escuro" | "claro"
    pasta_projetos    caminho absoluto (vazio = Documentos/LibertyTube)
    projeto_ativo     nome da pasta do projeto
    formato           "9:16" | "1:1" | "16:9"
    enquadramento     "centro" | "esquerda" | "direita" | "inteiro" | "seguir"
    plataforma        "tiktok" | "reels" | "shorts" | "feed" | "youtube" | "facebook"
    gemini_key        chave da API do Gemini
    gemini_modelo     ex: "gemini-2.5-flash"
    email_lembrado    email preenchido na tela de login
    ultima_versao_novidades  versão cujo popup o usuário já viu
    etapas_auto       lista das etapas ligadas nas chavinhas da tela inicial
    legenda_estilo    estilo escolhido na biblioteca de legendas
    legenda_tamanho   pequena | media | grande | gigante
"""

import os
import json
import threading

from . import paths

_LOCK = threading.RLock()
_CACHE = None

PADROES = {
    "tema": "escuro",
    "pasta_projetos": "",
    "projeto_ativo": "",
    "formato": "9:16",
    "enquadramento": "centro",
    "plataforma": "tiktok",
    "gemini_key": "",
    "gemini_modelo": "gemini-2.5-flash",
    "email_lembrado": "",
    "lembrar_email": True,
    "ultima_versao_novidades": "",
    "letterbox": True,
    "usar_broll": False,
    "legenda_estilo": "classica",
    "legenda_tamanho": "media",
    "estilo_edicao": "viral",
    "movimento_edicao": "zoom_suave",
    # etapas ligadas por padrão no "modo automático" da tela inicial
    "etapas_auto": ["baixar", "transcrever", "roteiro"],
}


def _carregar():
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    dados = dict(PADROES)
    try:
        if os.path.exists(paths.ARQ_PREFERENCIAS):
            with open(paths.ARQ_PREFERENCIAS, "r", encoding="utf-8-sig") as f:
                salvos = json.load(f)
            if isinstance(salvos, dict):
                dados.update(salvos)
    except Exception:
        pass  # arquivo corrompido: volta pros padrões em vez de travar o app
    _CACHE = dados
    return _CACHE


def _gravar():
    """Escrita atômica: grava num .tmp e só então substitui o arquivo.
    Assim um desligamento no meio da escrita não corrompe as preferências."""
    dados = _carregar()
    tmp = paths.ARQ_PREFERENCIAS + ".tmp"
    try:
        os.makedirs(os.path.dirname(paths.ARQ_PREFERENCIAS), exist_ok=True)
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(dados, f, indent=2, ensure_ascii=False)
        os.replace(tmp, paths.ARQ_PREFERENCIAS)
        return True
    except Exception:
        try:
            os.remove(tmp)
        except Exception:
            pass
        return False


def get(chave, padrao=None):
    with _LOCK:
        dados = _carregar()
        if chave in dados and dados[chave] not in (None, ""):
            return dados[chave]
        if chave in dados:
            return dados[chave]
        return padrao if padrao is not None else PADROES.get(chave)


def set(chave, valor):  # noqa: A001 (nome curto de propósito)
    with _LOCK:
        _carregar()[chave] = valor
        _gravar()
        return valor


def update(novos):
    with _LOCK:
        _carregar().update(novos or {})
        _gravar()


def tudo():
    with _LOCK:
        return dict(_carregar())
