"""
Adiciona o código curto de digitação manual.

Escrita à mão, em TRÊS passos, porque `makemigrations` não resolve este caso
sozinho: adicionar um campo `unique=True` com valor padrão numa tabela que já
tem linhas aplicaria o MESMO valor a todas e violaria a unicidade na hora. O
Django percebe isso e para para perguntar.

    1. cria a coluna sem unicidade, aceitando nulo;
    2. popula cada linha com um código próprio;
    3. só então torna a coluna obrigatória e única.
"""

from django.db import migrations, models

import ticketing.models


def gerar_codigos(apps, schema_editor):
    """Um código distinto por ingresso já existente."""
    Ticket = apps.get_model("ticketing", "Ticket")

    usados = set()
    pendentes = []
    for ticket in Ticket.objects.filter(short_code__isnull=True).only("id"):
        # Colisão é improvável (32^8), mas "improvável" não é "impossível" —
        # e aqui o custo de tratar é um while.
        codigo = ticketing.models.gerar_codigo_curto()
        while codigo in usados:
            codigo = ticketing.models.gerar_codigo_curto()
        usados.add(codigo)
        ticket.short_code = codigo
        pendentes.append(ticket)

    if pendentes:
        Ticket.objects.bulk_update(pendentes, ["short_code"], batch_size=500)


def apagar_codigos(apps, schema_editor):
    """Reverso: a coluna some inteira no passo 1, então não há o que desfazer."""


class Migration(migrations.Migration):
    dependencies = [("ticketing", "0003_reservation_reservation_expiry_idx")]

    operations = [
        migrations.AddField(
            model_name="ticket",
            name="short_code",
            field=models.CharField(editable=False, max_length=8, null=True),
        ),
        migrations.RunPython(gerar_codigos, apagar_codigos),
        migrations.AlterField(
            model_name="ticket",
            name="short_code",
            field=models.CharField(
                default=ticketing.models.gerar_codigo_curto,
                editable=False,
                max_length=8,
                unique=True,
            ),
        ),
    ]
