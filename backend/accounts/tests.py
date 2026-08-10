"""
Testes de autenticação e papéis.

O foco aqui não é "o Django sabe criar usuário" — é o que o PROJETO decidiu:
login por e-mail, papel dentro do JWT, e permissão negada por padrão. Cada
teste amarra uma dessas decisões para que ninguém a desfaça sem perceber.
"""

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

User = get_user_model()

SENHA = "verzel123456"


class UserModelTest(APITestCase):
    def test_cria_usuario_com_email_e_sem_username(self):
        u = User.objects.create_user(email="a@b.dev", password=SENHA, full_name="A")
        self.assertEqual(u.email, "a@b.dev")
        # username foi removido do model: o identificador é o e-mail.
        self.assertIsNone(u.username)
        self.assertEqual(User.USERNAME_FIELD, "email")

    def test_senha_e_guardada_com_hash(self):
        u = User.objects.create_user(email="a@b.dev", password=SENHA, full_name="A")
        self.assertNotEqual(u.password, SENHA)
        self.assertTrue(u.check_password(SENHA))

    def test_dominio_do_email_e_normalizado(self):
        u = User.objects.create_user(email="a@B.DEV", password=SENHA, full_name="A")
        self.assertEqual(u.email, "a@b.dev")

    def test_usuario_sem_email_e_recusado(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(email="", password=SENHA, full_name="A")

    def test_papel_padrao_e_cliente(self):
        u = User.objects.create_user(email="a@b.dev", password=SENHA, full_name="A")
        self.assertEqual(u.role, User.Role.CUSTOMER)
        self.assertTrue(u.is_customer)
        self.assertFalse(u.is_organizer)

    def test_superuser_tem_as_flags(self):
        u = User.objects.create_superuser(email="root@b.dev", password=SENHA, full_name="Root")
        self.assertTrue(u.is_staff)
        self.assertTrue(u.is_superuser)

    def test_email_e_unico(self):
        User.objects.create_user(email="a@b.dev", password=SENHA, full_name="A")
        from django.db import IntegrityError

        with self.assertRaises(IntegrityError):
            User.objects.create_user(email="a@b.dev", password=SENHA, full_name="Outro")


class RegisterTest(APITestCase):
    def setUp(self):
        self.url = reverse("register")

    def test_cria_conta_e_devolve_201(self):
        r = self.client.post(
            self.url,
            {"email": "novo@b.dev", "password": SENHA, "full_name": "Novo", "role": "ORGANIZER"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(User.objects.get(email="novo@b.dev").role, "ORGANIZER")

    def test_senha_nao_volta_na_resposta(self):
        r = self.client.post(
            self.url,
            {"email": "novo@b.dev", "password": SENHA, "full_name": "Novo", "role": "CUSTOMER"},
            format="json",
        )
        self.assertNotIn("password", r.json())

    def test_senha_fraca_e_recusada(self):
        r = self.client.post(
            self.url,
            {"email": "novo@b.dev", "password": "123", "full_name": "Novo", "role": "CUSTOMER"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("password", r.json())

    def test_email_repetido_e_recusado(self):
        User.objects.create_user(email="a@b.dev", password=SENHA, full_name="A")
        r = self.client.post(
            self.url,
            {"email": "a@b.dev", "password": SENHA, "full_name": "Outro", "role": "CUSTOMER"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("email", r.json())

    def test_papel_inexistente_e_recusado(self):
        """Sem isto, um POST com role='ADMIN' criaria um papel que não existe."""
        r = self.client.post(
            self.url,
            {"email": "novo@b.dev", "password": SENHA, "full_name": "Novo", "role": "ADMIN"},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("role", r.json())

    def test_nao_da_pra_se_promover_a_staff_pelo_cadastro(self):
        """is_staff não está no serializer: mandar no corpo tem que ser ignorado."""
        self.client.post(
            self.url,
            {
                "email": "novo@b.dev", "password": SENHA, "full_name": "Novo",
                "role": "CUSTOMER", "is_staff": True, "is_superuser": True,
            },
            format="json",
        )
        u = User.objects.get(email="novo@b.dev")
        self.assertFalse(u.is_staff)
        self.assertFalse(u.is_superuser)


class LoginTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@b.dev", password=SENHA, full_name="Ana", role=User.Role.GATE
        )

    def test_login_devolve_par_de_tokens_e_o_usuario(self):
        r = self.client.post(
            reverse("login"), {"email": "a@b.dev", "password": SENHA}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        corpo = r.json()
        self.assertIn("access", corpo)
        self.assertIn("refresh", corpo)
        self.assertEqual(corpo["user"]["role"], "GATE")

    def test_papel_viaja_dentro_do_token(self):
        """
        O front lê o papel do próprio token para montar o menu, sem uma 2ª
        chamada. Só é seguro porque o token é assinado — e é isto que garante
        que a claim continua sendo emitida.
        """
        from rest_framework_simplejwt.tokens import AccessToken

        r = self.client.post(
            reverse("login"), {"email": "a@b.dev", "password": SENHA}, format="json"
        )
        token = AccessToken(r.json()["access"])
        self.assertEqual(token["role"], "GATE")
        self.assertEqual(token["email"], "a@b.dev")

    def test_senha_errada_devolve_401(self):
        r = self.client.post(
            reverse("login"), {"email": "a@b.dev", "password": "errada"}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_usuario_inexistente_devolve_401_e_nao_404(self):
        """404 revelaria quais e-mails existem na base."""
        r = self.client.post(
            reverse("login"), {"email": "ninguem@b.dev", "password": SENHA}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_refresh_troca_por_um_novo_access(self):
        r = self.client.post(
            reverse("login"), {"email": "a@b.dev", "password": SENHA}, format="json"
        )
        novo = self.client.post(
            reverse("token-refresh"), {"refresh": r.json()["refresh"]}, format="json"
        )
        self.assertEqual(novo.status_code, status.HTTP_200_OK)
        self.assertIn("access", novo.json())


class MeTest(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="a@b.dev", password=SENHA, full_name="Ana", role=User.Role.CUSTOMER
        )

    def test_sem_token_devolve_401(self):
        self.assertEqual(
            self.client.get(reverse("me")).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_com_token_devolve_o_usuario_do_token(self):
        self.client.force_authenticate(self.user)
        r = self.client.get(reverse("me"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()["email"], "a@b.dev")

    def test_token_invalido_devolve_401(self):
        self.client.credentials(HTTP_AUTHORIZATION="Bearer nao-e-um-token")
        self.assertEqual(
            self.client.get(reverse("me")).status_code, status.HTTP_401_UNAUTHORIZED
        )


class PermissoesPorPapelTest(APITestCase):
    """
    Amarra a regra central de autorização: cada permission class deixa passar
    UM papel e barra os outros dois. `/api/catalog/search` é usada como sonda
    por ser a rota de organizador mais barata (não toca no banco).
    """

    def setUp(self):
        self.url = reverse("catalog-search")
        self.usuarios = {
            papel: User.objects.create_user(
                email=f"{papel.lower()}@b.dev", password=SENHA, full_name=papel, role=papel
            )
            for papel in (User.Role.ORGANIZER, User.Role.CUSTOMER, User.Role.GATE)
        }

    def test_anonimo_leva_401(self):
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_cliente_e_portaria_levam_403_na_rota_de_organizador(self):
        for papel in (User.Role.CUSTOMER, User.Role.GATE):
            with self.subTest(papel=papel):
                self.client.force_authenticate(self.usuarios[papel])
                self.assertEqual(
                    self.client.get(self.url).status_code, status.HTTP_403_FORBIDDEN
                )

    def test_organizador_passa_da_permissao(self):
        self.client.force_authenticate(self.usuarios[User.Role.ORGANIZER])
        # 503 (chave ausente no ambiente de teste) já prova que a permissão
        # deixou passar: o 403 aconteceria ANTES de a view rodar.
        self.assertNotIn(
            self.client.get(self.url).status_code,
            (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN),
        )

    def test_token_de_usuario_desativado_e_recusado(self):
        """Caminho real: token emitido, conta desativada depois."""
        from rest_framework_simplejwt.tokens import AccessToken

        org = self.usuarios[User.Role.ORGANIZER]
        token = str(AccessToken.for_user(org))

        org.is_active = False
        org.save(update_fields=["is_active"])

        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        self.assertEqual(
            self.client.get(self.url).status_code, status.HTTP_401_UNAUTHORIZED
        )

    def test_permission_class_sozinha_tambem_barra_inativo(self):
        """
        Defesa em profundidade, testada SEM depender do autenticador.

        A primeira versão deste teste usava force_authenticate e passava com
        200 — mas force_authenticate pula a camada de autenticação, que é
        exatamente onde o simplejwt recusa conta inativa. O teste estava
        medindo o artifício, não o sistema. Agora ele chama a permissão
        diretamente: se alguém trocar o backend de autenticação um dia, esta
        checagem continua de pé.
        """
        from rest_framework.test import APIRequestFactory

        from .permissions import IsOrganizer

        org = self.usuarios[User.Role.ORGANIZER]
        req = APIRequestFactory().get(self.url)

        req.user = org
        self.assertTrue(IsOrganizer().has_permission(req, None))

        org.is_active = False
        self.assertFalse(IsOrganizer().has_permission(req, None))


class HealthTest(APITestCase):
    def test_health_e_publico(self):
        self.assertEqual(self.client.get(reverse("health")).status_code, status.HTTP_200_OK)
