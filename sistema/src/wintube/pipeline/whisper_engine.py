"""
pipeline/whisper_engine.py
------------------------------------------------------------
Motor de transcrição (faster-whisper).

Por que não o Whisper original: ele exige o PyTorch (~2,5 GB). O
faster-whisper roda o mesmo modelo, pesa ~50 MB e é de 2 a 4 vezes mais
rápido na CPU — que é o que a maioria dos clientes tem.

O modelo é baixado uma vez e fica guardado na pasta de configuração,
não espalhado pelo PC.
"""

import os

from ..core import paths

PASTA_MODELOS = os.path.join(paths.CONFIG_DIR, "modelos")
_MODELOS = {}


class ErroTranscricao(Exception):
    pass


def carregar(tamanho="small"):
    """Carrega (e guarda em memória) o modelo. A primeira chamada baixa
    o modelo — por isso a tela avisa que pode demorar."""
    if tamanho in _MODELOS:
        return _MODELOS[tamanho]

    os.makedirs(PASTA_MODELOS, exist_ok=True)
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise ErroTranscricao(
            "O componente de transcrição não está instalado.\n"
            "Rode o instalador do LibertyTube de novo pra reparar.")

    try:
        modelo = WhisperModel(tamanho, device="cpu", compute_type="int8",
                              download_root=PASTA_MODELOS)
    except Exception as e:
        raise ErroTranscricao(
            f"Não consegui carregar a IA de transcrição.\n\nDetalhe: {e}")

    _MODELOS[tamanho] = modelo
    return modelo


def transcrever_arquivo(caminho, tamanho="small", por_palavra=False,
                        ao_avancar=None):
    """Devolve {"segmentos": [...], "palavras": [...], "idioma": "pt"}.

    Cada segmento: {"inicio", "fim", "texto"}.
    Com `por_palavra=True` vem também o tempo de cada palavra — é o que
    faz a legenda estilo TikTok ficar em sincronia com a fala.

    `ao_avancar(segundos_ouvidos, duracao_total)` é chamada a cada trecho
    reconhecido. O faster-whisper devolve os segmentos aos poucos, então
    dá pra mostrar a barra andando em vez de deixar o cliente olhando
    pra uma tela parada durante minutos.
    """
    modelo = carregar(tamanho)
    segmentos, info = modelo.transcribe(
        caminho, beam_size=5, vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=400 if por_palavra else 500),
        word_timestamps=por_palavra,
    )

    total = float(getattr(info, "duration", 0) or 0)
    lista, palavras = [], []
    for seg in segmentos:
        texto = (seg.text or "").strip()
        if texto:
            lista.append({"inicio": seg.start, "fim": seg.end, "texto": texto})
        if por_palavra:
            for w in (getattr(seg, "words", None) or []):
                palavra = (w.word or "").strip()
                if palavra:
                    palavras.append({"inicio": w.start, "fim": w.end, "texto": palavra})
        if ao_avancar and total:
            try:
                ao_avancar(min(float(seg.end or 0), total), total)
            except Exception:
                pass  # progresso nunca derruba a transcrição

    return {"segmentos": lista, "palavras": palavras,
            "idioma": getattr(info, "language", "")}
