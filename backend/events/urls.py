from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    CatalogSearchView,
    OrganizerEventViewSet,
    PublicEventDetailView,
    PublicEventListView,
)

# O router gera as 5 rotas REST do ViewSet (list/create/retrieve/update/destroy)
# a partir de uma linha, com nomes consistentes.
#
# trailing_slash=False: o padrão do router é "/organizer/events/", mas o resto
# da API é sem barra final ("/api/events", "/api/auth/login"). Misturar os dois
# faz o APPEND_SLASH do Django redirecionar 301 no GET e ESTOURAR no POST — ele
# não consegue redirecionar preservando o corpo do request.
router = DefaultRouter(trailing_slash=False)
router.register("organizer/events", OrganizerEventViewSet, basename="organizer-event")

urlpatterns = [
    path("events", PublicEventListView.as_view(), name="event-list"),
    path("events/<int:pk>", PublicEventDetailView.as_view(), name="event-detail"),
    path("catalog/search", CatalogSearchView.as_view(), name="catalog-search"),
    path("", include(router.urls)),
]
