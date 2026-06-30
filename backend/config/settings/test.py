"""Test settings — fast hashers, eager Celery, locmem cache, sqlite DB."""
from .base import *  # noqa: F401, F403
from .base import BASE_DIR

DEBUG = False
SECRET_KEY = "test-only"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "subpilot-test",
    }
}

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

# A deterministic Fernet key for tests. NOT for production use.
FIELD_ENCRYPTION_KEY = "Z3DRjAWuNrMK4wYwzL_oS5G2mHxEK4sB-_ucVE9hhxw="

DEMO_MFA_BYPASS_CODE = "123456"

# Disable throttling in tests.
REST_FRAMEWORK_OVERRIDES = {
    "DEFAULT_THROTTLE_CLASSES": [],
}
from .base import REST_FRAMEWORK  # noqa: E402
REST_FRAMEWORK = {**REST_FRAMEWORK, **REST_FRAMEWORK_OVERRIDES}

STATIC_ROOT = BASE_DIR / "staticfiles_test"
