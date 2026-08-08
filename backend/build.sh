#!/usr/bin/env bash
# Executado pela Render a cada deploy do backend.
# set -o errexit: se qualquer passo falhar, o deploy falha em vez de subir quebrado.
set -o errexit

pip install -r requirements.txt

# Junta os estáticos (inclui os do Django admin e do Swagger) num diretório
# que o WhiteNoise serve.
python manage.py collectstatic --no-input

# Migrations no build, não no start: se rodassem no start, várias instâncias
# tentariam migrar em paralelo.
python manage.py migrate

# Dados de teste exigidos pelo enunciado. É idempotente, então rodar a cada
# deploy não duplica nada — e garante que o avaliador sempre acha o seed no ar.
python manage.py seed
