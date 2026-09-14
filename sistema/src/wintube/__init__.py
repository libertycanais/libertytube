"""LibertyTube — pacote principal.

Estrutura:
    core/      caminhos, projetos, preferências, execução de tarefas
    backend/   tudo que fala com o servidor (Supabase): login, conteúdo, updates
    pipeline/  as etapas de vídeo (download, transcrição, cortes, montagem…)
    ui/        tema, componentes visuais e telas
"""

from .version import VERSAO

__all__ = ["VERSAO"]
