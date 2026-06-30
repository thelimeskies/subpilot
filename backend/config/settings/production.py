"""Production settings."""
from .base import *  # noqa: F401, F403
from .base import env_bool

DEBUG = False

# Hard fail if EMAIL_BACKEND is the console backend in production.
from .base import EMAIL_BACKEND  # noqa: E402
if EMAIL_BACKEND == "django.core.mail.backends.console.EmailBackend":
    raise RuntimeError("Refusing to start in production with the console email backend.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env_bool("DJANGO_SECURE_SSL_REDIRECT", True)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
