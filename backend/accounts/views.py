from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView

from .serializers import (
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


class LoginView(TokenObtainPairView):
    """POST /api/auth/login — devolve access, refresh e o usuário."""

    serializer_class = RoleTokenObtainPairSerializer
    permission_classes = [permissions.AllowAny]


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

    def get(self, request):
        return Response({"status": "ok", "service": "eventos-ingressos-api"})
