from django.contrib import admin

from .models import Event, Seat


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "kind", "status", "starts_at", "price", "sold_count", "capacity")
    list_filter = ("status", "kind", "source")
    search_fields = ("title", "venue", "external_id")
    # sold_count é escrito só pela lógica de reserva. Editável no admin, viraria
    # a porta dos fundos do no-double-sell.
    readonly_fields = ("sold_count", "created_at")


@admin.register(Seat)
class SeatAdmin(admin.ModelAdmin):
    list_display = ("event", "section", "row", "number", "price", "status")
    list_filter = ("status", "event")
