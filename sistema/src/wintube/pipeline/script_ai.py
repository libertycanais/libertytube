"""
pipeline/script_ai.py
------------------------------------------------------------
A parte de IA de texto: gerar o roteiro e conversar com o assistente.

Usa a API do Google Gemini direto por urllib (nada pra instalar). A
chave fica nas preferências do usuário, não no código.

Chave grátis: https://aistudio.google.com/apikey (sem cartão).
"""

import json
import os
import urllib.error
import urllib.request

from ..core import paths, settings

BASE = "https://generativelanguage.googleapis.com/v1beta"
MODELOS_RESERVA = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-2.5-flash-lite"]

SISTEMA_ASSISTENTE = (
    "Você é o assistente do LibertyTube, um app que cria vídeos automáticos pra "
    "YouTube, TikTok, Reels e Shorts. Você ajuda o usuário (que geralmente NÃO "
    "é técnico) a: melhorar e reescrever legendas, criar e ajustar prompts pra "
    "IA, ter ideias de vídeo e títulos chamativos, e escolher quais cortes "
    "ficam melhores. Responda em português do Brasil, curto, prático e "
    "amigável. Vá direto ao ponto e dê exemplos prontos pra usar."
)


class ErroIA(Exception):
    pass


# ── Chave e modelo ───────────────────────────────────────────────────
def chave():
    return (settings.get("gemini_key", "") or "").strip()


def definir_chave(valor):
    return settings.set("gemini_key", (valor or "").strip())


def modelo():
    return settings.get("gemini_modelo", "gemini-2.5-flash")


def definir_modelo(valor):
    return settings.set("gemini_modelo", valor or "gemini-2.5-flash")


def conectado():
    return bool(chave())


# ── HTTP ─────────────────────────────────────────────────────────────
def _tratar_http(e):
    try:
        dados = json.loads(e.read().decode("utf-8"))
        msg = dados.get("error", {}).get("message", str(e))
    except Exception:
        msg = str(e)

    if e.code in (400, 403) and ("API key" in msg or "API_KEY" in msg):
        raise ErroIA("A chave do Gemini foi recusada.\n\n"
                     "Pegue uma nova em aistudio.google.com/apikey "
                     "(ela começa com AIza).")
    if e.code == 429:
        raise ErroIA("Você atingiu o limite gratuito do Gemini por agora.\n"
                     "Espere alguns minutos e tente de novo.")
    if e.code == 404:
        raise ErroIA(f"Esse modelo não está disponível na sua conta.\n\n{msg}")
    raise ErroIA(f"O Gemini recusou (erro {e.code}):\n\n{msg}")


def _get(url, timeout=30):
    try:
        with urllib.request.urlopen(urllib.request.Request(url), timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        _tratar_http(e)
    except urllib.error.URLError as e:
        raise ErroIA(f"Sem conexão com o Google.\n\n{e.reason}")


def _post(url, corpo, timeout=600):
    dados = json.dumps(corpo).encode("utf-8")
    req = urllib.request.Request(url, data=dados,
                                 headers={"Content-Type": "application/json"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        _tratar_http(e)
    except urllib.error.URLError as e:
        raise ErroIA(f"Sem conexão com o Google.\n\n{e.reason}")


def _texto_da_resposta(dados):
    try:
        return (dados["candidates"][0]["content"]["parts"][0]["text"] or "").strip()
    except (KeyError, IndexError, TypeError):
        if (dados or {}).get("promptFeedback", {}).get("blockReason"):
            raise ErroIA("O Gemini bloqueou o conteúdo por segurança. "
                         "Tente reformular ou trocar de modelo.")
        raise ErroIA(f"Resposta inesperada do Gemini:\n\n{str(dados)[:300]}")


# ── Modelos ──────────────────────────────────────────────────────────
def listar_modelos(chave_teste=None):
    k = (chave_teste or chave()).strip()
    if not k:
        raise ErroIA("Cole a chave do Gemini primeiro.")
    dados = _get(f"{BASE}/models?key={k}")
    nomes = []
    for m in (dados or {}).get("models", []):
        if "generateContent" not in m.get("supportedGenerationMethods", []):
            continue
        nome = m.get("name", "").replace("models/", "")
        if not nome.startswith("gemini"):
            continue
        if any(x in nome for x in ("vision", "image", "tts", "embedding", "aqa", "learnlm")):
            continue
        nomes.append(nome)
    nomes.sort(reverse=True)
    return nomes or MODELOS_RESERVA


def testar_chave(k):
    """Devolve (ok, mensagem, modelos)."""
    try:
        modelos = listar_modelos(k)
        return True, f"Chave funcionando! {len(modelos)} modelo(s) disponíveis.", modelos
    except ErroIA as e:
        return False, str(e), []


# ── Prompts ──────────────────────────────────────────────────────────
def ler_prompt(nome="timesmap"):
    caminho = paths.prompt(f"{nome}.txt")
    if not os.path.exists(caminho):
        return ""
    try:
        with open(caminho, encoding="utf-8-sig") as f:
            return f.read()
    except Exception:
        return ""


def salvar_prompt(nome, texto):
    try:
        os.makedirs(paths.PROMPTS_DIR, exist_ok=True)
        with open(paths.prompt(f"{nome}.txt"), "w", encoding="utf-8") as f:
            f.write(texto or "")
        return True
    except Exception:
        return False


# ── Roteiro ──────────────────────────────────────────────────────────
def gerar_roteiro(transcricao, prompt=None, log=None, progresso=None, ctx=None):
    """Manda a transcrição pro Gemini e devolve o roteiro com timestamps."""
    if not chave():
        raise ErroIA("Conecte a IA primeiro (Configurações → Conectar IA). "
                     "A chave do Gemini é grátis.")
    if not (transcricao or "").strip():
        raise ErroIA("A transcrição está vazia.\n\n"
                     "Quase sempre isso quer dizer que as cenas baixaram sem áudio.")

    if progresso:
        progresso("Pedindo o roteiro pro Gemini…", 30)

    prompt = prompt or ler_prompt("timesmap")
    corpo = {"contents": [{"parts": [{
        "text": f"{prompt}\n\n===== TRANSCRIÇÃO =====\n{transcricao}"}]}]}
    dados = _post(f"{BASE}/models/{modelo()}:generateContent?key={chave()}", corpo)
    texto = _texto_da_resposta(dados)

    if not texto:
        raise ErroIA("O Gemini devolveu uma resposta vazia. Tente de novo.")
    if progresso:
        progresso("Roteiro pronto!", 100)
    return texto


# ── Assistente (chat) ────────────────────────────────────────────────
def conversar(mensagem, historico=None, contexto_extra=""):
    """Conversa livre. `historico` é uma lista de
    {"autor": "user"|"ia", "texto": ...}."""
    if not chave():
        raise ErroIA("Conecte a IA primeiro. A chave do Gemini é grátis e "
                     "leva 1 minuto — tem um passo a passo aqui na tela.")

    intro = SISTEMA_ASSISTENTE
    if contexto_extra:
        intro += f"\n\nContexto do projeto atual:\n{contexto_extra}"

    conteudo = [
        {"role": "user", "parts": [{"text": intro}]},
        {"role": "model", "parts": [{"text": "Beleza! Pode mandar, tô aqui "
                                             "pra ajudar com seu vídeo."}]},
    ]
    for msg in (historico or []):
        papel = "user" if msg.get("autor") == "user" else "model"
        conteudo.append({"role": papel, "parts": [{"text": msg.get("texto", "")}]})
    conteudo.append({"role": "user", "parts": [{"text": mensagem}]})

    dados = _post(f"{BASE}/models/{modelo()}:generateContent?key={chave()}",
                  {"contents": conteudo}, timeout=120)
    return _texto_da_resposta(dados)
