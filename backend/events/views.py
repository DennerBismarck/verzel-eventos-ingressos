"""
Views de evento.

Separadas por AUDIÊNCIA, não por model:
  - público  -> só eventos PUBLISHED, campos reduzidos, sem autenticação
  - organizador -> CRUD dos próprios eventos, exige papel ORGANIZER

Escrever uma view só que muda de comportamento conforme o usuário é onde nascem
vazamentos ("esqueci de filtrar status neste if"). Duas classes, dois querysets.
"""

from django.db.models import Q
from django.utils import timezone
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.permissions import IsOrganizer

from .catalog import CatalogError, get_provider
from .models import Event, Seat
from .serializers import (
    CatalogItemSerializer,
    EventPublicSerializer,
    EventSerializer,
    SeatLayoutSerializer,
    SeatSerializer,
)
from .services import SeatLayoutError, generate_seats


class PublicEventListView(generics.ListAPIView):
    """Vitrine. Busca por título/local e filtro por tipo."""

    serializer_class = EventPublicSerializer
    permission_classes = (AllowAny,)

    @extend_schema(parameters=[
        OpenApiParameter("q", str, description="Busca em título e local"),
        OpenApiParameter("kind", str, description="GA ou SEATED"),
    ])
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        # select_related evita uma query extra por evento para pegar o nome do
        # organizador (problema N+1: 12 eventos = 13 queries sem isto).
        qs = (
            Event.objects.filter(status=Event.Status.PUBLISHED)
            .select_related("organizer")
            .com_preco_inicial()
        )

        if q := self.request.query_params.get("q", "").strip():
            qs = qs.filter(Q(title__icontains=q) | Q(venue__icontains=q))
        if kind := self.request.query_params.get("kind", "").strip().upper():
            qs = qs.filter(kind=kind)
        return qs


class PublicEventDetailView(generics.RetrieveAPIView):
    serializer_class = EventPublicSerializer
    permission_classes = (AllowAny,)
    # O filtro de status está no queryset, não numa checagem depois do get():
    # assim um evento em rascunho devolve 404, e não 403. Um 403 confirmaria
    # que o evento existe — informação que o público não precisa ter.
    queryset = (
        Event.objects.filter(status=Event.Status.PUBLISHED)
        .select_related("organizer")
        .com_preco_inicial()
    )


class PublicEventSeatsView(generics.ListAPIView):
    """
    Mapa de assentos para o cliente desenhar a tela.

    Devolve o assento e se está livre ou vendido — nunca QUEM comprou. Saber
    que a poltrona C4 está ocupada é necessário para escolher; saber o nome de
    quem senta nela não é.
    """

    serializer_class = SeatSerializer
    permission_classes = (AllowAny,)
    pagination_class = None  # o mapa é desenhado inteiro; paginar quebraria a tela

    def get_queryset(self):
        # Filtra pelo evento E por ele estar publicado: o mapa de um rascunho
        # não vaza por esta rota.
        return Seat.objects.filter(
            event_id=self.kwargs["pk"], event__status=Event.Status.PUBLISHED
        )


# Ordenações que o painel oferece. É um DE-PARA, não uma lista de campos:
# passar o parâmetro cru para order_by() deixaria o cliente ordenar por
# qualquer coluna ou relação ("organizer__password"), e a ordem de um resultado
# revela o conteúdo do campo mesmo sem exibi-lo.
ORDENACOES = {
    "starts_at": ("starts_at",),
    "-starts_at": ("-starts_at",),
    # Desempate por data: sem ele, eventos com o mesmo sold_count trocam de
    # lugar entre requisições e a paginação repete ou pula linhas.
    "-sold_count": ("-sold_count", "starts_at"),
    "-created_at": ("-created_at",),
}


class OrganizerEventViewSet(viewsets.ModelViewSet):
    """CRUD dos eventos DO ORGANIZADOR LOGADO."""

    serializer_class = EventSerializer
    permission_classes = (IsOrganizer,)

    @extend_schema(parameters=[
        OpenApiParameter("status", str, description="DRAFT ou PUBLISHED"),
        OpenApiParameter("when", str, description="upcoming (futuros) ou past (já aconteceram)"),
        OpenApiParameter("ordering", str, enum=sorted(ORDENACOES)),
    ])
    def list(self, request, *args, **kwargs):
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        # A dona da autorização é esta linha. Um organizador não enxerga nem
        # edita evento de outro, mesmo sabendo o id — o objeto simplesmente não
        # está no queryset, então PATCH /api/organizer/events/99 dá 404.
        qs = (
            Event.objects.filter(organizer=self.request.user)
            .prefetch_related("seats")
            .com_preco_inicial()
        )

        # Filtro e ordenação ficam no BANCO, e não na tela. A lista é paginada
        # de 12 em 12: filtrar no front só reordenaria a página atual e
        # esconderia o resto — um organizador com 20 eventos veria "nenhum
        # rascunho" tendo três deles na página 2.
        p = self.request.query_params

        if (status_pedido := p.get("status", "").strip().upper()) in Event.Status.values:
            qs = qs.filter(status=status_pedido)

        agora = timezone.now()
        when = p.get("when", "").strip().lower()
        if when == "upcoming":
            qs = qs.filter(starts_at__gte=agora)
        elif when == "past":
            qs = qs.filter(starts_at__lt=agora)

        if ordem := ORDENACOES.get(p.get("ordering", "").strip()):
            qs = qs.order_by(*ordem)

        return qs

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)

    @extend_schema(request=SeatLayoutSerializer, responses=SeatSerializer(many=True))
    @action(detail=True, methods=["get", "post"])
    def seats(self, request, pk=None):
        """
        GET  — mapa atual (inclusive de rascunho, por ser o dono).
        POST — (re)gera o mapa a partir de um layout de seções.

        Fica como ação do ViewSet, e não numa view solta, para herdar o
        get_queryset: o mapa de um evento alheio devolve 404 de graça.
        """
        evento = self.get_object()

        if request.method == "GET":
            return Response(SeatSerializer(evento.seats.all(), many=True).data)

        entrada = SeatLayoutSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)

        try:
            total = generate_seats(event=evento, sections=entrada.validated_data["sections"])
        except SeatLayoutError as exc:
            # 409 e não 400: o corpo pode estar perfeito e mesmo assim a ação
            # ser impossível agora (evento de pista, assentos já vendidos).
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)

        return Response(
            {"created": total, "seats": SeatSerializer(evento.seats.all(), many=True).data},
            status=status.HTTP_201_CREATED,
        )


class CatalogSearchView(APIView):
    """
    Proxy para TMDb / Ticketmaster.

    Existe para que a CHAVE DA API NUNCA CHEGUE AO NAVEGADOR. O front pede ao
    nosso backend, o backend fala com o terceiro. Se o front chamasse o TMDb
    direto, a chave estaria no bundle JavaScript, legível por qualquer um.
    """

    permission_classes = (IsOrganizer,)
    # Cada chamada aqui vira uma requisição à API de terceiro e gasta cota
    # NOSSA. O cache de 15 min já ajuda; o limite fecha a porta de alguém
    # esgotar a cota de propósito.
    throttle_classes = (ScopedRateThrottle,)
    throttle_scope = "catalog"

    @extend_schema(
        parameters=[
            OpenApiParameter("source", str, description="TMDB ou TICKETMASTER", required=True),
            OpenApiParameter("q", str, description="Termo de busca (vazio = em cartaz)"),
        ],
        responses=CatalogItemSerializer(many=True),
    )
    def get(self, request):
        source = request.query_params.get("source", "TMDB")
        query = request.query_params.get("q", "").strip()

        try:
            provider = get_provider(source)
        except CatalogError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        if not provider.is_configured():
            # 503 e não 500: a API está de pé, falta configuração do ambiente.
            return Response(
                {"detail": f"Catálogo {source} indisponível: chave não configurada."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        try:
            items = provider.search(query)
        except CatalogError as exc:
            # 502 Bad Gateway: quem falhou foi o serviço de terceiro, não nós.
            return Response({"detail": str(exc)}, status=status.HTTP_502_BAD_GATEWAY)

        return Response([item.to_dict() for item in items])
