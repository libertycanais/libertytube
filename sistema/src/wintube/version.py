"""Versão única do LibertyTube.

Todo mundo (dashboard, atualizador, instalador, popup de novidades) lê
daqui. Na 2.48 a versão estava escrita em três lugares diferentes e o
atualizador comparava "2.2.0" com "2.48" — nunca batia.
"""

VERSAO = "1.0.0"
NOME = "LibertyTube"
TITULO_JANELA = "LibertyTube"

# Canal de atualização (o versao.json publicado no seu domínio).
URL_ATUALIZACAO = "https://libertytube.com.br/app/versao.json"


def _ordem(versao):
    """Chave de comparação de versões.

    Cuidado com a numeração antiga: a linha velha ia até 2.48 (versão 48
    da série 2), e a nova é 2.6.0, 2.6.1… Comparando só os números,
    2.48 > 2.6.1 e o app acharia que a versão antiga é mais nova — foi
    exatamente isso que fazia o popup de novidades listar a 2.48 inteira
    pra quem já estava na 2.6.

    Regra: qualquer "2.N" com dois números e N >= 7 é da linha velha e
    vem SEMPRE antes de qualquer versão da linha nova.
    """
    partes = [int(p) for p in str(versao).replace(",", ".").split(".") if p.isdigit()]
    if not partes:
        return (0, [0])
    linha_velha = len(partes) == 2 and partes[0] == 2 and partes[1] >= 7
    return (0 if linha_velha else 1, partes)


def maior_que(a, b):
    """True se a versão `a` for mais nova que `b`."""
    linha_a, partes_a = _ordem(a)
    linha_b, partes_b = _ordem(b)
    if linha_a != linha_b:
        return linha_a > linha_b
    tamanho = max(len(partes_a), len(partes_b))
    partes_a = partes_a + [0] * (tamanho - len(partes_a))
    partes_b = partes_b + [0] * (tamanho - len(partes_b))
    return partes_a > partes_b
