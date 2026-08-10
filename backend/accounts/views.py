from rest_framework import generics, permissions, status
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .throttling import ForcaBrutaThrottle
from .serializers import (
    LogoutSerializer,
    RegisterSerializer,
    RoleTokenObtainPairSerializer,
    UserSerializer,
)


class RegisterView(generics.CreateAPIView):
    """POST /api/auth/register — cria conta com um dos 3 papéis."""

    serializer_class = RegisterSerializer
    # Precisa ser aberto: quem se cadastra ainda não tem token.
    # (Lembrar: o default do projeto é IsAuthenticated.)
    permission_classes = [permissions.AllowAny]
    # Escopo "auth": 10/min. Cadastro aberto sem limite é convite para encher
    # a base de contas automáticas.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class LoginView(TokenObtainPairView):
    """POST /api/auth/login — devolve access, refresh e o usuário."""

    serializer_class = RoleTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]
    # O limite mais importante do projeto. Chaveado pela CONTA ALVO, não pelo
    # IP: um atacante rotaciona endereço com facilidade, mas o e-mail que ele
    # quer invadir continua o mesmo. Ver accounts/throttling.py.
    throttle_classes = [ForcaBrutaThrottle]

    def check_throttles(self, request):
        """
        Igual ao do DRF, com uma diferença: guarda as instâncias.

        O `check_throttles` original cria os throttles, usa e descarta. Aqui
        eles precisam sobreviver até depois da resposta, porque quem sabe se a
        credencial prestava é o serializer — e é esse desfecho que decide se a
        tentativa gasta cota.
        """
        self.limites = self.get_throttles()
        esperas = [
            limite.wait()
            for limite in self.limites
            if not limite.allow_request(request, self)
        ]
        if esperas:
            self.throttled(request, max((e for e in esperas if e is not None), default=None))

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except (AuthenticationFailed, ValidationError):
            # Senha errada, e-mail que não existe ou corpo sem os campos: as
            # três formas de martelar a porta. Só aqui a cota é gasta.
            for limite in self.limites:
                limite.registrar_falha()
            raise


class RefreshView(TokenRefreshView):
    """POST /api/auth/refresh — troca o refresh por um access novo."""

    # Mesmo escopo do login: quem tenta adivinhar refresh token está fazendo
    # força bruta igual, só que noutra porta.
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth"


class LogoutView(APIView):
    """
    POST /api/auth/logout — revoga o refresh token.

    Sem isto, "sair" apagava o token do navegador e torcia. Quem já tivesse
    uma cópia do refresh (log, backup, extensão maliciosa) seguiria emitindo
    access novos por 7 dias, mesmo depois do usuário achar que tinha saído.

    O access em si continua válido até expirar — é a natureza de um token
    autocontido, que não é consultado no banco a cada uso. Por isso ele dura
    60 minutos e não uma semana: é a janela que se aceita nesse desenho.
    """

    # AllowAny de propósito: a credencial desta operação é o PRÓPRIO refresh
    # token enviado no corpo. Exigir um access válido impediria de revogar
    # justamente quem mais precisa — alguém cujo access já expirou, ou que
    # desconfia que a sessão vazou.
    permission_classes = [permissions.AllowAny]
    serializer_class = LogoutSerializer

    def post(self, request):
        entrada = LogoutSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        try:
            RefreshToken(entrada.validated_data["refresh"]).blacklist()
        except TokenError:
            # Token já expirado, já revogado ou malformado. O resultado que o
            # usuário queria — não valer mais — já está garantido, então isso
            # não é erro. Responder 400 aqui só deixaria a tela presa numa
            # falha que não importa.
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(generics.RetrieveAPIView):
    """GET /api/auth/me — quem sou eu, segundo o token enviado."""

    serializer_class = UserSerializer

    def get_object(self):
        # request.user é preenchido pela JWTAuthentication a partir do
        # header Authorization: Bearer <access>.
        return self.request.user


class HealthView(APIView):
    """
    GET /api/health — o "hello world" que vamos usar pra provar que o
    deploy está de pé e que o front conversa com o back.
    """

    permission_classes = [permissions.AllowAny]
    # Sem limite: é o endpoint que o monitoramento da Render bate de minuto em
    # minuto para saber se o serviço está vivo. Limitar derrubaria o healthcheck.
    throttle_classes = []

    def get(self, request):
        return Response({"status": "ok", "service": "eventos-ingressos-api"})
