"""
ui/screens/whats_new.py
------------------------------------------------------------
Popup "o que há de novo": mostra só as versões que o usuário ainda não
viu, lendo o assets/NOVIDADES.txt.
"""

import os
import re

from ...core import paths, settings
from ...version import VERSAO, maior_que as _versao_maior


def ler_novidades(desde=None):
    """Lista de (versão, texto) mais nova que `desde`."""
    arquivo = paths.asset("NOVIDADES.txt")
    if not os.path.exists(arquivo):
        return []
    try:
        with open(arquivo, encoding="utf-8-sig") as f:
            conteudo = f.read()
    except Exception:
        return []

    blocos = []
    atual, linhas = None, []
    for linha in conteudo.splitlines():
        cabecalho = re.match(r"^##\s*([\d.]+)\s*$", linha.strip())
        if cabecalho:
            if atual:
                blocos.append((atual, "\n".join(linhas).strip()))
            atual, linhas = cabecalho.group(1), []
        elif atual:
            linhas.append(linha)
    if atual:
        blocos.append((atual, "\n".join(linhas).strip()))

    if desde:
        blocos = [b for b in blocos if _versao_maior(b[0], desde)]
    return blocos


def mostrar_se_novo(app):
    vista = settings.get("ultima_versao_novidades", "")
    novidades = ler_novidades(desde=vista or None)

    if not vista:
        # primeira vez: mostra só a versão atual, não o histórico inteiro
        novidades = [n for n in novidades if not _versao_maior(n[0], VERSAO)][:1]

    if not novidades:
        settings.set("ultima_versao_novidades", VERSAO)
        return

    mostrar(app, novidades)


def mostrar(app, novidades):
    """A janela em si mora em ui/dialogs.py — é a mesma usada pelo aviso
    de atualização, pra tudo que aparece por cima do app ter a mesma cara."""
    from .. import dialogs

    return dialogs.novidades(
        app, novidades,
        ao_fechar=lambda: settings.set("ultima_versao_novidades", VERSAO))
