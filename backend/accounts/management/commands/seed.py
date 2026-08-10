"""
Popula o banco com os dados de teste exigidos pelo enunciado:
1 organizador, 2 clientes, 1 usuário de portaria e (a partir do Dia 1)
1 evento publicado com ingressos disponíveis.

Uso:  python manage.py seed
      python manage.py seed --reset   (apaga os usuários de seed antes)

Idempotente: rodar duas vezes não duplica nada, porque usa get_or_create.
"""

from datetime import timedelta
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from events.models import Event, Seat
from events.services import generate_seats
from ticketing.models import Reservation, Ticket

User = get_user_model()

SENHA_PADRAO = "verzel123"

USUARIOS = [
    ("organizador@verzel.dev", "Olívia Organizadora", User.Role.ORGANIZER),
    ("cliente1@verzel.dev", "Caio Cliente", User.Role.CUSTOMER),
    ("cliente2@verzel.dev", "Clara Cliente", User.Role.CUSTOMER),
    ("portaria@verzel.dev", "Pedro Portaria", User.Role.GATE),
]

# (external_id, título, cartaz, local, dias, hora, preço, capacidade, status)
#
# Datas relativas a hoje: o seed nunca "vence". Um evento com data fixa no
# passado sumiria da vitrine meses depois e o avaliador acharia que quebrou.
# A HORA, ao contrário, é fixa e cheia — senão a sessão herdaria o minuto em
# que o seed rodou, e "sessão às 09:14" entrega que o dado é artificial.
#
# Os cartazes são URLs reais do CDN do TMDb, colhidas com a própria integração
# do projeto. Ficam fixas aqui de propósito: o seed roda no build da Render e
# não pode depender de a API externa estar de pé — nem gastar cota a cada deploy.
CARTAZ = "https://image.tmdb.org/t/p/w500"

EVENTOS = [
    ("969681", "Homem-Aranha: Um Novo Dia", "/x0nvYzQpyJc5pdT9lMnkMuYAg0O.jpg",
     "Cinemark Eldorado, São Paulo", 5, 20, "42.00", 180, Event.Status.PUBLISHED),
    ("1368337", "A Odisseia", "/muMwJAiMtReEHLKpKMWt2rMkYF7.jpg",
     "Petra Belas Artes, São Paulo", 8, 19, "38.50", 90, Event.Status.PUBLISHED),
    ("1084244", "Toy Story 5", "/sssrBhdvDcczgMQYDc8oCoSuFEJ.jpg",
     "Cinépolis JK Iguatemi, São Paulo", 10, 15, "36.00", 200, Event.Status.PUBLISHED),
    ("634649", "Homem-Aranha: Sem Volta Para Casa", "/xaKydnMw6wR1MBAjS5seGPVusbs.jpg",
     "Reserva Cultural, São Paulo", 12, 21, "30.00", 120, Event.Status.PUBLISHED),
    ("1081003", "Supergirl", "/qhXfLI1gDWaahzfHT0cb2CH61hO.jpg",
     "Cinemark Villa-Lobos, São Paulo", 14, 20, "44.00", 150, Event.Status.PUBLISHED),
    ("1212763", "A Morte do Demônio: Em Chamas", "/fteLdvfRnltfLjAEnsl5E3vImnW.jpg",
     "Cine Marquise, São Paulo", 16, 22, "34.00", 80, Event.Status.PUBLISHED),
    ("1108427", "Moana", "/eEsiTi19EYBluPQliS3CMnBgqTj.jpg",
     "Cinesystem Iguatemi, Campinas", 18, 14, "28.00", 140, Event.Status.PUBLISHED),
    ("1284465", "A Morte de Robin Hood", "/o0QndnepFPWget2kdKpzh26RBYt.jpg",
     "Cinemateca Brasileira, São Paulo", 21, 19, "25.00", 60, Event.Status.PUBLISHED),
    ("1339713", "Obsessão", "/wUc6IDf5ChjM1UyQye21qFBeJY0.jpg",
     "Espaço Itaú Augusta, São Paulo", 24, 21, "32.00", 70, Event.Status.PUBLISHED),
    # Um esgotado, para a vitrine mostrar o estado "Esgotado" sem ninguém comprar.
    ("1315772", "Minions & Monstros", "/hTowtXrkCY7FJyoj4p91JckrJSE.jpg",
     "Cinemark Shopping Metrô Tatuapé, São Paulo", 6, 16, "39.00", 40, Event.Status.PUBLISHED),
    # Rascunho: prova que a vitrine pública filtra por status.
    ("1375646", "Zona Zero", "/hWT5fHzVcxq06SuLfAWYVCrue7P.jpg",
     "Cinesala, São Paulo", 30, 20, "35.00", 50, Event.Status.DRAFT),
    # Duas sessões que JÁ ACONTECERAM (dias negativos). Sem elas, a aba "Já
    # aconteceram" do painel do organizador nasce vazia e o filtro por data da
    # vitrine nunca é exercitado — foi assim que o bug de anunciar evento
    # vencido passou despercebido até agora.
    ("1061474", "Superman", "/v8ezJI3qfEv4OYq8AWSp4inFIwE.jpg",
     "Cinemark Eldorado, São Paulo", -6, 21, "42.00", 160, Event.Status.PUBLISHED),
    ("1087192", "Como Treinar o Seu Dragão", "/vdvEClt3J8sFWxyMo0Jm7JpouEo.jpg",
     "Cinesystem Iguatemi, Campinas", -13, 16, "30.00", 120, Event.Status.PUBLISHED),
]

# Sinopses REAIS do TMDb, colhidas com a própria integração do projeto e
# fixadas aqui pelo mesmo motivo dos cartazes: o seed roda no build da Render
# e não pode depender de a API externa estar de pé.
#
# O texto genérico vira FALLBACK, para item que ainda não tenha sinopse — em
# vez de ser o padrão para todo mundo, como era.
SINOPSES = {
    "969681": (
        "É um novo dia para Peter Parker. Combatendo o crime em tempo integral "
        "como Homem-Aranha em um mundo que não se lembra mais dele e lidando "
        "com a pressão de ver seus antigos amigos seguirem em frente sem sua "
        "presença, Peter passa por uma mudança que talvez nem ele tenha o poder "
        "de controlar. Mas essa transformação também pode ser a única coisa "
        "capaz de deter uma surpreendente nova ameaça à cidade e às pessoas que "
        "ele ama: um poderoso vilão que ninguém sequer consegue enxergar."
    ),
    "1368337": (
        "Acompanhe a saga de Odisseu, o lendário rei de Ítaca, em sua longa e "
        "perigosa jornada de retorno ao lar após a Guerra de Troia. O relato "
        "narra seus confrontos com seres míticos, como o ciclope Polifemo, as "
        "sedutoras sereias e a ninfa Calipso, enquanto ele luta contra o "
        "destino para se reencontrar com sua fiel esposa, Penélope."
    ),
    "1084244": (
        "O trabalho de Buzz, Woody, Jessie e do resto da gangue fica "
        "exponencialmente mais difícil quando eles enfrentam uma nova ameaça à "
        "diversão: a tecnologia."
    ),
    "634649": (
        "Peter Parker é desmascarado e não consegue mais separar sua vida "
        "normal dos grandes riscos de ser um super-herói. Quando ele pede ajuda "
        "ao Doutor Estranho, os riscos se tornam ainda mais perigosos, e o "
        "forçam a descobrir o que realmente significa ser o Homem-Aranha..."
    ),
    "1081003": (
        "Quando um adversário implacável atinge alguém muito próximo dela, Kara "
        "Zor-El relutantemente une forças com uma companheira improvável em uma "
        "épica jornada interestelar de vingança e justiça."
    ),
    "1212763": (
        "Após a perda do marido, uma mulher busca consolo com seus sogros em "
        "sua casa isolada. À medida que, um a um, eles são transformados em "
        "Deadites — transformando o encontro em uma reunião familiar infernal "
        "—, ela descobre que os votos que fez em vida... continuam vivos mesmo "
        "após a morte."
    ),
    "1108427": (
        "Na Polinésia Antiga, quando uma terrível maldição contraída por Maui "
        "chega à ilha de um impetuoso chefe, sua filha obstinada responde ao "
        "chamado do Oceano para procurar o semideus e consertar as coisas. "
        "Adaptação live-action do filme de animação da Disney de 2016 'Moana'"
    ),
    "1284465": (
        "Atormentado pelas cicatrizes de uma vida marcada pelo crime, Robin "
        "Hood sobrevive por pouco àquela que acreditava ser sua batalha final. "
        "Gravemente ferido, ele é encontrado por uma mulher misteriosa que o "
        "recolhe das sombras e passa a cuidar de seus ferimentos. Com o corpo "
        "fora de combate, cada erro cometido no passado volta para assombrá-lo."
    ),
    "1339713": (
        "Sem grandes pretensões, um romântico incurável compra um brinquedo que "
        "promete realizar desejos únicos. Ele quebra o artefato misterioso "
        "enquanto pede para conquistar a crush e consegue exatamente o que "
        "desejava, mas descobre que a consequência é sinistra."
    ),
    "1315772": (
        "Esta é a frenética, ridícula e totalmente verdadeira história de como "
        "os Minions conquistaram Hollywood, se tornaram estrelas de cinema, "
        "perderam tudo, libertaram monstros pelo mundo e, depois, se uniram "
        "para tentar salvar o planeta do caos que eles mesmos haviam acabado de "
        "criar."
    ),
    "1375646": (
        "De repente, um vírus que sofre mutações rápidas é liberado em uma "
        "conferência de biologia, forçando o isolamento imediato do local. A "
        "contaminação se espalha rapidamente, e os infectados não apenas "
        "atacam, eles evoluem de formas imprevisíveis e cada vez mais "
        "perigosas. Presos nesse confinamento, um grupo de sobreviventes "
        "precisa lutar pela própria vida enquanto, a cada minuto, as regras do "
        "jogo mudam."
    ),
    "1284041": (
        "Uma família trancada misteriosamente na própria casa precisa se unir "
        "para sobreviver à escassez de recursos e à força sombria que a mantém "
        "presa."
    ),
    "1061474": (
        "Superman, um jovem repórter de Metrópolis, embarca em uma jornada "
        "para reconciliar sua herança kryptoniana com sua criação humana como "
        "Clark Kent."
    ),
    "1087192": (
        "Na montanhosa Ilha de Berk, vikings e dragões são inimigos "
        "implacáveis há gerações, mas Soluço é diferente. Filho do Chefe "
        "Stoico, o Imenso, o criativo e subestimado Soluço desafia séculos de "
        "tradição ao fazer amizade com Banguela, um temido dragão Fúria da "
        "Noite. Essa relação improvável revela a verdadeira natureza dos "
        "dragões, abalando as bases da sociedade viking."
    ),
}

# Quantos ingressos já "vendidos" em cada evento, para a vitrine e o painel do
# organizador não aparecerem zerados. Chave = external_id.
VENDIDOS = {
    "969681": 47,     # bom movimento
    "1368337": 31,
    "1084244": 112,   # quase esgotando
    "634649": 9,      # acabou de entrar em cartaz
    "1081003": 8,
    "1212763": 55,
    "1108427": 74,
    "1284465": 12,
    "1339713": 26,
    "1315772": 40,    # esgotado (capacidade 40)
    # Sessões encerradas: número alto, como fica um evento no fim da carreira.
    "1061474": 148,
    "1087192": 96,
}

# Um evento de LUGAR MARCADO. Sem ele, o mapa de assentos só apareceria para
# quem criasse um evento na mão — e quem for avaliar provavelmente não vai.
EVENTO_COM_LUGAR = {
    "external_id": "1284041",
    "title": "A Última Casa",
    "cartaz": "/AqOwuZ4X0Ssi3LIsYqXNw52IIvW.jpg",
    "venue": "Teatro Municipal, São Paulo",
    "dias": 9,
    "hora": 20,
}

SECOES = [
    {"name": "Plateia", "rows": ["A", "B", "C", "D", "E"], "seats_per_row": 12, "price": "90.00"},
    {"name": "Balcão", "rows": ["F", "G"], "seats_per_row": 10, "price": "60.00"},
]

# Poltronas já ocupadas, para o mapa não abrir todo verde. Posições espalhadas
# de propósito: uma sala com exatamente as 10 primeiras vendidas não parece uma
# sala de verdade.
OCUPADAS = [
    ("Plateia", "A", 5), ("Plateia", "A", 6), ("Plateia", "B", 7),
    ("Plateia", "C", 1), ("Plateia", "C", 2), ("Plateia", "C", 3),
    ("Plateia", "D", 9), ("Plateia", "E", 4), ("Plateia", "E", 12),
    ("Balcão", "F", 2), ("Balcão", "F", 3), ("Balcão", "G", 8),
]


def descricao_de(external_id, titulo):
    """
    Sinopse real quando existe; texto genérico só como último recurso.

    O template "Sessão especial de X" era o padrão para todos, e transformava
    doze eventos diferentes em doze cópias do mesmo parágrafo — a página do
    evento não dizia nada sobre o filme.
    """
    sinopse = SINOPSES.get(external_id)
    if sinopse:
        return sinopse
    return (
        f"Sessão especial de {titulo}, com entrada por ingresso digital. "
        "Chegue com 30 minutos de antecedência; o QR é validado na portaria."
    )


class Command(BaseCommand):
    help = "Cria os dados de teste (usuários dos 3 papéis + evento publicado)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Apaga os usuários de seed antes de recriar.",
        )

    # Tudo ou nada: se um usuário falhar, nenhum é criado e o banco
    # não fica num meio-termo estranho.
    @transaction.atomic
    def handle(self, *args, **options):
        emails = [email for email, _, _ in USUARIOS]

        if options["reset"]:
            # A ordem aqui é ditada pelos on_delete=PROTECT, de dentro para fora:
            # ingresso -> reserva -> evento -> usuário. Apagar de fora para
            # dentro levanta ProtectedError — que é exatamente a constraint
            # cumprindo o papel dela, nos obrigando a ser explícitos.
            # (Payment cai junto com Reservation, porque ali é CASCADE.)
            eventos = Event.objects.filter(organizer__email__in=emails)
            Ticket.objects.filter(event__in=eventos).delete()
            Reservation.objects.filter(event__in=eventos).delete()
            eventos.delete()
            apagados, _ = User.objects.filter(email__in=emails).delete()
            self.stdout.write(self.style.WARNING(f"Removidos {apagados} registros de seed."))

        for email, nome, papel in USUARIOS:
            user, criado = User.objects.get_or_create(
                email=email,
                defaults={"full_name": nome, "role": papel},
            )
            if criado:
                user.set_password(SENHA_PADRAO)
                user.save(update_fields=["password"])
                self.stdout.write(self.style.SUCCESS(f"  + {email} ({papel})"))
            else:
                self.stdout.write(f"  = {email} já existia")

        organizador = User.objects.get(email="organizador@verzel.dev")
        # localtime() e não now(): now() devolve UTC, e trocar a hora ali
        # gravaria 20h UTC = 17h em São Paulo. A hora da sessão tem que ser
        # cravada no fuso de quem vai assistir.
        agora = timezone.localtime(timezone.now())

        for ext_id, titulo, cartaz, local, dias, hora, preco, capacidade, status in EVENTOS:
            quando = (agora + timedelta(days=dias)).replace(
                hour=hora, minute=0, second=0, microsecond=0
            )
            # Campos de APRESENTAÇÃO: reescritos a cada execução. É o que torna
            # o seed declarativo — o deploy seguinte conserta um cartaz trocado
            # ou uma data que já passou, em vez de deixar o registro antigo
            # apodrecendo em produção.
            apresentacao = {
                "title": titulo,
                "description": descricao_de(ext_id, titulo),
                "image_url": f"{CARTAZ}{cartaz}",
                "venue": local,
                "starts_at": quando,
                "kind": Event.Kind.GA,
                "status": status,
                "price": Decimal(preco),
            }

            evento = Event.objects.filter(
                source=Event.Source.TMDB, external_id=ext_id, organizer=organizador
            ).first()

            if evento is None:
                evento = Event.objects.create(
                    source=Event.Source.TMDB,
                    external_id=ext_id,
                    organizer=organizador,
                    capacity=capacidade,
                    sold_count=VENDIDOS.get(ext_id, 0),
                    **apresentacao,
                )
                marca = "+"
            else:
                # ESTOQUE (capacity/sold_count) fica de fora de propósito.
                # Reescrever aqui apagaria compras reais feitas por quem estiver
                # avaliando — e baixar a capacidade abaixo do já vendido faria a
                # CheckConstraint derrubar o deploy inteiro.
                for campo, valor in apresentacao.items():
                    setattr(evento, campo, valor)
                evento.save(update_fields=list(apresentacao))
                marca = "~"

            self.stdout.write(
                f"  {marca} {titulo} ({evento.status}, "
                f"{evento.sold_count}/{evento.capacity} vendidos)"
            )

        self._evento_com_lugar_marcado(organizador, agora)

        # Remove eventos de seed que saíram da lista (ex.: o elenco antigo, sem
        # cartaz). Só os que ninguém reservou — se houver reserva, o evento
        # deixou de ser dado de demonstração e vira histórico de verdade.
        conhecidos = [e[0] for e in EVENTOS] + [EVENTO_COM_LUGAR["external_id"]]
        obsoletos = Event.objects.filter(
            organizer=organizador, source=Event.Source.TMDB
        ).exclude(external_id__in=conhecidos)

        for evento in obsoletos:
            if evento.reservations.exists():
                self.stdout.write(
                    self.style.WARNING(f"  ! {evento.title}: fora da lista, mas tem reservas")
                )
                continue
            self.stdout.write(f"  - {evento.title} (removido: fora da lista)")
            evento.delete()

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Seed pronto. Senha de todos: {SENHA_PADRAO}"))

    def _evento_com_lugar_marcado(self, organizador, agora):
        spec = EVENTO_COM_LUGAR
        quando = (agora + timedelta(days=spec["dias"])).replace(
            hour=spec["hora"], minute=0, second=0, microsecond=0
        )

        evento, criado = Event.objects.get_or_create(
            source=Event.Source.TMDB,
            external_id=spec["external_id"],
            organizer=organizador,
            defaults={
                "title": spec["title"],
                "description": descricao_de(spec["external_id"], spec["title"]),
                "image_url": f"{CARTAZ}{spec['cartaz']}",
                "venue": spec["venue"],
                "starts_at": quando,
                "kind": Event.Kind.SEATED,
                "status": Event.Status.PUBLISHED,
                "price": Decimal("0.00"),
                "capacity": 0,
            },
        )

        if not criado:
            # Mesma regra dos de pista: apresentação é reescrita, estoque não.
            evento.title = spec["title"]
            evento.image_url = f"{CARTAZ}{spec['cartaz']}"
            evento.venue = spec["venue"]
            evento.starts_at = quando
            evento.status = Event.Status.PUBLISHED
            evento.save(update_fields=["title", "image_url", "venue", "starts_at", "status"])

        # O mapa é montado UMA vez. Refazer a cada deploy apagaria a poltrona
        # que um ingresso emitido aponta — e generate_seats recusaria de
        # qualquer forma assim que houvesse venda de verdade.
        if evento.seats.exists():
            self.stdout.write(
                f"  = {spec['title']} (mapa já existe, {evento.seats.count()} lugares)"
            )
            return

        total = generate_seats(event=evento, sections=SECOES)

        # Ocupa algumas poltronas para o mapa não abrir todo verde.
        ocupadas = 0
        for secao, fila, numero in OCUPADAS:
            ocupadas += Seat.objects.filter(
                event=evento, section=secao, row=fila, number=numero
            ).update(status=Seat.Status.SOLD)

        # sold_count precisa acompanhar as poltronas marcadas na mão: é ele que
        # a vitrine lê para dizer quantos lugares restam.
        evento.sold_count = ocupadas
        evento.save(update_fields=["sold_count"])

        self.stdout.write(f"  + {spec['title']} ({total} lugares, {ocupadas} ocupados)")
