"""
Provedor Ticketmaster Discovery — shows.
Docs: developer.ticketmaster.com/products-and-docs/apis/discovery-api/v2
"""

import logging

import requests
from django.conf import settings
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

        # v2 marca o formato guardado — ver o comentário equivalente no tmdb.py.
        chave = f"catalog:v2:tm:{query.lower()}:{limit}"
        return self.com_cache(chave, lambda: self._buscar_na_api(query, limit))

    def _buscar_na_api(self, query, limit):
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
            # Mesmo motivo do tmdb.py: a chave vai na query string (?apikey=),
            # então o traceback do requests vazaria o segredo para o log.
            logger.error(
                "Falha ao consultar a Ticketmaster (tipo=%s, status=%s)",
                type(exc).__name__,
                getattr(exc.response, "status_code", "sem resposta"),
            )
            raise CatalogError("Falha ao consultar a Ticketmaster.") from exc

        # A Ticketmaster segue HAL: os dados vêm aninhados em "_embedded".
        raw_events = payload.get("_embedded", {}).get("events", [])
        return [self._to_item(raw) for raw in raw_events[:limit]]

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
