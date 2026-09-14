"""
Etapas de vídeo do LibertyTube.

    download    baixa os vídeos/playlists do YouTube
    transcribe  transcreve as cenas (faster-whisper)
    script_ai   fala com o Gemini (roteiro e assistente)
    cuts        corta as cenas pelo roteiro e gera os B-Rolls
    assembly    junta tudo na montagem final
    music       baixa trilhas e sonoriza
    captions    legenda estilo viral + marca d'água
    flow        o botão "fazer tudo sozinho"

Todas as funções seguem a mesma assinatura:

    funcao(..., log=None, progresso=None, ctx=None)

`log(texto, nivel)` escreve no console, `progresso(texto, pct)` move a
barra e `ctx` (core.tasks.Contexto) permite cancelar de verdade.
"""
