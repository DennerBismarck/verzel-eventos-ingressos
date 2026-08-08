"""
Models de evento — ESCRITOS POR DENNER (Dia 1).

Referência: docs/PLANNING.md §2. Esboço do que precisa existir:

    class Event(models.Model):
        organizer    -> FK(settings.AUTH_USER_MODEL)
        source       -> "tmdb" | "ticketmaster"
        external_id  -> id do item no catálogo externo
        title, description, image_url, venue, starts_at
        kind         -> GA (pista) | SEATED (assentos)
        status       -> draft | published
        price, capacity, sold_count      # caso GA
        created_at

    class Seat(models.Model):          # só no Dia 5 (SEATED)
        event, section, row, number, price, status
        Meta: unique_together (event, section, row, number)

Pontos que a defesa provavelmente cobra e que valem pensar AGORA:

1. `sold_count` como contador no Event, ou contar Reservations toda vez?
   (contador = leitura rápida, mas exige disciplina na transação; contar =
   sempre correto, mas mais caro. Qual você escolhe e por quê?)

2. Uma CONSTRAINT no banco garantindo `sold_count <= capacity`:
   models.CheckConstraint. Ela é o cinto de segurança — se um dia a lógica
   Python tiver um furo, o banco recusa. Vale a pena? Argumente.

3. `unique_together` em (source, external_id, organizer)? Um organizador pode
   publicar o mesmo filme duas vezes em datas diferentes — pense antes de
   travar demais.
"""

from django.db import models  # noqa: F401
