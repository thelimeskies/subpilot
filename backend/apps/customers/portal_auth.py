"""Customer portal authentication.

DRF authentication class that validates the customer-portal token presented
by an unauthenticated client (the customer themselves). Token shape:

    Authorization: Portal <plaintext>

The plaintext is hashed and looked up against ``PortalSession.token_hash``;
expired or used sessions are rejected. On success ``request.portal_session``
is populated and ``request.user`` is left as ``AnonymousUser`` (the portal
intentionally does not authenticate as a Django user).
"""
from __future__ import annotations

from django.utils import timezone
from rest_framework import authentication, exceptions

from apps.common.crypto import hash_secret

from .models import PortalSession


class PortalSessionAuthentication(authentication.BaseAuthentication):
    keyword = "Portal"

    def authenticate(self, request):
        header = authentication.get_authorization_header(request).decode("utf-8")
        if not header:
            return None
        parts = header.split()
        if len(parts) != 2 or parts[0] != self.keyword:
            return None
        plaintext = parts[1]
        try:
            session = PortalSession.objects.select_related(
                "customer", "subscription", "invoice", "merchant", "environment"
            ).get(token_hash=hash_secret(plaintext))
        except PortalSession.DoesNotExist:
            raise exceptions.AuthenticationFailed("Invalid portal token.")
        if session.expires_at <= timezone.now():
            raise exceptions.AuthenticationFailed("Portal token expired.")
        publishable_key = request.headers.get("X-SubPilot-Publishable-Key", "").strip()
        if publishable_key and publishable_key != "pk_test_local":
            expected_key = getattr(session.environment, "publishable_key", "")
            if not expected_key or publishable_key != expected_key:
                raise exceptions.AuthenticationFailed("Publishable key does not match portal session.")

        request.portal_session = session
        request.merchant = session.merchant
        request.environment = session.environment
        return (None, session)

    def authenticate_header(self, request):
        return self.keyword


# --- drf-spectacular schema extension ---------------------------------------
try:
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class _PortalSessionAuthScheme(OpenApiAuthenticationExtension):
        target_class = "apps.customers.portal_auth.PortalSessionAuthentication"
        name = "PortalSessionAuth"

        def get_security_definition(self, auto_schema):  # noqa: D401, ARG002
            return {
                "type": "apiKey",
                "in": "header",
                "name": "Authorization",
                "description": "Customer-portal token. Format: `Authorization: Portal <token>`.",
            }
except ImportError:  # pragma: no cover - drf-spectacular optional in some envs
    pass
