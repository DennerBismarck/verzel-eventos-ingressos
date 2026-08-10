"""
Regras de evento que não cabem no serializer.

Hoje: a geração do mapa de assentos.
"""

from django.db import transaction

from .models import Event, Seat

# Tetos de sanidade. Sem eles, um POST com seats_per_row=1000000 tentaria um
# INSERT gigante e derrubaria o processo — não por malícia, basta um zero a
# mais digitado no formulário.
MAX_SECOES = 20
MAX_FILAS_POR_SECAO = 50
MAX_LUGARES_POR_FILA = 100
MAX_ASSENTOS = 5000


class SeatLayoutError(Exception):
    """Layout inválido ou impossível de aplicar. A view traduz para 400/409."""


@transaction.atomic
def generate_seats(*, event: Event, sections: list[dict]) -> int:
    """
    (Re)cria o mapa de assentos de um evento. Devolve quantos foram criados.

    É idempotente por substituição: chamar de novo com outro layout apaga o
    anterior e monta o novo. Só que isso é destrutivo, então há uma trava —
    ver abaixo.
    """
    if event.kind != Event.Kind.SEATED:
        raise SeatLayoutError(
            "Só eventos de lugar marcado têm mapa de assentos. "
            "Este evento é de pista, onde o estoque é a capacidade."
        )

    if not sections:
        raise SeatLayoutError("Informe ao menos uma seção.")

    if len(sections) > MAX_SECOES:
        raise SeatLayoutError(f"No máximo {MAX_SECOES} seções.")

    # A trava: se QUALQUER assento já foi vendido, o mapa vira histórico.
    # Recriá-lo apagaria a linha que um ingresso emitido aponta — e o
    # on_delete=PROTECT do Ticket.seat impediria de qualquer forma, só que
    # com um erro de banco em vez de uma explicação.
    if Seat.objects.filter(event=event, status=Seat.Status.SOLD).exists():
        raise SeatLayoutError(
            "Este evento já vendeu assentos; o mapa não pode mais ser refeito."
        )

    # PRIMEIRA passada: valida a forma e CONTA. Nada de Seat é construído aqui.
    #
    # A contagem precisa vir antes de materializar: com 20 seções de 50 filas ×
    # 100 lugares, construir para depois recusar alocaria 100 mil objetos em
    # memória só para dizer "não". Somar é barato; instanciar não.
    total = 0
    for secao in sections:
        nome = str(secao.get("name", "")).strip()
        filas = secao.get("rows") or []
        por_fila = secao.get("seats_per_row")

        if not nome:
            raise SeatLayoutError("Toda seção precisa de um nome.")
        if not filas:
            raise SeatLayoutError(f"A seção {nome} precisa de ao menos uma fila.")
        if len(filas) > MAX_FILAS_POR_SECAO:
            raise SeatLayoutError(f"A seção {nome} passa de {MAX_FILAS_POR_SECAO} filas.")
        if not isinstance(por_fila, int) or not 1 <= por_fila <= MAX_LUGARES_POR_FILA:
            raise SeatLayoutError(
                f"A seção {nome} precisa de 1 a {MAX_LUGARES_POR_FILA} lugares por fila."
            )
        if secao.get("price") is None:
            raise SeatLayoutError(f"A seção {nome} precisa de preço.")

        total += len(filas) * por_fila

    if total > MAX_ASSENTOS:
        raise SeatLayoutError(f"O mapa passa de {MAX_ASSENTOS} assentos ({total}).")

    # SEGUNDA passada: agora sim, constrói.
    novos: list[Seat] = []
    vistos: set[tuple[str, str, int]] = set()

    for secao in sections:
        nome = str(secao["name"]).strip()
        preco = secao["price"]
        for fila in secao["rows"]:
            fila = str(fila).strip()
            if not fila:
                raise SeatLayoutError(f"A seção {nome} tem fila sem nome.")
            for numero in range(1, secao["seats_per_row"] + 1):
                chave = (nome, fila, numero)
                # O UniqueConstraint do banco pegaria isso, mas com IntegrityError
                # no meio do INSERT em lote. Detectar aqui devolve uma frase
                # dizendo QUAL posição está repetida.
                if chave in vistos:
                    raise SeatLayoutError(f"Posição repetida no layout: {nome} {fila}{numero}.")
                vistos.add(chave)
                novos.append(
                    Seat(event=event, section=nome, row=fila, number=numero, price=preco)
                )

    # Apaga o mapa anterior. Seguro porque já garantimos que nada foi vendido.
    Seat.objects.filter(event=event).delete()
    Seat.objects.bulk_create(novos)

    # capacity espelha o total de assentos para que a vitrine e a
    # CheckConstraint funcionem igual nos dois tipos de evento.
    event.capacity = len(novos)
    event.sold_count = 0
    event.save(update_fields=["capacity", "sold_count"])

    return len(novos)
