"""
backend/content.py
------------------------------------------------------------
Conteúdo que vem do servidor: Aulas, Como Usar, Bônus, Material VIP e
as configurações do app (link do suporte, link do grupo).

Duas mudanças importantes em relação à 2.48:

  * As consultas usam o TOKEN DO USUÁRIO, não a chave anônima embutida
    no programa. Com a chave anônima, qualquer pessoa que abrisse o
    arquivo do app conseguia baixar as aulas sem ter comprado.

  * O acesso ao Material VIP é decidido pelo id que está dentro do
    token assinado. Antes vinha do arquivo local de sessão, que o
    usuário podia editar pra liberar sozinho.

Só `config_app` continua aceitando a chave anônima: a tela de login
precisa do link do suporte antes de existir usuário logado.
"""

import re
import time

from . import auth, config, http

# cache em memória: evita refazer a consulta a cada clique no menu
_CACHE = {}
_TTL = 300  # 5 minutos


def _do_cache(chave):
    item = _CACHE.get(chave)
    if item and (time.time() - item[0]) < _TTL:
        return item[1]
    return None


def _guardar(chave, valor):
    _CACHE[chave] = (time.time(), valor)
    return valor


def limpar_cache():
    _CACHE.clear()


# ── Normalização ─────────────────────────────────────────────────────
def _normalizar(linha):
    """Deixa todo item com os mesmos campos, venha da tabela que vier."""
    return {
        "id": linha.get("id"),
        "titulo": linha.get("titulo") or "Sem título",
        "descricao": linha.get("descricao") or "",
        "link": linha.get("link_url") or linha.get("video_url") or "",
        "icone": linha.get("icone") or "",
        "modulo": linha.get("modulo") or "",
        "duracao": linha.get("duracao") or "",
        "ordem": linha.get("ordem") or 0,
    }


def _buscar(tabela, ordem="ordem.asc", demo=None):
    cache = _do_cache(tabela)
    if cache is not None:
        return cache

    if not config.configurado():
        return _guardar(tabela, {"ok": True, "motivo": "modo demo",
                                 "itens": [_normalizar(x) for x in (demo or [])]})

    token = auth.token_valido()
    if not token:
        return {"ok": False, "motivo": "Faça login pra ver este conteúdo.", "itens": []}

    resp = http.tabela(tabela, token=token, filtros={"ativo": "eq.true"}, ordem=ordem)
    if not resp.ok:
        return {"ok": False, "motivo": resp.erro or "Não consegui carregar agora.",
                "itens": []}

    itens = [_normalizar(x) for x in (resp.dados or []) if isinstance(x, dict)]
    return _guardar(tabela, {"ok": True, "motivo": "", "itens": itens})


# ── Seções ───────────────────────────────────────────────────────────
def aulas():
    demo = [
        {"id": 1, "titulo": "Bem-vindo ao LibertyTube", "modulo": "Começando",
         "descricao": "Visão geral do app e do que dá pra fazer.",
         "video_url": "", "duracao": "5 min", "ordem": 1},
        {"id": 2, "titulo": "Sua primeira montagem", "modulo": "Começando",
         "descricao": "Passo a passo do primeiro vídeo, do link ao arquivo pronto.",
         "video_url": "", "duracao": "12 min", "ordem": 2},
        {"id": 3, "titulo": "Conectando a IA", "modulo": "Avançado",
         "descricao": "Como pegar a chave do Gemini e gerar roteiros sozinho.",
         "video_url": "", "duracao": "8 min", "ordem": 3},
    ]
    return _buscar(config.TABELA_AULAS, ordem="modulo.asc,ordem.asc", demo=demo)


def como_usar():
    demo = [
        {"id": 1, "titulo": "Baixando suas primeiras cenas", "icone": "📥",
         "descricao": "Como colar o link e baixar automaticamente.", "ordem": 1},
        {"id": 2, "titulo": "Gerando o roteiro com IA", "icone": "🤖",
         "descricao": "Conectando o Gemini e criando roteiros.", "ordem": 2},
        {"id": 3, "titulo": "Montagem e trilha", "icone": "🎬",
         "descricao": "Como finalizar seu vídeo com música.", "ordem": 3},
    ]
    return _buscar(config.TABELA_COMO_USAR, demo=demo)


def bonus():
    demo = [
        {"id": 1, "titulo": "Guia de Monetização em 7 Dias", "icone": "📘",
         "descricao": "PDF passo a passo pra monetizar seu canal.", "ordem": 1},
        {"id": 2, "titulo": "Modelos de Thumbs e Capas", "icone": "🎨",
         "descricao": "Pacote de templates prontos pra usar.", "ordem": 2},
    ]
    return _buscar(config.TABELA_BONUS, demo=demo)


def material_vip():
    demo = [
        {"id": 1, "titulo": "Pack de Vídeos 4K — Natureza", "icone": "🎬",
         "descricao": "50+ clipes em Ultra HD prontos pra usar.", "ordem": 1},
    ]
    return _buscar(config.TABELA_VIP, demo=demo)


def tem_acesso_vip():
    """True só quando o servidor confirma `material_vip = true` para o
    usuário do token. Qualquer dúvida = bloqueado."""
    if not config.configurado():
        return False

    token = auth.token_valido()
    if not token:
        return False

    from . import session
    uid = auth.user_id(session.carregar())
    if not uid:
        return False

    resp = http.tabela(config.TABELA_PERFIS, token=token,
                       filtros={"user_id": f"eq.{uid}"}, select="material_vip")
    if not resp.ok or not isinstance(resp.dados, list) or not resp.dados:
        return False
    return bool(resp.dados[0].get("material_vip"))


# ── Configurações do app (links de suporte, grupo…) ──────────────────
def config_app(chave, padrao=None):
    """Lê uma chave da tabela `config_app`.

    Precisa funcionar ANTES do login (a tela de login mostra o botão de
    suporte), então aqui a chave anônima é aceita — mas só pra esta
    tabela, que não tem conteúdo de cliente.
    """
    cache = _do_cache(f"cfg:{chave}")
    if cache is not None:
        return cache

    if not config.configurado():
        demos = {
            "whatsapp_suporte": "",
            "whatsapp_grupo": "",
        }
        return demos.get(chave, padrao)

    token = auth.token_valido() or config.ANON_KEY
    resp = http.tabela(config.TABELA_CONFIG, token=token,
                       filtros={"chave": f"eq.{chave}"}, select="valor")
    if not resp.ok or not isinstance(resp.dados, list) or not resp.dados:
        return padrao
    return _guardar(f"cfg:{chave}", resp.dados[0].get("valor", padrao))


# ── YouTube ──────────────────────────────────────────────────────────
_PADROES_YT = (
    r"youtu\.be/([A-Za-z0-9_-]{11})",
    r"youtube\.com/watch\?v=([A-Za-z0-9_-]{11})",
    r"youtube\.com/embed/([A-Za-z0-9_-]{11})",
    r"youtube\.com/shorts/([A-Za-z0-9_-]{11})",
    r"youtube\.com/live/([A-Za-z0-9_-]{11})",
)


def id_youtube(url):
    if not url or not isinstance(url, str):
        return None
    for p in _PADROES_YT:
        m = re.search(p, url)
        if m:
            return m.group(1)
    return None


def thumbnail_youtube(url):
    vid = id_youtube(url)
    return f"https://img.youtube.com/vi/{vid}/hqdefault.jpg" if vid else None


def info_youtube(url):
    """Título e canal via oEmbed (público, não precisa de chave)."""
    vid = id_youtube(url)
    if not vid:
        return None
    resp = http.get("https://www.youtube.com/oembed",
                    params={"url": f"https://www.youtube.com/watch?v={vid}",
                            "format": "json"}, timeout=8)
    if not resp.ok or not isinstance(resp.dados, dict):
        return None
    return {"titulo": resp.dados.get("title", ""),
            "canal": resp.dados.get("author_name", ""),
            "thumb": f"https://img.youtube.com/vi/{vid}/hqdefault.jpg"}
