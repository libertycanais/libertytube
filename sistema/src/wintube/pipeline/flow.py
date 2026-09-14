"""
pipeline/flow.py
------------------------------------------------------------
O "modo automático": o cliente liga as chavinhas das etapas que quer e o
    LibertyTube faz uma atrás da outra, sozinho.

    executar_etapas(["baixar", "transcrever", "roteiro"], links=[...])

Cada etapa tem um peso (quanto ela costuma demorar em relação às
outras). A barra de progresso da tela usa esses pesos pra andar de forma
honesta: o download não pode ocupar 90% da barra se, na prática, a
transcrição é que leva o tempo todo.

`roteiro_automatico` continua existindo — hoje ele é só um atalho pras
três primeiras etapas.
"""

from ..core import projects, settings
from . import assembly, captions, cuts, download, music, script_ai, transcribe
from .base import listar_audios, normalizar


class ErroFluxo(Exception):
    pass


# ordem fixa: é a ordem em que as etapas fazem sentido
ETAPAS = [
    {"chave": "baixar", "nome": "Baixar os vídeos", "peso": 22,
     "descricao": "pega os links do YouTube (playlist inteira também)"},
    {"chave": "transcrever", "nome": "Transcrever com a IA", "peso": 26,
     "descricao": "a IA ouve as cenas e escreve tudo com os tempos"},
    {"chave": "roteiro", "nome": "Roteiro pela IA", "peso": 8,
     "descricao": "o Gemini escolhe os melhores trechos (precisa da chave)"},
    {"chave": "cortar", "nome": "Cortar as cenas", "peso": 14,
     "descricao": "corta nos tempos do roteiro, com no mínimo 1 minuto por cena"},
    {"chave": "montar", "nome": "Montar o vídeo", "peso": 14,
     "descricao": "junta cortes, transições, efeitos e B-Rolls"},
    {"chave": "trilha", "nome": "Colocar a trilha", "peso": 6,
     "descricao": "mixa uma música já baixada por baixo da fala"},
    {"chave": "legenda", "nome": "Legenda e marca", "peso": 10,
     "descricao": "legenda estilo viral e a sua marca d'água"},
]

CHAVES = [e["chave"] for e in ETAPAS]


def etapa(chave):
    for item in ETAPAS:
        if item["chave"] == chave:
            return item
    return None


# ── o motor ──────────────────────────────────────────────────────────
def executar_etapas(selecionadas, links=None, opcoes=None,
                    log=None, progresso=None, ctx=None):
    """Roda, em ordem, só as etapas ligadas. Devolve o que cada uma
    produziu: {"baixar": 5, "roteiro": "…/roteiro.txt", …}."""
    log, progresso = normalizar(log, progresso)
    opcoes = dict(opcoes or {})

    pedidas = set(selecionadas or [])
    escolhidas = [e for e in ETAPAS if e["chave"] in pedidas]
    if not escolhidas:
        raise ErroFluxo("Ligue pelo menos uma etapa nas chavinhas antes de "
                        "clicar em executar.")

    _conferir_antes(escolhidas, links)

    projects.atual().criar_pastas()
    total = sum(e["peso"] for e in escolhidas)
    quantas = len(escolhidas)
    resultados = {}
    andado = 0

    for numero, item in enumerate(escolhidas, 1):
        if ctx is not None:
            ctx.checar()

        inicio = andado / total * 100
        fim = (andado + item["peso"]) / total * 100

        log("═" * 44)
        log(f"ETAPA {numero} de {quantas} — {item['nome']}")
        progresso(f"{item['nome']} ({numero} de {quantas})", int(inicio))

        def relatar(texto, pct=None, _a=inicio, _b=fim, _n=numero):
            """Encaixa o progresso da etapa no pedaço dela na barra."""
            rotulo = f"[{_n}/{quantas}] {texto}"
            if pct is None:
                progresso(rotulo, None)
            else:
                progresso(rotulo, int(_a + (_b - _a) * max(0, min(100, pct)) / 100))

        resultados[item["chave"]] = _rodar(item["chave"], links, opcoes,
                                           log, relatar, ctx)
        andado += item["peso"]

    progresso("Tudo pronto!", 100)
    log("═" * 44)
    log(f"{quantas} etapa(s) concluída(s).", "ok")
    return resultados


def _conferir_antes(escolhidas, links):
    """Tudo que dá pra checar ANTES de baixar 500 MB à toa."""
    chaves = {e["chave"] for e in escolhidas}

    if "baixar" in chaves and not links:
        raise ErroFluxo("Cole pelo menos um link do YouTube antes de executar.")

    if "roteiro" in chaves and not script_ai.conectado():
        raise ErroFluxo(
            "A etapa 'Roteiro pela IA' precisa da chave do Gemini.\n"
            "Vá em Configurações → Conectar IA (é grátis e leva 1 minuto), "
            "ou desligue essa chavinha.")

    if "cortar" in chaves and "roteiro" not in chaves and not cuts.ler_roteiro():
        raise ErroFluxo(
            "A etapa 'Cortar as cenas' precisa de um roteiro com os tempos.\n"
            "Ligue também 'Roteiro pela IA' ou cole o roteiro no passo 3.")

    if "trilha" in chaves and not listar_audios(projects.atual().trilhas_baixadas):
        raise ErroFluxo(
            "A etapa 'Colocar a trilha' precisa de uma música baixada.\n"
            "Baixe uma trilha no passo 4 ou desligue essa chavinha.")


def _rodar(chave, links, opcoes, log, progresso, ctx):
    if chave == "baixar":
        return download.baixar(links, log=log, progresso=progresso, ctx=ctx)

    if chave == "transcrever":
        return transcribe.transcrever(log=log, progresso=progresso, ctx=ctx)

    if chave == "roteiro":
        texto = transcribe.ler_transcricao()
        if len(texto.strip()) < 40:
            raise ErroFluxo(
                "A transcrição está vazia — sem ela a IA não tem o que ler.\n"
                "Ligue também a etapa 'Transcrever com a IA'.")
        roteiro = script_ai.gerar_roteiro(texto, log=log, progresso=progresso,
                                          ctx=ctx)
        caminho = cuts.salvar_roteiro(roteiro)
        log(f"Roteiro salvo com {cuts.contar_blocos(roteiro)} trecho(s).", "ok")
        return caminho

    if chave == "cortar":
        return cuts.cortar(log=log, progresso=progresso, ctx=ctx)

    if chave == "montar":
        return assembly.montar(
            usar_broll=bool(opcoes.get("usar_broll",
                                       settings.get("usar_broll", False))),
            usar_letterbox=bool(opcoes.get("usar_letterbox",
                                            settings.get("letterbox", True))),
            estilo=opcoes.get("estilo_edicao")
            or settings.get("estilo_edicao", "viral"),
            movimento=opcoes.get("movimento_edicao")
            or settings.get("movimento_edicao", "zoom_suave"),
            log=log, progresso=progresso, ctx=ctx)

    if chave == "trilha":
        return music.sonorizar(log=log, progresso=progresso, ctx=ctx)

    if chave == "legenda":
        return captions.aplicar(
            video=opcoes.get("video"),
            estilo_legenda=opcoes.get("estilo_legenda")
            or settings.get("legenda_estilo", "classica"),
            tamanho=opcoes.get("tamanho_legenda")
            or settings.get("legenda_tamanho", "media"),
            usar_legenda=True,
            marca_img=opcoes.get("marca_img"),
            marca_texto=opcoes.get("marca_texto")
            or settings.get("marca_texto", "") or None,
            posicao=opcoes.get("posicao", "inferior_direito"),
            log=log, progresso=progresso, ctx=ctx)

    raise ErroFluxo(f"Etapa desconhecida: {chave}")


# ── atalho antigo ────────────────────────────────────────────────────
def roteiro_automatico(links, log=None, progresso=None, ctx=None):
    """Baixar → transcrever → roteiro. Devolve o caminho do roteiro."""
    resultados = executar_etapas(["baixar", "transcrever", "roteiro"],
                                 links=links, log=log, progresso=progresso,
                                 ctx=ctx)
    return resultados.get("roteiro")
