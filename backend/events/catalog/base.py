"""
Contrato comum dos catálogos externos.

O problema: TMDb e Ticketmaster devolvem JSONs completamente diferentes, e nem
sequer descrevem a mesma coisa. Um filme não tem local nem horário; um show tem.

A solução: os dois provedores são normalizados para o mesmo `CatalogItem`. O
resto do sistema (view, front, criação de Event) nunca sabe de qual API o item
veio. Trocar de provedor, ou somar um terceiro, não toca em nada fora deste
pacote.

Decisão de contrato: `venue` e `starts_at` são OPCIONAIS aqui e OBRIGATÓRIOS no
Event. O catálogo devolve uma *sugestão*; quem transforma sugestão em evento à
venda é o organizador, preenchendo local e horário. Isso resolve a assimetria
entre filme e show sem inventar dado falso.
"""

from dataclasses import dataclass, asdict
from datetime import datetime


class CatalogError(Exception):
    """
    Falha ao falar com o catálogo externo (timeout, 5xx, chave inválida).

    Existe para a view distinguir "a API de fora quebrou" (502) de "eu quebrei"
    (500). Erro de terceiro não pode virar erro nosso no log nem na tela.
    """


@dataclass(frozen=True)
class CatalogItem:
    source: str
    external_id: str
    title: str
    description: str = ""
    image_url: str = ""
    venue: str = ""
    starts_at: datetime | None = None

    def to_dict(self):
        data = asdict(self)
        data["starts_at"] = self.starts_at.isoformat() if self.starts_at else None
        return data


class CatalogProvider:
    """Interface que todo provedor implementa. Ver tmdb.py / ticketmaster.py."""

    source = None
    # Segundos. Sem timeout, uma API externa lenta prende o worker do gunicorn
    # até ele morrer — um provedor de fora derruba a nossa API inteira.
    timeout = 6
    # Segundos de cache. Catálogo muda devagar e a cota de requisições é finita.
    cache_ttl = 60 * 15

    def search(self, query: str, limit: int = 12) -> list[CatalogItem]:
        raise NotImplementedError

    def is_configured(self) -> bool:
        """False quando a chave não foi preenchida — vira 503, não 500."""
        raise NotImplementedError
