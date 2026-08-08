from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class UserSerializer(serializers.ModelSerializer):
    """Representação pública do usuário. Nunca inclui senha."""

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "role")
        read_only_fields = fields


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True,
        # Roda os AUTH_PASSWORD_VALIDATORS do settings (tamanho mínimo,
        # senha comum, só números...). Reaproveita a política do Django
        # em vez de inventar uma regra nossa.
        validators=[validate_password],
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = ("id", "email", "full_name", "password", "role")

    def validate_role(self, value):
        # O papel vem do corpo da requisição, então precisa ser validado.
        # Não é uma decisão livre: o enunciado só prevê estes três.
        if value not in User.Role.values:
            raise serializers.ValidationError("Papel inválido.")
        return value

    def create(self, validated_data):
        # Usa o manager (não `User.objects.create`) para que a senha passe
        # pelo hash. `create` cru salvaria a senha em texto puro.
        return User.objects.create_user(**validated_data)


class RoleTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Login. Além do par access/refresh, embute o papel no token e devolve
    o usuário no corpo.

    Por que o papel dentro do JWT: o front precisa saber qual menu mostrar
    logo após o login, sem uma segunda chamada. O token é assinado, então o
    valor não pode ser adulterado pelo cliente.
    Atenção: isso é para a UI. A autorização real continua sendo a checagem
    no banco feita pelas permissions do DRF.
    """

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["email"] = user.email
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data
