"""
Devolve ao estoque as reservas que passaram do prazo sem pagamento.

Uso:  python manage.py expirar_reservas
      python manage.py expirar_reservas --dry-run

Este comando é para quem tem agendador (cron, Celery beat, o scheduler da
plataforma). Ele NÃO é pré-requisito para o sistema estar correto: a expiração
também acontece sozinha na hora de reservar, que é o momento em que o estoque
importa. A Render no plano free não tem cron, e o sistema funciona lá mesmo
assim — foi de propósito.

O comando existe para dois casos que a expiração preguiçosa não cobre bem:
  1. evento sem tráfego nenhum, onde ninguém reserva e nada dispara a limpeza;
  2. relatório: o organizador olhando as vendas quer ver o estoque real, e não
     um número inflado por reservas mortas.
"""

from django.core.management.base import BaseCommand
from django.utils import timezone

from ticketing.models import Reservation
from ticketing.services import PRAZO_PAGAMENTO, expire_reservations


class Command(BaseCommand):
    help = "Expira reservas pendentes fora do prazo e devolve o estoque."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Só mostra o que seria expirado, sem alterar nada.",
        )

    def handle(self, *args, **options):
        limite = timezone.now() - PRAZO_PAGAMENTO
        vencidas = Reservation.objects.filter(
            status=Reservation.Status.PENDING, created_at__lt=limite
        ).select_related("event", "customer")

        if not vencidas.exists():
            self.stdout.write("Nenhuma reserva vencida.")
            return

        for r in vencidas:
            idade = timezone.now() - r.created_at
            self.stdout.write(
                f"  #{r.pk} {r.customer.email} · {r.event.title[:34]} · "
                f"{r.quantity} lugar(es) · parada há {int(idade.total_seconds() // 60)} min"
            )

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING(f"\n--dry-run: {vencidas.count()} seriam expiradas."))
            return

        total = expire_reservations()
        self.stdout.write(self.style.SUCCESS(f"\n{total} reservas expiradas; estoque devolvido."))
