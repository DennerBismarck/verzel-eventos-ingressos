from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    GateEventsView,
    GateValidateView,
    MyTicketsView,
    ReservationViewSet,
    SharedTicketView,
)

# trailing_slash=False para casar com o resto da API (ver events/urls.py).
router = DefaultRouter(trailing_slash=False)
router.register("reservations", ReservationViewSet, basename="reservation")

urlpatterns = [
    path("tickets", MyTicketsView.as_view(), name="my-tickets"),
    path("shared/<uuid:share_token>", SharedTicketView.as_view(), name="shared-ticket"),
    path("gate/events", GateEventsView.as_view(), name="gate-events"),
    path("gate/validate", GateValidateView.as_view(), name="gate-validate"),
    path("", include(router.urls)),
]
