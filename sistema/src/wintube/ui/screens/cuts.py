"""
ui/screens/cuts.py
------------------------------------------------------------
Etapa 3 — cortar as cenas nos melhores momentos.

Aqui o usuário cola o roteiro da IA, escolhe de onde cortar (quando o
vídeo é vertical) e gera os cortes e os B-Rolls.
"""

import os
import tkinter as tk

from ...core import projects
from ...pipeline import base, cuts as pipeline_cuts
from ..media import Galeria, cabecalho_galeria
from ..theme import ESPACO, tema
from ..widgets import (Banner, Botao, Cabecalho, Cartao, Seletor, espaco,
                       rotulo)

ENQUADRAMENTOS = [
    ("centro", "Centro"),
    ("esquerda", "Esquerda"),
    ("direita", "Direita"),
    ("inteiro", "Vídeo inteiro"),
    ("seguir", "Seguir o rosto"),
]

EXPLICACAO = {
    "centro": "O padrão: corta pelo meio do vídeo.",
    "esquerda": "Use quando quem fala aparece do lado esquerdo.",
    "direita": "Use quando quem fala aparece do lado direito.",
    "inteiro": "Não corta ninguém — encaixa o vídeo com barras pretas.",
    "seguir": "A câmera acompanha o rosto de quem fala. "
              "Demora um pouco mais e precisa de rosto visível.",
}


def _cortes_do_projeto():
    """Os cortes que a etapa acabou de gerar, na ordem certa."""
    proj = projects.atual()
    return [os.path.join(proj.cenas_cortadas, c)
            for c in base.listar_videos(proj.cenas_cortadas)]


def montar(app, parent):
    proj = app.projeto
    roteiro = pipeline_cuts.ler_roteiro()
    cortes = base.listar_videos(proj.cenas_cortadas)
    brolls = base.listar_videos(proj.broll)

    Cabecalho(parent, "Cortar cenas",
              "Cole aqui o roteiro que a IA gerou. O LibertyTube corta cada "
              "trecho no tempo exato, com pelo menos 1 minuto, e já no formato "
              "da sua rede.",
              etapa=3).pack(fill="x", pady=(4, ESPACO["lg"]))

    # ── roteiro ──
    cartao = Cartao(parent, "Roteiro (os trechos que vão virar corte)",
                     "Formato: o nome da cena numa linha e, embaixo, os "
                     "trechos com [0:00:12 --> 0:00:21]. Cada corte terá no "
                     "mínimo 1 minuto.",
                    accent=tema.etapa(3))
    cartao.pack(fill="x")

    editor = tk.Text(cartao.corpo, height=12, bg=tema.cor("input"),
                     fg=tema.cor("texto"), insertbackground=tema.cor("primario"),
                     relief="flat", bd=0, wrap="word", font=tema.fonte_mono(10),
                     padx=12, pady=10, highlightthickness=1,
                     highlightbackground=tema.cor("borda"))
    editor.pack(fill="x", pady=(ESPACO["sm"], 0))
    if roteiro:
        editor.insert("1.0", roteiro)

    contador = rotulo(cartao.corpo, "", "pequeno", "texto2")
    contador.configure(bg=tema.cor("card"))
    contador.pack(anchor="w", pady=(8, 0))

    def atualizar_contador(_=None):
        total = pipeline_cuts.contar_blocos(editor.get("1.0", "end"))
        contador.configure(
            text=f"{total} trecho(s) reconhecido(s) no roteiro.",
            fg=tema.cor("sucesso") if total else tema.cor("muted"))

    editor.bind("<KeyRelease>", atualizar_contador)
    atualizar_contador()

    acoes = tk.Frame(cartao.corpo, bg=tema.cor("card"))
    acoes.pack(fill="x", pady=(ESPACO["md"], 0))

    def salvar():
        pipeline_cuts.salvar_roteiro(editor.get("1.0", "end").strip())
        app.aviso("Roteiro salvo neste projeto.", "sucesso")
        atualizar_contador()

    def colar():
        try:
            texto = app.root.clipboard_get()
        except Exception:
            app.aviso("Não há nada copiado.", "aviso")
            return
        editor.delete("1.0", "end")
        editor.insert("1.0", texto)
        salvar()

    Botao(acoes, "Colar resposta da IA", colar, icone="📋",
          variante="secundario", altura=40).pack(side="left")
    Botao(acoes, "Salvar roteiro", salvar, variante="fantasma",
          altura=40).pack(side="left", padx=(10, 0))

    espaco(parent, ESPACO["md"])

    # ── enquadramento (só no vertical) ──
    if projects.formato() == "9:16":
        cartao_enq = Cartao(parent, "De onde cortar o vídeo?",
                            "No formato vertical o vídeo precisa perder as "
                            "laterais — escolha o lado certo pra não cortar "
                            "quem está falando.", accent=tema.etapa(3))
        cartao_enq.pack(fill="x")

        explicacao = rotulo(cartao_enq.corpo, "", "pequeno", "texto2")
        explicacao.configure(bg=tema.cor("card"))

        def escolher(chave):
            projects.definir_enquadramento(chave)
            explicacao.configure(text=EXPLICACAO.get(chave, ""))

        Seletor(cartao_enq.corpo, ENQUADRAMENTOS,
                valor=projects.enquadramento(), ao_mudar=escolher, colunas=5
                ).pack(anchor="w", pady=(ESPACO["sm"], 0))
        explicacao.configure(text=EXPLICACAO.get(projects.enquadramento(), ""))
        explicacao.pack(anchor="w", pady=(6, 0))

        espaco(parent, ESPACO["md"])

    # ── gerar ──
    cartao_gerar = Cartao(parent, "Gerar os cortes", accent=tema.etapa(3))
    cartao_gerar.pack(fill="x")

    linha = tk.Frame(cartao_gerar.corpo, bg=tema.cor("card"))
    linha.pack(fill="x", pady=(ESPACO["sm"], 0))

    def cortar():
        pipeline_cuts.salvar_roteiro(editor.get("1.0", "end").strip())
        app.rodar(lambda log, prog, ctx: pipeline_cuts.cortar(log, prog, ctx),
                  nome="Cortando as cenas", recarregar=True,
                  prontos=lambda: _cortes_do_projeto())

    def gerar_broll():
        app.rodar(lambda log, prog, ctx: pipeline_cuts.gerar_broll(
            log=log, progresso=prog, ctx=ctx),
            nome="Gerando os B-Rolls", recarregar=True)

    Botao(linha, "Cortar cenas", cortar, icone="✂️", altura=44).pack(side="left")
    Botao(linha, "Gerar B-Rolls", gerar_broll, icone="🎞️",
          variante="secundario", altura=44).pack(side="left", padx=(10, 0))

    rotulo(cartao_gerar.corpo,
           "B-Rolls são clipes curtos de 5 s tirados das cenas. Eles entram "
           "intercalados na montagem pra dar movimento ao vídeo.",
           "pequeno", "muted").pack(anchor="w", pady=(10, 0))

    espaco(parent, ESPACO["md"])

    if cortes:
        Banner(parent, f"{len(cortes)} corte(s) prontos. Agora é só montar o vídeo.",
               tipo="sucesso",
               acao=("Ir para montar →", lambda: app.navegar("montar"))
               ).pack(fill="x", pady=(0, ESPACO["md"]))

    # ── galerias ──
    cabecalho_galeria(parent, "Cenas cortadas", len(cortes), proj.cenas_cortadas,
                      ao_atualizar=app.recarregar).pack(fill="x", pady=(0, 8))
    Galeria(parent, [os.path.join(proj.cenas_cortadas, c) for c in cortes],
            ao_atualizar=app.recarregar,
            vazio="Nenhum corte ainda. Cole o roteiro e clique em Cortar cenas."
            ).pack(fill="x", pady=(0, ESPACO["md"]))

    cabecalho_galeria(parent, "B-Rolls", len(brolls), proj.broll,
                      ao_atualizar=app.recarregar).pack(fill="x", pady=(0, 8))
    # B-Roll é recorte da cena original, não passa pelo formato da rede
    Galeria(parent, [os.path.join(proj.broll, b) for b in brolls[:12]],
            ao_atualizar=app.recarregar, formato="16:9",
            vazio="Nenhum B-Roll ainda (é opcional)."
            ).pack(fill="x", pady=(0, ESPACO["lg"]))
