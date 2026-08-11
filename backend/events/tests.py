"""
Testes de evento e catálogo externo.

Os testes do catálogo NÃO tocam a rede: `requests.get` é substituído por um
dublê. Teste que depende de API de terceiro falha quando o terceiro cai, gasta
cota a cada execução e não roda no CI sem chave — deixa de ser teste e vira
monitoramento.
"""

import threading
import time
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TransactionTestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .catalog import CatalogError, get_provider
from .catalog.base import CatalogItem, CatalogProvider
from .models import Event

User = get_user_model()

SENHA = "verzel123456"


def daqui(dias):
    """Data relativa a agora. Negativo = passado."""
    return timezone.now() + timedelta(days=dias)


def criar_evento(organizer, **kwargs):
    dados = {
        "source": Event.Source.TMDB,
        "external_id": "1",
        "title": "Filme de Teste",
        "venue": "Cine Teste, São Paulo",
        "starts_at": timezone.now() + timedelta(days=10),
        "kind": Event.Kind.GA,
        "status": Event.Status.PUBLISHED,
        "price": Decimal("30.00"),
        "capacity": 50,
    }
    dados.update(kwargs)
    return Event.objects.create(organizer=organizer, **dados)


class VitrinePublicaTest(APITestCase):
    def setUp(self):
        self.org = User.objects.create_user(
            email="org@b.dev", password=SENHA, full_name="Org", role=User.Role.ORGANIZER
        )
        self.publicado = criar_evento(self.org, external_id="1", title="Duna")
        self.rascunho = criar_evento(
            self.org, external_id="2", title="Segredo", status=Event.Status.DRAFT
        )

    def test_lista_e_publica_e_so_mostra_publicados(self):
        r = self.client.get(reverse("event-list"))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual([e["title"] for e in r.json()["results"]], ["Duna"])

    def test_rascunho_devolve_404_e_nao_403(self):
        """403 confirmaria que o evento existe. 404 não conta nada."""
        r = self.client.get(reverse("event-detail", args=[self.rascunho.pk]))
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_busca_por_titulo_e_por_local(self):
        criar_evento(self.org, external_id="3", title="Outro", venue="Arena Teatro")
        self.assertEqual(self.client.get(reverse("event-list"), {"q": "dun"}).json()["count"], 1)
        self.assertEqual(
            self.client.get(reverse("event-list"), {"q": "arena"}).json()["count"], 1
        )
        self.assertEqual(self.client.get(reverse("event-list"), {"q": "zzz"}).json()["count"], 0)

    def test_filtro_por_tipo(self):
        criar_evento(self.org, external_id="4", title="Com lugar", kind=Event.Kind.SEATED)
        r = self.client.get(reverse("event-list"), {"kind": "seated"})
        self.assertEqual([e["title"] for e in r.json()["results"]], ["Com lugar"])

    def test_vitrine_nao_expoe_estoque_nem_dono(self):
        """sold_count e organizer_id são informação interna do organizador."""
        campos = self.client.get(reverse("event-list")).json()["results"][0]
        self.assertNotIn("sold_count", campos)
        self.assertNotIn("capacity", campos)
        self.assertNotIn("organizer", campos)
        self.assertIn("available", campos)

    def test_disponivel_desconta_o_vendido(self):
        self.publicado.sold_count = 20
        self.publicado.save(update_fields=["sold_count"])
        r = self.client.get(reverse("event-detail", args=[self.publicado.pk]))
        self.assertEqual(r.json()["available"], 30)

    def test_vitrine_sai_em_ordem_de_data(self):
        """
        Regressão: `com_preco_inicial()` anota um Min() sobre `seats`, e
        annotate() com agregação de relação múltipla DESCARTA o Meta.ordering.
        A vitrine passou a sair sem ORDER BY nenhum — na prática na ordem de
        inserção, e sem garantia de estabilidade entre páginas.
        """
        criar_evento(self.org, external_id="7", title="Depois", starts_at=daqui(40))
        criar_evento(self.org, external_id="8", title="Antes", starts_at=daqui(1))

        titulos = [e["title"] for e in self.client.get(reverse("event-list")).json()["results"]]
        self.assertEqual(titulos, ["Antes", "Duna", "Depois"])

    def test_vitrine_nao_anuncia_evento_que_ja_comecou(self):
        """
        O backend já recusa reservar evento começado ("Este evento já
        começou"). Mantê-lo em "Em cartaz" só entregava ao cliente um caminho
        que termina em erro — e a busca trazia o mesmo evento de volta.
        """
        criar_evento(self.org, external_id="9", title="Ontem", starts_at=daqui(-1))

        lista = self.client.get(reverse("event-list")).json()["results"]
        self.assertNotIn("Ontem", [e["title"] for e in lista])
        self.assertEqual(self.client.get(reverse("event-list"), {"q": "ontem"}).json()["count"], 0)

    def test_pagina_do_evento_passado_continua_existindo(self):
        """
        Sumir da vitrine e deixar de existir são coisas diferentes: quem foi ao
        evento ainda tem o link da sessão em "Meus ingressos".
        """
        passado = criar_evento(self.org, external_id="9", title="Ontem", starts_at=daqui(-1))
        r = self.client.get(reverse("event-detail", args=[passado.pk]))
        self.assertEqual(r.status_code, status.HTTP_200_OK)

    def test_a_consulta_da_vitrine_tem_order_by(self):
        """
        O teste acima passaria por acidente se o banco devolvesse na ordem de
        inserção. Este olha o SQL: sem ORDER BY, a paginação pode repetir uma
        linha na página 2 e nunca mostrar outra.
        """
        sql = str(Event.objects.com_preco_inicial().query)
        self.assertIn("ORDER BY", sql)


class PainelDoOrganizadorTest(APITestCase):
    def setUp(self):
        self.org = User.objects.create_user(
            email="org@b.dev", password=SENHA, full_name="Org", role=User.Role.ORGANIZER
        )
        self.outro = User.objects.create_user(
            email="outro@b.dev", password=SENHA, full_name="Outro", role=User.Role.ORGANIZER
        )
        self.cliente = User.objects.create_user(
            email="cli@b.dev", password=SENHA, full_name="Cli", role=User.Role.CUSTOMER
        )
        self.meu = criar_evento(self.org, external_id="1", title="Meu")
        self.alheio = criar_evento(self.outro, external_id="9", title="Alheio")
        self.lista = reverse("organizer-event-list")

    def corpo(self, **extra):
        dados = {
            "source": "TMDB", "external_id": "77", "title": "Novo",
            "venue": "Arena", "starts_at": (timezone.now() + timedelta(days=20)).isoformat(),
            "kind": "GA", "status": "PUBLISHED", "price": "50.00", "capacity": 100,
        }
        dados.update(extra)
        return dados

    def test_organizador_ve_os_proprios_inclusive_rascunho(self):
        criar_evento(self.org, external_id="5", title="Rascunho", status=Event.Status.DRAFT)
        self.client.force_authenticate(self.org)
        titulos = {e["title"] for e in self.client.get(self.lista).json()["results"]}
        self.assertEqual(titulos, {"Meu", "Rascunho"})

    def test_evento_de_outro_organizador_devolve_404(self):
        """
        A autorização mora no get_queryset. O objeto alheio simplesmente não
        está lá, então some — em vez de existir e ser negado com 403.
        """
        self.client.force_authenticate(self.org)
        url = reverse("organizer-event-detail", args=[self.alheio.pk])
        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(
            self.client.patch(url, {"title": "Sequestrado"}, format="json").status_code,
            status.HTTP_404_NOT_FOUND,
        )
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_404_NOT_FOUND)
        self.alheio.refresh_from_db()
        self.assertEqual(self.alheio.title, "Alheio")

    def test_cliente_nao_acessa_o_painel(self):
        self.client.force_authenticate(self.cliente)
        self.assertEqual(self.client.get(self.lista).status_code, status.HTTP_403_FORBIDDEN)

    def test_anonimo_leva_401(self):
        self.assertEqual(self.client.get(self.lista).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_dono_vem_do_token_e_nao_do_corpo(self):
        """Mandar organizer no JSON não pode criar evento no nome de outro."""
        self.client.force_authenticate(self.org)
        r = self.client.post(self.lista, self.corpo(organizer=self.outro.pk), format="json")
        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(Event.objects.get(external_id="77").organizer, self.org)

    def test_sold_count_e_somente_leitura(self):
        """Se o cliente pudesse mandar sold_count, o no-double-sell não valeria nada."""
        self.client.force_authenticate(self.org)
        self.client.patch(
            reverse("organizer-event-detail", args=[self.meu.pk]),
            {"sold_count": 999},
            format="json",
        )
        self.meu.refresh_from_db()
        self.assertEqual(self.meu.sold_count, 0)

    def test_data_no_passado_e_recusada(self):
        self.client.force_authenticate(self.org)
        r = self.client.post(
            self.lista,
            self.corpo(starts_at=(timezone.now() - timedelta(days=1)).isoformat()),
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("starts_at", r.json())

    def test_publicar_pista_sem_capacidade_e_recusado(self):
        self.client.force_authenticate(self.org)
        r = self.client.post(self.lista, self.corpo(capacity=0), format="json")
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("capacity", r.json())

    def test_nao_reduz_capacidade_abaixo_do_ja_vendido(self):
        """
        Sem esta validação o UPDATE bateria na CheckConstraint e viraria 500.
        Erro de regra tem que sair como 400 explicando, não como falha do
        servidor.
        """
        self.meu.sold_count = 30
        self.meu.save(update_fields=["sold_count"])
        self.client.force_authenticate(self.org)
        r = self.client.patch(
            reverse("organizer-event-detail", args=[self.meu.pk]),
            {"capacity": 10},
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("30", str(r.json()["capacity"]))

    def test_despublicar_tira_da_vitrine(self):
        self.client.force_authenticate(self.org)
        self.client.patch(
            reverse("organizer-event-detail", args=[self.meu.pk]),
            {"status": "DRAFT"},
            format="json",
        )
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse("event-list")).json()["count"], 1)


class MapaDeAssentosTest(APITestCase):
    def setUp(self):
        self.org = User.objects.create_user(
            email="org@b.dev", password=SENHA, full_name="Org", role=User.Role.ORGANIZER
        )
        self.outro = User.objects.create_user(
            email="outro@b.dev", password=SENHA, full_name="Outro", role=User.Role.ORGANIZER
        )
        self.cliente = User.objects.create_user(
            email="cli@b.dev", password=SENHA, full_name="Cli", role=User.Role.CUSTOMER
        )
        self.evento = criar_evento(
            self.org, external_id="s1", title="Teatro", kind=Event.Kind.SEATED, capacity=0
        )
        self.url = reverse("organizer-event-seats", args=[self.evento.pk])

    def layout(self, **extra):
        dados = {
            "sections": [
                {"name": "Plateia", "rows": ["A", "B"], "seats_per_row": 4, "price": "80.00"},
                {"name": "Balcão", "rows": ["C"], "seats_per_row": 3, "price": "50.00"},
            ]
        }
        dados.update(extra)
        return dados

    def test_gera_o_mapa_e_espelha_a_capacidade(self):
        self.client.force_authenticate(self.org)
        r = self.client.post(self.url, self.layout(), format="json")

        self.assertEqual(r.status_code, status.HTTP_201_CREATED)
        self.assertEqual(r.json()["created"], 11)  # 2x4 + 1x3
        self.evento.refresh_from_db()
        # capacity espelha o total para a vitrine e a CheckConstraint valerem
        # igual nos dois tipos de evento.
        self.assertEqual(self.evento.capacity, 11)
        self.assertEqual(self.evento.seats.filter(section="Plateia").count(), 8)

    def test_evento_de_pista_nao_tem_mapa(self):
        pista = criar_evento(self.org, external_id="p1", kind=Event.Kind.GA)
        self.client.force_authenticate(self.org)
        r = self.client.post(
            reverse("organizer-event-seats", args=[pista.pk]), self.layout(), format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("pista", r.json()["detail"].lower())

    def test_regerar_substitui_o_mapa_anterior(self):
        self.client.force_authenticate(self.org)
        self.client.post(self.url, self.layout(), format="json")
        r = self.client.post(
            self.url,
            {"sections": [{"name": "Única", "rows": ["A"], "seats_per_row": 2, "price": "10.00"}]},
            format="json",
        )
        self.assertEqual(r.json()["created"], 2)
        self.assertEqual(self.evento.seats.count(), 2)

    def test_nao_refaz_o_mapa_depois_de_vender(self):
        """
        Recriar apagaria a linha que um ingresso emitido aponta. O PROTECT do
        Ticket.seat barraria de qualquer forma, mas com erro de banco em vez
        de uma explicação.
        """
        from .models import Seat

        self.client.force_authenticate(self.org)
        self.client.post(self.url, self.layout(), format="json")
        Seat.objects.filter(event=self.evento).update(status=Seat.Status.SOLD)

        r = self.client.post(self.url, self.layout(), format="json")
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("vendeu", r.json()["detail"])

    def test_posicao_repetida_e_apontada_pelo_nome(self):
        self.client.force_authenticate(self.org)
        r = self.client.post(
            self.url,
            {
                "sections": [
                    {"name": "P", "rows": ["A", "A"], "seats_per_row": 2, "price": "10.00"}
                ]
            },
            format="json",
        )
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("A1", r.json()["detail"])

    def test_mapa_gigante_e_recusado_antes_de_construir(self):
        """
        Um zero a mais no formulário não pode virar um INSERT de milhões.

        A recusa acontece na passada de CONTAGEM, antes de qualquer objeto Seat
        existir — senão 100 mil objetos seriam alocados só para dizer "não".
        """
        self.client.force_authenticate(self.org)
        secao = lambda i: {  # noqa: E731
            "name": f"S{i}",
            "rows": [f"F{r}" for r in range(50)],
            "seats_per_row": 100,
            "price": "10.00",
        }
        r = self.client.post(
            self.url, {"sections": [secao(1), secao(2)]}, format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_409_CONFLICT)
        self.assertIn("10000", r.json()["detail"])
        self.assertEqual(self.evento.seats.count(), 0)

    def test_mapa_de_evento_alheio_devolve_404(self):
        alheio = criar_evento(self.outro, external_id="s9", kind=Event.Kind.SEATED)
        self.client.force_authenticate(self.org)
        r = self.client.post(
            reverse("organizer-event-seats", args=[alheio.pk]), self.layout(), format="json"
        )
        self.assertEqual(r.status_code, status.HTTP_404_NOT_FOUND)

    def test_cliente_nao_gera_mapa(self):
        self.client.force_authenticate(self.cliente)
        self.assertEqual(
            self.client.post(self.url, self.layout(), format="json").status_code,
            status.HTTP_403_FORBIDDEN,
        )

    def test_mapa_publico_mostra_situacao_mas_nao_o_comprador(self):
        self.client.force_authenticate(self.org)
        self.client.post(self.url, self.layout(), format="json")
        self.client.force_authenticate(None)

        r = self.client.get(reverse("event-seats", args=[self.evento.pk]))
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        assento = r.json()[0]
        self.assertIn("status", assento)
        # Saber que a poltrona está ocupada é necessário; saber de quem, não.
        self.assertNotIn("customer", str(assento))
        self.assertNotIn("reservations", assento)

    def test_mapa_publico_nao_vaza_o_de_um_rascunho(self):
        self.client.force_authenticate(self.org)
        self.client.post(self.url, self.layout(), format="json")
        self.evento.status = Event.Status.DRAFT
        self.evento.save(update_fields=["status"])
        self.client.force_authenticate(None)

        self.assertEqual(self.client.get(reverse("event-seats", args=[self.evento.pk])).json(), [])

    def test_mapa_publico_nao_e_paginado(self):
        """Paginar o mapa desenharia meia sala na tela."""
        self.client.force_authenticate(self.org)
        self.client.post(self.url, self.layout(), format="json")
        self.client.force_authenticate(None)
        corpo = self.client.get(reverse("event-seats", args=[self.evento.pk])).json()
        self.assertIsInstance(corpo, list)
        self.assertEqual(len(corpo), 11)


# --------------------------------------------------------------------------
# Catálogo externo — sempre com a rede dublada
# --------------------------------------------------------------------------
TMDB_CRU = {
    "results": [
        {
            "id": 693134,
            "title": "Duna: Parte Dois",
            "overview": "Paul Atreides se une aos Fremen.",
            "poster_path": "/abc.jpg",
        },
        {"id": 999, "original_title": "Sem Título Traduzido", "poster_path": None},
    ]
}

TM_CRU = {
    "_embedded": {
        "events": [
            {
                "id": "G5vYZbJGkdvWZ",
                "name": "Coldplay",
                "info": "Turnê mundial.",
                "images": [
                    {"url": "https://img/p.jpg", "width": 205},
                    {"url": "https://img/g.jpg", "width": 1024},
                ],
                "dates": {"start": {"dateTime": "2026-09-12T23:00:00Z"}},
                "_embedded": {"venues": [{"name": "Allianz Parque", "city": {"name": "São Paulo"}}]},
            },
            {"id": "SEM-DATA", "name": "Show sem horário", "dates": {"start": {"localDate": "2026-10-01"}}},
        ]
    }
}


class RespostaFalsa:
    def __init__(self, payload, erro=None):
        self._payload = payload
        self._erro = erro

    def raise_for_status(self):
        if self._erro:
            raise self._erro

    def json(self):
        return self._payload


@override_settings(TMDB_API_KEY="chave-de-teste", TICKETMASTER_API_KEY="chave-de-teste")
class ProvedoresTest(APITestCase):
    def setUp(self):
        # O provedor guarda resultado em cache; sem limpar, um teste contamina
        # o seguinte com a resposta do anterior.
        cache.clear()

    @patch("events.catalog.tmdb.requests.get")
    def test_tmdb_normaliza_e_monta_a_url_do_cartaz(self, mock_get):
        mock_get.return_value = RespostaFalsa(TMDB_CRU)
        itens = get_provider("TMDB").search("duna")

        self.assertEqual(itens[0].external_id, "693134")
        self.assertEqual(itens[0].title, "Duna: Parte Dois")
        self.assertTrue(itens[0].image_url.endswith("/abc.jpg"))
        # Filme não tem sessão: o organizador é quem preenche.
        self.assertEqual(itens[0].venue, "")
        self.assertIsNone(itens[0].starts_at)

    def test_tmdb_aguenta_item_sem_titulo_traduzido_e_sem_cartaz(self):
        with patch("events.catalog.tmdb.requests.get", return_value=RespostaFalsa(TMDB_CRU)):
            itens = get_provider("TMDB").search("x")
        self.assertEqual(itens[1].title, "Sem Título Traduzido")
        self.assertEqual(itens[1].image_url, "")

    @patch("events.catalog.tmdb.requests.get")
    def test_a_chave_nao_aparece_no_item_normalizado(self, mock_get):
        mock_get.return_value = RespostaFalsa(TMDB_CRU)
        item = get_provider("TMDB").search("duna")[0]
        self.assertNotIn("chave-de-teste", str(item.to_dict()))

    @patch("events.catalog.ticketmaster.requests.get")
    def test_ticketmaster_normaliza_local_data_e_maior_imagem(self, mock_get):
        mock_get.return_value = RespostaFalsa(TM_CRU)
        itens = get_provider("TICKETMASTER").search("coldplay")

        self.assertEqual(itens[0].title, "Coldplay")
        self.assertEqual(itens[0].venue, "Allianz Parque, São Paulo")
        self.assertIsNotNone(itens[0].starts_at)
        # Entre 205px e 1024px, fica a maior.
        self.assertEqual(itens[0].image_url, "https://img/g.jpg")

    def test_ticketmaster_sem_horario_prefere_nulo_a_inventar(self):
        with patch("events.catalog.ticketmaster.requests.get", return_value=RespostaFalsa(TM_CRU)):
            itens = get_provider("TICKETMASTER").search("x")
        self.assertIsNone(itens[1].starts_at)
        self.assertEqual(itens[1].venue, "")

    @patch("events.catalog.tmdb.requests.get")
    def test_timeout_vira_catalog_error(self, mock_get):
        mock_get.side_effect = requests.Timeout()
        with self.assertRaises(CatalogError):
            get_provider("TMDB").search("duna")

    @patch("events.catalog.tmdb.requests.get")
    def test_erro_http_vira_catalog_error_sem_vazar_a_url(self, mock_get):
        """A URL do TMDb carrega a api_key na query string."""
        mock_get.return_value = RespostaFalsa(None, erro=requests.HTTPError("401 para ...api_key=chave-de-teste"))
        with self.assertRaises(CatalogError) as ctx:
            get_provider("TMDB").search("duna")
        self.assertNotIn("chave-de-teste", str(ctx.exception))

    @patch("events.catalog.tmdb.requests.get")
    def test_a_chave_nao_vaza_para_o_log(self, mock_get):
        """
        O TMDb autentica pela query string, então a mensagem de erro do
        `requests` carrega a api_key dentro da URL. Um `logger.exception` aqui
        despejaria o traceback inteiro e gravaria a chave de produção nos logs
        da Render. Este teste existe para que ninguém a reintroduza.
        """
        mock_get.return_value = RespostaFalsa(
            None, erro=requests.HTTPError("401 Client Error for url: ...api_key=chave-de-teste")
        )
        with self.assertLogs("events.catalog.tmdb", level="ERROR") as registro:
            with self.assertRaises(CatalogError):
                get_provider("TMDB").search("duna")

        self.assertNotIn("chave-de-teste", "\n".join(registro.output))
        # ...mas o log ainda precisa servir para diagnosticar.
        self.assertIn("HTTPError", "\n".join(registro.output))

    @patch("events.catalog.tmdb.requests.get")
    def test_segunda_busca_igual_sai_do_cache(self, mock_get):
        mock_get.return_value = RespostaFalsa(TMDB_CRU)
        p = get_provider("TMDB")
        p.search("duna")
        p.search("duna")
        self.assertEqual(mock_get.call_count, 1)

    @patch("events.catalog.tmdb.requests.get")
    def test_busca_diferente_nao_reaproveita_o_cache(self, mock_get):
        mock_get.return_value = RespostaFalsa(TMDB_CRU)
        p = get_provider("TMDB")
        p.search("duna")
        p.search("matrix")
        self.assertEqual(mock_get.call_count, 2)

    def test_fonte_desconhecida_levanta_catalog_error(self):
        with self.assertRaises(CatalogError):
            get_provider("SPOTIFY")


class CatalogoViewTest(APITestCase):
    def setUp(self):
        cache.clear()
        self.url = reverse("catalog-search")
        self.org = User.objects.create_user(
            email="org@b.dev", password=SENHA, full_name="Org", role=User.Role.ORGANIZER
        )
        self.client.force_authenticate(self.org)

    @override_settings(TMDB_API_KEY="")
    def test_sem_chave_devolve_503_e_nao_500(self):
        """Falta de configuração do ambiente não é erro do servidor."""
        r = self.client.get(self.url, {"source": "TMDB"})
        self.assertEqual(r.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertIn("chave", r.json()["detail"].lower())

    @override_settings(TMDB_API_KEY="chave-de-teste")
    def test_falha_do_terceiro_devolve_502(self):
        """502 Bad Gateway: quem caiu foi a API de fora, não a nossa."""
        with patch("events.catalog.tmdb.requests.get", side_effect=requests.Timeout()):
            r = self.client.get(self.url, {"source": "TMDB"})
        self.assertEqual(r.status_code, status.HTTP_502_BAD_GATEWAY)

    def test_fonte_invalida_devolve_400(self):
        r = self.client.get(self.url, {"source": "SPOTIFY"})
        self.assertEqual(r.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(TMDB_API_KEY="chave-de-teste")
    def test_busca_bem_sucedida_devolve_a_lista_normalizada(self):
        with patch("events.catalog.tmdb.requests.get", return_value=RespostaFalsa(TMDB_CRU)):
            r = self.client.get(self.url, {"source": "TMDB", "q": "duna"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual(r.json()[0]["title"], "Duna: Parte Dois")


class FiltroDoPainelTest(APITestCase):
    """
    Filtro e ordenação do painel do organizador.

    Ficam no banco, e não na tela: a lista é paginada de 12 em 12, então
    filtrar no front só reordenaria a página atual e esconderia o resto.
    """

    def setUp(self):
        self.org = User.objects.create_user(
            email="org@b.dev", password=SENHA, full_name="Org", role=User.Role.ORGANIZER
        )
        self.outro = User.objects.create_user(
            email="outro@b.dev", password=SENHA, full_name="Outro", role=User.Role.ORGANIZER
        )
        self.lista = reverse("organizer-event-list")

        self.futuro = criar_evento(
            self.org, external_id="1", title="Futuro", starts_at=daqui(20), sold_count=5
        )
        self.rascunho = criar_evento(
            self.org, external_id="2", title="Rascunho", starts_at=daqui(3),
            status=Event.Status.DRAFT,
        )
        self.passado = criar_evento(
            self.org, external_id="3", title="Passado", starts_at=daqui(-4), sold_count=40
        )
        self.client.force_authenticate(self.org)

    def titulos(self, **params):
        return [e["title"] for e in self.client.get(self.lista, params).json()["results"]]

    def test_sem_parametro_traz_tudo_por_data_crescente(self):
        self.assertEqual(self.titulos(), ["Passado", "Rascunho", "Futuro"])

    def test_filtra_por_status(self):
        self.assertEqual(self.titulos(status="DRAFT"), ["Rascunho"])
        self.assertEqual(self.titulos(status="PUBLISHED"), ["Passado", "Futuro"])

    def test_separa_futuros_de_passados(self):
        self.assertEqual(self.titulos(when="upcoming"), ["Rascunho", "Futuro"])
        self.assertEqual(self.titulos(when="past"), ["Passado"])

    def test_combina_aba_e_status(self):
        self.assertEqual(self.titulos(when="upcoming", status="PUBLISHED"), ["Futuro"])

    def test_ordena_por_mais_vendidos(self):
        self.assertEqual(self.titulos(ordering="-sold_count"), ["Passado", "Futuro", "Rascunho"])

    def test_ordena_por_data_decrescente(self):
        self.assertEqual(self.titulos(ordering="-starts_at"), ["Futuro", "Rascunho", "Passado"])

    def test_ordenacao_desconhecida_cai_no_padrao_em_vez_de_estourar(self):
        """
        O parâmetro passa por um DE-PARA, não direto para order_by(). Um campo
        inventado é ignorado; um campo real mas não oferecido também.
        """
        self.assertEqual(self.titulos(ordering="capacity"), ["Passado", "Rascunho", "Futuro"])
        self.assertEqual(self.titulos(ordering="não-existe"), ["Passado", "Rascunho", "Futuro"])

    def test_ordenar_por_relacao_do_usuario_nao_e_aceito(self):
        """
        Ordenar por `organizer__password` não mostra a senha, mas a ORDEM do
        resultado revela como os hashes se comparam entre si. Nenhum caminho
        leva entrada do cliente até order_by().
        """
        r = self.client.get(self.lista, {"ordering": "organizer__password"})
        self.assertEqual(r.status_code, status.HTTP_200_OK)
        self.assertEqual([e["title"] for e in r.json()["results"]],
                         ["Passado", "Rascunho", "Futuro"])

    def test_status_invalido_nao_zera_a_lista(self):
        """Filtro que não casa com o enum é ignorado, e não filtra por lixo."""
        self.assertEqual(len(self.titulos(status="EXCLUIDO")), 3)

    def test_filtro_nao_atravessa_organizador(self):
        criar_evento(self.outro, external_id="9", title="Alheio", starts_at=daqui(1))
        self.assertNotIn("Alheio", self.titulos(when="upcoming"))


class RelacionadosTest(APITestCase):
    """
    O bloco que preenche a metade de baixo da página do evento.

    Duas listas: outras sessões do MESMO item do catálogo, e o que mais está
    em cartaz.
    """

    def setUp(self):
        self.org = User.objects.create_user(
            email="org@b.dev", password=SENHA, full_name="Org", role=User.Role.ORGANIZER
        )
        self.duna = criar_evento(
            self.org, external_id="500", title="Duna", starts_at=daqui(5)
        )
        self.url = reverse("event-related", args=[self.duna.pk])

    def corpo(self, evento=None):
        return self.client.get(
            reverse("event-related", args=[(evento or self.duna).pk])
        ).json()

    def test_outra_sessao_do_mesmo_filme_vem_separada(self):
        criar_evento(
            self.org, external_id="500", title="Duna", venue="Outro cine",
            starts_at=daqui(9),
        )
        criar_evento(self.org, external_id="900", title="Outro filme", starts_at=daqui(7))

        dados = self.corpo()
        self.assertEqual([e["venue"] for e in dados["same_title"]], ["Outro cine"])
        self.assertEqual([e["title"] for e in dados["others"]], ["Outro filme"])

    def test_o_proprio_evento_nunca_se_sugere(self):
        self.assertEqual(self.corpo()["same_title"], [])
        self.assertEqual(self.corpo()["others"], [])

    def test_rascunho_e_sessao_encerrada_ficam_de_fora(self):
        criar_evento(
            self.org, external_id="500", title="Duna", venue="Rascunho",
            starts_at=daqui(3), status=Event.Status.DRAFT,
        )
        criar_evento(
            self.org, external_id="500", title="Duna", venue="Ontem", starts_at=daqui(-1)
        )
        criar_evento(
            self.org, external_id="901", title="Outro rascunho", starts_at=daqui(2),
            status=Event.Status.DRAFT,
        )

        dados = self.corpo()
        self.assertEqual(dados["same_title"], [])
        self.assertEqual(dados["others"], [])

    def test_sessao_sobrando_do_mesmo_filme_nao_reaparece_como_outro_evento(self):
        """
        O corte é de 6. Com 8 sessões do mesmo filme, as 2 que sobram não
        podem voltar na lista de baixo como se fossem outro evento — por isso
        o exclude é por (source, external_id), e não pelos ids já colhidos.
        """
        for i in range(8):
            criar_evento(
                self.org, external_id="500", title="Duna",
                venue=f"Sala {i}", starts_at=daqui(10 + i),
            )

        dados = self.corpo()
        self.assertEqual(len(dados["same_title"]), 6)
        self.assertEqual(dados["others"], [])

    def test_sessao_encerrada_ainda_recebe_sugestao(self):
        """
        A página de uma sessão que já passou continua de pé para quem esteve
        lá — e é justamente onde sugerir o que está em cartaz vale mais.
        """
        passado = criar_evento(
            self.org, external_id="700", title="Passado", starts_at=daqui(-2)
        )
        dados = self.corpo(passado)
        self.assertEqual([e["title"] for e in dados["others"]], ["Duna"])

    def test_rota_e_publica_e_evento_inexistente_da_404(self):
        self.assertEqual(self.client.get(self.url).status_code, status.HTTP_200_OK)
        self.assertEqual(
            self.client.get(reverse("event-related", args=[999999])).status_code,
            status.HTTP_404_NOT_FOUND,
        )

    def test_nao_dispara_uma_query_por_evento_sugerido(self):
        """
        A lista mostra preço "a partir de", que em lugar marcado mora nas
        poltronas. Sem a anotação, cada card custaria uma query própria.
        """
        from django.test.utils import CaptureQueriesContext
        from django.db import connection

        for i in range(6):
            criar_evento(self.org, external_id=f"8{i}", title=f"E{i}", starts_at=daqui(4))

        with CaptureQueriesContext(connection) as poucos:
            self.client.get(self.url)

        for i in range(6):
            criar_evento(self.org, external_id=f"9{i}", title=f"F{i}", starts_at=daqui(4))

        with CaptureQueriesContext(connection) as muitos:
            self.client.get(self.url)

        self.assertEqual(len(poucos), len(muitos))


class CacheDoCatalogoTest(TransactionTestCase):
    """
    "Serve primeiro, atualiza depois" — o cache que não faz ninguém esperar.

    TransactionTestCase, e não TestCase, pelo mesmo motivo dos testes de
    concorrência do ticketing: a renovação roda numa THREAD, com conexão
    própria. O TestCase envolve o teste numa transação que nunca commita, então
    a thread não enxergaria a linha gravada aqui — e, pior, ficaria BLOQUEADA
    tentando inserir a mesma chave primária até o teste acabar.

    Antes: TTL de 15 min e, ao expirar, o próximo usuário PAGAVA a ida ao
    TMDb (1 a 3 segundos olhando um esqueleto) para receber exatamente a mesma
    lista de antes.
    """

    def setUp(self):
        cache.clear()
        self.provider = get_provider("TMDB")

    def tearDown(self):
        cache.clear()

    def _chamadas(self, retorno=None):
        """Um dublê que conta quantas vezes a API externa foi chamada."""
        chamadas = []

        def falso(query, limit):
            chamadas.append(query)
            return retorno if retorno is not None else [
                CatalogItem(source="TMDB", external_id="1", title=f"Filme {len(chamadas)}")
            ]

        return chamadas, falso

    def test_copia_fresca_nao_toca_na_api(self):
        chamadas, falso = self._chamadas()
        with patch.object(self.provider, "_buscar_na_api", falso), override_settings(
            TMDB_API_KEY="x"
        ):
            self.provider.search("duna")
            self.provider.search("duna")
            self.provider.search("duna")

        self.assertEqual(len(chamadas), 1)

    def test_copia_velha_e_servida_na_hora_e_renovada_depois(self):
        """
        A propriedade que importa: quem chega com a cópia vencida NÃO espera
        pela API externa. Recebe o que está guardado e a renovação acontece
        atrás.
        """
        chamadas, falso = self._chamadas()
        with patch.object(self.provider, "_buscar_na_api", falso), override_settings(
            TMDB_API_KEY="x"
        ):
            primeiro = self.provider.search("duna")

            # Envelhece a cópia à mão, em vez de esperar seis horas.
            chave = self.chave
            itens, _ = cache.get(chave)
            cache.set(chave, (itens, time.time() - CatalogProvider.FRESCOR - 1), 600)

            servido = self.provider.search("duna")
            # Devolveu a cópia ANTIGA, não o resultado da renovação.
            self.assertEqual(servido[0].title, primeiro[0].title)

            # A renovação roda numa thread; espera ela terminar.
            for t in threading.enumerate():
                if t.name == "catalogo-renova":
                    t.join(timeout=5)

        self.assertEqual(len(chamadas), 2)
        self.assertEqual(cache.get(chave)[0][0].title, "Filme 2")

    def test_falha_na_renovacao_nao_derruba_o_catalogo(self):
        """
        Melhor a lista de ontem do que uma tela de erro. Se a renovação falhar,
        a cópia guardada continua sendo servida.
        """
        chamadas, falso = self._chamadas()
        with patch.object(self.provider, "_buscar_na_api", falso), override_settings(
            TMDB_API_KEY="x"
        ):
            self.provider.search("duna")
            chave = self.chave
            itens, _ = cache.get(chave)
            cache.set(chave, (itens, time.time() - CatalogProvider.FRESCOR - 1), 600)

            def explode(query, limit):
                raise CatalogError("TMDb fora do ar")

            with patch.object(self.provider, "_buscar_na_api", explode):
                servido = self.provider.search("duna")
                for t in threading.enumerate():
                    if t.name == "catalogo-renova":
                        t.join(timeout=5)

        self.assertEqual(servido[0].title, "Filme 1")
        self.assertEqual(cache.get(chave)[0][0].title, "Filme 1")

    def test_uma_renovacao_so_mesmo_com_varios_pedidos(self):
        """
        Debandada de cache: com a cópia vencida e dez pedidos chegando juntos,
        um dispara a renovação e os outros nove seguem servindo o guardado.
        Sem a trava, os dez iriam ao TMDb ao mesmo tempo — e é justamente aí
        que a cota de API estoura.
        """
        chamadas = []
        # A renovação fica PRESA até o teste liberar. Sem isso ela terminaria
        # no meio do laço, o cache voltaria a ficar fresco e a contagem viraria
        # uma corrida — teste que às vezes dá 2 e às vezes 3 não afirma nada.
        liberar = threading.Event()

        def falso(query, limit):
            chamadas.append(query)
            if len(chamadas) > 1:
                liberar.wait(timeout=5)
            return [CatalogItem(source="TMDB", external_id="1", title=f"Filme {len(chamadas)}")]

        with patch.object(self.provider, "_buscar_na_api", falso), override_settings(
            TMDB_API_KEY="x"
        ):
            self.provider.search("duna")
            chave = self.chave
            itens, _ = cache.get(chave)
            cache.set(chave, (itens, time.time() - CatalogProvider.FRESCOR - 1), 600)

            # A trava é criada de forma SÍNCRONA, antes de a thread começar —
            # é o que garante que o segundo pedido já a encontre no lugar.
            for _ in range(10):
                self.provider.search("duna")

            liberar.set()
            for t in threading.enumerate():
                if t.name == "catalogo-renova":
                    t.join(timeout=5)

        # 1 da carga inicial + 1 renovação. Nunca 11.
        self.assertEqual(len(chamadas), 2)

    @property
    def chave(self):
        """
        Espelha o formato montado pelo provedor. Repetir aqui é proposital:
        se alguém mudar a chave sem pensar, estes testes caem — e cair é o
        aviso de que TODA cópia em produção virou lixo no mesmo instante.
        """
        return f"catalog:v2:tmdb:{settings.TMDB_LANGUAGE}:duna:12"
