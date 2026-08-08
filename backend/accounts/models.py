from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """
    O manager padrão do Django assume que existe um campo `username`.
    Como trocamos por `email`, precisamos reescrever a criação de usuários.
    """

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("E-mail é obrigatório.")
        # normalize_email deixa o domínio em minúsculas (Foo@GMAIL.com -> Foo@gmail.com),
        # evitando dois cadastros que só diferem no caixa do domínio.
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        # set_password aplica o hash (PBKDF2). Nunca guardamos a senha em texto.
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        # O superusuário existe pra administrar tudo (Django admin), então o
        # papel de organizador é o mais útil como padrão.
        extra_fields.setdefault("role", User.Role.ORGANIZER)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superusuário precisa de is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superusuário precisa de is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """
    Usuário da plataforma. Login por e-mail e um papel único.

    Decisão: papel como campo único (não Groups do Django) porque o enunciado
    define exatamente 3 papéis mutuamente exclusivos. Um CharField com choices
    é mais simples de ler, de serializar no JWT e de defender do que o sistema
    de grupos/permissões, que resolveria um problema que não temos.
    """

    class Role(models.TextChoices):
        ORGANIZER = "ORGANIZER", "Organizador"
        CUSTOMER = "CUSTOMER", "Cliente"
        GATE = "GATE", "Portaria"

    # AbstractUser traz `username` obrigatório e único. Não queremos.
    username = None
    email = models.EmailField("e-mail", unique=True)
    full_name = models.CharField("nome completo", max_length=150, blank=True)
    role = models.CharField(
        "papel",
        max_length=16,
        choices=Role.choices,
        default=Role.CUSTOMER,
        db_index=True,  # filtramos por papel com frequência
    )

    # Diz ao Django o que usar como identificador no login...
    USERNAME_FIELD = "email"
    # ...e o que mais pedir no `createsuperuser` (além de email e senha).
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    # Atalhos de leitura — deixam as views e templates mais legíveis
    # do que espalhar `user.role == "ORGANIZER"` por todo lado.
    @property
    def is_organizer(self) -> bool:
        return self.role == self.Role.ORGANIZER

    @property
    def is_customer(self) -> bool:
        return self.role == self.Role.CUSTOMER

    @property
    def is_gate(self) -> bool:
        return self.role == self.Role.GATE
