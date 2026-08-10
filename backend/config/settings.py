"""
Configuração do Django para a Plataforma de Eventos e Ingressos.

Tudo que muda entre máquinas/ambientes vem de variável de ambiente (.env),
nunca hardcoded. Ver .env.example.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
    CORS_ALLOWED_ORIGINS=(list, []),
)
# Lê o .env se existir. Em produção (Render/Railway) não existe arquivo:
# as variáveis vêm do painel, e environ lê direto do os.environ.
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="dev-inseguro-troque-em-producao")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")

# A Render injeta o hostname público do serviço em runtime. Adicionar aqui evita
# ter que editar ALLOWED_HOSTS na mão toda vez que a URL do deploy muda.
RENDER_HOST = env("RENDER_EXTERNAL_HOSTNAME", default="")
if RENDER_HOST:
    ALLOWED_HOSTS.append(RENDER_HOST)

# Chave dedicada à assinatura do QR do ingresso (usada no app ticketing).
TICKET_SIGNING_KEY = env("TICKET_SIGNING_KEY", default=SECRET_KEY)

# Credenciais das APIs externas de catálogo (usadas pelo proxy no backend).
TMDB_API_KEY = env("TMDB_API_KEY", default="")
TMDB_LANGUAGE = env("TMDB_LANGUAGE", default="pt-BR")
TICKETMASTER_API_KEY = env("TICKETMASTER_API_KEY", default="")


# --------------------------------------------------------------------------
# Apps
# --------------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # terceiros
    "rest_framework",
    # Guarda os refresh tokens revogados. Sem este app, "sair" só apagaria o
    # token do navegador — quem já tivesse uma cópia continuaria entrando.
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "drf_spectacular",
    # nossos
    "accounts",
    "events",
    "ticketing",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    # WhiteNoise serve os arquivos estáticos em produção sem precisar de Nginx.
    "whitenoise.middleware.WhiteNoiseMiddleware",
    # CorsMiddleware precisa vir ANTES do CommonMiddleware para conseguir
    # responder às requisições preflight (OPTIONS) do browser.
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"


# --------------------------------------------------------------------------
# Banco
# --------------------------------------------------------------------------
# Uma única variável (DATABASE_URL) descreve o banco inteiro. É o formato que
# Render/Railway/Heroku entregam pronto, então dev e produção usam o mesmo código.
DATABASES = {
    "default": env.db_url(
        "DATABASE_URL",
        default="postgres://ingressos:ingressos@localhost:5433/ingressos",
    )
}
# Reaproveita conexões por 60s em vez de abrir uma nova a cada request.
DATABASES["default"]["CONN_MAX_AGE"] = 60


# --------------------------------------------------------------------------
# Autenticação
# --------------------------------------------------------------------------
# User customizado desde o PRIMEIRO migrate. Trocar isso depois de migrar é
# uma dor enorme no Django — por isso está definido já no Dia 0.
AUTH_USER_MODEL = "accounts.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# --------------------------------------------------------------------------
# DRF
# --------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    # Fail closed: por padrão TUDO exige login. Endpoint público (catálogo de
    # eventos, ingresso compartilhado) declara AllowAny explicitamente.
    # Assim, esquecer a permissão numa view nova fecha a porta em vez de abri-la.
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 12,
    # ----------------------------------------------------------------------
    # Rate limit
    #
    # Sem isto, /api/auth/login aceita quantas tentativas o atacante quiser:
    # a senha do seed é pública no README, mas as reais não são, e uma lista
    # de senhas comuns roda em minutos.
    #
    # Escopos separados porque os riscos são diferentes:
    #   auth    — força bruta de senha. Apertado.
    #   gate    — a portaria valida em rajada numa entrada movimentada;
    #             apertar aqui atrapalharia o uso legítimo.
    #   catalog — cada chamada vira uma requisição à API de terceiro e gasta
    #             cota nossa. O cache de 15 min já ajuda; o limite fecha a
    #             porta de esgotar a cota de propósito.
    # ----------------------------------------------------------------------
    "DEFAULT_THROTTLE_CLASSES": (
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ),
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "300/min",
        # Configurável por ambiente, com PADRÃO ESTRITO. Limite de taxa é
        # configuração de ambiente por natureza: produção quer 10/min, e uma
        # suíte de testes que se martela do mesmo IP precisa de outro valor —
        # senão o throttle derruba os próprios testes e a reação natural é
        # afrouxar o limite de produção, que é o pior desfecho possível.
        "auth": env("THROTTLE_AUTH_RATE", default="10/min"),
        "gate": "120/min",
        "catalog": "30/min",
    },
}

SIMPLE_JWT = {
    # Access curto + refresh longo: se um access vazar, a janela de abuso é pequena.
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "SIGNING_KEY": SECRET_KEY,
    # Cada refresh usado devolve um refresh NOVO e invalida o anterior. Duas
    # consequências práticas:
    #   1. um refresh vazado só serve até a vítima usar o dela — e quando o
    #      atacante tentar reusar o token velho, ele já não vale;
    #   2. o logout consegue revogar de verdade, em vez de só apagar do
    #      navegador e torcer.
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "API — Plataforma de Eventos e Ingressos",
    "DESCRIPTION": "Desafio Elite Dev (Verzel). Organizador publica, cliente compra, portaria valida.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
}


# --------------------------------------------------------------------------
# Cache
# --------------------------------------------------------------------------
# COMPARTILHADO entre processos, e este é o ponto.
#
# O padrão do Django é LocMemCache: memória por PROCESSO. O gunicorn roda
# vários workers, cada um com o próprio dicionário — e duas coisas quebram em
# silêncio:
#
#   1. o rate limit do DRF conta no cache. Com contadores separados, o limite
#      efetivo vira "10/min VEZES o número de workers", e a requisição seguinte
#      cai noutro worker que ainda não viu nada. Medido em produção: 13
#      tentativas de login seguidas, nenhum 429;
#
#   2. o cache do catálogo externo perde eficácia na mesma proporção — cada
#      worker faz a própria chamada e gasta cota nossa de novo.
#
# DatabaseCache e não Redis porque não há Redis no plano free, e acrescentar um
# serviço para isto seria desproporcional. O custo é uma escrita por
# requisição contabilizada, aceitável neste volume. Se o tráfego crescesse a
# ponto de isso pesar, a troca para Redis é uma linha aqui.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "cache_compartilhado",
    }
}


# --------------------------------------------------------------------------
# CORS
# --------------------------------------------------------------------------
# O front (Vercel, porta 3000 em dev) roda em outra origem que a API.
# Sem isto, o browser bloqueia as chamadas. Lista explícita, nunca allow-all.
CORS_ALLOWED_ORIGINS = env("CORS_ALLOWED_ORIGINS")


# --------------------------------------------------------------------------
# i18n / estáticos
# --------------------------------------------------------------------------
LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
# Guarda tudo em UTC no banco e converte na borda. Evita bug de horário de verão
# na data do evento.
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Atrás do proxy da Render/Railway, o Django precisa deste header pra saber
# que a requisição original era HTTPS.
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

if not DEBUG:
    # Sem o próprio host aqui, o login do /admin em produção falha com
    # "CSRF verification failed" — o Django exige origem confiável em HTTPS.
    CSRF_TRUSTED_ORIGINS = list(CORS_ALLOWED_ORIGINS)
    if RENDER_HOST:
        CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_HOST}")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

    # ----------------------------------------------------------------------
    # Cabeçalhos de segurança
    #
    # Só fora de DEBUG: em desenvolvimento o SSL redirect quebraria o
    # http://localhost e o HSTS deixaria o navegador preso em https por meses,
    # inclusive depois de desligar a flag.
    # ----------------------------------------------------------------------
    SECURE_SSL_REDIRECT = True

    # HSTS: o navegador passa a recusar http neste domínio sem nem tentar,
    # fechando a janela do primeiro request em texto claro (onde um ataque de
    # rede sequestraria o redirect). 1 ano é o valor que os pré-carregadores
    # exigem. NÃO incluímos subdomínios: não controlamos todos em .onrender.com.
    SECURE_HSTS_SECONDS = 31_536_000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

    # Impede o navegador de "adivinhar" o tipo do conteúdo. Sem isso, um
    # arquivo enviado como texto pode ser interpretado como script.
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # A API não deve ser embutida em iframe de ninguém — nem o /admin.
    X_FRAME_OPTIONS = "DENY"

    # Não vaza o caminho completo da nossa URL para sites de terceiros,
    # incluindo os CDNs de imagem que o front consulta.
    SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
