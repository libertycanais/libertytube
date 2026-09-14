"""
backend/errors.py
------------------------------------------------------------
Traduz os erros do Supabase (em inglês, técnicos) para frases que o
usuário do LibertyTube entende. Uma frase só, direta, sempre dizendo o que
fazer em seguida.
"""

SEM_INTERNET = "Sem internet. Conecte e tente de novo."


def traduzir(mensagem, status=0):
    erro = (mensagem or "")
    if isinstance(erro, dict):
        erro = erro.get("message") or erro.get("msg") or str(erro)
    erro = str(erro).lower()

    if status == 0 or "sem_internet" in erro or "timed out" in erro:
        return SEM_INTERNET

    # credenciais
    if "invalid_grant" in erro or (
            "invalid" in erro and any(x in erro for x in
                                      ("credential", "login", "password", "grant"))):
        return "Email ou senha incorretos."
    if "wrong password" in erro or "incorrect password" in erro:
        return "Senha incorreta."
    if "user not found" in erro or "no user found" in erro:
        return "Este email não está cadastrado. Confira ou fale com o suporte."

    # conta
    if "email not confirmed" in erro or "email_not_confirmed" in erro:
        return "Sua conta ainda não foi confirmada. Fale com o suporte pra liberar."
    if "email logins are disabled" in erro or "signups not allowed" in erro:
        return "Login por email desabilitado. Fale com o suporte."
    if "user is banned" in erro or "banned" in erro:
        return "Esta conta está bloqueada. Fale com o suporte."

    # limites
    if status == 429 or "rate limit" in erro or "too many" in erro:
        return "Muitas tentativas. Espere alguns minutos e tente de novo."
    if "for security purposes" in erro:
        return "Aguarde alguns segundos antes de tentar de novo."

    # senha
    if "password should be" in erro or "weak password" in erro:
        return "Senha muito fraca. Use pelo menos 8 caracteres, com letras e números."
    if "same password" in erro or "should be different" in erro:
        return "A senha nova precisa ser diferente da atual."

    # sessão
    if "refresh_token_not_found" in erro or "invalid refresh token" in erro:
        return "Sua sessão expirou. Faça login de novo."
    if "token" in erro and any(x in erro for x in ("expired", "invalid", "revoked")):
        return "Sua sessão expirou. Faça login de novo."

    # formato
    if "invalid email" in erro or "email address" in erro:
        return "Digite um email válido (ex: seu@email.com)."

    # servidor
    if status in (500, 502, 503, 504):
        return "O servidor está fora do ar no momento. Tente de novo em alguns minutos."
    if status == 403:
        return "O servidor recusou o acesso. Se continuar, fale com o suporte."
    if status == 404:
        return "Recurso não encontrado no servidor. Fale com o suporte."

    if mensagem:
        return f"Não consegui completar. O servidor respondeu: {mensagem}"
    return "Não consegui completar. Confira sua internet e tente de novo."
