"""Provedor TMDb — filmes em cartaz. Docs: developer.themoviedb.org/docs"""

import logging

import requests
from django.conf import settings

from .base import CatalogError, CatalogItem, CatalogProvider

logger = logging.getLogger(__name__)

API_BASE = "https://api.themoviedb.org/3"
# O TMDb devolve só o caminho do arquivo ("/abc.jpg"); a URL completa é montada
# com um prefixo de CDN + o tamanho desejado. w500 = 500px de largura.
IMAGE_BASE = "https://image.tmdb.org/t/p/w500"


class TMDbProvider(CatalogProvider):
    source = "TMDB"

    def is_configured(self):
        return bool(settings.TMDB_API_KEY)

    def search(self, query, limit=12):
        if not self.is_configured():
            raise CatalogError("TMDB_API_KEY não configurada.")

        # A chave inclui a query e o idioma: buscas diferentes, entradas
        # diferentes. O "v2" marca o FORMATO do que está guardado — a entrada
        # deixou de ser uma lista e passou a ser (lista, quando_foi_gravado).
        # Sem o prefixo, uma cópia antiga em produção quebraria o desempacote
        # logo depois do deploy.
        chave = f"catalog:v2:tmdb:{settings.TMDB_LANGUAGE}:{query.lower()}:{limit}"
        return self.com_cache(chave, lambda: self._buscar_na_api(query, limit))

    def _buscar_na_api(self, query, limit):
        # "em cartaz" quando não há busca; senão, busca por título.
        if query:
            url, params = f"{API_BASE}/search/movie", {"query": query}
        else:
            url, params = f"{API_BASE}/movie/now_playing", {}

        params |= {"api_key": settings.TMDB_API_KEY, "language": settings.TMDB_LANGUAGE}

        try:
            resp = requests.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            payload = resp.json()
        except requests.Timeout as exc:
            raise CatalogError("TMDb não respondeu a tempo.") from exc
        except requests.RequestException as exc:
            # NÃO usar logger.exception aqui. O traceback inclui a mensagem do
            # requests, que traz a URL — e no TMDb a autenticação vai na query
            # string (?api_key=...). Isso escreveria a chave de produção nos
            # logs da Render, onde ela não deveria existir em hipótese alguma.
            # Registramos só o que ajuda a diagnosticar: tipo e status.
            logger.error(
                "Falha ao consultar o TMDb (tipo=%s, status=%s)",
                type(exc).__name__,
                getattr(exc.response, "status_code", "sem resposta"),
            )
            raise CatalogError("Falha ao consultar o TMDb.") from exc

        return [self._to_item(raw) for raw in payload.get("results", [])[:limit]]

    def _to_item(self, raw):
        poster = raw.get("poster_path")
        return CatalogItem(
            source=self.source,
            external_id=str(raw["id"]),
            title=raw.get("title") or raw.get("original_title") or "Sem título",
            description=raw.get("overview") or "",
            image_url=f"{IMAGE_BASE}{poster}" if poster else "",
            # Filme não tem local nem sessão: o organizador preenche.
            venue="",
            starts_at=None,
        )
