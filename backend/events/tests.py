"""
Testes de evento e catálogo externo.

Os testes do catálogo NÃO tocam a rede: `requests.get` é substituído por um
dublê. Teste que depende de API de terceiro falha quando o terceiro cai, gasta
cota a cada execução e não roda no CI sem chave — deixa de ser teste e vira
monitoramento.
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import requests
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from .catalog import CatalogError, get_provider
from .models import Event

User = get_user_model()

SENHA = "verzel123456"


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
