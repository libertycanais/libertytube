"""
pipeline/captions.py
------------------------------------------------------------
Etapa 5 — legenda estilo viral e marca d'água.

A legenda é gerada ouvindo o próprio vídeo (faster-whisper com tempo por
palavra) e aparece em pedaços curtos, em sincronia com a fala — igual
aos vídeos que viralizam, em vez de blocos grandes cobrindo a tela.

A marca d'água pode ser uma imagem (a logo do cliente) ou um texto
(o @ do canal).
"""

import os
from datetime import timedelta

from ..core import projects, runtime
from . import whisper_engine
from .base import normalizar

POSICOES_MARCA = {
    "inferior_direito": ("W-w-25", "H-h-25", "w-tw-25", "h-th-25"),
    "inferior_esquerdo": ("25", "H-h-25", "25", "h-th-25"),
    "superior_direito": ("W-w-25", "25", "w-tw-25", "25"),
    "superior_esquerdo": ("25", "25", "25", "25"),
}


class ErroLegenda(Exception):
    pass


# ── Biblioteca de estilos ────────────────────────────────────────────
# Cada estilo é um jeito inteiro de escrever a legenda: fonte, cor,
# contorno, caixa, quantas palavras aparecem por vez e onde ela fica.
# A tela de legenda desenha a prévia a partir DESTES MESMOS campos, então
# o que o cliente vê na prévia é o que sai no vídeo.
#
# Fontes: só as que já vêm no Windows — fonte que não existe faz o FFmpeg
# cair pra uma qualquer e a legenda sai diferente na máquina do cliente.
ESTILOS = [
    {"chave": "classica", "nome": "Clássica", "grupo": "Populares",
     "descricao": "branca com contorno preto — combina com tudo",
     "fonte": "Arial", "negrito": True, "cor": "#FFFFFF",
     "contorno": "#000000", "largura_contorno": 3, "sombra": 1,
     "caixa": None, "maiusculas": False, "palavras": 3,
     "tamanho_base": 20, "posicao": "baixo"},

    {"chave": "amarela", "nome": "Amarela viral", "grupo": "Populares",
     "descricao": "a mais usada em corte de podcast",
     "fonte": "Arial", "negrito": True, "cor": "#FFD400",
     "contorno": "#000000", "largura_contorno": 3, "sombra": 1,
     "caixa": None, "maiusculas": False, "palavras": 3,
     "tamanho_base": 20, "posicao": "baixo"},

    {"chave": "uma_palavra", "nome": "Uma palavra por vez", "grupo": "Populares",
     "descricao": "palavra gigante trocando na batida da fala",
     "fonte": "Arial", "negrito": True, "cor": "#FFFFFF",
     "contorno": "#000000", "largura_contorno": 4, "sombra": 1,
     "caixa": None, "maiusculas": True, "palavras": 1,
     "tamanho_base": 30, "posicao": "meio"},

    {"chave": "impacto", "nome": "Impacto", "grupo": "Populares",
     "descricao": "maiúsculas com contorno grosso, estilo meme",
     "fonte": "Impact", "negrito": False, "cor": "#FFFFFF",
     "contorno": "#000000", "largura_contorno": 5, "sombra": 0,
     "caixa": None, "maiusculas": True, "palavras": 2,
     "tamanho_base": 26, "posicao": "baixo"},

    {"chave": "caixa_preta", "nome": "Caixa preta", "grupo": "Com fundo",
     "descricao": "texto branco numa tarja preta — lê bem em qualquer vídeo",
     "fonte": "Arial", "negrito": True, "cor": "#FFFFFF",
     "contorno": "#000000", "largura_contorno": 0, "sombra": 0,
     "caixa": "#000000", "maiusculas": False, "palavras": 4,
     "tamanho_base": 18, "posicao": "baixo"},

    {"chave": "caixa_branca", "nome": "Caixa branca", "grupo": "Com fundo",
     "descricao": "tarja branca com letra preta, bem limpo",
     "fonte": "Arial", "negrito": True, "cor": "#111111",
     "contorno": "#FFFFFF", "largura_contorno": 0, "sombra": 0,
     "caixa": "#FFFFFF", "maiusculas": False, "palavras": 4,
     "tamanho_base": 18, "posicao": "baixo"},

    {"chave": "caixa_roxa", "nome": "Caixa LibertyTube", "grupo": "Com fundo",
     "descricao": "tarja roxa da marca com texto branco",
     "fonte": "Arial", "negrito": True, "cor": "#FFFFFF",
     "contorno": "#6C5CE7", "largura_contorno": 0, "sombra": 0,
     "caixa": "#6C5CE7", "maiusculas": False, "palavras": 3,
     "tamanho_base": 18, "posicao": "baixo"},

    {"chave": "verde_neon", "nome": "Verde neon", "grupo": "Coloridas",
     "descricao": "verde forte, chama atenção no feed",
     "fonte": "Arial", "negrito": True, "cor": "#22FF6A",
     "contorno": "#04220F", "largura_contorno": 3, "sombra": 1,
     "caixa": None, "maiusculas": False, "palavras": 3,
     "tamanho_base": 20, "posicao": "baixo"},

    {"chave": "rosa_viral", "nome": "Rosa viral", "grupo": "Coloridas",
     "descricao": "rosa forte, funciona bem em vídeo de moda e beleza",
     "fonte": "Arial", "negrito": True, "cor": "#FF3EA5",
     "contorno": "#000000", "largura_contorno": 3, "sombra": 1,
     "caixa": None, "maiusculas": False, "palavras": 3,
     "tamanho_base": 20, "posicao": "baixo"},

    {"chave": "azul_gelo", "nome": "Azul gelo", "grupo": "Coloridas",
     "descricao": "azul claro com contorno escuro, bom pra tecnologia",
     "fonte": "Trebuchet MS", "negrito": True, "cor": "#7FD8FF",
     "contorno": "#06213A", "largura_contorno": 3, "sombra": 1,
     "caixa": None, "maiusculas": False, "palavras": 3,
     "tamanho_base": 20, "posicao": "baixo"},

    {"chave": "minimalista", "nome": "Minimalista", "grupo": "Discretas",
     "descricao": "fina, sem contorno grosso — pra vídeo mais sério",
     "fonte": "Verdana", "negrito": False, "cor": "#F2F2F2",
     "contorno": "#000000", "largura_contorno": 1, "sombra": 1,
     "caixa": None, "maiusculas": False, "palavras": 5,
     "tamanho_base": 16, "posicao": "baixo"},

    {"chave": "legenda_topo", "nome": "No topo", "grupo": "Discretas",
     "descricao": "sobe pro alto do vídeo, livra o rosto de quem fala",
     "fonte": "Arial", "negrito": True, "cor": "#FFFFFF",
     "contorno": "#000000", "largura_contorno": 3, "sombra": 1,
     "caixa": None, "maiusculas": False, "palavras": 4,
     "tamanho_base": 18, "posicao": "topo"},
]

# quanto cada tamanho multiplica o `tamanho_base` do estilo
TAMANHOS = [
    ("pequena", "Pequena", 0.78),
    ("media", "Média", 1.0),
    ("grande", "Grande", 1.28),
    ("gigante", "Gigante", 1.6),
]

# nome antigo (só cor) -> estilo novo, pra projeto/config salvo antes
CORES_ANTIGAS = {"branca": "classica", "amarela": "amarela",
                 "verde": "verde_neon"}

# CUIDADO: o FFmpeg converte o .srt usando a numeração ANTIGA (SSA v4),
# não a do ASS v4+. Medido na mão, num vídeo preto:
#     1,2,3     rodapé (esquerda, centro, direita)
#     5,6,7     topo
#     9,10,11   meio
# Com a numeração do ASS v4+ (5 = meio-centro, 8 = topo-centro) a legenda
# do "uma palavra por vez" saía colada no canto superior esquerdo.
_ALINHAMENTO = {"baixo": 2, "meio": 10, "topo": 6}
_MARGEM = {"baixo": 90, "meio": 10, "topo": 50}


def estilo(chave):
    """Devolve o estilo pedido (ou a Clássica, se o nome não existir)."""
    chave = CORES_ANTIGAS.get(chave, chave)
    for item in ESTILOS:
        if item["chave"] == chave:
            return item
    return ESTILOS[0]


def fator_tamanho(chave):
    for item in TAMANHOS:
        if item[0] == chave:
            return item[2]
    return 1.0


def _cor_ass(hex_cor, transparente=False):
    """#RRGGBB -> &HAABBGGRR (o ASS inverte a ordem das cores)."""
    hex_cor = (hex_cor or "#FFFFFF").lstrip("#")
    r, g, b = hex_cor[0:2], hex_cor[2:4], hex_cor[4:6]
    alfa = "FF" if transparente else "00"
    return f"&H{alfa}{b}{g}{r}".upper()


def force_style(chave_estilo, tamanho="media"):
    """Monta a string de estilo que o FFmpeg entende."""
    e = estilo(chave_estilo)
    corpo = max(10, int(round(e["tamanho_base"] * fator_tamanho(tamanho))))

    partes = [
        f"FontName={e['fonte']}",
        f"FontSize={corpo}",
        f"Bold={1 if e['negrito'] else 0}",
        f"PrimaryColour={_cor_ass(e['cor'])}",
        f"OutlineColour={_cor_ass(e['contorno'])}",
        f"Alignment={_ALINHAMENTO.get(e['posicao'], 2)}",
        f"MarginV={_MARGEM.get(e['posicao'], 90)}",
        # margem lateral pequena: a "tela" que o FFmpeg usa pra legenda é
        # estreita, e com 40 de cada lado a frase quebrava em três linhas
        "MarginL=25", "MarginR=25",
    ]

    if e["caixa"]:
        # BorderStyle=3 pinta uma tarja atrás do texto em vez de contorno
        partes += [f"BorderStyle=3", f"BackColour={_cor_ass(e['caixa'])}",
                   "Outline=6", "Shadow=0"]
    else:
        partes += ["BorderStyle=1",
                   f"Outline={e['largura_contorno']}",
                   f"Shadow={e['sombra']}"]

    return ",".join(partes)


def _tempo_srt(segundos):
    ms = int((segundos - int(segundos)) * 1000)
    t = str(timedelta(seconds=int(segundos)))
    if len(t.split(":")[0]) == 1:
        t = "0" + t
    return f"{t},{ms:03d}"


def gerar_srt(video, palavras_por_bloco=3, maiusculas=False,
              log=None, progresso=None):
    """Transcreve o áudio e escreve um .srt com blocos curtos.

    `palavras_por_bloco` e `maiusculas` vêm do estilo escolhido — é o que
    faz "uma palavra por vez" e "Impacto" serem diferentes de verdade, e
    não só uma troca de cor."""
    log, progresso = normalizar(log, progresso)
    proj = projects.atual().criar_pastas()

    # sem porcentagem aqui de propósito: a IA não avisa quanto falta, e
    # uma barra parada em 10% parece app travado. A barra fica andando.
    progresso("A IA está ouvindo o vídeo pra escrever a legenda "
              "(na primeira vez ela é baixada)…", None)
    log("A IA está ouvindo o vídeo — esta parte é a mais demorada.")

    def avancou(ouvidos, total):
        progresso(f"A IA já ouviu {ouvidos / 60:.1f} de {total / 60:.1f} min "
                  "do vídeo…", int(45 * ouvidos / total) if total else None)

    resultado = whisper_engine.transcrever_arquivo(video, por_palavra=True,
                                                   ao_avancar=avancou)
    progresso("Montando a legenda…", 45)

    caminho = os.path.join(proj.trilhas, "_legenda.srt")
    palavras = resultado["palavras"]

    def escrever(texto):
        return texto.upper() if maiusculas else texto

    with open(caminho, "w", encoding="utf-8") as f:
        if palavras:
            indice = 1
            passo = max(1, int(palavras_por_bloco))
            for i in range(0, len(palavras), passo):
                grupo = palavras[i:i + passo]
                inicio = grupo[0]["inicio"]
                fim = max(grupo[-1]["fim"], inicio + 0.3)
                texto = " ".join(p["texto"] for p in grupo)
                f.write(f"{indice}\n{_tempo_srt(inicio)} --> {_tempo_srt(fim)}\n"
                        f"{escrever(texto)}\n\n")
                indice += 1
        else:
            # sem tempo por palavra (raro): cai pro modo por frase
            for i, seg in enumerate(resultado["segmentos"], 1):
                f.write(f"{i}\n{_tempo_srt(seg['inicio'])} --> "
                        f"{_tempo_srt(seg['fim'])}\n{escrever(seg['texto'])}\n\n")

    log(f"Legenda gerada com {len(palavras) or len(resultado['segmentos'])} trechos.")
    return caminho


def _escapar(caminho):
    """Escapa o caminho pra usar dentro do filtro do ffmpeg."""
    return caminho.replace("\\", "/").replace(":", "\\:")


def aplicar(video=None, estilo_legenda="classica", tamanho="media",
            usar_legenda=True, marca_img=None, marca_texto=None,
            posicao="inferior_direito", cor=None,
            log=None, progresso=None, ctx=None):
    """Queima a legenda e/ou a marca d'água. Devolve o caminho do vídeo
    final, pronto pra postar.

    `estilo_legenda` é uma das chaves de ESTILOS e `tamanho` uma das de
    TAMANHOS. `cor` só existe pra não quebrar chamada antiga (branca /
    amarela / verde)."""
    log, progresso = normalizar(log, progresso)
    proj = projects.atual().criar_pastas()

    if not video or not os.path.exists(video):
        video = proj.video_base()
    if video and os.path.abspath(video) == os.path.abspath(proj.video_legendado):
        video = proj.video_base()
    if not video:
        raise ErroLegenda(
            "Não achei um vídeo pra legendar.\n\n"
            "Monte o vídeo no passo 4, ou clique em 'Escolher vídeo do "
            "computador' pra usar um arquivo seu.")

    if not usar_legenda and not marca_img and not marca_texto:
        raise ErroLegenda("Escolha pelo menos uma coisa: legenda ou marca d'água.")

    saida = proj.video_legendado
    saida_temporaria = saida + ".tmp.mp4"
    filtros = []

    if usar_legenda:
        escolhido = estilo(cor if cor else estilo_legenda)
        srt = gerar_srt(video, palavras_por_bloco=escolhido["palavras"],
                        maiusculas=escolhido["maiusculas"],
                        log=log, progresso=progresso)
        log(f"Legenda no estilo “{escolhido['nome']}”, tamanho {tamanho}.")
        filtros.append(
            f"subtitles='{_escapar(srt)}'"
            f":force_style='{force_style(escolhido['chave'], tamanho)}'")

    pos = POSICOES_MARCA.get(posicao, POSICOES_MARCA["inferior_direito"])

    if marca_texto:
        texto = marca_texto.replace("'", "").replace(":", "")
        filtros.append(
            f"drawtext=text='{texto}':fontcolor=white@0.85:fontsize=22:"
            f"box=1:boxcolor=black@0.35:boxborderw=8:x={pos[2]}:y={pos[3]}")

    progresso("Aplicando no vídeo…", 55)
    segundos = runtime.duracao(video)

    if marca_img and os.path.exists(marca_img):
        cadeia = ",".join(filtros) if filtros else "null"
        complexo = (f"[0:v]{cadeia}[base];[1:v]scale=140:-1[marca];"
                    f"[base][marca]overlay={pos[0]}:{pos[1]}:format=auto[vout]")
        args = ["-i", video, "-i", marca_img, "-filter_complex", complexo,
                "-map", "[vout]", "-map", "0:a?"]
    else:
        args = ["-i", video, "-vf", ",".join(filtros) if filtros else "null"]

    args += ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
             "-pix_fmt", "yuv420p",          # abre em qualquer player
             "-c:a", "aac", "-b:a", "192k",
             "-movflags", "+faststart",      # já sai pronto pra postar
              saida_temporaria]

    try:
        runtime.rodar_ffmpeg(args, ctx=ctx, progresso=progresso,
                             duracao_total=segundos,
                             rotulo="Queimando legenda e marca",
                             faixa=(55, 99))
        os.replace(saida_temporaria, saida)
    except runtime.ErroFFmpeg as e:
        raise ErroLegenda(f"O FFmpeg não conseguiu finalizar o vídeo.\n\n{e}")
    finally:
        try:
            os.remove(saida_temporaria)
        except OSError:
            pass

    progresso("Vídeo pronto pra postar!", 100)
    log("Vídeo final em 5_trilhas/video_final_legendado.mp4", "ok")
    return saida
