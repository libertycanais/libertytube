"""
backend/auth.py
------------------------------------------------------------
Login e controle de acesso do LibertyTube.

Regras (e o porquê de cada uma):

  1. FALHA FECHADA. Se este módulo não carregar, o app NÃO abre. Na 2.48
     um erro aqui caía num "modo aberto" que liberava o app inteiro —
     bastava renomear licenca.py pra usar sem pagar.

  2. Conta desativada ou vencida trava. A checagem de `perfis_usuario`
     só libera com resposta explícita do servidor. Se a consulta falhar
     (RLS errado, servidor fora), vale o último "conta ativa" conhecido
     por até GRACA_PERFIL_DIAS — depois disso pede login. Antes,
     qualquer erro era tratado como "tudo certo".

  3. Quem manda é o token, não o arquivo. O id do usuário é lido de
     dentro do JWT assinado pelo servidor, nunca do JSON local (que o
     usuário pode editar).

  4. Nada trava a tela. Todas as funções aqui são feitas pra rodar em
     thread (veja core.tasks.em_thread).

  5. A sessão TEM PRAZO. A cada config.MAX_DIAS_SESSAO dias (15, por
     padrão) o app desloga sozinho e pede email e senha de novo. Isso
     mostra que a conta continua em uso e resolve o reembolso: é só
     desativar o perfil no Supabase que, no próximo login obrigatório,
     o app não abre mais. Antes, quem entrasse uma vez ficava logado
     praticamente pra sempre, porque o refresh token se renovava
     sozinho.
"""

import base64
import json
import re
import threading
import time

from . import config, http, session

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[a-zA-Z]{2,}$")


class Resultado:
    """Resposta de uma ação de login/senha."""

    def __init__(self, ok, motivo="", sessao=None, offline=False):
        self.ok = ok
        self.motivo = motivo
        self.sessao = sessao
        self.offline = offline

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return f"<Resultado ok={self.ok} motivo={self.motivo!r}>"


# ── JWT ──────────────────────────────────────────────────────────────
def _ler_jwt(token):
    """Lê o miolo do JWT (sem validar assinatura — quem valida é o
    servidor). Serve pra saber o id do usuário e quando expira."""
    try:
        meio = token.split(".")[1]
        meio += "=" * (-len(meio) % 4)
        return json.loads(base64.urlsafe_b64decode(meio).decode("utf-8"))
    except Exception:
        return {}


def user_id(sessao):
    """Id do usuário vindo do token (fonte confiável)."""
    if not sessao:
        return None
    dados = _ler_jwt(sessao.get("access_token", ""))
    return dados.get("sub") or (sessao.get("user") or {}).get("id")


def usuario(sessao):
    return (sessao or {}).get("user") or {}


def email_do(sessao):
    return usuario(sessao).get("email", "")


# ── Prazo da sessão (relogin obrigatório) ────────────────────────────
MSG_PRAZO = ("Por segurança, o LibertyTube pede seu email e senha a cada "
             "{dias} dias. Entre de novo pra continuar — leva 10 segundos.")


def dias_de_sessao(sessao):
    """Há quantos dias este login foi feito."""
    return session.dias_desde((sessao or {}).get("criada_em"))


def dias_restantes(sessao):
    """Quantos dias faltam pro relogin obrigatório (0 = é hoje)."""
    if not sessao:
        return 0
    return max(0, int(config.MAX_DIAS_SESSAO - dias_de_sessao(sessao)))


def sessao_vencida(sessao=None):
    """True quando já passou do prazo e o cliente precisa logar de novo."""
    sessao = sessao if sessao is not None else session.carregar()
    if not sessao:
        return False
    return dias_de_sessao(sessao) >= config.MAX_DIAS_SESSAO


def _token_expirado(sessao, folga=60):
    exp = sessao.get("expira_em_ts") or 0
    if not exp:
        exp = _ler_jwt(sessao.get("access_token", "")).get("exp", 0)
    return (exp - folga) <= time.time()


# ── Perfil (conta ativa / assinatura) ────────────────────────────────
def _checar_perfil(uid, token):
    """Devolve (situacao, motivo, perfil).

    situacao: "ok" | "bloqueado" | "indeterminado"
    """
    if not config.configurado():
        return "indeterminado", "Servidor de login não configurado.", None
    if not uid or not token:
        return "indeterminado", "Não consegui identificar sua conta.", None

    resp = http.tabela(config.TABELA_PERFIS, token=token,
                       filtros={"user_id": f"eq.{uid}"})

    if not resp.ok:
        return "indeterminado", resp.erro or "Servidor indisponível.", None
    if not isinstance(resp.dados, list):
        return "indeterminado", "Resposta inesperada do servidor.", None
    if not resp.dados:
        # O LibertyTube exige um perfil explícito. Login válido sozinho não
        # comprova compra nem autorização para acessar o conteúdo.
        return "bloqueado", "Seu perfil ainda não foi liberado. Fale com o suporte.", None

    perfil = resp.dados[0]
    if perfil.get("ativo") is False:
        return "bloqueado", "Sua conta está desativada. Fale com o suporte.", perfil

    expira = perfil.get("expira_em")
    if expira:
        try:
            from datetime import datetime
            data = datetime.fromisoformat(str(expira).split("T")[0]).date()
            if data < datetime.now().date():
                return ("bloqueado",
                        f"Sua assinatura venceu em {data.strftime('%d/%m/%Y')}. "
                        "Renove pra continuar usando.", perfil)
        except Exception:
            pass
    return "ok", "", perfil


# ── Login ────────────────────────────────────────────────────────────
def entrar(email, senha):
    """Login com email e senha. Roda em thread — pode demorar."""
    email = (email or "").strip().lower()
    senha = senha or ""

    if not email or not senha:
        return Resultado(False, "Preencha email e senha.")
    if not EMAIL_RE.match(email):
        return Resultado(False, "Digite um email válido (ex: seu@email.com).")

    # O build de produção nunca libera acesso sem o Supabase configurado.
    if not config.configurado():
        return Resultado(False, "Servidor de login não configurado. "
                                "Fale com o suporte para concluir a instalação.")

    resp = http.post(f"{config.base_auth()}/token?grant_type=password",
                     {"email": email, "password": senha})

    if not resp.ok or not (resp.dados or {}).get("access_token"):
        return Resultado(False, resp.erro or "Email ou senha incorretos.",
                         offline=resp.offline)

    dados = resp.dados
    sessao = {
        "access_token": dados["access_token"],
        "refresh_token": dados.get("refresh_token"),
        "expira_em_ts": int(time.time()) + int(dados.get("expires_in", 3600)),
        "user": dados.get("user") or {"email": email},
    }

    situacao, motivo, perfil = _checar_perfil(user_id(sessao), sessao["access_token"])
    if situacao == "bloqueado":
        session.remover()
        return Resultado(False, motivo)
    if situacao == "ok":
        sessao["perfil_ok_em"] = int(time.time())
    if perfil:
        sessao["perfil"] = perfil

    return Resultado(True, "Login realizado.", session.salvar(sessao))


def sair():
    """Logout local. Também avisa o servidor pra invalidar o refresh.

    O que vale é apagar a sessão daqui, e isso é feito NA HORA. O aviso
    ao servidor vai numa thread: ele levava até 5 segundos de espera de
    rede — e como esta função é chamada quando o cliente clica em "Sair"
    ou "Trocar de conta", o app ficava parado nesse tempo todo, com cara
    de travado (ou nem fechava, se a internet estivesse ruim).
    """
    sessao = session.carregar()
    token = (sessao or {}).get("access_token")
    resultado = session.remover()

    if token and config.configurado():
        threading.Thread(target=_avisar_logout, args=(token,),
                         daemon=True).start()
    return resultado


def _avisar_logout(token):
    try:
        http.post(f"{config.base_auth()}/logout", {}, token=token, timeout=5)
    except Exception:
        pass          # servidor fora do ar não pode atrapalhar quem quer sair


# ── Renovação ────────────────────────────────────────────────────────
def _renovar(sessao):
    """Troca o refresh_token por um access_token novo.
    Devolve (situacao, sessao_ou_msg): "ok" | "invalida" | "offline"."""
    if not config.configurado():
        return "invalida", "Servidor de login não configurado."

    rt = sessao.get("refresh_token")
    if not rt:
        return "invalida", "Sua sessão expirou. Faça login de novo."

    resp = http.post(f"{config.base_auth()}/token?grant_type=refresh_token",
                     {"refresh_token": rt})
    if resp.offline:
        return "offline", resp.erro
    if not resp.ok or not (resp.dados or {}).get("access_token"):
        return "invalida", resp.erro or "Sua sessão expirou. Faça login de novo."

    dados = resp.dados
    sessao["access_token"] = dados["access_token"]
    sessao["refresh_token"] = dados.get("refresh_token", rt)
    sessao["expira_em_ts"] = int(time.time()) + int(dados.get("expires_in", 3600))
    sessao["user"] = dados.get("user") or sessao.get("user", {})
    return "ok", session.salvar(sessao)


def token_valido():
    """Access token pronto pra usar numa consulta (renova se venceu).
    Usado por backend.content. Devolve None se não dá pra renovar."""
    sessao = session.carregar()
    if not sessao or sessao_vencida(sessao):
        return None
    if not _token_expirado(sessao):
        return sessao.get("access_token")
    situacao, resultado = _renovar(sessao)
    if situacao == "ok":
        return resultado.get("access_token")
    return None


# ── Verificação no boot ──────────────────────────────────────────────
def verificar():
    """Chamada quando o app abre (em thread). Devolve dict:

        status:   "ok" | "login" | "bloqueado"
        mensagem: texto pra mostrar
        sessao:   sessão válida (quando status == "ok")
        offline:  True se entrou usando o período sem internet
    """
    sessao = session.carregar()
    if not sessao:
        return {"status": "login", "mensagem": "", "sessao": None}

    # prazo do login: vem ANTES do cache e do modo demo, senão a sessão
    # guardada entraria direto sem nunca conferir o prazo
    if sessao_vencida(sessao):
        session.remover()
        return {"status": "login", "sessao": None,
                "mensagem": MSG_PRAZO.format(dias=config.MAX_DIAS_SESSAO)}

    if sessao.get("demo"):
        session.remover()
        return {"status": "login", "mensagem": "Sessão antiga inválida.",
                "sessao": None}

    verificada_em = sessao.get("verificada_em", 0)

    # 1) sessão conferida faz pouco tempo: entra direto, sem rede
    if session.horas_desde(verificada_em) < config.CACHE_HORAS:
        return {"status": "ok", "mensagem": "", "sessao": sessao}

    # 2) precisa revalidar
    situacao, resultado = _renovar(sessao)

    if situacao == "invalida":
        session.remover()
        return {"status": "login", "mensagem": resultado, "sessao": None}

    if situacao == "offline":
        if session.dias_desde(verificada_em) < config.MAX_DIAS_OFFLINE:
            return {"status": "ok", "sessao": sessao, "offline": True,
                    "mensagem": "Sem internet — usando a última sessão válida."}
        session.remover()
        return {"status": "login", "sessao": None,
                "mensagem": "Você ficou muitos dias sem conexão. Entre de novo."}

    sessao = resultado
    estado, motivo, perfil = _checar_perfil(user_id(sessao), sessao["access_token"])

    if estado == "bloqueado":
        session.remover()
        return {"status": "bloqueado", "mensagem": motivo, "sessao": None}

    if estado == "indeterminado":
        # não deu pra confirmar: vale o último "ok" conhecido por alguns dias
        if session.dias_desde(sessao.get("perfil_ok_em", 0)) < config.GRACA_PERFIL_DIAS:
            return {"status": "ok", "sessao": session.salvar(sessao),
                    "mensagem": "Não consegui confirmar sua assinatura agora."}
        session.remover()
        return {"status": "bloqueado", "sessao": None,
                "mensagem": ("Não consegui confirmar sua assinatura. "
                             "Conecte à internet e entre de novo, ou fale com o suporte.")}

    sessao["perfil_ok_em"] = int(time.time())
    if perfil:
        sessao["perfil"] = perfil
    return {"status": "ok", "mensagem": "", "sessao": session.salvar(sessao)}


# ── Senha ────────────────────────────────────────────────────────────
def recuperar_senha(email):
    email = (email or "").strip().lower()
    if not email:
        return Resultado(False, "Digite seu email primeiro.")
    if not EMAIL_RE.match(email):
        return Resultado(False, "Digite um email válido (ex: seu@email.com).")
    if not config.configurado():
        return Resultado(False, "Recuperação de senha indisponível no modo demo.")

    resp = http.post(f"{config.base_auth()}/recover", {"email": email})
    if resp.status in (200, 204):
        return Resultado(True, f"Enviei um email para {email} com o link "
                               "pra criar uma senha nova. Confira também o spam.")
    return Resultado(False, resp.erro or "Não consegui enviar o email.")


def precisa_criar_senha(sessao):
    """True quando o usuário entrou com a senha temporária que recebeu
    por email e ainda não escolheu a definitiva."""
    meta = (usuario(sessao).get("user_metadata") or {})
    return bool(meta.get("primeira_senha"))


def definir_senha(nova, confirmacao=None):
    """Troca a senha do usuário logado e limpa a marca de senha temporária."""
    nova = nova or ""
    if confirmacao is not None and nova != confirmacao:
        return Resultado(False, "As duas senhas não são iguais.")

    forca, aviso = forca_senha(nova)
    if forca < 2:
        return Resultado(False, aviso)

    sessao = session.carregar()
    if not sessao or not sessao.get("access_token"):
        return Resultado(False, "Você precisa estar logado.")

    if not config.configurado():
        return Resultado(False, "Servidor de login não configurado.")

    token = token_valido() or sessao["access_token"]
    resp = http.put(f"{config.base_auth()}/user",
                    {"password": nova, "data": {"primeira_senha": False}},
                    token=token)
    if not resp.ok:
        return Resultado(False, resp.erro or "Não consegui atualizar a senha.")

    if isinstance(resp.dados, dict) and resp.dados:
        sessao["user"] = resp.dados
    return Resultado(True, "Senha atualizada com sucesso.", session.salvar(sessao))


def forca_senha(senha):
    """(nota de 0 a 4, dica) — usada na barrinha de força da tela de senha."""
    senha = senha or ""
    if len(senha) < config.SENHA_MINIMA:
        return 0, f"Use pelo menos {config.SENHA_MINIMA} caracteres."

    nota = 1
    if re.search(r"[a-z]", senha) and re.search(r"[A-Z]", senha):
        nota += 1
    if re.search(r"\d", senha):
        nota += 1
    if re.search(r"[^\w\s]", senha):
        nota += 1
    if len(senha) >= 12:
        nota = min(4, nota + 1)

    comuns = {"12345678", "senha123", "password", "libertytube123", "qwertyui"}
    if senha.lower() in comuns:
        return 1, "Essa senha é muito comum. Escolha outra."

    dicas = {
        1: "Senha fraca — misture letras maiúsculas e números.",
        2: "Senha razoável — dá pra melhorar com um símbolo (!, @, #).",
        3: "Senha boa.",
        4: "Senha forte.",
    }
    return nota, dicas[nota]
