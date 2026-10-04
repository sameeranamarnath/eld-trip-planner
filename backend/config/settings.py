"""Django settings for the Spotter ELD trip-planner service.

Every operational knob is environment-overridable so a container, a Vercel
serverless function or a CI runner can change behaviour without editing code.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def _env(name: str, default: str) -> str:
    raw = os.environ.get(name)
    return default if raw is None or raw == "" else raw


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ[name])
    except (KeyError, TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Core Django
# ---------------------------------------------------------------------------
SECRET_KEY = _env("DJANGO_SECRET_KEY", "django-insecure-dev-only-change-me")
DEBUG = _env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = [h.strip() for h in _env("DJANGO_ALLOWED_HOSTS", "*").split(",") if h.strip()]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "rest_framework",
    "corsheaders",
    "eld",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# The planner is stateless - it never touches the database.  Keeping the
# sqlite entry means ``manage.py`` still works for shell/debugging.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = False  # the ELD domain is deliberately timezone-naive (home-terminal local time)

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# DRF
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "EXCEPTION_HANDLER": "eld.exceptions.api_exception_handler",
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
}

# ---------------------------------------------------------------------------
# CORS - the React frontend is served from a different origin on Vercel.
# ---------------------------------------------------------------------------
CORS_ALLOW_ALL_ORIGINS = _env_bool("CORS_ALLOW_ALL_ORIGINS", True)
CORS_ALLOWED_ORIGINS = [
    o.strip() for o in _env("CORS_ALLOWED_ORIGINS", "").split(",") if o.strip()
]

# ---------------------------------------------------------------------------
# Domain configuration
# ---------------------------------------------------------------------------
SPOTTER = {
    "HTTP_TIMEOUT_SECONDS": _env_float("SPOTTER_HTTP_TIMEOUT_SECONDS", 25.0),
    "USER_AGENT": _env("SPOTTER_USER_AGENT", "spotter-eld-trip-planner/1.0"),
    "OSRM_BASE_URL": _env("SPOTTER_OSRM_BASE_URL", "https://router.project-osrm.org"),
    "NOMINATIM_BASE_URL": _env("SPOTTER_NOMINATIM_BASE_URL", "https://nominatim.openstreetmap.org"),
    "PHOTON_BASE_URL": _env("SPOTTER_PHOTON_BASE_URL", "https://photon.komoot.io"),
    "BIGDATACLOUD_BASE_URL": _env(
        "SPOTTER_BIGDATACLOUD_BASE_URL", "https://api.bigdatacloud.net"
    ),
    # In-process caches keep repeated requests free of external calls.
    "GEOCODE_CACHE_SIZE": int(_env_float("SPOTTER_GEOCODE_CACHE_SIZE", 512)),
    "ROUTE_CACHE_SIZE": int(_env_float("SPOTTER_ROUTE_CACHE_SIZE", 64)),
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"simple": {"format": "{levelname} {asctime} {name} {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "simple"}},
    "root": {"handlers": ["console"], "level": _env("DJANGO_LOG_LEVEL", "INFO")},
}
