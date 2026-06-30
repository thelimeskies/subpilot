"""Tenant-context middleware.

Resolves the active ``Merchant``, ``Environment``, and ``TeamMember`` for the
current request and attaches them to ``request`` so views/permissions never
have to repeat the lookup.

Resolution order:

1. **Session-authenticated dashboard request**: pick the user's first active
   ``TeamMember`` (stable order by created_at). Environment override comes
   from header ``X-Environment: test|live`` (default ``test``).
2. **API-key request**: ``request.auth`` is the ``ApiKey``; the merchant +
   environment are taken straight from it.
3. **Anonymous / public endpoints**: leave attributes as ``None``.

The middleware never raises; views enforce auth via ``IsAuthenticated`` /
``IsTenantMember``.
"""
from __future__ import annotations

import logging

from django.utils.deprecation import MiddlewareMixin

from .models import ApiKey, Environment, Merchant, TeamMember

log = logging.getLogger("subpilot.middleware")


class TenantContextMiddleware(MiddlewareMixin):
    def process_request(self, request) -> None:
        request.merchant = None
        request.environment = None
        request.team_member = None

        # 1. API-key path. ``request.auth`` is set by DRF *after* view dispatch,
        #    so we can't rely on it here; instead, sniff the header ourselves.
        api_key_obj = self._maybe_resolve_api_key(request)
        if api_key_obj is not None:
            request.merchant = api_key_obj.merchant
            request.environment = api_key_obj.environment
            return

        # 2. Session path. AuthenticationMiddleware has run; ``request.user`` is
        #    already populated for cookie-authenticated requests.
        user = getattr(request, "user", None)
        if not user or not user.is_authenticated:
            return
        if getattr(user, "is_staff", False):
            # Platform Operator — they choose tenant via query param later.
            return

        tm = (
            TeamMember.objects.select_related("merchant")
            .filter(user_id=user.id, status=TeamMember.Status.ACTIVE)
            .order_by("created_at")
            .first()
        )
        if tm is None:
            return
        request.team_member = tm
        request.merchant = tm.merchant

        mode_header = (request.META.get("HTTP_X_ENVIRONMENT") or "test").lower()
        mode = mode_header if mode_header in {"test", "live"} else "test"
        request.environment = (
            Environment.objects.filter(merchant=tm.merchant, mode=mode).first()
            or Environment.objects.filter(merchant=tm.merchant, mode=Environment.Mode.TEST).first()
        )

    @staticmethod
    def _maybe_resolve_api_key(request) -> ApiKey | None:
        header = request.META.get("HTTP_AUTHORIZATION", "")
        if not header.startswith("Bearer nse_"):
            return None
        try:
            raw = header.split(" ", 1)[1]
            parts = raw.split("_", 3)
            if len(parts) != 4:
                return None
            _, env_mode, prefix_part, _secret = parts
            prefix = f"nse_{env_mode}_{prefix_part}"
        except (IndexError, ValueError):
            return None
        try:
            return (
                ApiKey.objects.select_related("merchant", "environment")
                .get(key_prefix=prefix, status=ApiKey.Status.ACTIVE)
            )
        except ApiKey.DoesNotExist:
            return None


# Re-export so consumers don't have to reach into the model module just to
# discover the FK target name.
__all__ = ["TenantContextMiddleware", "Merchant", "Environment", "TeamMember"]
