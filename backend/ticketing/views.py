"""
Views de reserva, ingresso e portaria.

Todas as regras moram em services.py. Aqui só se traduz HTTP: ler o request,
chamar o serviço, transformar ReservationError em 409.
"""

from decimal import Decimal

from django.db.models import Count, Q, Sum
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from accounts.permissions import IsCustomer, IsGate, IsOrganizer
from events.models import Event

from . import services
from .models import Reservation, Ticket
from .serializers import (
    GateValidateSerializer,
    PaymentSerializer,
    ReservationCreateSerializer,
    ReservationSerializer,
    SaleSerializer,
    SharedTicketSerializer,
    TicketSerializer,
)


class ReservationViewSet(ReadOnlyModelViewSet):
    """Reservas DO CLIENTE LOGADO, mais as ações de pagar e cancelar."""

    serializer_class = ReservationSerializer
    permission_classes = (IsCustomer,)

    def get_queryset(self):
        return (
            Reservation.objects.filter(customer=self.request.user)
            .select_related("event")
            # tickets__event e tickets__seat, e não só "tickets": o serializer
            # aninhado lê event_title, venue e seat_label de CADA ingresso.
            # Prefetchando só a coleção, cada ingresso disparava duas queries
            # próprias — medido: 17 queries para 5 reservas, e crescendo com o
            # histórico do cliente.
            .prefetch_related("tickets__event", "tickets__seat", "payments")
        )

    @extend_schema(request=ReservationCreateSerializer, responses=ReservationSerializer)
    def create(self, request):
        entrada = ReservationCreateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        dados = entrada.validated_data

        try:
            reserva = services.create_reservation(
                customer=request.user,
                event_id=dados["event"],
                quantity=dados.get("quantity", 1),
                seat_ids=dados.get("seats"),
            )
        except services.Event.DoesNotExist:
            return Response({"detail": "Evento não encontrado."}, status=status.HTTP_404_NOT_FOUND)
        except services.ReservationError as exc:
            # 409 Conflict e não 400: o pedido está bem formado, o que mudou foi
            # o ESTADO do mundo (acabou o estoque). O cliente pode tentar de
            # novo com outra quantidade e dar certo.
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(ReservationSerializer(reserva).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def pay(self, request, pk=None):
        try:
            pagamento, ingressos = services.pay_reservation(
                reservation_id=pk, customer=request.user
            )
        except Reservation.DoesNotExist:
            return Response({"detail": "Reserva não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        except services.ReservationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        corpo = {
            "payment": PaymentSerializer(pagamento).data,
            "tickets": TicketSerializer(ingressos, many=True).data,
        }
        # 402 Payment Required quando a simulação recusa: o cliente precisa
        # saber que NÃO tem ingresso, e um 200 com lista vazia seria fácil de
        # ignorar por engano no front.
        codigo = (
            status.HTTP_200_OK
            if pagamento.status == pagamento.Status.CONFIRMED
            else status.HTTP_402_PAYMENT_REQUIRED
        )
        return Response(corpo, status=codigo)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        try:
            reserva = services.cancel_reservation(reservation_id=pk, customer=request.user)
        except Reservation.DoesNotExist:
            return Response({"detail": "Reserva não encontrada."}, status=status.HTTP_404_NOT_FOUND)
        except services.ReservationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(ReservationSerializer(reserva).data)


class MyTicketsView(generics.ListAPIView):
    """Carteira de ingressos do cliente."""

    serializer_class = TicketSerializer
    permission_classes = (IsCustomer,)

    def get_queryset(self):
        return Ticket.objects.filter(customer=self.request.user).select_related(
            "event", "seat"
        )


class SharedTicketView(generics.RetrieveAPIView):
    """
    Link compartilhado — público e somente leitura.

    Busca por `share_token`, nunca por `code`. O token é um uuid4 aleatório:
    não dá para enumerar ingressos incrementando um id.
    """

    serializer_class = SharedTicketSerializer
    permission_classes = (AllowAny,)
    lookup_field = "share_token"
    queryset = Ticket.objects.select_related("event", "customer", "seat")


class OrganizerSalesView(APIView):
    """
    Vendas de UM evento do organizador logado.

    Resumo + lista de compradores. Existe porque o painel mostrava o contador
    subindo e nada mais: o organizador via "112/200 vendidos" sem saber quem
    comprou, quanto entrou, nem quantos já passaram pela portaria.
    """

    permission_classes = (IsOrganizer,)

    @extend_schema(responses=SaleSerializer(many=True))
    def get(self, request, pk):
        # get_object_or_404 com organizer=request.user: evento de outro
        # organizador não existe para este usuário. Mesmo padrão do ViewSet —
        # 404, e não 403, para não confirmar que o evento existe.
        evento = get_object_or_404(Event, pk=pk, organizer=request.user)

        reservas = (
            evento.reservations.select_related("customer")
            .prefetch_related("seats")
            # Anota no BANCO em vez de contar em Python: sem isto seriam duas
            # queries por reserva só para preencher as colunas de ingressos.
            .annotate(
                tickets_total=Count("tickets", distinct=True),
                tickets_used=Count(
                    "tickets",
                    filter=Q(tickets__status=Ticket.Status.USED),
                    distinct=True,
                ),
            )
        )

        # Uma passada por tabela em vez de quatro: as agregações que antes
        # eram Sum + count + count + count viram dois SELECTs com Count
        # condicional. Menos ida ao banco pelo mesmo resultado.
        vendas = evento.reservations.aggregate(
            receita=Sum("total_price", filter=Q(status=Reservation.Status.PAID)),
            pagas=Count("id", filter=Q(status=Reservation.Status.PAID)),
        )
        ingressos = Ticket.objects.filter(event=evento).aggregate(
            emitidos=Count("id"),
            usados=Count("id", filter=Q(status=Ticket.Status.USED)),
        )

        resumo = {
            "event_id": evento.pk,
            "event_title": evento.title,
            "capacity": evento.capacity,
            "sold_count": evento.sold_count,
            "available": evento.available,
            # Só reserva PAGA vira receita. Pendente ainda pode ser recusada,
            # e recusada/cancelada nunca entrou.
            #
            # str() com 2 casas, e não o Decimal cru: num dicionário solto o
            # renderizador do DRF serializa Decimal como NÚMERO JSON, e o
            # JavaScript o lê como float — justamente o que DecimalField evita
            # no resto da API. Dinheiro trafega como string aqui também.
            "revenue": str((vendas["receita"] or Decimal("0")).quantize(Decimal("0.01"))),
            "paid_reservations": vendas["pagas"],
            "tickets_issued": ingressos["emitidos"],
            "tickets_used": ingressos["usados"],
        }

        return Response({"summary": resumo, "sales": SaleSerializer(reservas, many=True).data})


class GateValidateView(APIView):
    """Portaria: 4 respostas possíveis — válido, inválido, já utilizado, evento errado."""

    permission_classes = (IsGate,)
    # Escopo próprio e FOLGADO: numa entrada movimentada a portaria valida em
    # rajada, e o limite padrão de usuário atrapalharia o uso legítimo — o
    # oposto do que se quer numa fila de gente esperando para entrar.
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "gate"

    @extend_schema(request=GateValidateSerializer)
    def post(self, request):
        entrada = GateValidateSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        resultado, ticket, detalhe = services.validate_ticket(
            payload=entrada.validated_data["payload"],
            event_id=entrada.validated_data["event"],
            gate_user=request.user,
        )

        corpo = {"result": resultado, "detail": detalhe}
        if ticket is not None:
            corpo["ticket"] = {
                "customer_name": ticket.customer.full_name,
                "event_title": ticket.event.title,
                "seat_label": str(ticket.seat) if ticket.seat else None,
            }

        # Sempre HTTP 200: a portaria PERGUNTOU e foi respondida com sucesso.
        # "Ingresso inválido" é a resposta, não uma falha da requisição — quem
        # está na porta precisa ler o resultado, e um 4xx faria o front tratar
        # como erro de rede.
        return Response(corpo, status=status.HTTP_200_OK)


class GateEventsView(generics.ListAPIView):
    """Eventos que a portaria pode selecionar na tela."""

    permission_classes = (IsGate,)

    def list(self, request, *args, **kwargs):
        from events.models import Event

        eventos = Event.objects.filter(status=Event.Status.PUBLISHED).values(
            "id", "title", "venue", "starts_at"
        )
        return Response(list(eventos))
