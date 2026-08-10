"""Serializers de reserva e ingresso."""

from rest_framework import serializers

from .models import Payment, Reservation, Ticket


class ReservationCreateSerializer(serializers.Serializer):
    event = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    seats = serializers.ListField(child=serializers.IntegerField(), required=False)


class TicketSerializer(serializers.ModelSerializer):
    """Ingresso do DONO. Só aqui o payload do QR é exposto."""

    event_title = serializers.CharField(source="event.title", read_only=True)
    event_starts_at = serializers.DateTimeField(source="event.starts_at", read_only=True)
    venue = serializers.CharField(source="event.venue", read_only=True)
    seat_label = serializers.SerializerMethodField()
    qr_payload = serializers.CharField(read_only=True)

    class Meta:
        model = Ticket
        fields = (
            "id", "code", "status", "used_at", "qr_payload", "share_token",
            "event", "event_title", "event_starts_at", "venue", "seat_label",
        )

    def get_seat_label(self, obj):
        return str(obj.seat) if obj.seat else None


class SharedTicketSerializer(serializers.ModelSerializer):
    """
    Ingresso visto por quem recebeu o LINK. Somente leitura.

    Note o que NÃO está aqui: `code` e `qr_payload`. Quem abre o link vê que o
    ingresso existe, para qual evento e se já foi usado — mas não recebe o que
    valida a entrada. Compartilhar a visualização não é ceder o acesso.
    """

    event_title = serializers.CharField(source="event.title", read_only=True)
    event_starts_at = serializers.DateTimeField(source="event.starts_at", read_only=True)
    venue = serializers.CharField(source="event.venue", read_only=True)
    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    seat_label = serializers.SerializerMethodField()

    class Meta:
        model = Ticket
        fields = (
            "status", "event_title", "event_starts_at", "venue",
            "customer_name", "seat_label",
        )

    def get_seat_label(self, obj):
        return str(obj.seat) if obj.seat else None


class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = ("id", "status", "reason", "created_at")


class ReservationSerializer(serializers.ModelSerializer):
    event_title = serializers.CharField(source="event.title", read_only=True)
    event_starts_at = serializers.DateTimeField(source="event.starts_at", read_only=True)
    tickets = TicketSerializer(many=True, read_only=True)
    payments = PaymentSerializer(many=True, read_only=True)

    class Meta:
        model = Reservation
        fields = (
            "id", "event", "event_title", "event_starts_at", "status",
            "quantity", "total_price", "created_at", "tickets", "payments",
        )


class GateValidateSerializer(serializers.Serializer):
    # O conteúdo lido do QR ("codigo.assinatura") OU o código digitado à mão.
    payload = serializers.CharField()
    # A portaria escolhe o evento na tela antes de começar a validar. Sem isso
    # não dá para responder "evento errado" — que é um dos 4 retornos exigidos.
    event = serializers.IntegerField()
