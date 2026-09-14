"""
ui/screens/captions.py
------------------------------------------------------------
Etapa 5 — legenda estilo viral e marca d'água.

Funciona com o vídeo montado aqui no app OU com qualquer vídeo do
computador — dá pra usar só esta etapa, se quiser.
"""

import os
import tkinter as tk
from tkinter import filedialog

from ...core import projects, settings
from ...pipeline import captions
from ..media import Galeria
from ..theme import ESPACO, mesclar, tema
from ..widgets import (Banner, Botao, Cabecalho, Cartao, Chave, Seletor,
                       divisor, espaco, rotulo)

POSICOES_UI = [("inferior_direito", "Canto inferior direito"),
               ("inferior_esquerdo", "Canto inferior esquerdo"),
               ("superior_direito", "Canto superior direito"),
               ("superior_esquerdo", "Canto superior esquerdo")]

FRASE_PREVIA = "você consegue sim"


def montar(app, parent):
    proj = app.projeto
    estado = {
        "video": proj.video_base(),
        "estilo": settings.get("legenda_estilo", "classica"),
        "tamanho": settings.get("legenda_tamanho", "media"),
        "usar_legenda": True,
        "marca_img": None,
        "posicao": "inferior_direito",
    }

    Cabecalho(parent, "Legenda e marca",
              "Legenda curta e em sincronia com a fala (estilo TikTok) mais a "
              "sua marca — o vídeo sai pronto pra postar.",
              etapa=5).pack(fill="x", pady=(4, ESPACO["lg"]))

    # ── 1. vídeo ──
    cartao_video = Cartao(parent, "1. Qual vídeo?", accent=tema.etapa(5))
    cartao_video.pack(fill="x")

    escolhido = rotulo(cartao_video.corpo, "", "pequeno", "texto2")
    escolhido.configure(bg=tema.cor("card"))
    escolhido.pack(anchor="w", pady=(ESPACO["sm"], 0))

    def atualizar_rotulo():
        if estado["video"]:
            escolhido.configure(text=f"✓  {os.path.basename(estado['video'])}",
                                fg=tema.cor("sucesso"))
        else:
            escolhido.configure(
                text="Nenhum vídeo escolhido — monte no passo 4 ou escolha um "
                     "arquivo do computador.", fg=tema.cor("aviso"))

    atualizar_rotulo()

    linha = tk.Frame(cartao_video.corpo, bg=tema.cor("card"))
    linha.pack(fill="x", pady=(ESPACO["md"], 0))

    def usar_do_projeto():
        estado["video"] = proj.video_base()
        atualizar_rotulo()

    def escolher_arquivo():
        caminho = filedialog.askopenfilename(
            title="Escolha o vídeo",
            filetypes=[("Vídeos", "*.mp4 *.mkv *.mov *.avi *.webm"),
                       ("Todos os arquivos", "*.*")])
        if caminho:
            estado["video"] = caminho
            atualizar_rotulo()

    Botao(linha, "Usar o vídeo deste projeto", usar_do_projeto,
          variante="secundario", altura=40).pack(side="left")
    Botao(linha, "Escolher do computador", escolher_arquivo, icone="💻",
          variante="fantasma", altura=40).pack(side="left", padx=(10, 0))

    espaco(parent, ESPACO["md"])

    # ── 2. legenda ──
    cartao_legenda = Cartao(parent, "2. Legenda",
                            "Escolha o estilo e o tamanho. A prévia mostra "
                            "exatamente como vai sair no vídeo.",
                            accent=tema.etapa(5))
    cartao_legenda.pack(fill="x")

    chave_legenda = Chave(cartao_legenda.corpo, "Colocar legenda no vídeo",
                          "desligue se você só quer a marca d'água",
                          valor=True)
    chave_legenda.pack(fill="x", pady=(ESPACO["sm"], ESPACO["md"]))

    previa = tk.Canvas(cartao_legenda.corpo, height=150, bg="#101014",
                       highlightthickness=1,
                       highlightbackground=tema.cor("borda"))
    previa.pack(fill="x", pady=(0, ESPACO["md"]))

    cartoes_estilo = {}

    def desenhar_previa():
        previa.delete("all")
        largura = previa.winfo_width() or 700
        altura = 150

        # "tela do celular" pra dar noção de onde a legenda cai
        previa.create_rectangle(0, 0, largura, altura, fill="#101014",
                                outline="")
        previa.create_text(14, 14, anchor="w",
                           text="assim vai ficar no seu vídeo",
                           font=tema.fonte("micro"), fill="#4A5160")

        if not chave_legenda.ligada():
            previa.create_text(largura / 2, altura / 2, text="(sem legenda)",
                               font=tema.fonte("corpo"), fill=tema.cor("muted"))
            return

        _desenhar_legenda(previa, captions.estilo(estado["estilo"]),
                          captions.fator_tamanho(estado["tamanho"]),
                          largura, altura, escala=1.0)

    previa.bind("<Configure>", lambda e: desenhar_previa())

    # ── tamanho ──
    rotulo(cartao_legenda.corpo, "Tamanho da letra", "pequeno_forte").pack(
        anchor="w", pady=(0, 8))

    def escolher_tamanho(chave):
        estado["tamanho"] = chave
        settings.set("legenda_tamanho", chave)
        desenhar_previa()
        for c in cartoes_estilo.values():
            c["redesenhar"]()

    Seletor(cartao_legenda.corpo,
            [(t[0], t[1]) for t in captions.TAMANHOS],
            valor=estado["tamanho"], ao_mudar=escolher_tamanho,
            colunas=4).pack(anchor="w")

    divisor(cartao_legenda.corpo)

    # ── biblioteca de estilos ──
    rotulo(cartao_legenda.corpo,
           f"Biblioteca de estilos ({len(captions.ESTILOS)} opções)",
           "pequeno_forte").pack(anchor="w", pady=(0, 2))
    rotulo(cartao_legenda.corpo,
           "Clique num estilo pra ver na prévia acima.", "micro", "muted"
           ).pack(anchor="w", pady=(0, 10))

    def escolher_estilo(chave):
        estado["estilo"] = chave
        settings.set("legenda_estilo", chave)
        if not chave_legenda.ligada():
            chave_legenda.definir(True)
        for c in cartoes_estilo.values():
            c["marcar"]()
        desenhar_previa()

    grupo_atual = None
    grade = None
    coluna = 0
    for item in captions.ESTILOS:
        if item["grupo"] != grupo_atual:
            grupo_atual = item["grupo"]
            rotulo(cartao_legenda.corpo, grupo_atual.upper(), "micro", "muted"
                   ).pack(anchor="w", pady=(10, 6))
            grade = tk.Frame(cartao_legenda.corpo, bg=tema.cor("card"))
            grade.pack(fill="x")
            for c in range(4):
                grade.grid_columnconfigure(c, weight=1)
            coluna = 0

        cartoes_estilo[item["chave"]] = _cartao_estilo(
            grade, item, estado, escolher_estilo)
        cartoes_estilo[item["chave"]]["widget"].grid(
            row=0, column=coluna, padx=(0, 8), pady=(0, 8), sticky="nsew")
        coluna += 1

    def ligar_desligar(ligada):
        estado["usar_legenda"] = ligada
        desenhar_previa()

    chave_legenda.ao_mudar = ligar_desligar
    desenhar_previa()

    espaco(parent, ESPACO["md"])

    # ── 3. marca d'água ──
    cartao_marca = Cartao(parent, "3. Sua marca (opcional)",
                          "Ponha o @ do seu canal ou a sua logo pra deixar o "
                          "vídeo com a sua cara.", accent=tema.etapa(5))
    cartao_marca.pack(fill="x")

    campo_texto = tk.Frame(cartao_marca.corpo, bg=tema.cor("input"),
                           highlightthickness=1,
                           highlightbackground=tema.cor("borda"))
    campo_texto.pack(fill="x", pady=(ESPACO["sm"], 0))
    entrada_marca = tk.Entry(campo_texto, bg=tema.cor("input"),
                             fg=tema.cor("texto"), relief="flat", bd=0,
                             insertbackground=tema.cor("primario"),
                             font=tema.fonte("corpo"), highlightthickness=0)
    entrada_marca.pack(fill="x", padx=12, pady=11)
    entrada_marca.insert(0, app.preferencia("marca_texto") or "")

    linha_logo = tk.Frame(cartao_marca.corpo, bg=tema.cor("card"))
    linha_logo.pack(fill="x", pady=(ESPACO["md"], 0))

    logo_rotulo = rotulo(linha_logo, "nenhuma imagem escolhida", "pequeno", "muted")
    logo_rotulo.configure(bg=tema.cor("card"))

    def escolher_logo():
        caminho = filedialog.askopenfilename(
            title="Escolha a sua logo",
            filetypes=[("Imagens", "*.png *.jpg *.jpeg *.webp")])
        if caminho:
            estado["marca_img"] = caminho
            logo_rotulo.configure(text=os.path.basename(caminho),
                                  fg=tema.cor("sucesso"))

    def limpar_logo():
        estado["marca_img"] = None
        logo_rotulo.configure(text="nenhuma imagem escolhida",
                              fg=tema.cor("muted"))

    Botao(linha_logo, "Escolher logo", escolher_logo, icone="🖼️",
          variante="secundario", altura=38).pack(side="left")
    Botao(linha_logo, "tirar", limpar_logo, variante="fantasma", altura=38,
          fonte=tema.fonte("micro")).pack(side="left", padx=(8, 0))
    logo_rotulo.pack(side="left", padx=(12, 0))

    divisor(cartao_marca.corpo)

    rotulo(cartao_marca.corpo, "Onde colocar a marca", "pequeno_forte"
           ).pack(anchor="w", pady=(0, 8))
    Seletor(cartao_marca.corpo, POSICOES_UI, valor="inferior_direito",
            ao_mudar=lambda c: estado.__setitem__("posicao", c), colunas=2
            ).pack(anchor="w")

    espaco(parent, ESPACO["md"])

    # ── 4. gerar ──
    cartao_gerar = Cartao(parent, "4. Gerar o vídeo final", accent=tema.etapa(5))
    cartao_gerar.pack(fill="x")

    def aplicar():
        if not estado["video"]:
            app.aviso("Escolha um vídeo primeiro.", "aviso")
            return
        marca_texto = entrada_marca.get().strip()
        app.preferencia("marca_texto", marca_texto)

        app.rodar(lambda log, prog, ctx: captions.aplicar(
            video=estado["video"],
            estilo_legenda=estado["estilo"], tamanho=estado["tamanho"],
            usar_legenda=chave_legenda.ligada(),
            marca_img=estado["marca_img"],
            marca_texto=marca_texto or None, posicao=estado["posicao"],
            log=log, progresso=prog, ctx=ctx),
            nome="Gerando o vídeo final", recarregar=True,
            prontos=lambda: [projects.atual().video_legendado])

    Botao(cartao_gerar.corpo, "Gerar vídeo pronto pra postar", aplicar,
          icone="✨", altura=48).pack(anchor="w", pady=(ESPACO["sm"], 0))
    rotulo(cartao_gerar.corpo,
           "A legenda é gerada ouvindo o próprio vídeo, então esta etapa "
           "demora alguns minutos.", "pequeno", "muted"
           ).pack(anchor="w", pady=(10, 0))

    espaco(parent, ESPACO["md"])

    if os.path.exists(proj.video_legendado):
        Banner(parent, "Vídeo final pronto! Ele está em 5_trilhas/"
                       "video_final_legendado.mp4",
               tipo="sucesso",
               acao=("Abrir vídeo", lambda: _abrir(proj.video_legendado, parent))
               ).pack(fill="x", pady=(0, ESPACO["md"]))
        Galeria(parent, [proj.video_legendado], colunas=3,
                ao_atualizar=app.recarregar, mostrar_lixeira=False
                ).pack(fill="x", pady=(0, ESPACO["lg"]))


def _abrir(caminho, pai=None):
    from ..media import abrir_arquivo
    abrir_arquivo(caminho, pai=pai)


# ── prévia dos estilos ───────────────────────────────────────────────
def _texto_exemplo(estilo):
    """Frase do tamanho certo pro estilo: não adianta mostrar cinco
    palavras num estilo que só mostra uma por vez."""
    palavras = FRASE_PREVIA.split()
    texto = " ".join(palavras[:max(1, estilo["palavras"])])
    return texto.upper() if estilo["maiusculas"] else texto


def _desenhar_legenda(tela, estilo, fator, largura, altura, escala=1.0):
    """Desenha a legenda do jeito que o FFmpeg vai queimar no vídeo:
    mesma fonte, mesma cor, mesmo contorno, mesma posição."""
    from tkinter import font as tkfont

    tamanho = max(7, int(round(estilo["tamanho_base"] * fator * escala)))
    peso = "bold" if estilo["negrito"] else "normal"
    fonte = (estilo["fonte"], tamanho, peso)
    texto = _texto_exemplo(estilo)

    x = largura / 2
    y = {"baixo": altura - max(18, altura * 0.24),
         "meio": altura / 2,
         "topo": max(16, altura * 0.26)}.get(estilo["posicao"], altura * 0.76)

    if estilo["caixa"]:
        medidor = tkfont.Font(font=fonte)
        larg = medidor.measure(texto)
        alt = medidor.metrics("linespace")
        folga_x, folga_y = 10 * escala + 4, 4 * escala + 3
        tela.create_rectangle(x - larg / 2 - folga_x, y - alt / 2 - folga_y,
                              x + larg / 2 + folga_x, y + alt / 2 + folga_y,
                              fill=estilo["caixa"], outline=estilo["caixa"])
        tela.create_text(x, y, text=texto, font=fonte, fill=estilo["cor"])
        return

    if estilo["sombra"]:
        deslocamento = max(1, int(round(estilo["sombra"] * escala)))
        tela.create_text(x + deslocamento, y + deslocamento, text=texto,
                         font=fonte, fill="#000000")

    if estilo["largura_contorno"]:
        passo = max(1, int(round(estilo["largura_contorno"] * escala * 0.7)))
        for dx in (-passo, 0, passo):
            for dy in (-passo, 0, passo):
                if dx or dy:
                    tela.create_text(x + dx, y + dy, text=texto, font=fonte,
                                     fill=estilo["contorno"])

    tela.create_text(x, y, text=texto, font=fonte, fill=estilo["cor"])


def _cartao_estilo(parent, item, estado, escolher):
    """Um quadradinho da biblioteca: prévia em cima, nome embaixo."""
    card = tk.Frame(parent, bg=tema.cor("elevado"), highlightthickness=2,
                    highlightbackground=tema.cor("borda"), cursor="hand2")

    tela = tk.Canvas(card, height=62, bg="#101014", highlightthickness=0, bd=0)
    tela.pack(fill="x")

    nome = tk.Label(card, text=item["nome"], font=tema.fonte("pequeno_forte"),
                    bg=tema.cor("elevado"), fg=tema.cor("texto"), anchor="w")
    nome.pack(fill="x", padx=8, pady=(6, 0))

    descricao = tk.Label(card, text=item["descricao"], font=tema.fonte("micro"),
                         bg=tema.cor("elevado"), fg=tema.cor("texto2"),
                         anchor="w", justify="left", wraplength=150)
    descricao.pack(fill="x", padx=8, pady=(1, 8))

    def redesenhar(_=None):
        largura = tela.winfo_width() or 150
        tela.delete("all")
        _desenhar_legenda(tela, item, captions.fator_tamanho(estado["tamanho"]),
                          largura, 62, escala=0.52)

    def marcar():
        escolhido = estado["estilo"] == item["chave"]
        card.configure(highlightbackground=tema.cor("primario") if escolhido
                       else tema.cor("borda"),
                       bg=mesclar(tema.cor("elevado"), tema.cor("primario"), 0.12)
                       if escolhido else tema.cor("elevado"))
        for widget in (nome, descricao):
            widget.configure(bg=card.cget("bg"))

    tela.bind("<Configure>", redesenhar)
    for widget in (card, tela, nome, descricao):
        widget.bind("<Button-1>", lambda e, c=item["chave"]: escolher(c))

    marcar()
    return {"widget": card, "marcar": marcar, "redesenhar": redesenhar}
