"""Base Django settings shared by all environments."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env if present (no-op in production where env vars come from the orchestrator).
load_dotenv(BASE_DIR / ".env")


def env(name: str, default: str | None = None) -> str:
    value = os.environ.get(name, default)
    if value is None:
        raise RuntimeError(f"Required environment variable {name} is not set")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: list[str] | None = None) -> list[str]:
    raw = os.environ.get(name)
    if not raw:
        return default or []
    return [item.strip() for item in raw.split(",") if item.strip()]


# --- Core ---
SECRET_KEY = env("DJANGO_SECRET_KEY", "insecure-default-replace-me")
DEBUG = env_bool("DJANGO_DEBUG", False)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", ["*"])

# --- Apps ---
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework.authtoken",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    "drf_standardized_errors",
    "django_celery_beat",
]

LOCAL_APPS = [
    "apps.common",
    "apps.audit",
    "apps.accounts",
    "apps.catalog",
    "apps.customers",
    "apps.subscriptions",
    "apps.invoices",
    "apps.payments",
    "apps.dunning",
    "apps.events",
    "apps.analytics",
    "apps.demo",
    "apps.platform_admin",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# --- Middleware ---
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
    # Custom
    "apps.common.middleware.RequestIdMiddleware",
    "apps.common.middleware.IdempotencyMiddleware",
    "apps.accounts.middleware.TenantContextMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# --- Database ---
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("POSTGRES_DB", "subpilot"),
        "USER": env("POSTGRES_USER", "subpilot"),
        "PASSWORD": env("POSTGRES_PASSWORD", "subpilot"),
        "HOST": env("POSTGRES_HOST", "db"),
        "PORT": env("POSTGRES_PORT", "5432"),
        "CONN_MAX_AGE": 60,
    }
}

# --- Auth ---
AUTH_USER_MODEL = "accounts.User"

# Argon2 first per plan; PBKDF2 kept as fallback for any legacy hashes.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
     "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

# --- Internationalization ---
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# --- Static files ---
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Sessions / cookies (dashboard auth) ---
SESSION_COOKIE_NAME = "subpilot_session"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_AGE = 60 * 60 * 12  # 12h
CSRF_COOKIE_NAME = "subpilot_csrf"
CSRF_COOKIE_SAMESITE = "Lax"

# --- CORS ---
CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:5175",
    ],
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", list(CORS_ALLOWED_ORIGINS))

# --- DRF ---
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "apps.accounts.authentication.ApiKeyAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_PAGINATION_CLASS": "apps.common.pagination.DefaultCursorPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/min",
        "user": "600/min",
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "drf_standardized_errors.handler.exception_handler",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "SubPilot API",
    "DESCRIPTION": "SubPilot subscription billing platform API.",
    "VERSION": "0.1.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Each domain model defines its own ``Status`` TextChoices; drf-spectacular
    # auto-disambiguates colliding names by suffixing (Status244Enum, etc.).
    "ENUM_GENERATE_CHOICE_DESCRIPTION": False,
}

# --- Cache (Redis) ---
REDIS_URL = env("REDIS_URL", "redis://redis:6379/0")
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": REDIS_URL,
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
        },
    }
}

# --- Nomba / payments ---
NOMBA_SANDBOX_BASE_URL = env("NOMBA_SANDBOX_BASE_URL", "https://sandbox.nomba.com")
NOMBA_LIVE_BASE_URL = env("NOMBA_LIVE_BASE_URL", "https://api.nomba.com")
NOMBA_PLATFORM_TEST_ACCOUNT_ID = env("NOMBA_PLATFORM_TEST_ACCOUNT_ID", "")
NOMBA_PLATFORM_TEST_SUB_ACCOUNT_ID = env("NOMBA_PLATFORM_TEST_SUB_ACCOUNT_ID", "")
NOMBA_PLATFORM_TEST_CLIENT_ID = env("NOMBA_PLATFORM_TEST_CLIENT_ID", "")
NOMBA_PLATFORM_TEST_CLIENT_SECRET = env("NOMBA_PLATFORM_TEST_CLIENT_SECRET", "")
NOMBA_PLATFORM_LIVE_ACCOUNT_ID = env("NOMBA_PLATFORM_LIVE_ACCOUNT_ID", "")
NOMBA_PLATFORM_LIVE_SUB_ACCOUNT_ID = env("NOMBA_PLATFORM_LIVE_SUB_ACCOUNT_ID", "")
NOMBA_PLATFORM_LIVE_CLIENT_ID = env("NOMBA_PLATFORM_LIVE_CLIENT_ID", "")
NOMBA_PLATFORM_LIVE_CLIENT_SECRET = env("NOMBA_PLATFORM_LIVE_CLIENT_SECRET", "")
NOMBA_WEBHOOK_SECRET = env("NOMBA_WEBHOOK_SECRET", "")
NOMBA_CHECKOUT_CALLBACK_URL = env(
    "NOMBA_CHECKOUT_CALLBACK_URL",
    "https://portal.subpilot.kylodo.com/payments/nomba/callback",
)
NOMBA_HTTP_USER_AGENT = env("NOMBA_HTTP_USER_AGENT", "SubPilot/0.1 (+https://subpilot.kylodo.com; nomba-api-client)")

# --- Celery ---
CELERY_BROKER_URL = env("CELERY_BROKER_URL", "redis://redis:6379/1")
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", "redis://redis:6379/2")
CELERY_TASK_ALWAYS_EAGER = False
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1

# Six dedicated queues per docs/technical/celery-job-contracts.md.
# `task_queues` must be a sequence of kombu.Queue instances, not bare strings.
from kombu import Queue  # noqa: E402

CELERY_TASK_QUEUES = tuple(
    Queue(name)
    for name in ("billing", "payments", "dunning", "webhooks", "notifications", "analytics")
)
CELERY_TASK_DEFAULT_QUEUE = "notifications"
CELERY_TASK_ROUTES = {
    "apps.subscriptions.tasks.scan_due_subscriptions": {"queue": "billing"},
    "apps.subscriptions.tasks.process_subscription_renewal": {"queue": "billing"},
    "apps.invoices.tasks.*": {"queue": "billing"},
    "apps.payments.tasks.charge_invoice_with_nomba": {"queue": "payments"},
    "apps.payments.tasks.process_nomba_webhook": {"queue": "payments"},
    "apps.dunning.tasks.*": {"queue": "dunning"},
    "apps.events.tasks.dispatch_outbound_webhook": {"queue": "webhooks"},
    "apps.events.tasks.*": {"queue": "webhooks"},
    "apps.accounts.tasks.*": {"queue": "notifications"},
    "apps.notifications.tasks.*": {"queue": "notifications"},
    "apps.analytics.tasks.*": {"queue": "analytics"},
}

# --- Email ---
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", "mailhog")
EMAIL_PORT = int(env("EMAIL_PORT", "1025"))
EMAIL_HOST_USER = env("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", False)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", "SubPilot <no-reply@subpilot.test>")

# --- Crypto ---
FIELD_ENCRYPTION_KEY = env("FIELD_ENCRYPTION_KEY", "")

# --- App-specific knobs ---
DEMO_MFA_BYPASS_CODE = env("DEMO_MFA_BYPASS_CODE", "123456")
SUBPILOT_FRONTEND_URLS = {
    "merchant": env("FRONTEND_MERCHANT_URL", "http://localhost:5173"),
    "customer": env("FRONTEND_CUSTOMER_URL", "https://portal.subpilot.kylodo.com"),
    "platform": env("FRONTEND_PLATFORM_URL", "http://localhost:5175"),
}

# --- Logging ---
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "subpilot": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
    },
}
