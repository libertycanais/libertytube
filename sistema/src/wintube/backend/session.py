"""
backend/session.py
------------------------------------------------------------
A sessão local (tokens do usuário) guardada no computador.

O que mudou em relação à 2.48:

  * O arquivo era JSON puro — dava pra abrir no Bloco de Notas e ler o
    refresh_token (que vale 60 dias). Agora o conteúdo é embaralhado com
    uma chave derivada do próprio computador.
  * O `dispositivo_id` era salvo mas nunca conferido, então copiar a
    pasta pra outro PC funcionava. Agora, se o id não bate, a sessão é
    descartada e o app pede login.
  * No Windows/macOS/Linux o arquivo é criado só com permissão do dono.

Isso não é criptografia forte (a chave sai do próprio PC), mas resolve
os dois casos reais: cópia de sessão entre máquinas e leitura casual do
token por quem mexe no computador.
"""

import os
import json
import time
import base64
import hashlib
import platform
import uuid

from ..core import paths

ARQUIVO = paths.ARQ_SESSAO
_MARCA = b"WT26"  # identifica o formato embaralhado


# ── Identidade do computador ─────────────────────────────────────────
def dispositivo_id():
    """Impressão digital simples deste computador: nome da máquina,
    sistema e endereço MAC. Igual em todo boot, diferente em outro PC."""
    try:
        mac = uuid.getnode()
    except Exception:
        mac = 0
    fonte = f"{platform.node()}|{platform.system()}|{mac}".encode("utf-8")
    return hashlib.sha256(fonte).hexdigest()[:24]


def _chave():
    return hashlib.sha256(("libertytube-1.0|" + dispositivo_id()).encode("utf-8")).digest()


def _embaralhar(texto):
    dados = texto.encode("utf-8")
    chave = _chave()
    misturado = bytes(b ^ chave[i % len(chave)] for i, b in enumerate(dados))
    return base64.b64encode(_MARCA + misturado).decode("ascii")


def _desembaralhar(conteudo):
    bruto = base64.b64decode(conteudo.encode("ascii"))
    if not bruto.startswith(_MARCA):
        raise ValueError("formato desconhecido")
    bruto = bruto[len(_MARCA):]
    chave = _chave()
    return bytes(b ^ chave[i % len(chave)] for i, b in enumerate(bruto)).decode("utf-8")


def _proteger_arquivo(caminho):
    """Só o dono do usuário lê o arquivo."""
    try:
        if os.name == "nt":
            import subprocess
            usuario = os.environ.get("USERNAME", "")
            if usuario:
                subprocess.run(["icacls", caminho, "/inheritance:r",
                                "/grant:r", f"{usuario}:F"],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.chmod(caminho, 0o600)
    except Exception:
        pass


# ── Ler / gravar ─────────────────────────────────────────────────────
def carregar():
    """Devolve a sessão salva, ou None se não existir / for de outro PC."""
    if not os.path.exists(ARQUIVO):
        return None
    try:
        with open(ARQUIVO, "r", encoding="utf-8") as f:
            conteudo = f.read().strip()
        if not conteudo:
            return None
        if conteudo.startswith("{"):
            dados = json.loads(conteudo)  # sessão da 2.48, ainda legível
        else:
            dados = json.loads(_desembaralhar(conteudo))
    except Exception:
        return None

    if not isinstance(dados, dict):
        return None

    # sessão copiada de outro computador não vale
    if dados.get("dispositivo_id") and dados["dispositivo_id"] != dispositivo_id():
        remover()
        return None
    return dados


def salvar(sessao, marcar_verificacao=True):
    sessao = dict(sessao or {})
    agora = int(time.time())
    sessao["dispositivo_id"] = dispositivo_id()
    sessao.setdefault("criada_em", agora)
    if marcar_verificacao:
        sessao["verificada_em"] = agora
    try:
        os.makedirs(os.path.dirname(ARQUIVO), exist_ok=True)
        tmp = ARQUIVO + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(_embaralhar(json.dumps(sessao, ensure_ascii=False)))
        os.replace(tmp, ARQUIVO)
        _proteger_arquivo(ARQUIVO)
    except Exception:
        pass
    return sessao


def remover():
    try:
        if os.path.exists(ARQUIVO):
            os.remove(ARQUIVO)
        return True
    except Exception:
        return False


# ── Ajudinhas ────────────────────────────────────────────────────────
def horas_desde(ts):
    return (time.time() - (ts or 0)) / 3600.0


def dias_desde(ts):
    return (time.time() - (ts or 0)) / 86400.0
