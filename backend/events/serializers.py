"""
Serializers de evento.

Dois serializers para o mesmo model, de propósito:

  - EventPublicSerializer  -> o que o cliente vê. Não expõe `sold_count` nem
    dados do organizador. Um serializer só, com campos "escondidos" via lógica,
    é onde vaza informação por descuido.
  - EventSerializer        -> o que o organizador manda e recebe.
"""

from django.utils import timezone
from rest_framework import serializers

from .models import Event, Seat


class EventPublicSerializer(serializers.ModelSerializer):
    available = serializers.IntegerField(read_only=True)
    organizer_name = serializers.CharField(source="organizer.full_name", read_only=True)
    # O "a partir de" da vitrine. Em lugar marcado, `price` é zero e o valor
    # real está nas poltronas — ver Event.price_from.
    price_from = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Event
        fields = (
            "id", "title", "description", "image_url", "venue", "starts_at",
            "kind", "price", "price_from", "available", "organizer_name", "source",
        )


class EventSerializer(serializers.ModelSerializer):
    available = serializers.IntegerField(read_only=True)
    price_from = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Event
        fields = (
            "id", "source", "external_id", "title", "description", "image_url",
            "venue", "starts_at", "kind", "status", "price", "price_from",
            "capacity", "sold_count", "available", "created_at",
        )
        # organizer nunca vem do corpo do request: vem de request.user. Se viesse
        # do JSON, um organizador criaria evento no nome de outro.
        # sold_count nunca vem do corpo: só a lógica de reserva mexe nele.
        read_only_fields = ("sold_count", "created_at")

    def validate_starts_at(self, value):
        if value <= timezone.now():
            raise serializers.ValidationError("O evento precisa começar no futuro.")
        return value

    def validate(self, attrs):
        # Em update parcial (PATCH) os campos ausentes vêm do objeto existente.
        kind = attrs.get("kind", getattr(self.instance, "kind", Event.Kind.GA))
        capacity = attrs.get("capacity", getattr(self.instance, "capacity", 0))
        status = attrs.get("status", getattr(self.instance, "status", Event.Status.DRAFT))

        if kind == Event.Kind.GA and status == Event.Status.PUBLISHED and capacity < 1:
            raise serializers.ValidationError(
                {"capacity": "Um evento de pista publicado precisa de capacidade maior que zero."}
            )

        # Reduzir a capacidade abaixo do que já foi vendido deixaria o banco em
        # estado que a própria CheckConstraint recusa. Erro 400 explica; 500 não.
        sold = getattr(self.instance, "sold_count", 0)
        if capacity < sold:
            raise serializers.ValidationError(
                {"capacity": f"Já foram vendidos {sold} ingressos; a capacidade não pode ser menor."}
            )
        return attrs


class SeatSerializer(serializers.ModelSerializer):
    class Meta:
        model = Seat
        fields = ("id", "section", "row", "number", "price", "status")


class SeatSectionSerializer(serializers.Serializer):
    """Uma seção do mapa: N filas × M lugares, todos ao mesmo preço."""

    name = serializers.CharField(max_length=30)
    rows = serializers.ListField(child=serializers.CharField(max_length=10), min_length=1)
    seats_per_row = serializers.IntegerField(min_value=1, max_value=100)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=0)


class SeatLayoutSerializer(serializers.Serializer):
    sections = SeatSectionSerializer(many=True, min_length=1)


class CatalogItemSerializer(serializers.Serializer):
    """Só para o Swagger: o catálogo não tem model por trás, é proxy de API externa."""

    source = serializers.CharField()
    external_id = serializers.CharField()
    title = serializers.CharField()
    description = serializers.CharField(allow_blank=True)
    image_url = serializers.CharField(allow_blank=True)
    venue = serializers.CharField(allow_blank=True)
    starts_at = serializers.DateTimeField(allow_null=True)
