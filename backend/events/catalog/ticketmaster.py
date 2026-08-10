"""
Provedor Ticketmaster Discovery — shows.
Docs: developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2
"""

import logging

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils.dateparse import parse_datetime

from .base import CatalogError, CatalogItem, CatalogProvider

logger = logging.getLogger(__name__)

API_BASE = "https://app.ticketmaster.com/discovery/v2"


class TicketmasterProvider(CatalogProvider):
    source = "TICKETMASTER"

    def is_configured(self):
        return bool(settings.TICKETMASTER_API_KEY)

    def search(self, query, limit=12):
        if not self.is_configured():
            raise CatalogError("TICKETMASTER_API_KEY não configurada.")

        cache_key = f"catalog:tm:{query.lower()}:{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        params = {"apikey": settings.TICKETMASTER_API_KEY, "size": limit}
        if query:
            params["keyword"] = query

        try:
            resp = requests.get(f"{API_BASE}/events.json", params=params, timeout=self.timeout)
            resp.raise_for_status()
            payload = resp.json()
        except requests.Timeout as exc:
            raise CatalogError("Ticketmaster não respondeu a tempo.") from exc
        except requests.RequestException as exc:
            logger.exception("Falha ao consultar a Ticketmaster")
            raise CatalogError("Falha ao consultar a Ticketmaster.") from exc

        # A Ticketmaster segue HAL: os dados vêm aninhados em "_embedded".
        raw_events = payload.get("_embedded", {}).get("events", [])
        items = [self._to_item(raw) for raw in raw_events[:limit]]
        cache.set(cache_key, items, self.cache_ttl)
        return items

    def _to_item(self, raw):
        return CatalogItem(
            source=self.source,
            external_id=str(raw["id"]),
            title=raw.get("name") or "Sem título",
            description=(raw.get("info") or raw.get("pleaseNote") or ""),
            image_url=self._best_image(raw.get("images") or []),
            venue=self._venue(raw),
            # Show TEM data — diferente do filme. Ainda assim o organizador pode
            # sobrescrever: a sessão dele não é necessariamente a do catálogo.
            starts_at=self._starts_at(raw),
        )

    def _best_image(self, images):
        if not images:
            return ""
        # A API devolve várias resoluções; pegamos a mais larga disponível.
        return max(images, key=lambda i: i.get("width", 0)).get("url", "")

    def _venue(self, raw):
        venues = raw.get("_embedded", {}).get("venues") or []
        if not venues:
            return ""
        v = venues[0]
        name = v.get("name") or ""
        city = (v.get("city") or {}).get("name") or ""
        return ", ".join(p for p in (name, city) if p)

    def _starts_at(self, raw):
        dates = (raw.get("dates") or {}).get("start") or {}
        # dateTime já vem em UTC ISO-8601 ("2026-09-12T23:00:00Z"). Quando só há
        # localDate (evento sem horário definido), preferimos None a inventar.
        return parse_datetime(dates["dateTime"]) if dates.get("dateTime") else None
