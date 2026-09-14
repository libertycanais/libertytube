"""
ui/screens/home.py
------------------------------------------------------------
Etapa 1 — escolher a rede social, colar o link e baixar.

Também é a tela inicial: mostra as cenas já baixadas e o atalho
"fazer tudo sozinho" (baixar + transcrever + roteiro pela IA).
"""

import os
import shutil
import tkinter as tk
from tkinter import filedialog

from ...backend import content
from ...core import projects, settings, tasks
from ...pipeline import base, download, flow, script_ai
from .. import player
from ..media import Galeria, cabecalho_galeria
from ..theme import ESPACO, tema
from ..widgets import (Banner, Botao, Cabecalho, Cartao, Chave, Seletor,
                       divisor, espaco, rotulo)

PLATAFORMAS_UI = [
    ("tiktok", "TikTok"), ("reels", "Reels"), ("shorts", "Shorts"),
    ("kwai", "Kwai"), ("feed", "Feed Insta"), ("youtube", "YouTube"),
    ("facebook", "Facebook"),
]

ESTILOS_EDICAO_UI = [
    ("viral", "Viral TikTok/Reels"),
    ("podcast", "Podcast profissional"),
    ("cinematico", "Cinematográfico"),
]


def montar(app, parent):
    proj = app.projeto
    cenas = base.listar_videos(proj.cenas_baixadas)

    cabecalho = Cabecalho(parent, "Baixar vídeos",
                          "Escolha a rede social, cole o link do YouTube e "
                           "deixe o LibertyTube baixar tudo.", etapa=1)
    cabecalho.pack(fill="x", pady=(4, ESPACO["lg"]))

    # ── 1. plataforma ──
    cartao_plataforma = Cartao(
        parent, "Pra onde vai esse vídeo?",
        "Os cortes e a montagem já saem no formato certo da rede escolhida.",
        accent=tema.etapa(1))
    cartao_plataforma.pack(fill="x")

    espaco(cartao_plataforma.corpo, ESPACO["sm"])

    rotulo_formato = tk.Label(
        cartao_plataforma.corpo, text="", font=tema.fonte("pequeno"),
        bg=tema.cor("card"), fg=tema.cor("texto2"), anchor="w")

    def escolher_plataforma(chave):
        projects.definir_plataforma(chave)
        nome, formato = projects.PLATAFORMAS[chave]
        rotulo_formato.configure(text=f"✓  {nome} — vídeo {formato}")
        app.log(f"Plataforma: {nome} ({formato})", "info")

    seletor = Seletor(cartao_plataforma.corpo, PLATAFORMAS_UI,
                      valor=projects.plataforma(), ao_mudar=escolher_plataforma,
                      colunas=6)
    seletor.pack(anchor="w")
    rotulo_formato.pack(fill="x", pady=(6, 0))
    nome, formato = projects.PLATAFORMAS[projects.plataforma()]
    rotulo_formato.configure(text=f"✓  {nome} — vídeo {formato}")

    espaco(parent, ESPACO["md"])

    # ── 2. link ──
    cartao_link = Cartao(parent, "Cole o link do vídeo ou da playlist",
                         "Pode colar vários links, um por linha. "
                         "Playlists são baixadas inteiras.",
                         accent=tema.etapa(1))
    cartao_link.pack(fill="x")

    caixa = tk.Frame(cartao_link.corpo, bg=tema.cor("input"),
                     highlightthickness=1, highlightbackground=tema.cor("borda"))
    caixa.pack(fill="x", pady=(ESPACO["sm"], 0))

    entrada = tk.Text(caixa, height=3, bg=tema.cor("input"), fg=tema.cor("texto"),
                      insertbackground=tema.cor("primario"), relief="flat", bd=0,
                      font=tema.fonte("corpo"), wrap="word", padx=12, pady=10,
                      highlightthickness=0)
    entrada.pack(fill="x")

    salvos = ""
    if os.path.exists(proj.arquivo_links):
        try:
            with open(proj.arquivo_links, encoding="utf-8-sig") as f:
                salvos = f.read().strip()
        except Exception:
            salvos = ""
    if salvos:
        entrada.insert("1.0", salvos)

    previa = tk.Frame(cartao_link.corpo, bg=tema.cor("card"))
    previa.pack(fill="x", pady=(ESPACO["sm"], 0))

    def atualizar_previa(_=None):
        texto = entrada.get("1.0", "end")
        links = base.extrair_links(texto)
        for widget in previa.winfo_children():
            widget.destroy()
        if not links:
            return
        _previa_video(app, previa, links[0], len(links))

    entrada.bind("<KeyRelease>", lambda e: app.root.after(600, atualizar_previa))
    entrada.bind("<<Paste>>", lambda e: app.root.after(120, atualizar_previa))
    atualizar_previa()

    acoes = tk.Frame(cartao_link.corpo, bg=tema.cor("card"))
    acoes.pack(fill="x", pady=(ESPACO["md"], 0))

    def links_digitados():
        return base.extrair_links(entrada.get("1.0", "end"))

    def baixar():
        links = links_digitados()
        if not links:
            app.aviso("Cole pelo menos um link do YouTube.", "aviso")
            return
        app.rodar(lambda log, prog, ctx: download.baixar(links, log, prog, ctx),
                  nome="Baixando as cenas", recarregar=True)

    def baixar_e_editar():
        links = links_digitados()
        if not links:
            app.aviso("Cole pelo menos um link do YouTube.", "aviso")
            return
        if not script_ai.conectado():
            app.aviso("Conecte a IA nas Configurações para criar o roteiro "
                      "e editar automaticamente.", "aviso")
            return

        etapas = ["baixar", "transcrever", "roteiro", "cortar"]
        estilo = settings.get("estilo_edicao", "viral")
        legendas = {"viral": "amarela", "podcast": "classica",
                    "cinematico": "minimalista"}
        app.rodar(
            lambda log, prog, ctx: flow.executar_etapas(
                etapas, links=links,
                opcoes={"estilo_edicao": estilo,
                        "estilo_legenda": legendas.get(estilo, "classica")},
                log=log, progresso=prog, ctx=ctx),
            nome="Baixando e editando o vídeo", recarregar=True,
            ao_terminar=lambda _: app.navegar("editor"))

    Botao(acoes, "Baixar cenas", baixar, icone="📥", altura=44).pack(side="left")
    Botao(acoes, "Baixar + editar", baixar_e_editar, icone="✨",
          variante="secundario", altura=44).pack(side="left", padx=(10, 0))
    Botao(acoes, "Usar vídeos do meu PC", lambda: _importar(app),
          variante="fantasma", icone="💻", altura=44).pack(side="left", padx=(10, 0))

    espaco(parent, ESPACO["md"])

    # ── 2b. modo automático (as chavinhas) ──
    _cartao_automatico(app, parent, links_digitados)

    espaco(parent, ESPACO["md"])

    # ── 3. próximo passo ──
    if cenas:
        Banner(parent,
               f"{len(cenas)} cena(s) baixada(s). O próximo passo é a "
               "transcrição, pra IA ouvir os vídeos.",
               tipo="sucesso", acao=("Ir para transcrever →",
                                     lambda: app.navegar("transcrever"))
               ).pack(fill="x", pady=(0, ESPACO["md"]))

    # ── 4. galeria ──
    cabecalho_galeria(parent, "Cenas baixadas", len(cenas), proj.cenas_baixadas,
                      ao_atualizar=app.recarregar).pack(fill="x",
                                                        pady=(0, ESPACO["sm"]))
    # cena baixada ainda é o vídeo original do YouTube: mostrar deitado
    # é o certo — quem sai no formato da rede é o corte
    Galeria(parent, [os.path.join(proj.cenas_baixadas, c) for c in cenas],
            colunas=4, ao_atualizar=app.recarregar, formato="16:9",
            vazio="Nenhuma cena ainda. Cole um link acima e clique em Baixar cenas."
            ).pack(fill="x", pady=(0, ESPACO["lg"]))


# ── modo automático ──────────────────────────────────────────────────
def _cartao_automatico(app, parent, links_digitados):
    """As chavinhas: o cliente liga o que quer e o LibertyTube faz tudo em
    sequência, mostrando na barra em que etapa está."""
    cartao = Cartao(
        parent, "Modo automático",
        "Ligue as etapas que o LibertyTube deve fazer sozinho, uma atrás da "
        "outra. O que ficar desligado você faz na mão, no seu tempo.",
        accent=tema.cor("primario"))
    cartao.pack(fill="x")

    rotulo(cartao.corpo, "Estilo da edição automática", "pequeno_forte").pack(
        anchor="w", pady=(ESPACO["sm"], 4))
    Seletor(cartao.corpo, ESTILOS_EDICAO_UI,
            valor=settings.get("estilo_edicao", "viral"),
            ao_mudar=lambda valor: settings.set("estilo_edicao", valor),
            colunas=3).pack(anchor="w")
    rotulo(cartao.corpo,
           "O estilo define transições, efeitos visuais e legenda do vídeo.",
           "micro", "muted").pack(anchor="w", pady=(5, ESPACO["sm"]))

    ligadas = set(settings.get("etapas_auto") or [])
    chaves = {}

    lista = tk.Frame(cartao.corpo, bg=tema.cor("card"))
    lista.pack(fill="x", pady=(ESPACO["sm"], 0))

    resumo = rotulo(cartao.corpo, "", "pequeno", "texto2")
    resumo.configure(bg=tema.cor("card"))

    def selecionadas():
        return [c for c in flow.CHAVES if chaves[c].ligada()]

    def atualizar_resumo():
        escolhidas = selecionadas()
        if not escolhidas:
            resumo.configure(text="Nenhuma etapa ligada — ligue pelo menos "
                                  "uma pra usar o modo automático.",
                             fg=tema.cor("aviso"))
            return
        nomes = ", ".join(flow.etapa(c)["nome"] for c in escolhidas)
        resumo.configure(text=f"{len(escolhidas)} etapa(s) ligada(s): {nomes}",
                         fg=tema.cor("texto2"))

    def mudou(_=None):
        settings.set("etapas_auto", selecionadas())
        atualizar_resumo()

    for i, item in enumerate(flow.ETAPAS):
        if i:
            divisor(lista, pady=6)
        chave = Chave(lista, item["nome"], item["descricao"],
                      valor=item["chave"] in ligadas, ao_mudar=mudou)
        chave.pack(fill="x", pady=3)
        chaves[item["chave"]] = chave

    divisor(cartao.corpo, pady=ESPACO["sm"])
    resumo.pack(fill="x", pady=(0, ESPACO["sm"]))
    atualizar_resumo()

    def executar():
        escolhidas = selecionadas()
        if not escolhidas:
            app.aviso("Ligue pelo menos uma etapa.", "aviso")
            return
        links = links_digitados()
        if "baixar" in escolhidas and not links:
            app.aviso("Cole pelo menos um link do YouTube.", "aviso")
            return
        estilo = settings.get("estilo_edicao", "viral")
        legendas = {"viral": "amarela", "podcast": "classica",
                    "cinematico": "minimalista"}
        app.rodar(
            lambda log, prog, ctx: flow.executar_etapas(
                escolhidas, links=links,
                opcoes={"estilo_edicao": estilo,
                        "estilo_legenda": legendas.get(estilo, "classica")},
                log=log, progresso=prog, ctx=ctx),
            nome="Modo automático", recarregar=True,
            prontos=player.prontos_do_projeto)

    Botao(cartao.corpo, "Executar as etapas ligadas", executar, icone="✨",
          altura=46).pack(anchor="w")


# ── prévia do vídeo ──────────────────────────────────────────────────
def _previa_video(app, parent, link, quantidade):
    caixa = tk.Frame(parent, bg=tema.cor("elevado"), highlightthickness=1,
                     highlightbackground=tema.cor("borda"))
    caixa.pack(fill="x")

    visor = tk.Label(caixa, text="🎬", font=(tema.familia, 20),
                     bg=tema.cor("elevado"), fg=tema.cor("muted"), width=8)
    visor.pack(side="left", padx=10, pady=10)

    textos = tk.Frame(caixa, bg=tema.cor("elevado"))
    textos.pack(side="left", fill="both", expand=True, pady=10)

    titulo = tk.Label(textos, text="carregando informações do vídeo…",
                      font=tema.fonte("corpo_forte"), bg=tema.cor("elevado"),
                      fg=tema.cor("texto"), anchor="w", justify="left",
                      wraplength=520)
    titulo.pack(fill="x")

    canal = tk.Label(textos, text=link[:70], font=tema.fonte("micro"),
                     bg=tema.cor("elevado"), fg=tema.cor("muted"), anchor="w")
    canal.pack(fill="x", pady=(2, 0))

    if quantidade > 1:
        tk.Label(textos, text=f"+ {quantidade - 1} outro(s) link(s) na fila",
                 font=tema.fonte("micro"), bg=tema.cor("elevado"),
                 fg=tema.cor("info"), anchor="w").pack(fill="x", pady=(4, 0))

    def chegou(info):
        if not info or not caixa.winfo_exists():
            if caixa.winfo_exists():
                titulo.configure(text="Link pronto pra baixar")
            return
        titulo.configure(text=info["titulo"] or "Vídeo do YouTube")
        canal.configure(text=info["canal"])
        _carregar_thumb(visor, info["thumb"])

    tasks.em_thread(lambda: content.info_youtube(link), ao_terminar=chegou,
                    root=app.root)


def _carregar_thumb(visor, url):
    try:
        from PIL import Image, ImageTk
    except ImportError:
        return
    import io
    import urllib.request

    def baixar():
        with urllib.request.urlopen(url, timeout=8) as r:
            return r.read()

    def pronto(dados):
        try:
            imagem = Image.open(io.BytesIO(dados)).convert("RGB")
            imagem.thumbnail((132, 74))
            foto = ImageTk.PhotoImage(imagem)
            visor.configure(image=foto, text="", width=132)
            visor.imagem = foto
        except Exception:
            pass

    tasks.em_thread(baixar, ao_terminar=pronto, root=visor)


# ── importar vídeos do computador ────────────────────────────────────
def _importar(app):
    arquivos = filedialog.askopenfilenames(
        title="Escolha os vídeos que você já tem",
        filetypes=[("Vídeos", "*.mp4 *.mkv *.mov *.avi *.webm"),
                   ("Todos os arquivos", "*.*")])
    if not arquivos:
        return

    proj = app.projeto.criar_pastas()

    def trabalho(log, progresso, ctx):
        copiados = 0
        numero = base.proximo_numero(proj.cenas_baixadas)
        for i, origem in enumerate(arquivos, 1):
            ctx.checar()
            extensao = os.path.splitext(origem)[1] or ".mp4"
            destino = os.path.join(proj.cenas_baixadas,
                                   f"cena_{numero:02d}{extensao}")
            progresso(f"Copiando {os.path.basename(origem)}…",
                      int(i / len(arquivos) * 100))
            shutil.copy2(origem, destino)
            log(f"  ✓ {os.path.basename(destino)}")
            numero += 1
            copiados += 1
        return copiados

    app.rodar(trabalho, nome="Importando vídeos do computador", recarregar=True)
