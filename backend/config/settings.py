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
}

SIMPLE_JWT = {
    # Access curto + refresh longo: se um access vazar, a janela de abuso é pequena.
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=60),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "AUTH_HEADER_TYPES": ("Bearer",),
    "SIGNING_KEY": SECRET_KEY,
}

SPECTACULAR_SETTINGS = {
    "TITLE": "API — Plataforma de Eventos e Ingressos",
    "DESCRIPTION": "Desafio Elite Dev (Verzel). Organizador publica, cliente compra, portaria valida.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
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
