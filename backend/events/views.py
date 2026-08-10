"""
Views de evento.

Separadas por AUDIÊNCIA, não por model:
  - público  -> só eventos PUBLISHED, campos reduzidos, sem autenticação
  - organizador -> CRUD dos próprios eventos, exige papel ORGANIZER

Escrever uma view só que muda de comportamento conforme o usuário é onde nascem
vazamentos ("esqueci de filtrar status neste if"). Duas classes, dois querysets.
"""

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import generics, status, viewsets
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.permissions import IsOrganizer

from .catalog import CatalogError, get_provider
from .models import Event
from .serializers import CatalogItemSerializer, EventPublicSerializer, EventSerializer


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
        qs = Event.objects.filter(status=Event.Status.PUBLISHED).select_related("organizer")

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
    queryset = Event.objects.filter(status=Event.Status.PUBLISHED).select_related("organizer")


class OrganizerEventViewSet(viewsets.ModelViewSet):
    """CRUD dos eventos DO ORGANIZADOR LOGADO."""

    serializer_class = EventSerializer
    permission_classes = (IsOrganizer,)

    def get_queryset(self):
        # A dona da autorização é esta linha. Um organizador não enxerga nem
        # edita evento de outro, mesmo sabendo o id — o objeto simplesmente não
        # está no queryset, então PATCH /api/organizer/events/99 dá 404.
        return Event.objects.filter(organizer=self.request.user).prefetch_related("seats")

    def perform_create(self, serializer):
        serializer.save(organizer=self.request.user)


class CatalogSearchView(APIView):
    """
    Proxy para TMDb / Ticketmaster.

    Existe para que a CHAVE DA API NUNCA CHEGUE AO NAVEGADOR. O front pede ao
    nosso backend, o backend fala com o terceiro. Se o front chamasse o TMDb
    direto, a chave estaria no bundle JavaScript, legível por qualquer um.
    """

    permission_classes = (IsOrganizer,)

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
