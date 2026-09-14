"""Camada de servidor do LibertyTube (Supabase).

    config    endereço do projeto, tabelas e prazos
    http      cliente HTTP simples, com timeout e erro traduzido
    session   sessão local (tokens) presa ao computador
    auth      login, refresh, troca e recuperação de senha
    content   aulas, bônus, como usar, material VIP e configs do app
    updates   atualização automática do app

Nenhuma tela fala com a internet direto: tudo passa por aqui.
"""
