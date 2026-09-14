"""
ui/screens/library.py
------------------------------------------------------------
As telas de conteúdo: Crie seu canal (aulas), Como usar, Bônus,
Material VIP e Networking.

Todas usam o mesmo desenho de cards — o que muda é a tabela do servidor
de onde vem o conteúdo. O carregamento é sempre em thread, com um
"carregando…" no lugar de travar a janela.
"""

import tkinter as tk

from ...backend import content
from ...core import tasks
from ..theme import ESPACO, tema
from ..widgets import Botao, Cabecalho, Cartao, Chip, espaco, rotulo


# ── telas ────────────────────────────────────────────────────────────
def montar_aulas(app, parent):
    _tela(app, parent, "Crie seu canal",
          "Aulas passo a passo pra criar, crescer e monetizar seu canal.",
          content.aulas, agrupar=True)


def montar_como_usar(app, parent):
    _tela(app, parent, "Como usar o app",
          "Tutoriais rápidos de cada etapa do LibertyTube.",
          content.como_usar)


def montar_bonus(app, parent):
    _tela(app, parent, "Bônus",
          "Tudo que vem junto com o LibertyTube. Clique pra abrir.",
          content.bonus)


def montar_vip(app, parent):
    Cabecalho(parent, "Material VIP",
              "Vídeos e imagens em Ultra HD prontos pra usar nos seus cortes."
              ).pack(fill="x", pady=(4, ESPACO["lg"]))

    carregando = rotulo(parent, "conferindo seu acesso…", "pequeno", "muted")
    carregando.pack(anchor="w")

    def conferido(liberado):
        carregando.destroy()
        if liberado:
            _carregar_cards(app, parent, content.material_vip)
        else:
            _bloqueado(app, parent)

    tasks.em_thread(content.tem_acesso_vip, ao_terminar=conferido, root=app.root)


def montar_networking(app, parent):
    Cabecalho(parent, "Networking",
              "A comunidade do LibertyTube: troque ideia, tire dúvidas e veja o "
              "que está funcionando pros outros."
              ).pack(fill="x", pady=(4, ESPACO["lg"]))

    cartao = Cartao(parent, "Grupo oficial no WhatsApp",
                    "Entre no grupo e fale com quem usa o LibertyTube todo dia.",
                    accent=tema.cor("whatsapp"))
    cartao.pack(fill="x")

    espera = rotulo(cartao.corpo, "buscando o link do grupo…", "pequeno", "muted")
    espera.configure(bg=tema.cor("card"))
    espera.pack(anchor="w", pady=(ESPACO["sm"], 0))

    def chegou(url):
        espera.destroy()
        if url and isinstance(url, str) and url.strip():
            Botao(cartao.corpo, "Entrar no grupo",
                  lambda: app.abrir_link(url.strip()),
                  variante="whatsapp", icone="✆", altura=46
                  ).pack(anchor="w", pady=(ESPACO["sm"], 0))
        else:
            rotulo(cartao.corpo,
                   "O link do grupo ainda não foi publicado. "
                   "Fale com o suporte pra receber o convite.",
                   "pequeno", "texto2").pack(anchor="w")

    tasks.em_thread(lambda: content.config_app("whatsapp_grupo"),
                    ao_terminar=chegou, root=app.root)

    espaco(parent, ESPACO["lg"])


# ── motor comum ──────────────────────────────────────────────────────
def _tela(app, parent, titulo, subtitulo, buscador, agrupar=False):
    Cabecalho(parent, titulo, subtitulo).pack(fill="x", pady=(4, ESPACO["lg"]))
    _carregar_cards(app, parent, buscador, agrupar)


def _carregar_cards(app, parent, buscador, agrupar=False):
    espera = rotulo(parent, "carregando…", "pequeno", "muted")
    espera.pack(anchor="w")

    def chegou(resposta):
        espera.destroy()
        if not resposta.get("ok"):
            Cartao(parent, "Não consegui carregar agora",
                   resposta.get("motivo", "Confira sua internet e tente de novo.")
                   ).pack(fill="x")
            Botao(parent, "Tentar de novo", app.recarregar,
                  variante="secundario", altura=38).pack(anchor="w",
                                                          pady=(ESPACO["md"], 0))
            return

        itens = resposta.get("itens") or []
        if not itens:
            Cartao(parent, "Nada publicado ainda",
                   "Assim que novos conteúdos forem liberados eles aparecem "
                   "aqui automaticamente.").pack(fill="x")
            return

        if agrupar:
            modulos = {}
            for item in itens:
                modulos.setdefault(item.get("modulo") or "Geral", []).append(item)
            for modulo, lista in modulos.items():
                _titulo_modulo(parent, modulo, len(lista))
                _grade(app, parent, lista)
        else:
            _grade(app, parent, itens)

        espaco(parent, ESPACO["lg"])

    tasks.em_thread(buscador, ao_terminar=chegou, root=app.root)


def _titulo_modulo(parent, nome, quantidade):
    linha = tk.Frame(parent, bg=tema.cor("fundo"))
    linha.pack(fill="x", pady=(ESPACO["md"], ESPACO["sm"]))
    tk.Frame(linha, bg=tema.cor("primario"), width=4, height=22).pack(side="left",
                                                                      padx=(0, 10))
    tk.Label(linha, text=nome, font=tema.fonte("subtitulo"),
             bg=tema.cor("fundo"), fg=tema.cor("texto")).pack(side="left")
    Chip(linha, f"{quantidade} item(ns)").pack(side="left", padx=(10, 0))


def _grade(app, parent, itens, colunas=3):
    grade = tk.Frame(parent, bg=tema.cor("fundo"))
    grade.pack(fill="x")
    for i, item in enumerate(itens):
        _card(app, grade, item).grid(row=i // colunas, column=i % colunas,
                                     padx=(0, 12), pady=(0, 12), sticky="nsew")
    for c in range(colunas):
        grade.grid_columnconfigure(c, weight=1)


def _card(app, parent, item):
    card = tk.Frame(parent, bg=tema.cor("card"), highlightthickness=1,
                    highlightbackground=tema.cor("borda"), cursor="hand2")

    corpo = tk.Frame(card, bg=tema.cor("card"))
    corpo.pack(fill="both", expand=True, padx=16, pady=14)

    topo = tk.Frame(corpo, bg=tema.cor("card"))
    topo.pack(fill="x")
    if item.get("icone"):
        tk.Label(topo, text=item["icone"], font=(tema.familia, 16),
                 bg=tema.cor("card")).pack(side="left", padx=(0, 8))
    tk.Label(topo, text=item["titulo"][:44], font=tema.fonte("corpo_forte"),
             bg=tema.cor("card"), fg=tema.cor("texto"), anchor="w",
             wraplength=240, justify="left").pack(side="left")

    if item.get("descricao"):
        tk.Label(corpo, text=item["descricao"], font=tema.fonte("pequeno"),
                 bg=tema.cor("card"), fg=tema.cor("texto2"), anchor="w",
                 justify="left", wraplength=280).pack(fill="x", pady=(8, 0))

    rodape = tk.Frame(corpo, bg=tema.cor("card"))
    rodape.pack(fill="x", pady=(12, 0))
    if item.get("duracao"):
        Chip(rodape, item["duracao"]).pack(side="left")
    tk.Label(rodape, text="abrir  →", font=tema.fonte("micro"),
             bg=tema.cor("card"), fg=tema.cor("primario")).pack(side="right")

    def abrir(_=None):
        if item.get("link"):
            app.abrir_link(item["link"])
        else:
            app.aviso("Este item ainda não tem link publicado.", "aviso")

    for widget in (card, corpo, topo, rodape):
        widget.bind("<Button-1>", abrir)
    card.bind("<Enter>", lambda e: card.configure(
        highlightbackground=tema.cor("primario")))
    card.bind("<Leave>", lambda e: card.configure(
        highlightbackground=tema.cor("borda")))
    return card


def _bloqueado(app, parent):
    cartao = Cartao(parent, "👑  Conteúdo exclusivo",
                    "O Material VIP é um pacote separado, com vídeos e "
                    "imagens em Ultra HD liberados pra quem adquiriu.",
                    accent=tema.cor("aviso"))
    cartao.pack(fill="x")

    rotulo(cartao.corpo,
           "Se você já comprou e ainda aparece bloqueado, fale com o suporte "
           "que a gente libera na hora.", "pequeno", "texto2"
           ).pack(anchor="w", pady=(ESPACO["sm"], 0))

    linha = tk.Frame(cartao.corpo, bg=tema.cor("card"))
    linha.pack(fill="x", pady=(ESPACO["md"], 0))

    def falar_com_suporte():
        def abrir(url):
            if url:
                app.abrir_link(url)
            else:
                app.aviso("Link de suporte não configurado.", "aviso")
        tasks.em_thread(lambda: content.config_app("whatsapp_suporte"),
                        ao_terminar=abrir, root=app.root)

    Botao(linha, "Quero o Material VIP", falar_com_suporte, icone="👑",
          altura=44).pack(side="left")
    Botao(linha, "Conferir de novo", app.recarregar, variante="secundario",
          altura=44).pack(side="left", padx=(10, 0))

    espaco(parent, ESPACO["lg"])
