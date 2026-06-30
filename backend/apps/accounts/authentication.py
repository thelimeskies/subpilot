"""DRF authentication classes.

Two classes, both register globally:

- :class:`SessionAuthentication` (from DRF, registered in settings) - cookies
  authenticate the React dashboard.
- :class:`ApiKeyAuthentication` - validates ``Authorization: Bearer <api_key>``
  for the public REST API. The header value is the format
  ``nse_<env>_<prefix>_<secret>`` so we can identify the merchant +
  environment by ``key_prefix`` before doing the expensive hash compare.
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework import authentication, exceptions

from .models import ApiKey


class ApiKeyAuthentication(authentication.BaseAuthentication):
    keyword = "Bearer"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("ascii", errors="ignore")
        if not header:
            return None
        try:
            scheme, _, raw_key = header.partition(" ")
        except ValueError:
            return None
        if scheme.lower() != self.keyword.lower() or not raw_key:
            return None
        # Only attempt API-key auth if the value looks like one of ours.
        if not raw_key.startswith("nse_"):
            return None

        # Format: nse_<env>_<prefix>_<secret>
        parts = raw_key.split("_", 3)
        if len(parts) != 4:
            raise exceptions.AuthenticationFailed("Malformed API key.")
        _, _env_mode, prefix_part, secret_part = parts
        prefix = f"nse_{_env_mode}_{prefix_part}"

        try:
            api_key = (
                ApiKey.objects.select_related("merchant", "environment")
                .get(key_prefix=prefix, status=ApiKey.Status.ACTIVE)
            )
        except ApiKey.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid API key.")

        if ApiKey.hash_secret(secret_part) != api_key.key_hash:
            raise exceptions.AuthenticationFailed("Invalid API key.")

        # Update last_used_at without bumping updated_at race-y. (Best-effort.)
        ApiKey.objects.filter(pk=api_key.pk).update(last_used_at=timezone.now())

        # We attach a synthetic identity. ``request.user`` is anonymous; the
        # API key is exposed via ``request.auth`` for downstream consumers.
        return (api_key.created_by or _ApiKeyUserStub(api_key), api_key)

    def authenticate_header(self, request) -> str:
        return f'{self.keyword} realm="api"'


class _ApiKeyUserStub:
    """Stand-in user for API-key calls so ``IsAuthenticated`` is happy."""

    is_authenticated = True
    is_active = True
    is_staff = False
    is_superuser = False

    def __init__(self, api_key: ApiKey):
        self.api_key = api_key
        self.id = f"apikey:{api_key.id}"
        self.email = f"apikey+{api_key.id}@subpilot.system"
        self.display_name = f"API Key ({api_key.name})"
        self.pk = self.id

    def __str__(self) -> str:  # pragma: no cover
        return self.display_name


# --- drf-spectacular schema extension ---------------------------------------
try:
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class _ApiKeyAuthScheme(OpenApiAuthenticationExtension):
        target_class = "apps.accounts.authentication.ApiKeyAuthentication"
        name = "ApiKeyAuth"

        def get_security_definition(self, auto_schema):  # noqa: D401, ARG002
            return {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "nse_<env>_<prefix>_<secret>",
                "description": "Public API key. Format: `Authorization: Bearer nse_<env>_<prefix>_<secret>`.",
            }
except ImportError:  # pragma: no cover - drf-spectacular optional in some envs
    pass
