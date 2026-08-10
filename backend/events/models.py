"""
Models de evento e assento.

Um Event nasce de um item do catálogo externo (TMDb ou Ticketmaster) que o
organizador escolheu publicar. Guardamos uma CÓPIA dos dados (título, imagem,
descrição) em vez de consultar a API externa a cada request: o catálogo é
inspiração, não fonte de verdade. Se o TMDb sair do ar, os eventos publicados
continuam à venda.

Dois tipos de evento (`kind`):
  - GA     (pista)    -> vende QUANTIDADE. Controle em `capacity` / `sold_count`.
  - SEATED (assentos) -> vende LUGAR. Controle nas linhas de `Seat`.
"""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Min


class EventQuerySet(models.QuerySet):
    def com_preco_inicial(self):
        """
        Anota o menor preço de assento, para o `price_from` não custar uma
        query por evento na vitrine — que é a página mais acessada e onde um
        N+1 dói mais.

        O order_by() no fim não é enfeite. annotate() com agregação sobre
        relação múltipla monta um GROUP BY, e o Django DESCARTA o Meta.ordering
        nesse caso (senão a coluna da ordenação entraria no agrupamento e
        mudaria o resultado). Sem esta linha o SELECT sai sem ORDER BY: o banco
        devolve na ordem que quiser, e numa lista PAGINADA isso faz a página 2
        repetir linhas da 1 e sumir com outras.

        Fica aqui, e não em cada view, porque quem chama esta função é quem
        perde a ordem. Um .order_by() posterior continua vencendo.
        """
        return self.annotate(_menor_preco_assento=Min("seats__price")).order_by(
            *self.model._meta.ordering
        )


class Event(models.Model):
    class Source(models.TextChoices):
        TMDB = "TMDB", "TMDb (filmes)"
        TICKETMASTER = "TICKETMASTER", "Ticketmaster (shows)"

    class Kind(models.TextChoices):
        GA = "GA", "Pista (por quantidade)"
        SEATED = "SEATED", "Lugar marcado"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "Rascunho"
        PUBLISHED = "PUBLISHED", "Publicado"

    # PROTECT: apagar um organizador que tem eventos vendidos apagaria o
    # histórico de ingressos junto. O banco recusa e obriga a decidir na mão.
    organizer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="events",
    )

    # --- origem no catálogo externo ---
    source = models.CharField(max_length=20, choices=Source.choices)
    # CharField e não Integer: o TMDb usa id numérico, a Ticketmaster usa
    # string alfanumérica ("G5vYZbJGkdvWZ"). String cobre os dois.
    external_id = models.CharField(max_length=64)

    # --- dados exibidos (cópia do catálogo, editável pelo organizador) ---
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    image_url = models.URLField(max_length=500, blank=True)

    # --- dados da sessão (o organizador define; o catálogo não tem) ---
    venue = models.CharField(max_length=200)
    starts_at = models.DateTimeField()

    kind = models.CharField(max_length=10, choices=Kind.choices, default=Kind.GA)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )

    # --- estoque (usado quando kind=GA; em SEATED quem manda são os Seats) ---
    # DecimalField e nunca FloatField para dinheiro: float é binário e não
    # representa 0.10 exatamente, então somas acumulam centavos de erro.
    price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    capacity = models.PositiveIntegerField(default=0)
    sold_count = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    objects = EventQuerySet.as_manager()

    class Meta:
        ordering = ["starts_at"]
        indexes = [
            # A busca do catálogo pergunta "já publiquei este item?".
            models.Index(fields=["source", "external_id"]),
            # A vitrine lista publicados em ordem de data.
            models.Index(fields=["status", "starts_at"]),
        ]
        constraints = [
            # Cinto de segurança do no-double-sell. Se um dia a lógica Python
            # tiver um furo (bug, script manual, race não coberta), o banco
            # recusa o INSERT/UPDATE em vez de vender ingresso que não existe.
            models.CheckConstraint(
                condition=models.Q(sold_count__lte=models.F("capacity")),
                name="event_sold_count_lte_capacity",
            ),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_kind_display()})"

    @property
    def is_ga(self):
        return self.kind == self.Kind.GA

    @property
    def available(self):
        """Ingressos ainda à venda. Só faz sentido em GA."""
        return max(self.capacity - self.sold_count, 0)

    @property
    def price_from(self):
        """
        O "a partir de" que a vitrine mostra.

        Em evento de pista é o preço único. Em lugar marcado, o `price` do
        evento é zero por construção — o preço mora em cada poltrona, e seções
        custam diferente. Ler `price` direto fazia a vitrine anunciar
        "a partir de R$ 0,00" num teatro de R$ 60.

        Usa a anotação de `com_preco_inicial()` quando existe; o fallback só
        dispara fora dos caminhos da API, que sempre anotam.
        """
        if self.kind != self.Kind.SEATED:
            return self.price

        anotado = getattr(self, "_menor_preco_assento", None)
        if anotado is not None:
            return anotado
        return self.seats.aggregate(m=Min("price"))["m"] or self.price


class Seat(models.Model):
    """Um lugar físico de um evento SEATED. Criado em lote ao publicar."""

    class Status(models.TextChoices):
        AVAILABLE = "AVAILABLE", "Disponível"
        SOLD = "SOLD", "Vendido"

    # CASCADE aqui (e PROTECT no organizer) porque o assento não existe sem o
    # evento — é parte dele, não uma entidade independente.
    event = models.ForeignKey(Event, on_delete=models.CASCADE, related_name="seats")
    section = models.CharField(max_length=30)
    row = models.CharField(max_length=10)
    number = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.AVAILABLE,
        db_index=True,
    )

    class Meta:
        ordering = ["section", "row", "number"]
        constraints = [
            # Não existem dois "A-3" na mesma seção do mesmo evento. Esta é a
            # garantia estrutural; o select_for_update é a garantia temporal.
            models.UniqueConstraint(
                fields=["event", "section", "row", "number"],
                name="seat_unique_position_per_event",
            ),
        ]

    def __str__(self):
        return f"{self.section} {self.row}{self.number}"
