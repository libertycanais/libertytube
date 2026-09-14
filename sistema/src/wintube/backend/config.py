"""
backend/config.py
------------------------------------------------------------
Endereço do servidor e nomes das tabelas.

Dá pra trocar tudo isso SEM mexer no código: crie um arquivo
    `backend.json` na pasta de configuração do LibertyTube
    (Windows: %LOCALAPPDATA%\\LibertyTube\\backend.json) com, por exemplo:

    {
      "url": "https://xxxx.supabase.co",
      "anon_key": "eyJ...",
      "cache_horas": 12
    }

Se `url` e `anon_key` estiverem vazios, o app permanece bloqueado até o
backend ser configurado. Não existe modo demo no build de produção.
"""

import os
import json

from ..core import paths

# ── Projeto Supabase ─────────────────────────────────────────────────
# Configure your own LibertyTube Supabase project here or in backend.json.
# The original product credentials must never be reused by this app.
URL = ""
ANON_KEY = ""

# ── Tabelas ──────────────────────────────────────────────────────────
TABELA_PERFIS = "perfis_usuario"
TABELA_AULAS = "aulas"
TABELA_BONUS = "bonus"
TABELA_COMO_USAR = "como_usar"
TABELA_VIP = "material_exclusivo"
TABELA_CONFIG = "config_app"

# ── Prazos ───────────────────────────────────────────────────────────
# de quantos em quantos dias o cliente é obrigado a digitar email e senha
# de novo. Serve pra duas coisas: saber que a conta continua em uso e,
# em caso de reembolso, cortar o acesso — basta desativar o perfil que no
# próximo login o app não abre mais.
MAX_DIAS_SESSAO = 15
# quanto tempo a sessão local vale antes de revalidar online
CACHE_HORAS = 12
# quantos dias o app funciona sem internet nenhuma antes de pedir login
MAX_DIAS_OFFLINE = 5
# se a checagem de perfil falhar (RLS, servidor fora), por quantos dias
# ainda confiamos no último "conta ativa" conhecido
GRACA_PERFIL_DIAS = 3
# timeout de rede (segundos)
TIMEOUT = 12

SENHA_DEMO = "demo1234"
SENHA_MINIMA = 8


def _aplicar_override():
    """Lê backend.json, se existir, e sobrescreve o que estiver lá."""
    arq = os.path.join(paths.CONFIG_DIR, "backend.json")
    if not os.path.exists(arq):
        return
    try:
        with open(arq, "r", encoding="utf-8-sig") as f:
            dados = json.load(f)
    except Exception:
        return
    mapa = {
        "url": "URL", "anon_key": "ANON_KEY",
        "cache_horas": "CACHE_HORAS", "max_dias_offline": "MAX_DIAS_OFFLINE",
        "max_dias_sessao": "MAX_DIAS_SESSAO",
        "graca_perfil_dias": "GRACA_PERFIL_DIAS", "timeout": "TIMEOUT",
        "tabela_perfis": "TABELA_PERFIS", "tabela_aulas": "TABELA_AULAS",
        "tabela_bonus": "TABELA_BONUS", "tabela_como_usar": "TABELA_COMO_USAR",
        "tabela_vip": "TABELA_VIP", "tabela_config": "TABELA_CONFIG",
    }
    globais = globals()
    for chave, nome in mapa.items():
        if chave in dados and dados[chave] not in (None, ""):
            globais[nome] = dados[chave]


_aplicar_override()


def configurado():
    """True quando existe servidor de verdade (não é modo demo)."""
    return bool((URL or "").strip()) and bool((ANON_KEY or "").strip())


def base_rest():
    return f"{URL.rstrip('/')}/rest/v1"


def base_auth():
    return f"{URL.rstrip('/')}/auth/v1"
