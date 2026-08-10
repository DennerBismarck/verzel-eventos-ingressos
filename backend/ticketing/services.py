"""
Regras de negócio de reserva, pagamento e validação.

Fica FORA das views de propósito: a view traduz HTTP, o serviço decide. Assim a
mesma regra vale para a API, para o admin e para um teste — e o teste de
concorrência (dois clientes disputando o último lugar) roda sem subir servidor.

O ponto central de tudo aqui é o par transaction.atomic() + select_for_update().
"""

import logging

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from events.models import Event, Seat

from .models import Payment, Reservation, Ticket

logger = logging.getLogger(__name__)

# Regra do pagamento SIMULADO: pedidos grandes são recusados. Determinística
# de propósito — dá para demonstrar o caminho de falha ao vivo. Uma recusa
# aleatória tornaria a demonstração irreprodutível.
LIMITE_RECUSA = 10


class ReservationError(Exception):
    """Regra de negócio violada. A view traduz para 400/409."""


# --------------------------------------------------------------------------
# Reserva
# --------------------------------------------------------------------------
def create_reservation(*, customer, event_id, quantity=1, seat_ids=None):
    """
    Cria a reserva JÁ SEGURANDO o estoque, antes do pagamento.

    Reservar depois de pagar deixaria uma janela em que dois clientes pagam
    pelo mesmo lugar e um dos dois precisa ser estornado. Segurando antes, o
    perdedor descobre na hora — que é onde ele consegue escolher outra coisa.
    """
    with transaction.atomic():
        # ---------------------------------------------------------------
        # A LINHA MAIS IMPORTANTE DO PROJETO.
        #
        # select_for_update() emite "SELECT ... FOR UPDATE", que trava ESTA
        # linha do evento até o fim da transação. Uma segunda transação que
        # tente travar a mesma linha FICA PARADA aqui até a primeira commitar
        # — e então lê o sold_count já atualizado.
        #
        # Sem isto, duas requisições simultâneas leem sold_count=99 (capacidade
        # 100), as duas concluem "tem vaga", as duas gravam 100, e dois
        # ingressos foram vendidos para o mesmo lugar. É uma race condition
        # clássica: o problema não é a checagem nem a escrita, é o intervalo
        # entre elas.
        #
        # Precisa estar DENTRO de atomic(): o lock dura até o COMMIT. Sem
        # transação, o autocommit do Django encerra o lock imediatamente e ele
        # não protege nada.
        # ---------------------------------------------------------------
        event = Event.objects.select_for_update().get(pk=event_id)

        if event.status != Event.Status.PUBLISHED:
            raise ReservationError("Este evento não está à venda.")
        if event.starts_at <= timezone.now():
            raise ReservationError("Este evento já começou.")

        if event.kind == Event.Kind.GA:
            reservation = _reserve_ga(customer, event, quantity)
        else:
            reservation = _reserve_seats(customer, event, seat_ids or [])

    return reservation


def _reserve_ga(customer, event, quantity):
    """Pista: o estoque é um contador na linha do evento (já travada)."""
    if quantity < 1:
        raise ReservationError("A quantidade precisa ser pelo menos 1.")

    disponivel = event.capacity - event.sold_count
    if quantity > disponivel:
        raise ReservationError(
            f"Restam apenas {disponivel} ingressos para este evento."
        )

    event.sold_count += quantity
    # update_fields: grava só esta coluna. Um save() completo sobrescreveria
    # title/price com os valores lidos no início da transação, desfazendo em
    # silêncio uma edição concorrente do organizador.
    event.save(update_fields=["sold_count"])

    return Reservation.objects.create(
        customer=customer,
        event=event,
        quantity=quantity,
        total_price=event.price * quantity,
    )


def _reserve_seats(customer, event, seat_ids):
    """Assentos: o estoque são as linhas de Seat, travadas uma a uma."""
    ids = set(seat_ids)
    if not ids:
        raise ReservationError("Selecione ao menos um assento.")

    # Trava só os assentos pedidos que AINDA estão disponíveis.
    #
    # Detalhe que costuma cair na entrevista: no isolamento READ COMMITTED
    # (padrão do Postgres), quando esta query espera por um lock e ele é
    # liberado, o Postgres RE-AVALIA o WHERE na versão nova da linha. Então um
    # assento que o concorrente acabou de marcar como SOLD sai do resultado
    # sozinho — não vem "disponível" desatualizado.
    travados = list(
        Seat.objects.select_for_update()
        .filter(id__in=ids, event=event, status=Seat.Status.AVAILABLE)
    )

    # Se travei menos do que pedi, alguém levou algum no meio do caminho.
    # Sair por exceção dentro do atomic() desfaz TUDO — inclusive os assentos
    # que eu já tinha conseguido travar. Reserva parcial não existe.
    if len(travados) != len(ids):
        raise ReservationError("Algum dos assentos escolhidos não está mais disponível.")

    Seat.objects.filter(id__in=[s.id for s in travados]).update(status=Seat.Status.SOLD)

    # sold_count também sobe em evento com lugar marcado. A verdade sobre QUAL
    # assento foi vendido está nas linhas de Seat; este contador existe para a
    # vitrine responder "quantos restam" sem contar assentos a cada card — e
    # para a CheckConstraint continuar valendo nos dois tipos de evento.
    # A linha do evento já está travada por create_reservation.
    event.sold_count += len(travados)
    event.save(update_fields=["sold_count"])

    reservation = Reservation.objects.create(
        customer=customer,
        event=event,
        quantity=len(travados),
        total_price=sum(s.price for s in travados),
    )
    reservation.seats.set(travados)
    return reservation


# --------------------------------------------------------------------------
# Pagamento (simulado) — emite os ingressos
# --------------------------------------------------------------------------
def pay_reservation(*, reservation_id, customer):
    with transaction.atomic():
        # Trava a reserva: sem isto, dois cliques no botão "pagar" emitiriam
        # dois conjuntos de ingressos para a mesma reserva.
        reservation = Reservation.objects.select_for_update().get(
            pk=reservation_id, customer=customer
        )

        if reservation.status != Reservation.Status.PENDING:
            raise ReservationError(
                f"Esta reserva não está aguardando pagamento (situação: "
                f"{reservation.get_status_display()})."
            )

        if reservation.quantity >= LIMITE_RECUSA:
            reservation.status = Reservation.Status.REFUSED
            reservation.save(update_fields=["status"])
            _release_stock(reservation)
            return Payment.objects.create(
                reservation=reservation,
                status=Payment.Status.REFUSED,
                reason=f"Pagamento recusado: pedidos de {LIMITE_RECUSA} ou mais ingressos "
                f"exigem aprovação manual.",
            ), []

        reservation.status = Reservation.Status.PAID
        reservation.save(update_fields=["status"])
        pagamento = Payment.objects.create(
            reservation=reservation, status=Payment.Status.CONFIRMED
        )
        tickets = _issue_tickets(reservation)

    return pagamento, tickets


def _issue_tickets(reservation):
    """Um ingresso por lugar. Cada um com code e share_token próprios."""
    assentos = list(reservation.seats.all())

    if assentos:
        novos = [
            Ticket(
                reservation=reservation,
                event=reservation.event,
                customer=reservation.customer,
                seat=assento,
            )
            for assento in assentos
        ]
    else:
        novos = [
            Ticket(
                reservation=reservation,
                event=reservation.event,
                customer=reservation.customer,
            )
            for _ in range(reservation.quantity)
        ]

    # bulk_create: 1 INSERT em vez de N. Comprar 8 ingressos não deve custar
    # 8 idas ao banco.
    return Ticket.objects.bulk_create(novos)


# --------------------------------------------------------------------------
# Cancelamento — devolve ao estoque
# --------------------------------------------------------------------------
def cancel_reservation(*, reservation_id, customer):
    with transaction.atomic():
        reservation = Reservation.objects.select_for_update().get(
            pk=reservation_id, customer=customer
        )

        if not reservation.holds_stock:
            raise ReservationError("Esta reserva já não está ativa.")

        if reservation.tickets.filter(status=Ticket.Status.USED).exists():
            raise ReservationError("Há ingressos desta reserva já utilizados na portaria.")

        reservation.status = Reservation.Status.CANCELLED
        reservation.save(update_fields=["status"])
        reservation.tickets.all().delete()
        _release_stock(reservation)

    return reservation


def _release_stock(reservation):
    """Devolve os lugares. Chamado sempre DENTRO de uma transação já aberta."""
    assentos = list(reservation.seats.all())

    # Em evento com lugar marcado, devolver o assento é só metade: o contador
    # do evento também precisa voltar. Antes esta função retornava aqui e
    # deixava sold_count inflado para sempre — a vitrine passaria a mostrar
    # menos lugares do que existem, sem ninguém notar.
    if assentos:
        Seat.objects.filter(id__in=[s.id for s in assentos]).update(
            status=Seat.Status.AVAILABLE
        )

    # F() faz a subtração NO BANCO ("sold_count = sold_count - 3") em vez de
    # em Python. Ler em Python, subtrair e gravar usaria um valor possivelmente
    # obsoleto e perderia atualizações concorrentes.
    Event.objects.filter(pk=reservation.event_id).update(
        sold_count=F("sold_count") - reservation.quantity
    )


# --------------------------------------------------------------------------
# Portaria
# --------------------------------------------------------------------------
class GateResult:
    VALID = "VALID"
    INVALID = "INVALID"
    ALREADY_USED = "ALREADY_USED"
    WRONG_EVENT = "WRONG_EVENT"


def validate_ticket(*, payload, event_id, gate_user):
    """
    Valida um ingresso na entrada. Devolve (resultado, ticket_ou_None, detalhe).

    A ORDEM das checagens é deliberada: assinatura primeiro, porque é a única
    que não exige ir ao banco. Um QR forjado é rejeitado sem custo de query.
    """
    from .signing import parse_payload

    # Aceita tanto o conteúdo do QR ("codigo.assinatura") quanto o código
    # digitado à mão pela portaria, quando a câmera não colabora.
    code = parse_payload(payload)
    if code is None:
        code = payload.strip() if payload else ""
        if not code:
            return GateResult.INVALID, None, "Código vazio."

    with transaction.atomic():
        try:
            # Trava o ingresso: dois leitores apontados para o mesmo QR ao
            # mesmo tempo. Sem o lock, ambos leem status=VALID e ambos deixam
            # entrar — a mesma race do double-sell, agora na porta.
            #
            # of=("self",) trava SÓ a linha do ingresso. Sem isso o Postgres
            # tentaria travar tudo que o select_related trouxe no JOIN e
            # recusaria: `seat` é nullable, logo LEFT OUTER JOIN, e "FOR UPDATE
            # cannot be applied to the nullable side of an outer join".
            # Travar evento e cliente para validar uma entrada seria errado de
            # qualquer forma — bloquearia a venda do evento inteiro na portaria.
            ticket = (
                Ticket.objects.select_for_update(of=("self",))
                .select_related("event", "customer", "seat")
                .get(code=code)
            )
        # ValidationError cobre o caso de o código digitado nem ser um UUID —
        # o Django recusa antes de ir ao banco.
        except (Ticket.DoesNotExist, ValueError, ValidationError):
            return GateResult.INVALID, None, "Ingresso não encontrado."

        if ticket.event_id != int(event_id):
            return GateResult.WRONG_EVENT, ticket, f"Este ingresso é de: {ticket.event.title}."

        if ticket.status == Ticket.Status.USED:
            quando = timezone.localtime(ticket.used_at).strftime("%d/%m/%Y %H:%M")
            quem = ticket.used_by.full_name if ticket.used_by else "desconhecido"
            return GateResult.ALREADY_USED, ticket, f"Utilizado em {quando} por {quem}."

        ticket.status = Ticket.Status.USED
        ticket.used_at = timezone.now()
        ticket.used_by = gate_user
        ticket.save(update_fields=["status", "used_at", "used_by"])

    return GateResult.VALID, ticket, "Entrada liberada."
