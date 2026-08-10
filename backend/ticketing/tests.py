"""
Testes do núcleo: no-double-sell, assinatura do QR e portaria.

Usa TransactionTestCase (e não TestCase) nos testes de concorrência. Motivo:
o TestCase envolve cada teste numa transação que sofre rollback no fim — e uma
transação não é visível de outra conexão. As threads do teste simplesmente não
enxergariam os dados criados no setUp. TransactionTestCase commita de verdade.
"""

import threading
from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from events.models import Event, Seat

from . import services
from .models import Reservation, Ticket
from .signing import build_payload, parse_payload, sign_code

User = get_user_model()


def _make_world(capacity=5, price="10.00"):
    org = User.objects.create_user(
        email="org@t.dev", password="x", full_name="Org", role=User.Role.ORGANIZER
    )
    evento = Event.objects.create(
        organizer=org,
        source=Event.Source.TMDB,
        external_id="1",
        title="Show de Teste",
        venue="Arena",
        starts_at=timezone.now() + timedelta(days=5),
        kind=Event.Kind.GA,
        status=Event.Status.PUBLISHED,
        price=Decimal(price),
        capacity=capacity,
    )
    return org, evento


class NoDoubleSellTest(TransactionTestCase):
    """O coração do desafio: capacidade N nunca vende N+1."""

    def _comprar_em_paralelo(self, evento, clientes, funcao):
        """Dispara todos os clientes ao mesmo tempo com uma barreira."""
        largada = threading.Barrier(len(clientes))
        resultados = []
        trava = threading.Lock()

        def tentar(cliente):
            # Barrier: todas as threads param aqui e são soltas juntas. Sem
            # isso a primeira terminaria antes da última começar e não haveria
            # concorrência nenhuma para testar.
            largada.wait()
            try:
                funcao(customer=cliente, event_id=evento.pk, quantity=1)
                ok = True
            except services.ReservationError:
                ok = False
            finally:
                # Cada thread abre a própria conexão com o banco; sem fechar,
                # elas vazam e o teste trava no teardown.
                connection.close()
            with trava:
                resultados.append(ok)

        threads = [threading.Thread(target=tentar, args=(c,)) for c in clientes]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        return resultados

    def test_dez_clientes_disputando_tres_lugares(self):
        _, evento = _make_world(capacity=3)
        clientes = [
            User.objects.create_user(
                email=f"c{i}@t.dev", password="x", full_name=f"C{i}", role=User.Role.CUSTOMER
            )
            for i in range(10)
        ]

        resultados = self._comprar_em_paralelo(evento, clientes, services.create_reservation)

        evento.refresh_from_db()
        self.assertEqual(sum(resultados), 3, "exatamente 3 compras deveriam passar")
        self.assertEqual(evento.sold_count, 3)
        self.assertEqual(Reservation.objects.count(), 3)

    def test_sem_lock_o_banco_seria_estourado(self):
        """
        Documenta POR QUE o select_for_update existe.

        Repete o teste anterior com uma versão idêntica da função, exceto por
        NÃO travar a linha. O resultado esperado é oversell — e é justamente o
        que a CheckConstraint do banco impede de ser gravado.
        """
        _, evento = _make_world(capacity=3)
        clientes = [
            User.objects.create_user(
                email=f"u{i}@t.dev", password="x", full_name=f"U{i}", role=User.Role.CUSTOMER
            )
            for i in range(10)
        ]

        def reservar_sem_lock(*, customer, event_id, quantity):
            from django.db import IntegrityError

            try:
                with transaction.atomic():
                    # A ÚNICA diferença: sem .select_for_update().
                    ev = Event.objects.get(pk=event_id)
                    if ev.capacity - ev.sold_count < quantity:
                        raise services.ReservationError("esgotado")
                    # Janela onde o outro cliente lê o mesmo sold_count.
                    ev.sold_count += quantity
                    ev.save(update_fields=["sold_count"])
            except IntegrityError:
                # A CheckConstraint do banco barrando o oversell.
                raise services.ReservationError("constraint do banco recusou")

        resultados = self._comprar_em_paralelo(evento, clientes, reservar_sem_lock)
        evento.refresh_from_db()

        # A asserção é a INVARIANTE (nunca passar da capacidade), não "a race
        # aconteceu" — esta última dependeria do escalonador e daria teste
        # instável. A demonstração da race sai no print.
        self.assertLessEqual(
            evento.sold_count, evento.capacity,
            "a CheckConstraint deveria impedir gravar acima da capacidade",
        )
        print(
            f"\n    [sem lock] {sum(resultados)} clientes aprovados para "
            f"{evento.capacity} vagas; sold_count gravado: {evento.sold_count}"
            f"\n    -> aprovados a mais do que existe vaga (oversell) E contador "
            f"abaixo do real (lost update):"
            f"\n       as threads leram o mesmo sold_count e sobrescreveram umas "
            f"às outras."
            f"\n    [com lock] o outro teste: exatamente {evento.capacity} aprovados, "
            f"contador exato."
        )


def _make_seated(seats=6, price="80.00", slug="a"):
    """
    Evento com lugar marcado e um mapa pronto.

    `slug` existe porque um teste monta DOIS eventos para provar que assento de
    outro evento não entra na reserva — e o e-mail do organizador é único.
    """
    org = User.objects.create_user(
        email=f"orgs-{slug}@t.dev", password="x", full_name="Org", role=User.Role.ORGANIZER
    )
    evento = Event.objects.create(
        organizer=org,
        source=Event.Source.TICKETMASTER,
        external_id=f"s-{slug}",
        title="Peça de Teste",
        venue="Teatro",
        starts_at=timezone.now() + timedelta(days=5),
        kind=Event.Kind.SEATED,
        status=Event.Status.PUBLISHED,
        price=Decimal("0.00"),
        capacity=seats,
    )
    Seat.objects.bulk_create(
        [
            Seat(event=evento, section="Plateia", row="A", number=n, price=Decimal(price))
            for n in range(1, seats + 1)
        ]
    )
    return org, evento


class AssentoConcorrenciaTest(TransactionTestCase):
    """A mesma disputa do double-sell, agora sobre a linha do assento."""

    def test_dez_clientes_disputando_a_mesma_poltrona(self):
        _, evento = _make_seated(seats=1)
        assento = evento.seats.first()
        clientes = [
            User.objects.create_user(
                email=f"s{i}@t.dev", password="x", full_name=f"S{i}", role=User.Role.CUSTOMER
            )
            for i in range(10)
        ]

        largada = threading.Barrier(len(clientes))
        vitorias = []
        trava = threading.Lock()

        def tentar(cliente):
            largada.wait()
            try:
                services.create_reservation(
                    customer=cliente, event_id=evento.pk, seat_ids=[assento.pk]
                )
                ok = True
            except services.ReservationError:
                ok = False
            finally:
                connection.close()
            with trava:
                vitorias.append(ok)

        threads = [threading.Thread(target=tentar, args=(c,)) for c in clientes]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assento.refresh_from_db()
        evento.refresh_from_db()
        self.assertEqual(sum(vitorias), 1, "só um cliente pode levar a poltrona")
        self.assertEqual(assento.status, Seat.Status.SOLD)
        self.assertEqual(evento.sold_count, 1)
        self.assertEqual(Reservation.objects.count(), 1)


class AssentoTest(TestCase):
    def setUp(self):
        _, self.evento = _make_seated(seats=6)
        self.cliente = User.objects.create_user(
            email="cs@t.dev", password="x", full_name="Cs", role=User.Role.CUSTOMER
        )
        self.outro = User.objects.create_user(
            email="cs2@t.dev", password="x", full_name="Cs2", role=User.Role.CUSTOMER
        )
        self.assentos = list(self.evento.seats.order_by("number"))

    def test_reserva_marca_os_assentos_e_soma_o_preco_deles(self):
        r = services.create_reservation(
            customer=self.cliente,
            event_id=self.evento.pk,
            seat_ids=[self.assentos[0].pk, self.assentos[1].pk],
        )
        self.assertEqual(r.quantity, 2)
        # O preço vem do assento, não do campo price do evento (que é da pista).
        self.assertEqual(r.total_price, Decimal("160.00"))
        self.assertEqual(
            list(self.evento.seats.filter(status=Seat.Status.SOLD).values_list("number", flat=True)),
            [1, 2],
        )

    def test_sold_count_do_evento_acompanha_os_assentos(self):
        """
        Sem isto a vitrine mentiria: mostraria a sala inteira livre enquanto as
        poltronas iam sendo vendidas, porque `available` lê o contador.
        """
        services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, seat_ids=[self.assentos[0].pk]
        )
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.sold_count, 1)
        self.assertEqual(self.evento.available, 5)

    def test_tudo_ou_nada_quando_um_assento_ja_foi_levado(self):
        services.create_reservation(
            customer=self.outro, event_id=self.evento.pk, seat_ids=[self.assentos[1].pk]
        )
        with self.assertRaises(services.ReservationError):
            services.create_reservation(
                customer=self.cliente,
                event_id=self.evento.pk,
                seat_ids=[self.assentos[0].pk, self.assentos[1].pk, self.assentos[2].pk],
            )
        # Nem o assento 1 nem o 3 podem ter ficado presos numa reserva parcial.
        for i in (0, 2):
            self.assentos[i].refresh_from_db()
            self.assertEqual(self.assentos[i].status, Seat.Status.AVAILABLE)
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.sold_count, 1)

    def test_reserva_sem_assento_nenhum_e_recusada(self):
        with self.assertRaises(services.ReservationError):
            services.create_reservation(
                customer=self.cliente, event_id=self.evento.pk, seat_ids=[]
            )

    def test_assento_de_outro_evento_nao_entra(self):
        _, outro_evento = _make_seated(seats=2, slug="b")
        with self.assertRaises(services.ReservationError):
            services.create_reservation(
                customer=self.cliente,
                event_id=self.evento.pk,
                seat_ids=[outro_evento.seats.first().pk],
            )

    def test_pagamento_emite_um_ingresso_por_poltrona(self):
        r = services.create_reservation(
            customer=self.cliente,
            event_id=self.evento.pk,
            seat_ids=[self.assentos[0].pk, self.assentos[3].pk],
        )
        _, tickets = services.pay_reservation(reservation_id=r.pk, customer=self.cliente)
        self.assertEqual(len(tickets), 2)
        self.assertEqual({t.seat.number for t in tickets}, {1, 4})

    def test_cancelar_devolve_a_poltrona_e_o_contador(self):
        r = services.create_reservation(
            customer=self.cliente,
            event_id=self.evento.pk,
            seat_ids=[self.assentos[0].pk, self.assentos[1].pk],
        )
        services.pay_reservation(reservation_id=r.pk, customer=self.cliente)
        services.cancel_reservation(reservation_id=r.pk, customer=self.cliente)

        self.evento.refresh_from_db()
        self.assertEqual(self.evento.sold_count, 0, "o contador também tem que voltar")
        self.assertEqual(self.evento.seats.filter(status=Seat.Status.AVAILABLE).count(), 6)


class VendasDoOrganizadorTest(TestCase):
    """O painel de vendas: resumo do evento e quem comprou."""

    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.org, self.evento = _make_world(capacity=20, price="30.00")
        self.outro_org = User.objects.create_user(
            email="org2@t.dev", password="x", full_name="Org2", role=User.Role.ORGANIZER
        )
        self.cliente = User.objects.create_user(
            email="comprador@t.dev", password="x", full_name="Caio", role=User.Role.CUSTOMER
        )
        self.portaria = User.objects.create_user(
            email="pt@t.dev", password="x", full_name="Pedro", role=User.Role.GATE
        )
        self.url = reverse("organizer-sales", args=[self.evento.pk])

    def _comprar(self, quantidade=2, pagar=True):
        r = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=quantidade
        )
        if pagar:
            _, tickets = services.pay_reservation(reservation_id=r.pk, customer=self.cliente)
            return r, tickets
        return r, []

    def test_resumo_conta_receita_ingressos_e_validados(self):
        _, tickets = self._comprar(3)
        services.validate_ticket(
            payload=tickets[0].qr_payload, event_id=self.evento.pk, gate_user=self.portaria
        )

        self.client.force_authenticate(self.org)
        resumo = self.client.get(self.url).json()["summary"]

        self.assertEqual(resumo["sold_count"], 3)
        self.assertEqual(resumo["available"], 17)
        self.assertEqual(resumo["revenue"], "90.00")
        self.assertEqual(resumo["tickets_issued"], 3)
        self.assertEqual(resumo["tickets_used"], 1)

    def test_receita_conta_so_reserva_paga(self):
        """
        Pendente ainda pode ser recusada; recusada e cancelada nunca entraram.
        Somar tudo inflaria o faturamento do organizador.
        """
        self._comprar(2, pagar=True)
        self._comprar(1, pagar=False)
        cancelada, _ = self._comprar(1, pagar=True)
        services.cancel_reservation(reservation_id=cancelada.pk, customer=self.cliente)

        self.client.force_authenticate(self.org)
        resumo = self.client.get(self.url).json()["summary"]
        self.assertEqual(resumo["revenue"], "60.00")
        self.assertEqual(resumo["paid_reservations"], 1)

    def test_lista_traz_o_comprador_mas_nao_o_codigo_do_ingresso(self):
        self._comprar(2)
        self.client.force_authenticate(self.org)
        venda = self.client.get(self.url).json()["sales"][0]

        self.assertEqual(venda["customer_name"], "Caio")
        self.assertEqual(venda["customer_email"], "comprador@t.dev")
        self.assertEqual(venda["tickets_total"], 2)
        # Nem o dono do evento recebe o que abre a catraca.
        self.assertNotIn("code", str(venda))
        self.assertNotIn("qr_payload", venda)

    def test_conta_ingressos_usados_por_reserva(self):
        _, tickets = self._comprar(3)
        services.validate_ticket(
            payload=tickets[0].qr_payload, event_id=self.evento.pk, gate_user=self.portaria
        )
        self.client.force_authenticate(self.org)
        venda = self.client.get(self.url).json()["sales"][0]
        self.assertEqual(venda["tickets_used"], 1)
        self.assertEqual(venda["tickets_total"], 3)

    def test_vendas_de_evento_alheio_devolvem_404(self):
        self.client.force_authenticate(self.outro_org)
        self.assertEqual(self.client.get(self.url).status_code, 404)

    def test_cliente_e_portaria_nao_veem_vendas(self):
        for user in (self.cliente, self.portaria):
            with self.subTest(user=user.email):
                self.client.force_authenticate(user)
                self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_anonimo_leva_401(self):
        self.assertEqual(self.client.get(self.url).status_code, 401)

    def test_evento_sem_venda_devolve_resumo_zerado(self):
        self.client.force_authenticate(self.org)
        corpo = self.client.get(self.url).json()
        self.assertEqual(corpo["sales"], [])
        self.assertEqual(corpo["summary"]["revenue"], "0.00")
        self.assertEqual(corpo["summary"]["tickets_issued"], 0)

    def test_numero_de_queries_nao_cresce_com_as_vendas(self):
        """
        As colunas de ingresso são ANOTADAS no banco. Sem isso, cada reserva
        custaria queries extras e o painel ficaria mais lento exatamente à
        medida que o evento vendesse mais — o pior momento possível.

        A asserção compara 1 venda contra 6, em vez de cravar um número: um
        número fixo quebraria a cada middleware ou índice novo, sem que nada
        de errado tivesse acontecido.
        """
        self.client.force_authenticate(self.org)

        self._comprar(1)
        with CaptureQueriesContext(connection) as com_uma:
            self.client.get(self.url)

        for _ in range(5):
            self._comprar(1)
        with CaptureQueriesContext(connection) as com_seis:
            self.client.get(self.url)

        self.assertEqual(
            len(com_uma), len(com_seis),
            f"1 venda usou {len(com_uma)} queries e 6 usaram {len(com_seis)}: "
            "o painel está com N+1",
        )


class SigningTest(TestCase):
    def test_assinatura_valida_volta_o_codigo(self):
        payload = build_payload("abc-123")
        self.assertEqual(parse_payload(payload), "abc-123")

    def test_assinatura_adulterada_e_rejeitada(self):
        payload = build_payload("abc-123")
        # Troca o último caractere por um GARANTIDAMENTE diferente. A primeira
        # versão deste teste fazia `payload[:-1] + "0"` e passava por engano
        # quando a assinatura já terminava em "0" — não adulterava nada.
        trocado = "1" if payload[-1] == "0" else "0"
        self.assertIsNone(parse_payload(payload[:-1] + trocado))

    def test_codigo_trocado_invalida_a_assinatura(self):
        """Assinatura de um ingresso não serve para outro."""
        assinatura = sign_code("ingresso-A")
        self.assertIsNone(parse_payload(f"ingresso-B.{assinatura}"))

    def test_payload_sem_assinatura_e_rejeitado(self):
        self.assertIsNone(parse_payload("so-o-codigo"))
        self.assertIsNone(parse_payload(""))


class GateTest(TestCase):
    def setUp(self):
        _, self.evento = _make_world(capacity=10)
        self.cliente = User.objects.create_user(
            email="cli@t.dev", password="x", full_name="Cli", role=User.Role.CUSTOMER
        )
        self.portaria = User.objects.create_user(
            email="gate@t.dev", password="x", full_name="Portaria", role=User.Role.GATE
        )
        reserva = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=1
        )
        _, tickets = services.pay_reservation(reservation_id=reserva.pk, customer=self.cliente)
        self.ticket = tickets[0]

    def _validar(self, payload, event_id=None):
        return services.validate_ticket(
            payload=payload,
            event_id=event_id or self.evento.pk,
            gate_user=self.portaria,
        )

    def test_primeira_leitura_libera(self):
        resultado, ticket, _ = self._validar(self.ticket.qr_payload)
        self.assertEqual(resultado, services.GateResult.VALID)
        ticket.refresh_from_db()
        self.assertEqual(ticket.status, Ticket.Status.USED)
        self.assertEqual(ticket.used_by, self.portaria)

    def test_segunda_leitura_acusa_ja_utilizado(self):
        self._validar(self.ticket.qr_payload)
        resultado, _, detalhe = self._validar(self.ticket.qr_payload)
        self.assertEqual(resultado, services.GateResult.ALREADY_USED)
        self.assertIn("Utilizado em", detalhe)

    def test_qr_forjado_e_invalido(self):
        import uuid

        forjado = f"{uuid.uuid4()}.assinatura-inventada"
        resultado, _, _ = self._validar(forjado)
        self.assertEqual(resultado, services.GateResult.INVALID)

    def test_evento_errado(self):
        outro = Event.objects.create(
            organizer=self.evento.organizer,
            source=Event.Source.TMDB,
            external_id="2",
            title="Outro Show",
            venue="X",
            starts_at=timezone.now() + timedelta(days=9),
            status=Event.Status.PUBLISHED,
            price=Decimal("1.00"),
            capacity=1,
        )
        resultado, _, detalhe = self._validar(self.ticket.qr_payload, event_id=outro.pk)
        self.assertEqual(resultado, services.GateResult.WRONG_EVENT)
        self.assertIn("Show de Teste", detalhe)

    def test_codigo_digitado_na_mao_funciona(self):
        """Quando a câmera falha, a portaria digita o código."""
        resultado, _, _ = self._validar(str(self.ticket.code))
        self.assertEqual(resultado, services.GateResult.VALID)


class PaymentAndStockTest(TestCase):
    def setUp(self):
        _, self.evento = _make_world(capacity=20, price="30.00")
        self.cliente = User.objects.create_user(
            email="cli2@t.dev", password="x", full_name="Cli", role=User.Role.CUSTOMER
        )

    def test_reserva_segura_estoque_antes_do_pagamento(self):
        services.create_reservation(customer=self.cliente, event_id=self.evento.pk, quantity=4)
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.sold_count, 4)

    def test_pagamento_confirmado_emite_um_ingresso_por_lugar(self):
        reserva = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=3
        )
        pagamento, tickets = services.pay_reservation(
            reservation_id=reserva.pk, customer=self.cliente
        )
        self.assertEqual(pagamento.status, pagamento.Status.CONFIRMED)
        self.assertEqual(len(tickets), 3)
        self.assertEqual(len({t.code for t in tickets}), 3, "códigos devem ser distintos")
        self.assertEqual(len({t.share_token for t in tickets}), 3)

    def test_pagamento_recusado_devolve_o_estoque(self):
        reserva = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=services.LIMITE_RECUSA
        )
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.sold_count, services.LIMITE_RECUSA)

        pagamento, tickets = services.pay_reservation(
            reservation_id=reserva.pk, customer=self.cliente
        )
        self.evento.refresh_from_db()
        self.assertEqual(pagamento.status, pagamento.Status.REFUSED)
        self.assertEqual(tickets, [])
        self.assertEqual(self.evento.sold_count, 0, "recusa deve devolver o estoque")

    def test_nao_paga_duas_vezes(self):
        reserva = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=1
        )
        services.pay_reservation(reservation_id=reserva.pk, customer=self.cliente)
        with self.assertRaises(services.ReservationError):
            services.pay_reservation(reservation_id=reserva.pk, customer=self.cliente)

    def test_cancelar_devolve_estoque_e_apaga_ingressos(self):
        reserva = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=2
        )
        services.pay_reservation(reservation_id=reserva.pk, customer=self.cliente)
        services.cancel_reservation(reservation_id=reserva.pk, customer=self.cliente)

        self.evento.refresh_from_db()
        self.assertEqual(self.evento.sold_count, 0)
        self.assertEqual(Ticket.objects.filter(reservation=reserva).count(), 0)

    def test_nao_cancela_com_ingresso_ja_utilizado(self):
        portaria = User.objects.create_user(
            email="g2@t.dev", password="x", full_name="G", role=User.Role.GATE
        )
        reserva = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=1
        )
        _, tickets = services.pay_reservation(reservation_id=reserva.pk, customer=self.cliente)
        services.validate_ticket(
            payload=tickets[0].qr_payload, event_id=self.evento.pk, gate_user=portaria
        )
        with self.assertRaises(services.ReservationError):
            services.cancel_reservation(reservation_id=reserva.pk, customer=self.cliente)

    def test_preco_e_congelado_na_reserva(self):
        reserva = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=2
        )
        self.assertEqual(reserva.total_price, Decimal("60.00"))

        self.evento.price = Decimal("99.00")
        self.evento.save(update_fields=["price"])
        reserva.refresh_from_db()
        self.assertEqual(reserva.total_price, Decimal("60.00"), "reajuste não muda reserva antiga")

    def test_evento_em_rascunho_nao_aceita_reserva(self):
        self.evento.status = Event.Status.DRAFT
        self.evento.save(update_fields=["status"])
        with self.assertRaises(services.ReservationError):
            services.create_reservation(customer=self.cliente, event_id=self.evento.pk, quantity=1)


class PrazoDeReservaTest(TestCase):
    """
    O prazo existe porque, sem ele, quem fecha a aba no checkout trava o lugar
    para sempre — a reserva fica PENDING e nada nunca a cancela.
    """

    def setUp(self):
        _, self.evento = _make_world(capacity=10, price="20.00")
        self.cliente = User.objects.create_user(
            email="prazo@t.dev", password="x", full_name="P", role=User.Role.CUSTOMER
        )
        self.outro = User.objects.create_user(
            email="prazo2@t.dev", password="x", full_name="P2", role=User.Role.CUSTOMER
        )

    def _envelhecer(self, reserva, minutos):
        """created_at é auto_now_add; para envelhecer é preciso um UPDATE."""
        Reservation.objects.filter(pk=reserva.pk).update(
            created_at=timezone.now() - timedelta(minutes=minutos)
        )

    def test_reserva_dentro_do_prazo_nao_expira(self):
        r = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=2
        )
        self._envelhecer(r, 5)
        self.assertEqual(services.expire_reservations(), 0)
        r.refresh_from_db()
        self.assertEqual(r.status, Reservation.Status.PENDING)

    def test_reserva_vencida_devolve_o_estoque(self):
        r = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=4
        )
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.sold_count, 4)

        self._envelhecer(r, 11)
        self.assertEqual(services.expire_reservations(), 1)

        r.refresh_from_db()
        self.evento.refresh_from_db()
        self.assertEqual(r.status, Reservation.Status.EXPIRED)
        self.assertEqual(self.evento.sold_count, 0)

    def test_expirar_e_idempotente(self):
        r = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=1
        )
        self._envelhecer(r, 11)
        self.assertEqual(services.expire_reservations(), 1)
        # Segunda passada não acha mais nada e não mexe no estoque de novo.
        self.assertEqual(services.expire_reservations(), 0)
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.sold_count, 0)

    def test_reserva_paga_nunca_expira(self):
        r = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=1
        )
        services.pay_reservation(reservation_id=r.pk, customer=self.cliente)
        self._envelhecer(r, 999)

        self.assertEqual(services.expire_reservations(), 0)
        r.refresh_from_db()
        self.assertEqual(r.status, Reservation.Status.PAID)

    def test_nao_paga_reserva_vencida(self):
        """
        Sem esta checagem, uma aba aberta há duas horas ainda pagaria — e o
        lugar já podia ter sido devolvido e revendido a outra pessoa.
        """
        r = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=1
        )
        self._envelhecer(r, 11)

        with self.assertRaises(services.ReservationError) as ctx:
            services.pay_reservation(reservation_id=r.pk, customer=self.cliente)
        self.assertIn("prazo", str(ctx.exception).lower())

        r.refresh_from_db()
        self.evento.refresh_from_db()
        self.assertEqual(r.status, Reservation.Status.EXPIRED)
        self.assertEqual(self.evento.sold_count, 0, "o estoque tem que voltar")

    def test_estoque_abandonado_volta_para_o_proximo_cliente(self):
        """
        O caso que motivou tudo: um evento pequeno esgotado por desistências
        silenciosas volta a vender sem ninguém intervir.
        """
        r = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=10
        )
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.available, 0)

        with self.assertRaises(services.ReservationError):
            services.create_reservation(
                customer=self.outro, event_id=self.evento.pk, quantity=1
            )

        self._envelhecer(r, 11)

        # Ninguém rodou comando nenhum: a própria tentativa de reservar limpa.
        nova = services.create_reservation(
            customer=self.outro, event_id=self.evento.pk, quantity=1
        )
        self.assertEqual(nova.status, Reservation.Status.PENDING)
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.sold_count, 1)

    def test_assentos_tambem_voltam_ao_expirar(self):
        _, teatro = _make_seated(seats=4, slug="prazo")
        assentos = list(teatro.seats.order_by("number")[:2])
        r = services.create_reservation(
            customer=self.cliente, event_id=teatro.pk, seat_ids=[a.pk for a in assentos]
        )
        self._envelhecer(r, 11)
        services.expire_reservations()

        teatro.refresh_from_db()
        self.assertEqual(teatro.sold_count, 0)
        self.assertEqual(teatro.seats.filter(status=Seat.Status.AVAILABLE).count(), 4)

    def test_comando_de_manutencao_expira_e_o_dry_run_nao(self):
        from io import StringIO

        from django.core.management import call_command

        r = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=3
        )
        self._envelhecer(r, 11)

        saida = StringIO()
        call_command("expirar_reservas", "--dry-run", stdout=saida)
        r.refresh_from_db()
        self.assertEqual(r.status, Reservation.Status.PENDING, "dry-run não pode alterar")
        self.assertIn("seriam expiradas", saida.getvalue())

        call_command("expirar_reservas", stdout=StringIO())
        r.refresh_from_db()
        self.assertEqual(r.status, Reservation.Status.EXPIRED)


class ConsultasTest(TestCase):
    """
    Trava o número de idas ao banco nas listagens.

    A asserção compara "poucos dados" contra "muitos dados" e exige o MESMO
    número de queries, em vez de cravar um valor. Um número fixo quebraria a
    cada middleware ou índice novo sem que nada de errado tivesse acontecido —
    o que interessa é a listagem não ficar mais lenta à medida que o cliente
    compra mais.
    """

    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        _, self.evento = _make_world(capacity=50, price="20.00")
        self.cliente = User.objects.create_user(
            email="q@t.dev", password="x", full_name="Q", role=User.Role.CUSTOMER
        )
        self.client.force_authenticate(self.cliente)

    def _comprar(self, quantidade=2):
        r = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=quantidade
        )
        services.pay_reservation(reservation_id=r.pk, customer=self.cliente)

    def test_listar_reservas_nao_cresce_em_queries(self):
        """
        O serializer aninhado lê event_title, venue e seat_label de CADA
        ingresso. Sem prefetch de tickets__event e tickets__seat, eram duas
        queries por ingresso — 17 no total para 5 reservas, e subindo.
        """
        self._comprar()
        with CaptureQueriesContext(connection) as poucas:
            self.client.get(reverse("reservation-list"))

        for _ in range(5):
            self._comprar()
        with CaptureQueriesContext(connection) as muitas:
            self.client.get(reverse("reservation-list"))

        self.assertEqual(
            len(poucas), len(muitas),
            f"1 reserva usou {len(poucas)} queries e 6 usaram {len(muitas)}: N+1 de volta",
        )

    def test_carteira_de_ingressos_nao_cresce_em_queries(self):
        self._comprar(1)
        with CaptureQueriesContext(connection) as poucas:
            self.client.get(reverse("my-tickets"))

        self._comprar(6)
        with CaptureQueriesContext(connection) as muitas:
            self.client.get(reverse("my-tickets"))

        self.assertEqual(len(poucas), len(muitas))

    def test_vitrine_nao_cresce_com_o_numero_de_eventos(self):
        from django.utils import timezone as tz

        self.client.force_authenticate(None)
        with CaptureQueriesContext(connection) as poucos:
            self.client.get(reverse("event-list"))

        for i in range(8):
            Event.objects.create(
                organizer=self.evento.organizer,
                source=Event.Source.TMDB,
                external_id=f"extra-{i}",
                title=f"Extra {i}",
                venue="X",
                starts_at=tz.now() + timedelta(days=30),
                status=Event.Status.PUBLISHED,
                price=Decimal("10.00"),
                capacity=10,
            )
        with CaptureQueriesContext(connection) as muitos:
            self.client.get(reverse("event-list"))

        self.assertEqual(
            len(poucos), len(muitos),
            "a vitrine é a página mais acessada: N+1 aqui é o pior lugar possível",
        )


class PortariaCodigoCurtoTest(TestCase):
    """Validação pelo código de 8 caracteres — a alternativa à câmera."""

    def setUp(self):
        _, self.evento = _make_world(capacity=10)
        self.cliente = User.objects.create_user(
            email="cc@t.dev", password="x", full_name="C", role=User.Role.CUSTOMER
        )
        self.portaria = User.objects.create_user(
            email="pcc@t.dev", password="x", full_name="P", role=User.Role.GATE
        )
        r = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=1
        )
        _, tickets = services.pay_reservation(reservation_id=r.pk, customer=self.cliente)
        self.ticket = tickets[0]

    def _validar(self, valor):
        return services.validate_ticket(
            payload=valor, event_id=self.evento.pk, gate_user=self.portaria
        )

    def test_codigo_curto_tem_oito_caracteres_sem_ambiguos(self):
        from ticketing.models import ALFABETO_CODIGO

        self.assertEqual(len(self.ticket.short_code), 8)
        # Sem O/0 e I/1: quem digita olhando um papel amassado não erra por isso.
        self.assertTrue(set(self.ticket.short_code) <= set(ALFABETO_CODIGO))
        for proibido in "O0I1":
            self.assertNotIn(proibido, ALFABETO_CODIGO)

    def test_valida_pelo_codigo_curto(self):
        resultado, _, _ = self._validar(self.ticket.short_code)
        self.assertEqual(resultado, services.GateResult.VALID)

    def test_codigo_curto_e_aceito_em_minusculas(self):
        """Teclado de celular capitaliza sozinho — e às vezes não."""
        outro = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=1
        )
        _, tickets = services.pay_reservation(reservation_id=outro.pk, customer=self.cliente)
        resultado, _, _ = self._validar(tickets[0].short_code.lower())
        self.assertEqual(resultado, services.GateResult.VALID)

    def test_uuid_completo_continua_funcionando(self):
        resultado, _, _ = self._validar(str(self.ticket.code))
        self.assertEqual(resultado, services.GateResult.VALID)

    def test_qr_assinado_continua_funcionando(self):
        resultado, _, _ = self._validar(self.ticket.qr_payload)
        self.assertEqual(resultado, services.GateResult.VALID)

    def test_codigo_curto_inexistente_e_invalido(self):
        resultado, _, _ = self._validar("ZZZZ9999")
        self.assertEqual(resultado, services.GateResult.INVALID)


class PortariaDesfazerTest(TestCase):
    """
    Desfazer existe porque a portaria erra: lê o QR da pessoa de trás, toca
    duas vezes. Sem isso, a saída é o cliente ficar de fora ou alguém abrir o
    admin do Django numa fila.
    """

    def setUp(self):
        _, self.evento = _make_world(capacity=10)
        self.cliente = User.objects.create_user(
            email="cd@t.dev", password="x", full_name="C", role=User.Role.CUSTOMER
        )
        self.portaria = User.objects.create_user(
            email="pd@t.dev", password="x", full_name="P", role=User.Role.GATE
        )
        r = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=1
        )
        _, tickets = services.pay_reservation(reservation_id=r.pk, customer=self.cliente)
        self.ticket = tickets[0]
        services.validate_ticket(
            payload=self.ticket.qr_payload,
            event_id=self.evento.pk,
            gate_user=self.portaria,
        )

    def test_desfazer_devolve_o_ingresso_ao_estado_valido(self):
        services.undo_validation(ticket_code=self.ticket.code, gate_user=self.portaria)
        self.ticket.refresh_from_db()
        self.assertEqual(self.ticket.status, Ticket.Status.VALID)
        self.assertIsNone(self.ticket.used_at)
        self.assertIsNone(self.ticket.used_by)

    def test_depois_de_desfazer_o_ingresso_valida_de_novo(self):
        services.undo_validation(ticket_code=self.ticket.code, gate_user=self.portaria)
        resultado, _, _ = services.validate_ticket(
            payload=self.ticket.qr_payload,
            event_id=self.evento.pk,
            gate_user=self.portaria,
        )
        self.assertEqual(resultado, services.GateResult.VALID)

    def test_fora_da_janela_nao_desfaz(self):
        """Passados 5 min a pessoa já entrou; reverter viraria reabrir a porta."""
        Ticket.objects.filter(pk=self.ticket.pk).update(
            used_at=timezone.now() - timedelta(minutes=6)
        )
        with self.assertRaises(services.ReservationError) as ctx:
            services.undo_validation(ticket_code=self.ticket.code, gate_user=self.portaria)
        self.assertIn("desfazer", str(ctx.exception).lower())

    def test_nao_desfaz_ingresso_que_nunca_foi_usado(self):
        services.undo_validation(ticket_code=self.ticket.code, gate_user=self.portaria)
        with self.assertRaises(services.ReservationError):
            services.undo_validation(ticket_code=self.ticket.code, gate_user=self.portaria)

    def test_codigo_inexistente(self):
        import uuid as _uuid

        with self.assertRaises(services.ReservationError):
            services.undo_validation(ticket_code=_uuid.uuid4(), gate_user=self.portaria)


class PortariaPlacarTest(TestCase):
    """O contador de entradas vem junto da lista de eventos, não numa 2ª chamada."""

    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        _, self.evento = _make_world(capacity=10)
        self.cliente = User.objects.create_user(
            email="cp@t.dev", password="x", full_name="C", role=User.Role.CUSTOMER
        )
        self.portaria = User.objects.create_user(
            email="pp@t.dev", password="x", full_name="P", role=User.Role.GATE
        )
        self.client.force_authenticate(self.portaria)

    def test_placar_reflete_as_validacoes(self):
        r = services.create_reservation(
            customer=self.cliente, event_id=self.evento.pk, quantity=3
        )
        _, tickets = services.pay_reservation(reservation_id=r.pk, customer=self.cliente)

        antes = self.client.get(reverse("gate-events")).json()[0]
        self.assertEqual((antes["tickets_total"], antes["tickets_used"]), (3, 0))

        services.validate_ticket(
            payload=tickets[0].qr_payload,
            event_id=self.evento.pk,
            gate_user=self.portaria,
        )
        depois = self.client.get(reverse("gate-events")).json()[0]
        self.assertEqual((depois["tickets_total"], depois["tickets_used"]), (3, 1))

    def test_placar_nao_cresce_em_queries_com_mais_eventos(self):
        with CaptureQueriesContext(connection) as poucos:
            self.client.get(reverse("gate-events"))

        for i in range(6):
            Event.objects.create(
                organizer=self.evento.organizer,
                source=Event.Source.TMDB,
                external_id=f"p-{i}",
                title=f"Evento {i}",
                venue="X",
                starts_at=timezone.now() + timedelta(days=20),
                status=Event.Status.PUBLISHED,
                price=Decimal("10.00"),
                capacity=10,
            )
        with CaptureQueriesContext(connection) as muitos:
            self.client.get(reverse("gate-events"))

        self.assertEqual(
            len(poucos), len(muitos),
            "a lista da portaria recarrega a cada validação: N+1 aqui é caro",
        )


class ResumoDoOrganizadorTest(TestCase):
    """
    O cabeçalho do painel: receita, ingressos e o próximo evento, somando
    TODOS os eventos do organizador.
    """

    def setUp(self):
        from rest_framework.test import APIClient

        self.client = APIClient()
        self.org, self.evento = _make_world(capacity=20, price="30.00")
        self.cliente = User.objects.create_user(
            email="comprador@t.dev", password="x", full_name="Caio", role=User.Role.CUSTOMER
        )
        self.url = reverse("organizer-summary")

    def _evento(self, titulo, dias, status=Event.Status.PUBLISHED, organizer=None, preco="10.00"):
        return Event.objects.create(
            organizer=organizer or self.org,
            source=Event.Source.TMDB,
            external_id=titulo,
            title=titulo,
            venue="Arena",
            starts_at=timezone.now() + timedelta(days=dias),
            kind=Event.Kind.GA,
            status=status,
            price=Decimal(preco),
            capacity=50,
        )

    def _comprar(self, evento, quantidade=1, pagar=True):
        r = services.create_reservation(
            customer=self.cliente, event_id=evento.pk, quantity=quantidade
        )
        if pagar:
            services.pay_reservation(reservation_id=r.pk, customer=self.cliente)
        return r

    def _get(self, usuario=None):
        self.client.force_authenticate(usuario or self.org)
        return self.client.get(self.url).json()

    def test_soma_a_receita_de_todos_os_eventos(self):
        outro = self._evento("Segundo", dias=9, preco="25.00")
        self._comprar(self.evento, 2)   # 60,00
        self._comprar(outro, 4)         # 100,00

        self.assertEqual(self._get()["revenue"], "160.00")

    def test_receita_nao_multiplica_pelo_numero_de_ingressos(self):
        """
        Regressão do bug clássico de agregação: pedir Sum("total_price") num
        queryset que também junta tickets repete a linha da reserva uma vez por
        ingresso. Uma reserva de 3 × R$ 30 valeria R$ 270 em vez de R$ 90.
        """
        self._comprar(self.evento, 3)

        dados = self._get()
        self.assertEqual(dados["revenue"], "90.00")
        self.assertEqual(dados["tickets_sold"], 3)

    def test_receita_ignora_reserva_nao_paga(self):
        self._comprar(self.evento, 2, pagar=True)
        self._comprar(self.evento, 5, pagar=False)

        dados = self._get()
        self.assertEqual(dados["revenue"], "60.00")
        # A pendente já ocupa estoque (sold_count = 7), mas não emitiu ingresso
        # nem virou dinheiro. O card conta ingresso justamente por isso.
        self.evento.refresh_from_db()
        self.assertEqual(self.evento.sold_count, 7)
        self.assertEqual(dados["tickets_sold"], 2)

    def test_nao_conta_evento_de_outro_organizador(self):
        alheio = User.objects.create_user(
            email="org2@t.dev", password="x", full_name="Org2", role=User.Role.ORGANIZER
        )
        de_outro = self._evento("Do outro", dias=2, organizer=alheio, preco="99.00")
        self._comprar(de_outro, 3)
        self._comprar(self.evento, 1)

        dados = self._get()
        self.assertEqual(dados["revenue"], "30.00")
        self.assertEqual(dados["tickets_sold"], 1)
        self.assertEqual(dados["next_event"]["title"], "Show de Teste")

    def test_proximo_evento_e_o_publicado_mais_perto(self):
        self._evento("Daqui a um mês", dias=30)
        logo = self._evento("Depois de amanhã", dias=2)

        proximo = self._get()["next_event"]
        self.assertEqual(proximo["id"], logo.pk)
        self.assertEqual(proximo["capacity"], 50)

    def test_proximo_evento_ignora_rascunho_e_passado(self):
        self._evento("Rascunho de amanhã", dias=1, status=Event.Status.DRAFT)
        self._evento("Já aconteceu", dias=-1)

        # Sobra só o do setUp, daqui a 5 dias.
        self.assertEqual(self._get()["next_event"]["title"], "Show de Teste")

    def test_proximo_evento_nulo_quando_nao_ha_futuro(self):
        Event.objects.update(starts_at=timezone.now() - timedelta(days=1))

        dados = self._get()
        self.assertIsNone(dados["next_event"])
        self.assertEqual(dados["upcoming_count"], 0)
        self.assertEqual(dados["past_count"], 1)

    def test_conta_futuros_e_passados_para_as_abas(self):
        self._evento("Passado 1", dias=-10)
        self._evento("Passado 2", dias=-3, status=Event.Status.DRAFT)
        self._evento("Futuro", dias=3)

        dados = self._get()
        self.assertEqual(dados["upcoming_count"], 2)
        self.assertEqual(dados["past_count"], 2)

    def test_cliente_nao_ve_o_resumo(self):
        self.client.force_authenticate(self.cliente)
        self.assertEqual(self.client.get(self.url).status_code, 403)

    def test_receita_zerada_vem_como_string(self):
        """Dinheiro é string em toda a API; zero não pode virar 0 (número)."""
        self.assertEqual(self._get()["revenue"], "0.00")
