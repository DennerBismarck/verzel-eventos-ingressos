"""
Models de reserva/ingresso/pagamento — ESCRITOS POR DENNER (Dia 2-3).

Referência: docs/PLANNING.md §2 e §3. Esboço:

    class Reservation(models.Model):
        customer, event, status (pending|paid|refused|cancelled)
        quantity (GA)  /  seats M2M (SEATED)
        total_price, created_at

    class Payment(models.Model):        # simulado
        reservation, status (confirmed|refused), created_at

    class Ticket(models.Model):
        reservation, event, customer, seat (null p/ GA)
        code        -> uuid4, o identificador que vai no QR
        status      -> valid | used
        used_at, used_by
        share_token -> uuid4, para o link público de compartilhamento

Sobre a assinatura do QR (§3.2): a assinatura NÃO precisa virar coluna.
Ela é derivável de (code + TICKET_SIGNING_KEY) a qualquer momento —
guardar seria duplicar estado. Decida e registre em DECISIONS.md.

Sobre `share_token` separado de `code`: são coisas diferentes de propósito.
`code` valida a entrada; `share_token` só exibe. Quem recebe o link
compartilhado não deveria conseguir deduzir o código de validação.
"""

from django.db import models  # noqa: F401
