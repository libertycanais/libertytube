"""
ui/screens/projects_screen.py
------------------------------------------------------------
Meus projetos — cada vídeo numa pasta separada, sem misturar cenas,
transcrição e montagem de vídeos diferentes.
"""

import tkinter as tk

from ...core import paths, projects
from ..theme import ESPACO, tema
from ..widgets import Botao, Cabecalho, Cartao, Chip, espaco


def montar(app, parent):
    ativo = projects.atual().nome
    lista = projects.listar()

    cabecalho = Cabecalho(parent, "Meus projetos",
                          "Um projeto por vídeo. Tudo que você baixa, corta e "
                          "monta fica guardado dentro dele.")
    cabecalho.pack(fill="x", pady=(4, ESPACO["lg"]))

    Botao(cabecalho.acoes, "Novo projeto", lambda: _criar(app), icone="＋",
          altura=40).pack(side="right")

    if not lista:
        Cartao(parent, "Nenhum projeto ainda",
               "Clique em Novo projeto pra começar.").pack(fill="x")
        return

    grade = tk.Frame(parent, bg=tema.cor("fundo"))
    grade.pack(fill="x")

    for i, nome in enumerate(lista):
        _card(app, grade, nome, nome == ativo).grid(
            row=i // 3, column=i % 3, padx=(0, 12), pady=(0, 12), sticky="nsew")
    for c in range(3):
        grade.grid_columnconfigure(c, weight=1)

    espaco(parent, ESPACO["lg"])


def _card(app, parent, nome, ativo):
    dados = projects.resumo(nome)

    card = tk.Frame(parent, bg=tema.cor("card"), highlightthickness=1,
                    highlightbackground=tema.cor("primario") if ativo
                    else tema.cor("borda"))

    if ativo:
        tk.Frame(card, bg=tema.cor("primario"), height=3).pack(fill="x")

    corpo = tk.Frame(card, bg=tema.cor("card"))
    corpo.pack(fill="both", expand=True, padx=16, pady=14)

    topo = tk.Frame(corpo, bg=tema.cor("card"))
    topo.pack(fill="x")
    tk.Label(topo, text=nome.replace("_", " ")[:26],
             font=tema.fonte("subtitulo"), bg=tema.cor("card"),
             fg=tema.cor("texto"), anchor="w").pack(side="left")
    if ativo:
        Chip(topo, "ativo", cor=tema.cor("primario"),
             cor_texto="#FFFFFF").pack(side="right")

    etapas = tk.Frame(corpo, bg=tema.cor("card"))
    etapas.pack(fill="x", pady=(10, 0))

    marcadores = [
        (f"{dados['cenas']} cena(s)", dados["cenas"] > 0),
        ("transcrição", dados["tem_transcricao"]),
        ("roteiro", dados["tem_roteiro"]),
        (f"{dados['cortes']} corte(s)", dados["cortes"] > 0),
        (f"{dados['montagens']} montagem(ns)", dados["montagens"] > 0),
    ]
    for texto, feito in marcadores:
        tk.Label(etapas, text=f"{'✓' if feito else '·'}  {texto}",
                 font=tema.fonte("micro"), bg=tema.cor("card"),
                 fg=tema.cor("sucesso") if feito else tema.cor("muted"),
                 anchor="w").pack(fill="x")

    acoes = tk.Frame(corpo, bg=tema.cor("card"))
    acoes.pack(fill="x", pady=(14, 0))

    if not ativo:
        Botao(acoes, "Usar este", lambda: _trocar(app, nome), altura=34,
              fonte=tema.fonte("micro")).pack(side="left")
    Botao(acoes, "abrir pasta",
          lambda: paths.abrir_no_explorador(
              projects.Projeto(nome, f"{projects.pasta_projetos()}/{nome}").raiz),
          variante="fantasma", altura=34, fonte=tema.fonte("micro")
          ).pack(side="left", padx=(8, 0))
    Botao(acoes, "apagar", lambda: _apagar(app, nome), variante="fantasma",
          altura=34, fonte=tema.fonte("micro")).pack(side="right")

    return card


def _criar(app):
    from .. import dialogs

    nome = dialogs.perguntar_texto(
        app, "Novo projeto",
        rotulo="NOME DO PROJETO",
        placeholder="ex: video motivacional 01",
        subtitulo="Cada projeto tem as pastas dele, sem misturar vídeos",
        botao="Criar projeto", icone="📁")
    if not nome:
        return
    projeto = projects.criar(nome)
    app.log(f"Projeto criado: {projeto.nome}", "ok")
    app.aviso(f"Projeto “{projeto.nome}” criado e já ativo.", "sucesso")
    app.abrir_painel()


def _trocar(app, nome):
    projects.definir_ativo(nome)
    app.log(f"Projeto ativo: {nome}", "sistema")
    app.aviso(f"Agora você está no projeto “{nome}”.", "sucesso")
    app.abrir_painel()


def _apagar(app, nome):
    from .. import dialogs

    if not dialogs.confirmar(
            app, "Apagar projeto",
            f"Apagar o projeto “{nome}” e TUDO que está dentro dele "
            "(vídeos baixados, cortes e montagens)?\n\nIsso não tem volta.",
            sim="Apagar tudo", nao="Cancelar", icone="🗑", perigoso=True):
        return
    if projects.excluir(nome):
        app.log(f"Projeto apagado: {nome}", "aviso")
        app.abrir_painel()
    else:
        app.aviso("Não consegui apagar. Feche os vídeos abertos e tente de novo.",
                  "erro")
