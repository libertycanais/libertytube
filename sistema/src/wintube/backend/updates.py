"""
backend/updates.py
------------------------------------------------------------
Atualização automática: você sobe um arquivo no seu site e todo mundo
recebe a correção sem reinstalar nada.

Como funciona
    1. Baixa o versao.json do seu domínio
    2. Compara o sha256 de cada arquivo com o que está no PC
    3. Baixa só o que mudou, confere o hash de novo
    4. Faz backup, troca os arquivos e avisa pra reiniciar

Segurança (isto executa código no PC do cliente, então é sério):
    - só HTTPS (http só em localhost, pra você testar)
    - confere o sha256 de cada arquivo ANTES de instalar
    - só troca arquivos listados no versao.json
    - nunca escreve fora da pasta do app (bloqueia "..", caminho
      absoluto, drive e extensões que não sejam .py/.txt/.png/.ico)
    - se qualquer passo falhar, desfaz tudo

Formato do versao.json:

    {
      "versao": "2.6.1",
      "base_url": "https://libertytube.com.br/app/1.0.0",
      "notas": "Corrige o travamento na montagem",
      "arquivos": {
        "wintube/ui/screens/login.py": {"sha256": "abc123..."}
      }
    }
"""

import hashlib
import os
import shutil
import sys
import tempfile
import urllib.error
import urllib.request

from ..core import paths
from ..version import VERSAO, URL_ATUALIZACAO, maior_que

TEMPO_CHECAGEM = 8      # segundos — não pode atrasar a abertura do app
TEMPO_DOWNLOAD = 120    # segundos por arquivo
EXTENSOES_OK = (".py", ".txt", ".png", ".ico", ".json")


class ErroAtualizacao(Exception):
    pass


def _url_configurada():
    """Dá pra apontar pra outro servidor criando `atualizacao.txt` na
    pasta de configuração — útil pra testar antes de publicar."""
    arq = os.path.join(paths.CONFIG_DIR, "atualizacao.txt")
    if os.path.exists(arq):
        try:
            with open(arq, "r", encoding="utf-8-sig") as f:
                url = f.read().strip().strip('"').strip("'")
            if url:
                return url
        except Exception:
            pass
    return URL_ATUALIZACAO


def _url_confiavel(url):
    u = (url or "").lower()
    if u.startswith("https://"):
        return True
    return u.startswith(("http://127.0.0.1", "http://localhost"))


def _nome_seguro(nome):
    """O servidor só pode gravar dentro da pasta do app."""
    if not nome or nome.strip() != nome:
        return False
    normalizado = nome.replace("\\", "/")
    if normalizado.startswith("/") or ".." in normalizado.split("/"):
        return False
    if os.path.isabs(nome) or ":" in nome:
        return False
    return normalizado.endswith(EXTENSOES_OK)


def _baixar(url, timeout):
    if not _url_confiavel(url):
        raise ErroAtualizacao(f"Recusado: a atualização precisa ser HTTPS. Veio: {url}")
    req = urllib.request.Request(url, headers={"User-Agent": f"LibertyTube/{VERSAO}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _sha256_arquivo(caminho):
    h = hashlib.sha256()
    with open(caminho, "rb") as f:
        for bloco in iter(lambda: f.read(65536), b""):
            h.update(bloco)
    return h.hexdigest()


def _versao_maior(a, b):
    """True se a > b (2.6.10 > 2.6.9, e a 2.48 antiga nunca é "mais nova"
    que a 2.6 — veja version.maior_que)."""
    return maior_que(a, b)


def checar():
    """Devolve o dicionário do versao.json se existir versão mais nova,
    senão None. Nunca levanta exceção — sem internet o app abre normal."""
    import json
    try:
        dados = json.loads(_baixar(_url_configurada(), TEMPO_CHECAGEM).decode("utf-8"))
    except Exception:
        return None
    if not isinstance(dados, dict) or not dados.get("arquivos"):
        return None
    if not _versao_maior(dados.get("versao", "0"), VERSAO):
        return None
    return dados


def pendentes(dados):
    """Só o que realmente mudou neste computador."""
    base = (dados.get("base_url") or "").rstrip("/") + "/"
    lista = []
    for nome, info in (dados.get("arquivos") or {}).items():
        if not _nome_seguro(nome):
            raise ErroAtualizacao(f"Nome de arquivo recusado: {nome!r}")
        local = os.path.join(paths.APP_DIR, nome)
        if os.path.exists(local) and _sha256_arquivo(local) == info.get("sha256"):
            continue
        lista.append((nome, base + nome, info.get("sha256")))
    return lista


def aplicar(dados, progresso=None):
    """Baixa tudo pra uma pasta temporária, confere os hashes e só então
    troca. Qualquer falha no meio desfaz o que já trocou."""
    fila = pendentes(dados)
    if not fila:
        return 0

    temp = tempfile.mkdtemp(prefix="libertytube_upd_")
    backup = tempfile.mkdtemp(prefix="libertytube_bkp_")
    try:
        for i, (nome, url, sha) in enumerate(fila, 1):
            if progresso:
                progresso(f"Baixando {nome}…", int(i / len(fila) * 70))
            conteudo = _baixar(url, TEMPO_DOWNLOAD)
            real = hashlib.sha256(conteudo).hexdigest()
            if sha and real != sha:
                raise ErroAtualizacao(
                    f"O arquivo {nome} chegou adulterado ou corrompido.")
            destino = os.path.join(temp, nome.replace("/", os.sep))
            os.makedirs(os.path.dirname(destino), exist_ok=True)
            with open(destino, "wb") as f:
                f.write(conteudo)

        if progresso:
            progresso("Guardando cópia de segurança…", 80)
        for nome, _u, _s in fila:
            atual = os.path.join(paths.APP_DIR, nome.replace("/", os.sep))
            if os.path.exists(atual):
                copia = os.path.join(backup, nome.replace("/", os.sep))
                os.makedirs(os.path.dirname(copia), exist_ok=True)
                shutil.copy2(atual, copia)

        if progresso:
            progresso("Instalando…", 90)
        trocados = []
        try:
            for nome, _u, _s in fila:
                origem = os.path.join(temp, nome.replace("/", os.sep))
                destino = os.path.join(paths.APP_DIR, nome.replace("/", os.sep))
                os.makedirs(os.path.dirname(destino), exist_ok=True)
                shutil.copy2(origem, destino)
                trocados.append(nome)
        except Exception as e:
            for nome in trocados:
                copia = os.path.join(backup, nome.replace("/", os.sep))
                if os.path.exists(copia):
                    shutil.copy2(copia, os.path.join(paths.APP_DIR,
                                                     nome.replace("/", os.sep)))
            raise ErroAtualizacao(f"Falha ao instalar — nada foi alterado: {e}")

        if progresso:
            progresso("Pronto!", 100)
        return len(fila)
    finally:
        shutil.rmtree(temp, ignore_errors=True)
        shutil.rmtree(backup, ignore_errors=True)


def reiniciar():
    """Fecha e abre o LibertyTube de novo, já com o código novo."""
    try:
        script = os.path.join(paths.APP_DIR, "wintube.py")
        os.execl(sys.executable, sys.executable, script)
    except Exception:
        os._exit(0)
