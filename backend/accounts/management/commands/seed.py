"""
Popula o banco com os dados de teste exigidos pelo enunciado:
1 organizador, 2 clientes, 1 usuário de portaria e (a partir do Dia 1)
1 evento publicado com ingressos disponíveis.

Uso:  python manage.py seed
      python manage.py seed --reset   (apaga os usuários de seed antes)

Idempotente: rodar duas vezes não duplica nada, porque usa get_or_create.
"""

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

User = get_user_model()

SENHA_PADRAO = "verzel123"

USUARIOS = [
    ("organizador@verzel.dev", "Olívia Organizadora", User.Role.ORGANIZER),
    ("cliente1@verzel.dev", "Caio Cliente", User.Role.CUSTOMER),
    ("cliente2@verzel.dev", "Clara Cliente", User.Role.CUSTOMER),
    ("portaria@verzel.dev", "Pedro Portaria", User.Role.GATE),
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

        # TODO (Dia 1, Denner): criar 1 evento GA publicado com capacidade > 0,
        # pertencente ao organizador acima. Sem isso o avaliador não consegue
        # percorrer o fluxo de compra sem montar tudo na mão — e o enunciado
        # pede exatamente isso.

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Seed pronto. Senha de todos: {SENHA_PADRAO}"))
