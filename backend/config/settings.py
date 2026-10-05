"""Django settings for RouteLedger."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_BASE = Path(__file__).resolve().parent.parent
# Local monorepo: repo-root/.env · Vercel (root=backend): backend/.env or dashboard env
load_dotenv(_BASE.parent / ".env")
load_dotenv(_BASE / ".env")

BASE_DIR = _BASE

SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-insecure-change-me")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() in ("1", "true", "yes")
ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h.strip()
]
# Vercel preview/production hostnames
if os.environ.get("VERCEL"):
    for host in (".vercel.app", ".now.sh"):
        if host not in ALLOWED_HOSTS:
            ALLOWED_HOSTS.append(host)

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "rest_framework",
    "drf_spectacular",
    "trips",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
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

DATABASE_URL = os.environ.get("DATABASE_URL")
if DATABASE_URL:
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(
            DATABASE_URL,
            conn_max_age=600,
            ssl_require=os.environ.get("VERCEL") == "1",
        )
    }
elif os.environ.get("VERCEL"):
    # Ephemeral fallback — prefer Neon DATABASE_URL in production
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": "/tmp/routeledger.sqlite3",
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "routeledger",
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STORAGES = {
    "staticfiles": {
        # Manifest storage breaks when hashes drift across serverless builds
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "120/min",
        "location_search": "30/min",
        "trip_create": "20/min",
    },
    "EXCEPTION_HANDLER": "trips.api.errors.custom_exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "RouteLedger API",
    "DESCRIPTION": "US trucking trip planner with planned daily logs",
    "VERSION": "1.0.0",
}

CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]
CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CSRF_TRUSTED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(",")
    if o.strip()
]

# OpenRouteService / HeiGIT
ORS_API_KEY = os.environ.get("OPENROUTESERVICE_API_KEY", "")
ORS_BASE_URL = os.environ.get(
    "ORS_BASE_URL", "https://api.heigit.org/openrouteservice"
)
# Geocoding moved to Pelias under the HeiGIT unified API
ORS_GEOCODE_BASE_URL = os.environ.get(
    "ORS_GEOCODE_BASE_URL", "https://api.heigit.org/pelias/v1"
)
ORS_PROFILE = "driving-hgv"
ORS_TIMEOUT_S = float(os.environ.get("ORS_TIMEOUT_S", "20"))
USE_FAKE_PROVIDER = os.environ.get("USE_FAKE_PROVIDER", "false").lower() in (
    "1",
    "true",
    "yes",
)

MAP_TILE_URL = os.environ.get(
    "MAP_TILE_URL", "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
)
MAP_TILE_ATTRIBUTION = os.environ.get(
    "MAP_TILE_ATTRIBUTION",
    '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
)

AI_INSIGHTS_ENABLED = os.environ.get("AI_INSIGHTS_ENABLED", "false").lower() in (
    "1",
    "true",
    "yes",
)

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
