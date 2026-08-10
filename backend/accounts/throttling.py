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
    """
    Limita tentativas contra UMA conta, independente de onde vêm.

    Conta só o que FALHA. Força bruta é, por definição, uma sequência de erros:
    quem acerta a senha não está adivinhando. Cobrar cota do acerto punia o uso
    legítimo — a pessoa que entra no celular, no tablet e no computador gastava
    o mesmo orçamento do atacante — sem tirar nada do atacante, que erra de
    qualquer jeito.

    Não abre brecha: quem já tem a senha certa não precisa de força bruta, e
    limitar o login dele não protegeria conta nenhuma.
    """

    scope = "auth"

    def allow_request(self, request, view):
        """
        Só CONSULTA o histórico. Quem grava é `registrar_falha()`, chamado pela
        view depois de saber que a credencial não prestava — é a única camada
        que conhece o desfecho.
        """
        self.key = self.get_cache_key(request, view)
        self.now = self.timer()
        self.history = [
            quando
            for quando in self.cache.get(self.key, [])
            if quando > self.now - self.duration
        ]

        if len(self.history) >= self.num_requests:
            return self.throttle_failure()
        return True

    def registrar_falha(self):
        """Gasta uma cota. Chamado só quando a tentativa foi recusada."""
        self.history.insert(0, self.now)
        self.cache.set(self.key, self.history, self.duration)

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
