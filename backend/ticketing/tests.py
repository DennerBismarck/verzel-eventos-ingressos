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
from django.utils import timezone

from events.models import Event

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
