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

import logging
import threading
import time
from dataclasses import dataclass, asdict
from datetime import datetime

from django.core.cache import cache
from django.db import connection

logger = logging.getLogger(__name__)


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

    # Enquanto a cópia tiver menos que isto, ela é servida sem mais perguntas.
    # Seis horas porque "em cartaz" muda em dias, não em minutos — o TTL antigo
    # de 15 min fazia o organizador esperar pelo TMDb quatro vezes por hora
    # sem que nada tivesse mudado do outro lado.
    FRESCOR = 60 * 60 * 6
    # Quanto tempo a cópia fica guardada, fresca ou não. É a rede de segurança
    # para quando o catálogo externo está fora do ar: melhor a lista de ontem
    # do que uma tela de erro.
    VALIDADE = 60 * 60 * 24 * 7

    def search(self, query: str, limit: int = 12) -> list[CatalogItem]:
        raise NotImplementedError

    def is_configured(self) -> bool:
        """False quando a chave não foi preenchida — vira 503, não 500."""
        raise NotImplementedError

    # ------------------------------------------------------------------ cache

    def com_cache(self, chave, buscar):
        """
        Serve primeiro, atualiza depois ("stale-while-revalidate").

        O cache anterior era simples: guardava por 15 min e, ao expirar, o
        próximo usuário PAGAVA a ida ao TMDb — 1 a 3 segundos olhando um
        esqueleto de carregamento, várias vezes por hora, para receber
        exatamente a mesma lista de antes.

        Agora ninguém espera pela API externa, exceto quem chega quando não há
        cópia nenhuma. Passado o frescor, a cópia guardada é entregue na hora e
        a atualização acontece em segundo plano, para o próximo.

        O custo dessa escolha, dito com todas as letras: um item pode ficar até
        seis horas desatualizado. Para um catálogo de filmes em cartaz — que é
        inspiração para o organizador, não fonte de verdade do sistema — é um
        preço barato. Os dados do evento são COPIADOS na criação; nada aqui
        afeta um evento já publicado.
        """
        guardado = cache.get(chave)

        if guardado is not None:
            itens, gravado_em = guardado
            if time.time() - gravado_em < self.FRESCOR:
                return itens
            self._atualizar_depois(chave, buscar)
            return itens

        itens = buscar()
        cache.set(chave, (itens, time.time()), self.VALIDADE)
        return itens

    def _atualizar_depois(self, chave, buscar):
        """
        Dispara a atualização numa thread e devolve na hora.

        Sem fila (Celery/RQ) de propósito: o projeto roda em um contêiner só no
        plano gratuito, e uma fila inteira para renovar uma lista de filmes
        seria infraestrutura maior que o problema. A thread é daemon e morre
        com o processo; se o deploy reiniciar no meio, a cópia antiga continua
        válida e a próxima requisição tenta de novo.
        """
        trava = f"{chave}:atualizando"
        # cache.add só grava se a chave não existir, e é atômico. É o que
        # impede a debandada: com dez requisições chegando juntas numa cópia
        # velha, uma dispara a atualização e as outras nove seguem servindo.
        if not cache.add(trava, True, self.timeout * 2):
            return

        def tarefa():
            try:
                cache.set(chave, (buscar(), time.time()), self.VALIDADE)
            except CatalogError:
                # A cópia antiga continua no ar. Falhar aqui é invisível para
                # quem está usando o sistema, que é exatamente a intenção.
                logger.warning("Não foi possível renovar o catálogo em %s", chave)
            except Exception:
                logger.exception("Erro inesperado ao renovar o catálogo")
            finally:
                cache.delete(trava)
                # A thread abre conexão PRÓPRIA com o banco (o cache é uma
                # tabela). Sem fechar, cada renovação vaza uma conexão até o
                # Postgres recusar novas.
                connection.close()

        threading.Thread(target=tarefa, daemon=True, name="catalogo-renova").start()
