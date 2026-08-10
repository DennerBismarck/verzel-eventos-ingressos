"""
Registry dos provedores de catálogo.

Quem consome escreve `get_provider("TMDB")` e recebe algo que responde
`.search(query)`. Adicionar um terceiro provedor = criar o módulo e somar uma
linha em PROVIDERS. Nenhuma view muda.
"""

from .base import CatalogError, CatalogItem, CatalogProvider
from .ticketmaster import TicketmasterProvider
from .tmdb import TMDbProvider

PROVIDERS = {
    TMDbProvider.source: TMDbProvider(),
    TicketmasterProvider.source: TicketmasterProvider(),
}


def get_provider(source: str) -> CatalogProvider:
    try:
        return PROVIDERS[source.upper()]
    except KeyError:
        raise CatalogError(f"Fonte desconhecida: {source!r}") from None


__all__ = ["CatalogError", "CatalogItem", "CatalogProvider", "PROVIDERS", "get_provider"]
