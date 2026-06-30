"""Local development settings."""
from .base import *  # noqa: F401, F403
from .base import env_bool

DEBUG = env_bool("DJANGO_DEBUG", True)

# Allow everything in dev to reduce friction.
ALLOWED_HOSTS = ["*"]

# In dev, prefer console email when MailHog isn't reachable. Compose stack overrides via env.
# (Keeps `manage.py check` happy without docker running.)
INTERNAL_IPS = ["127.0.0.1", "localhost"]
