"""Ordem editavel dos cortes de um projeto."""

import json
import os
import re

from . import projects


def _natural(nome):
    return [int(p) if p.isdigit() else p.lower()
            for p in re.split(r"(\d+)", nome)]


def _padrao(projeto):
    extensoes = (".mp4", ".mkv", ".mov", ".avi", ".webm")
    try:
        nomes = [n for n in os.listdir(projeto.cenas_cortadas)
                 if n.lower().endswith(extensoes)]
    except OSError:
        return []
    return sorted(nomes, key=_natural)


def listar(projeto=None):
    projeto = projeto or projects.atual()
    existentes = set(_padrao(projeto))
    salvo = []
    ocultos = set()
    try:
        with open(projeto.arquivo_timeline, encoding="utf-8-sig") as arquivo:
            dados = json.load(arquivo)
        if isinstance(dados, list):
            salvo = [os.path.basename(str(nome)) for nome in dados]
        elif isinstance(dados, dict):
            salvo = [os.path.basename(str(nome))
                     for nome in (dados.get("ordem") or [])]
            ocultos = {os.path.basename(str(nome))
                       for nome in (dados.get("ocultos") or [])}
    except Exception:
        pass

    ordem = [nome for nome in salvo if nome in existentes]
    ordem.extend(nome for nome in _padrao(projeto)
                 if nome not in ordem and nome not in ocultos)
    return ordem


def _ocultos(projeto):
    try:
        with open(projeto.arquivo_timeline, encoding="utf-8-sig") as arquivo:
            dados = json.load(arquivo)
        if isinstance(dados, dict):
            return {os.path.basename(str(nome))
                    for nome in (dados.get("ocultos") or [])}
    except Exception:
        pass
    return set()


def salvar(nomes, projeto=None, ocultos=None):
    projeto = projeto or projects.atual()
    validos = set(_padrao(projeto))
    ordem = [os.path.basename(str(nome)) for nome in (nomes or [])]
    ordem = [nome for i, nome in enumerate(ordem)
             if nome in validos and nome not in ordem[:i]]
    escondidos = sorted({os.path.basename(str(nome)) for nome in (ocultos or [])}
                        & validos)
    temporario = projeto.arquivo_timeline + ".tmp"
    os.makedirs(projeto.cortes, exist_ok=True)
    with open(temporario, "w", encoding="utf-8") as arquivo:
        json.dump({"ordem": ordem, "ocultos": escondidos}, arquivo,
                  indent=2, ensure_ascii=False)
    os.replace(temporario, projeto.arquivo_timeline)
    return ordem


def resetar(projeto=None):
    projeto = projeto or projects.atual()
    return salvar(_padrao(projeto), projeto, [])


def mover(indice, delta, projeto=None):
    projeto = projeto or projects.atual()
    ordem = listar(projeto)
    novo = indice + delta
    if not (0 <= indice < len(ordem) and 0 <= novo < len(ordem)):
        return ordem
    ordem[indice], ordem[novo] = ordem[novo], ordem[indice]
    return salvar(ordem, projeto, _ocultos(projeto))


def remover(indice, projeto=None):
    projeto = projeto or projects.atual()
    ordem = listar(projeto)
    ocultos = _ocultos(projeto)
    if 0 <= indice < len(ordem):
        removido = ordem.pop(indice)
        ocultos.add(removido)
    return salvar(ordem, projeto, ocultos)


def substituir(indice, novos, projeto=None):
    """Troca um item da timeline por um ou mais arquivos novos."""
    projeto = projeto or projects.atual()
    ordem = listar(projeto)
    if not (0 <= indice < len(ordem)):
        return ordem
    ocultos = _ocultos(projeto)
    ocultos.add(ordem[indice])
    novos_nomes = [os.path.basename(str(nome)) for nome in (novos or [])]
    ordem = [nome for i, nome in enumerate(ordem)
             if i == indice or nome not in novos_nomes]
    ordem[indice:indice + 1] = novos_nomes
    return salvar(ordem, projeto, ocultos)
