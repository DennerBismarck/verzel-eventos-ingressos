"""
Popula o banco com os dados de teste exigidos pelo enunciado:
1 organizador, 2 clientes, 1 usuário de portaria e (a partir do Dia 1)
1 evento publicado com ingressos disponíveis.

Uso:  python manage.py seed
      python manage.py seed --reset   (apaga os usuários de seed antes)

Idempotente: rodar duas vezes não duplica nada, porque usa get_or_create.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from events.models import Event

User = get_user_model()

SENHA_PADRAO = "verzel123"

USUARIOS = [
    ("organizador@verzel.dev", "Olívia Organizadora", User.Role.ORGANIZER),
    ("cliente1@verzel.dev", "Caio Cliente", User.Role.CUSTOMER),
    ("cliente2@verzel.dev", "Clara Cliente", User.Role.CUSTOMER),
    ("portaria@verzel.dev", "Pedro Portaria", User.Role.GATE),
]

# (external_id, título, local, dias_a_partir_de_hoje, preço, capacidade, status)
# Datas relativas a hoje: o seed nunca "vence". Um evento com data fixa no
# passado sumiria da vitrine meses depois e o avaliador acharia que quebrou.
EVENTOS = [
    ("693134", "Duna: Parte Dois", "Cinemark Eldorado, São Paulo", 7,
     "42.00", 120, Event.Status.PUBLISHED),
    ("157336", "Interestelar (reexibição)", "Petra Belas Artes, São Paulo", 12,
     "38.50", 80, Event.Status.PUBLISHED),
    ("27205", "A Origem", "Cine Belas Artes, São Paulo", 21,
     "35.00", 60, Event.Status.PUBLISHED),
    ("155", "Batman: O Cavaleiro das Trevas", "Reserva Cultural, São Paulo", 30,
     "40.00", 50, Event.Status.DRAFT),
]


class Command(BaseCommand):
    help = "Cria os dados de teste (usuários dos 3 papéis + evento publicado)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Apaga os usuários de seed antes de recriar.",
        )

    # Tudo ou nada: se um usuário falhar, nenhum é criado e o banco
    # não fica num meio-termo estranho.
    @transaction.atomic
    def handle(self, *args, **options):
        emails = [email for email, _, _ in USUARIOS]

        if options["reset"]:
            # Os eventos saem PRIMEIRO. Event.organizer é PROTECT: apagar o
            # organizador antes levantaria ProtectedError. É a constraint
            # fazendo o trabalho dela — nos obrigando a decidir a ordem.
            Event.objects.filter(organizer__email__in=emails).delete()
            apagados, _ = User.objects.filter(email__in=emails).delete()
            self.stdout.write(self.style.WARNING(f"Removidos {apagados} registros de seed."))

        for email, nome, papel in USUARIOS:
            user, criado = User.objects.get_or_create(
                email=email,
                defaults={"full_name": nome, "role": papel},
            )
            if criado:
                user.set_password(SENHA_PADRAO)
                user.save(update_fields=["password"])
                self.stdout.write(self.style.SUCCESS(f"  + {email} ({papel})"))
            else:
                self.stdout.write(f"  = {email} já existia")

        organizador = User.objects.get(email="organizador@verzel.dev")
        agora = timezone.now()

        for ext_id, titulo, local, dias, preco, capacidade, status in EVENTOS:
            evento, criado = Event.objects.get_or_create(
                source=Event.Source.TMDB,
                external_id=ext_id,
                organizer=organizador,
                defaults={
                    "title": titulo,
                    "description": f"Sessão especial de {titulo}. Evento de demonstração do seed.",
                    "image_url": "",
                    "venue": local,
                    "starts_at": agora + timedelta(days=dias),
                    "kind": Event.Kind.GA,
                    "status": status,
                    "price": Decimal(preco),
                    "capacity": capacidade,
                },
            )
            marca = "+" if criado else "="
            self.stdout.write(f"  {marca} {titulo} ({status}, {capacidade} lugares)")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Seed pronto. Senha de todos: {SENHA_PADRAO}"))
