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


class SaleSerializer(serializers.ModelSerializer):
    """
    Uma venda vista pelo ORGANIZADOR do evento.

    Aqui o nome e o e-mail do comprador aparecem — o organizador precisa deles
    para dar suporte a quem não achou o ingresso, e é ele quem responde pelo
    evento. O que continua fora: o `code` do ingresso. Nem o dono do evento
    precisa do que abre a catraca; para isso existe a portaria.
    """

    customer_name = serializers.CharField(source="customer.full_name", read_only=True)
    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    tickets_used = serializers.IntegerField(read_only=True)
    tickets_total = serializers.IntegerField(read_only=True)
    seats = serializers.SerializerMethodField()

    class Meta:
        model = Reservation
        fields = (
            "id", "customer_name", "customer_email", "status", "quantity",
            "total_price", "created_at", "tickets_used", "tickets_total", "seats",
        )

    def get_seats(self, obj):
        return [str(s) for s in obj.seats.all()]


class GateValidateSerializer(serializers.Serializer):
    # O conteúdo lido do QR ("codigo.assinatura") OU o código digitado à mão.
    payload = serializers.CharField()
    # A portaria escolhe o evento na tela antes de começar a validar. Sem isso
    # não dá para responder "evento errado" — que é um dos 4 retornos exigidos.
    event = serializers.IntegerField()
