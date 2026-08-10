"""
Limites de tentativa para autenticação.

Por que uma classe própria em vez do throttle padrão do DRF: a chave.

O `ScopedRateThrottle` anônimo chaveia por IP, lido do `X-Forwarded-For`. Atrás
do proxy da Render esse valor não é estável entre requisições, e o limite
simplesmente não fecha — medido em produção: 14 tentativas de login seguidas,
14 respostas 401, nenhum 429, com o mesmo throttle funcionando perfeitamente no
endpoint autenticado do catálogo (onde a chave é o usuário).

Dá para consertar acertando `NUM_PROXIES`, mas isso vira um número mágico
acoplado à topologia do provedor — muda de plataforma, quebra em silêncio, e
"quebrar em silêncio" é a pior propriedade possível para um controle de
segurança.

A chave escolhida é a CONTA ALVO. Isso muda o que o limite significa: em vez de
"este IP tentou demais", passa a ser "esta conta está sob ataque". É o que
protege de verdade — um atacante com uma lista de senhas rotaciona IP com
facilidade, mas o alvo continua o mesmo e-mail.
"""

from rest_framework.throttling import SimpleRateThrottle


class ForcaBrutaThrottle(SimpleRateThrottle):
    """Limita tentativas contra UMA conta, independente de onde vêm."""

    scope = "auth"

    def get_cache_key(self, request, view):
        alvo = ""
        # request.data pode não ser um dict (corpo malformado): não é motivo
        # para derrubar a requisição antes de o serializer explicar o erro.
        if isinstance(request.data, dict):
            alvo = str(request.data.get("email") or "").strip().lower()

        # Sem e-mail no corpo, cai no IP. Vale menos, mas é melhor que nada:
        # cobre quem martela o endpoint com lixo.
        ident = alvo or self.get_ident(request)

        return self.cache_format % {"scope": self.scope, "ident": ident}
