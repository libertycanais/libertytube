"""Editor de video do projeto.

Esta primeira camada organiza os cortes e aplica um preset profissional de
transicoes, efeitos, formato e legenda antes da renderizacao final.
"""

import os
import tkinter as tk
from tkinter import simpledialog

from ...core import projects, runtime, settings, timeline
from ...pipeline import assembly, base, captions, clip_editor
from ..media import Galeria
from ..theme import ESPACO, tema
from ..widgets import Banner, Botao, Cabecalho, Cartao, Chave, Seletor, divisor, espaco, rotulo


ESTILOS = [
    ("viral", "Viral TikTok/Reels"),
    ("podcast", "Podcast profissional"),
    ("cinematico", "Cinematografico"),
]

MOVIMENTOS = [
    ("nenhum", "Sem movimento"),
    ("zoom_suave", "Zoom suave"),
    ("pan_suave", "Pan suave"),
]


def _cortes_do_projeto(projeto):
    return [os.path.join(projeto.cenas_cortadas, nome)
            for nome in timeline.listar(projeto)]


def montar(app, parent):
    projeto = app.projeto
    cortes = _cortes_do_projeto(projeto)

    Cabecalho(
        parent,
        "Editor de video",
        "Revise os cortes, escolha o estilo e gere o video completo com "
        "transicoes, efeitos e legenda.",
    ).pack(fill="x", pady=(4, ESPACO["lg"]))

    if not cortes:
        Banner(
            parent,
            "Este projeto ainda nao tem cortes para editar.",
            tipo="aviso",
            icone="!",
            acao=("Ir para cortar cenas ->", lambda: app.navegar("cortar")),
        ).pack(fill="x")
        return

    cartao_timeline = Cartao(
        parent,
        "Timeline do projeto",
        f"{len(cortes)} corte(s) prontos para a montagem.",
        accent=tema.cor("primario"),
    )
    cartao_timeline.pack(fill="x")

    rotulo(cartao_timeline.corpo,
           "A ordem abaixo sera usada na montagem final.",
           "pequeno", "texto2").pack(anchor="w", pady=(ESPACO["sm"], 8))

    trilho = tk.Frame(cartao_timeline.corpo, bg=tema.cor("input"),
                      highlightthickness=1,
                      highlightbackground=tema.cor("borda"))
    trilho.pack(fill="x", pady=(0, ESPACO["sm"]))

    for indice, caminho in enumerate(cortes, 1):
        indice_zero = indice - 1
        item = tk.Frame(trilho, bg=tema.cor("card"),
                        highlightthickness=1,
                        highlightbackground=tema.cor("borda"))
        item.pack(side="left", fill="y", padx=(8 if indice == 1 else 0, 0),
                  pady=8)
        tk.Label(item, text=f"{indice:02d}", font=tema.fonte("titulo"),
                 bg=tema.cor("card"), fg=tema.cor("primario")).pack(
                     padx=14, pady=(8, 2))
        tk.Label(item, text=os.path.basename(caminho),
                 font=tema.fonte("micro"), bg=tema.cor("card"),
                 fg=tema.cor("texto2"), width=18).pack(padx=8, pady=(0, 8))

        acoes = tk.Frame(item, bg=tema.cor("card"))
        acoes.pack(fill="x", padx=6, pady=(0, 7))
        Botao(acoes, "<", lambda i=indice_zero: _mover(app, i, -1),
              variante="fantasma", altura=26,
              fonte=tema.fonte("micro")).pack(side="left")
        Botao(acoes, ">", lambda i=indice_zero: _mover(app, i, 1),
              variante="fantasma", altura=26,
              fonte=tema.fonte("micro")).pack(side="left", padx=(4, 0))
        Botao(acoes, "tirar", lambda i=indice_zero: _remover(app, i),
              variante="fantasma", altura=26,
              fonte=tema.fonte("micro")).pack(side="right")
        Botao(acoes, "aparar", lambda i=indice_zero, c=caminho:
              _aparar(app, i, c),
              variante="fantasma", altura=26,
              fonte=tema.fonte("micro")).pack(side="right", padx=(0, 4))
        Botao(acoes, "dividir", lambda i=indice_zero, c=caminho:
              _dividir(app, i, c), variante="fantasma", altura=26,
              fonte=tema.fonte("micro")).pack(side="right", padx=(0, 4))

    divisor(cartao_timeline.corpo, pady=ESPACO["sm"])
    Botao(cartao_timeline.corpo, "Restaurar ordem dos arquivos",
          lambda: _restaurar(app), variante="fantasma", altura=34,
          fonte=tema.fonte("micro")).pack(anchor="w", pady=(0, 8))
    Botao(cartao_timeline.corpo, "Abrir pre-visualizacao dos cortes",
          lambda: _abrir_cortes(app, cortes), variante="secundario",
          altura=40).pack(anchor="w")

    espaco(parent, ESPACO["md"])

    cartao_estilo = Cartao(
        parent,
        "Estilo profissional",
        "O preset controla transicoes, efeitos visuais e o estilo da legenda.",
        accent=tema.cor("primario"),
    )
    cartao_estilo.pack(fill="x")

    estilo = settings.get("estilo_edicao", "viral")
    Seletor(cartao_estilo.corpo, ESTILOS, valor=estilo,
            ao_mudar=lambda valor: settings.set("estilo_edicao", valor),
            colunas=3).pack(anchor="w", pady=(ESPACO["sm"], 0))

    rotulo(cartao_estilo.corpo, "Movimento de camera", "pequeno_forte").pack(
        anchor="w", pady=(ESPACO["md"], 4))
    Seletor(cartao_estilo.corpo, MOVIMENTOS,
            valor=settings.get("movimento_edicao", "zoom_suave"),
            ao_mudar=lambda valor: settings.set("movimento_edicao", valor),
            colunas=3).pack(anchor="w")

    rotulo(cartao_estilo.corpo,
           "Escolha o estilo antes de gerar o video final.",
           "micro", "muted").pack(anchor="w", pady=(6, 0))

    espaco(parent, ESPACO["md"])

    cartao_opcoes = Cartao(parent, "Opcoes de montagem",
                           "Ajustes aplicados antes da legenda final.")
    cartao_opcoes.pack(fill="x")

    usar_broll = Chave(
        cartao_opcoes.corpo,
        "Intercalar B-Rolls",
        "Usa os B-Rolls existentes entre os cortes.",
        valor=bool(settings.get("usar_broll", False)) and bool(base.listar_videos(projeto.broll)),
        ao_mudar=lambda valor: settings.set("usar_broll", valor),
    )
    usar_broll.pack(fill="x", pady=(ESPACO["sm"], 4))
    if not base.listar_videos(projeto.broll):
        usar_broll.bloquear("Gere B-Rolls no passo Cortar cenas primeiro.")

    usar_letterbox = Chave(
        cartao_opcoes.corpo,
        "Faixas pretas cinematograficas",
        "Usadas apenas no formato horizontal 16:9.",
        valor=bool(settings.get("letterbox", True)),
        ao_mudar=lambda valor: settings.set("letterbox", valor),
    )
    usar_letterbox.pack(fill="x")

    espaco(parent, ESPACO["md"])

    cartao_render = Cartao(parent, "Renderizacao final",
                           "A legenda sera sincronizada com a fala e o "
                           "resultado abrira no player do LibertyTube.",
                           accent=tema.cor("sucesso"))
    cartao_render.pack(fill="x")

    def renderizar():
        estilo_atual = settings.get("estilo_edicao", "viral")
        legenda_por_estilo = {
            "viral": "amarela",
            "podcast": "classica",
            "cinematico": "minimalista",
        }

        def trabalho(log, progresso, ctx):
            montado = assembly.montar(
                usar_broll=usar_broll.ligada(),
                usar_letterbox=usar_letterbox.ligada(),
                estilo=estilo_atual,
                movimento=settings.get("movimento_edicao", "zoom_suave"),
                log=log, progresso=progresso, ctx=ctx)
            return captions.aplicar(
                video=montado,
                estilo_legenda=legenda_por_estilo.get(estilo_atual, "classica"),
                tamanho=settings.get("legenda_tamanho", "media"),
                usar_legenda=True,
                log=log, progresso=progresso, ctx=ctx)

        app.rodar(
            trabalho,
            nome="Gerando video profissional",
            recarregar=True,
            prontos=lambda: [projeto.video_legendado],
        )

    Botao(cartao_render.corpo, "Gerar video completo", renderizar,
          icone="*", altura=48).pack(anchor="w", pady=(ESPACO["sm"], 0))

    if os.path.exists(projeto.video_legendado):
        Banner(parent, "Este projeto ja tem um video final legendado.",
               tipo="sucesso",
               acao=("Abrir legenda e marca ->",
                     lambda: app.navegar("legenda"))).pack(
                         fill="x", pady=(ESPACO["md"], 0))


def _abrir_cortes(app, cortes):
    from .. import player
    player.abrir(app, cortes, 0, projects.formato())


def _mover(app, indice, delta):
    timeline.mover(indice, delta, app.projeto)
    app.navegar("editor")


def _remover(app, indice):
    timeline.remover(indice, app.projeto)
    app.navegar("editor")


def _restaurar(app):
    timeline.resetar(app.projeto)
    app.navegar("editor")


def _aparar(app, indice, caminho):
    duracao = runtime.duracao(caminho)
    inicio = simpledialog.askfloat(
        "Aparar corte", "Início em segundos:", initialvalue=0.0,
        minvalue=0.0, parent=app.root)
    if inicio is None:
        return
    fim = simpledialog.askfloat(
        "Aparar corte", f"Fim em segundos (duração atual: {duracao:.1f}s):",
        initialvalue=duracao, minvalue=0.1, parent=app.root)
    if fim is None:
        return
    def terminou(novo):
        timeline.substituir(indice, [novo], app.projeto)

    app.rodar(
        lambda log, prog, ctx: clip_editor.aparar(
            caminho, inicio, fim, log=log, progresso=prog, ctx=ctx),
        nome="Aparando o corte", ao_terminar=terminou, recarregar=True)


def _dividir(app, indice, caminho):
    duracao = runtime.duracao(caminho)
    ponto = simpledialog.askfloat(
        "Dividir corte", f"Dividir em qual segundo? (duração: {duracao:.1f}s)",
        initialvalue=duracao / 2 if duracao else 30.0,
        minvalue=0.1, parent=app.root)
    if ponto is None:
        return

    def terminou(novos):
        timeline.substituir(indice, novos, app.projeto)

    app.rodar(
        lambda log, prog, ctx: clip_editor.dividir(
            caminho, ponto, log=log, progresso=prog, ctx=ctx),
        nome="Dividindo o corte", ao_terminar=terminou, recarregar=True)
