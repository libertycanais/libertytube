"""
backend/http.py
------------------------------------------------------------
Cliente HTTP mínimo (só urllib, nada pra instalar) usado por todo o
backend.

Nunca levanta exceção de rede: devolve sempre uma `Resposta`, com
`status`, `dados` e `erro` já traduzido pro português. Quem chama decide
o que fazer — foi assim que a 2.48 acabou "liberando por engano" quando
uma consulta falhava.
"""

import json
import urllib.error
import urllib.parse
import urllib.request

from . import config, errors


class Resposta:
    __slots__ = ("status", "dados", "erro")

    def __init__(self, status, dados=None, erro=""):
        self.status = status
        self.dados = dados
        self.erro = erro

    @property
    def ok(self):
        return 200 <= self.status < 300

    @property
    def offline(self):
        """True quando nem chegou no servidor (sem internet, DNS, etc)."""
        return self.status == 0

    def __repr__(self):
        return f"<Resposta {self.status} erro={self.erro!r}>"


def _cabecalhos(token=None, extras=None):
    h = {
        "apikey": config.ANON_KEY,
        "Accept": "application/json",
        "Content-Type": "application/json",
        "User-Agent": "LibertyTube",
    }
    if token:
        h["Authorization"] = f"Bearer {token}"
    if extras:
        h.update(extras)
    return h


def _executar(req, timeout):
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            corpo = resp.read().decode("utf-8")
            dados = json.loads(corpo) if corpo.strip() else {}
            return Resposta(resp.getcode(), dados)
    except urllib.error.HTTPError as e:
        try:
            corpo = e.read().decode("utf-8")
            dados = json.loads(corpo) if corpo.strip() else {}
        except Exception:
            dados = {}
        bruto = (dados.get("error_description") or dados.get("msg")
                 or dados.get("message") or dados.get("error") or "")
        return Resposta(e.code, dados, errors.traduzir(bruto, e.code))
    except urllib.error.URLError:
        return Resposta(0, None, errors.SEM_INTERNET)
    except Exception as e:  # noqa: BLE001
        return Resposta(0, None, errors.traduzir(str(e), 0))


def get(url, token=None, params=None, timeout=None):
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers=_cabecalhos(token), method="GET")
    return _executar(req, timeout or config.TIMEOUT)


def post(url, corpo=None, token=None, timeout=None, extras=None):
    dados = json.dumps(corpo or {}).encode("utf-8")
    req = urllib.request.Request(url, data=dados,
                                 headers=_cabecalhos(token, extras), method="POST")
    return _executar(req, timeout or config.TIMEOUT)


def put(url, corpo=None, token=None, timeout=None):
    dados = json.dumps(corpo or {}).encode("utf-8")
    req = urllib.request.Request(url, data=dados,
                                 headers=_cabecalhos(token), method="PUT")
    return _executar(req, timeout or config.TIMEOUT)


def tabela(nome, token=None, filtros=None, select="*", ordem=None, timeout=None):
    """Consulta uma tabela via PostgREST.

    filtros: {"ativo": "eq.true", "user_id": f"eq.{uid}"}
    """
    params = dict(filtros or {})
    params["select"] = select
    if ordem:
        params["order"] = ordem
    return get(f"{config.base_rest()}/{nome}", token=token,
               params=params, timeout=timeout)
