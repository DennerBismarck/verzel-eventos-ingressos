from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    GateEventsView,
    GateUndoView,
    GateValidateView,
    MyTicketsView,
    OrganizerSalesView,
    ReservationViewSet,
    SharedTicketView,
)

# trailing_slash=False para casar com o resto da API (ver events/urls.py).
router = DefaultRouter(trailing_slash=False)
router.register("reservations", ReservationViewSet, basename="reservation")

urlpatterns = [
    # Fica aqui, e não em events/urls.py, porque o assunto é reserva. O router
    # de eventos não engole esta URL: a rota de detalhe dele termina em "$",
    # então "/sales" não casa e a resolução segue até aqui.
    path("organizer/events/<int:pk>/sales", OrganizerSalesView.as_view(), name="organizer-sales"),
    path("tickets", MyTicketsView.as_view(), name="my-tickets"),
    path("shared/<uuid:share_token>", SharedTicketView.as_view(), name="shared-ticket"),
    path("gate/events", GateEventsView.as_view(), name="gate-events"),
    path("gate/validate", GateValidateView.as_view(), name="gate-validate"),
    path("gate/undo", GateUndoView.as_view(), name="gate-undo"),
    path("", include(router.urls)),
]
