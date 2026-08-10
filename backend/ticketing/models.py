"""
Models de reserva, pagamento e ingresso.

Fluxo: Reservation (PENDING) -> Payment -> Reservation (PAID) + N Tickets.

A reserva já segura o estoque no momento em que é criada, ANTES do pagamento.
É o que impede dois clientes de "reservar" o último lugar e só descobrirem o
conflito na hora de pagar. O estoque é liberado se a reserva for cancelada.
"""

import uuid

from django.conf import settings
from django.db import models


class Reservation(models.Model):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Aguardando pagamento"
        PAID = "PAID", "Paga"
        REFUSED = "REFUSED", "Pagamento recusado"
        CANCELLED = "CANCELLED", "Cancelada"
        # Estado próprio, e não CANCELLED: "você cancelou" e "o prazo acabou"
        # são histórias diferentes para quem lê o histórico, e a segunda pode
        # virar métrica de checkout abandonado.
        EXPIRED = "EXPIRED", "Prazo de pagamento esgotado"

    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="reservations",
    )
    event = models.ForeignKey("events.Event", on_delete=models.PROTECT, related_name="reservations")
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    quantity = models.PositiveIntegerField(default=1)
    # Assentos travados por esta reserva (vazio em eventos de pista).
    seats = models.ManyToManyField("events.Seat", blank=True, related_name="reservations")
    # O preço é CONGELADO na reserva. Se o organizador reajustar o evento
    # depois, quem já reservou paga o valor que viu — e o histórico não muda
    # retroativamente.
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            # A varredura de expiração pergunta sempre a mesma coisa:
            # "PENDING criadas antes de X?". Sem este índice ela varre a tabela
            # inteira — e roda a cada reserva nova, ou seja, no caminho quente.
            models.Index(fields=["status", "created_at"], name="reservation_expiry_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1), name="reservation_quantity_gte_1"
            ),
        ]

    def __str__(self):
        return f"Reserva #{self.pk} — {self.event.title} ({self.get_status_display()})"

    @property
    def holds_stock(self):
        """Estados em que a reserva ainda ocupa lugar no estoque."""
        return self.status in (self.Status.PENDING, self.Status.PAID)

    @property
    def expires_at(self):
        """
        Quando a reserva perde a validade, se ninguém pagar.

        Derivado de created_at em vez de virar coluna: o prazo é uma regra do
        sistema, não um dado do registro. Guardar duplicaria estado e abriria
        a chance de o banco discordar da constante.
        """
        from .services import PRAZO_PAGAMENTO

        return self.created_at + PRAZO_PAGAMENTO


class Payment(models.Model):
    """
    Pagamento SIMULADO — não há transação financeira real.

    Existe como model próprio (e não como um campo em Reservation) para
    registrar a tentativa: uma reserva recusada deixa rastro de que houve
    tentativa de pagamento, com data e motivo.
    """

    class Status(models.TextChoices):
        CONFIRMED = "CONFIRMED", "Confirmado"
        REFUSED = "REFUSED", "Recusado"

    reservation = models.ForeignKey(
        Reservation, on_delete=models.CASCADE, related_name="payments"
    )
    status = models.CharField(max_length=10, choices=Status.choices)
    reason = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Pagamento da reserva #{self.reservation_id}: {self.get_status_display()}"


class Ticket(models.Model):
    class Status(models.TextChoices):
        VALID = "VALID", "Válido"
        USED = "USED", "Utilizado"

    reservation = models.ForeignKey(Reservation, on_delete=models.PROTECT, related_name="tickets")
    # event e customer são desnormalizados de propósito: a portaria consulta o
    # ingresso pelo código e precisa do evento sem passear por reservation.
    event = models.ForeignKey("events.Event", on_delete=models.PROTECT, related_name="tickets")
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="tickets"
    )
    seat = models.ForeignKey(
        "events.Seat", on_delete=models.PROTECT, null=True, blank=True, related_name="tickets"
    )

    # O código que vai dentro do QR, junto com a assinatura HMAC.
    # uuid4 é aleatório (não sequencial): ninguém enumera ingressos chutando.
    code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    # Token do link de compartilhamento. SEPARADO do `code` de propósito:
    # quem recebe o link consegue VER o ingresso, mas o que valida a entrada é
    # o `code`, que o link não revela. Compartilhar não é ceder a entrada.
    share_token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)

    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.VALID, db_index=True
    )
    used_at = models.DateTimeField(null=True, blank=True)
    used_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="validated_tickets",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Ingresso {self.code} — {self.event.title}"

    # A assinatura NÃO é coluna: é derivável de (code + TICKET_SIGNING_KEY) a
    # qualquer momento. Guardar seria duplicar estado — e um banco vazado com a
    # assinatura junto entregaria QRs prontos em vez de só códigos.
    @property
    def signature(self):
        from .signing import sign_code

        return sign_code(self.code)

    @property
    def qr_payload(self):
        """Conteúdo exato que é codificado no QR."""
        from .signing import build_payload

        return build_payload(self.code)
