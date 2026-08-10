"""
Assinatura do ingresso (HMAC-SHA256).

O problema: se o QR carregasse só o código do ingresso, qualquer um geraria um
QR com um UUID inventado. A portaria consultaria o banco, não acharia, e
recusaria — mas isso vale para códigos falsos. O risco real é outro: um código
*adivinhado* ou *vazado* de outra pessoa viraria entrada válida.

A solução: o QR carrega `código.assinatura`, onde a assinatura é
HMAC-SHA256 do código com uma chave que só o servidor tem. Sem a chave,
não existe assinatura válida — nem para um código inventado, nem para um
código real roubado de outro ingresso, porque a assinatura é presa AO código.

Por que HMAC e não "só um hash SHA256 do código": um hash puro é público —
qualquer um calcula `sha256(code)`. O que torna a assinatura infalsificável é
o SEGREDO que entra no cálculo, e HMAC é a construção correta para misturar
chave e mensagem (concatenar chave + mensagem num hash tem fraquezas conhecidas,
como o length-extension attack).
"""

import hmac
from hashlib import sha256

from django.conf import settings

SEPARATOR = "."


def _key() -> bytes:
    # TICKET_SIGNING_KEY é separada da SECRET_KEY do Django de propósito:
    # rotacionar a chave de sessão não deve invalidar ingressos já emitidos.
    return settings.TICKET_SIGNING_KEY.encode()


def sign_code(code) -> str:
    """Assinatura hexadecimal do código."""
    return hmac.new(_key(), str(code).encode(), sha256).hexdigest()


def build_payload(code) -> str:
    """`código.assinatura` — exatamente o que é desenhado no QR."""
    return f"{code}{SEPARATOR}{sign_code(code)}"


def parse_payload(payload: str):
    """
    Valida o conteúdo lido do QR e devolve o código, ou None.

    None significa "não confie": formato errado ou assinatura que não bate.
    A view decide o que fazer; aqui não se levanta exceção, porque entrada
    inválida na portaria é rotina (QR sujo, foto tremida), não excepcional.
    """
    if not payload or SEPARATOR not in payload:
        return None

    code, _, signature = payload.strip().rpartition(SEPARATOR)
    if not code or not signature:
        return None

    # compare_digest e não '==': a comparação normal de strings sai no primeiro
    # byte diferente, e o TEMPO dessa saída vaza quantos bytes acertaram. Com
    # medições repetidas dá para descobrir a assinatura byte a byte (timing
    # attack). compare_digest sempre gasta o mesmo tempo.
    if not hmac.compare_digest(sign_code(code), signature):
        return None

    return code
