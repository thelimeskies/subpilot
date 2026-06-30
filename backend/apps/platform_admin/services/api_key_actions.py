"""Cross-tenant API-key actions (S7).

Wraps :func:`apps.accounts.services.api_keys.revoke_api_key` with platform-
admin auth context + audit logging under the ``platform.api_key.revoke``
namespace.

The platform side does NOT support create / rotate (per plan). Those flows
remain merchant-only.
"""
from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction
from django.http import HttpRequest

from apps.accounts.models import ApiKey
from apps.accounts.services.api_keys import revoke_api_key as _revoke_api_key_service
from apps.audit.services.log_event import log_event

from ..models import PlatformAdmin


class ApiKeyNotFoundError(LookupError):
    pass


class ApiKeyAlreadyRevokedError(ValueError):
    pass


@dataclass(frozen=True)
class ApiKeyActionResult:
    api_key_id: str
    status: str
    revoked_at: str | None = None


def _resolve(api_key_id) -> ApiKey:
    try:
        return (
            ApiKey.objects.select_related("merchant", "environment", "created_by")
            .get(pk=api_key_id)
        )
    except (ApiKey.DoesNotExist, ValueError) as exc:
        raise ApiKeyNotFoundError(str(api_key_id)) from exc


def _actor_label(admin: PlatformAdmin | None) -> str:
    if admin is None:
        return "platform_admin"
    return admin.email or admin.display_name or "platform_admin"


@transaction.atomic
def revoke_api_key_admin(
    *,
    api_key_id,
    admin: PlatformAdmin | None,
    request: HttpRequest | None = None,
) -> ApiKeyActionResult:
    """Revoke an API key cross-tenant. Idempotent on already-revoked keys.

    Raises :class:`ApiKeyAlreadyRevokedError` so callers can return 409.
    """
    api_key = _resolve(api_key_id)
    pre_status = api_key.status

    if api_key.status == ApiKey.Status.REVOKED:
        raise ApiKeyAlreadyRevokedError("API key is already revoked.")

    api_key = _revoke_api_key_service(api_key)

    log_event(
        action="platform.api_key.revoke",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=api_key.merchant,
        target_type="api_key",
        target_id=str(api_key.id),
        metadata={
            "previous_status": pre_status,
            "new_status": api_key.status,
            "key_prefix": api_key.key_prefix,
            "environment_id": str(api_key.environment_id),
            "merchant_id": str(api_key.merchant_id),
        },
        request=request,
    )

    return ApiKeyActionResult(
        api_key_id=str(api_key.id),
        status=api_key.status,
        revoked_at=api_key.revoked_at.isoformat() if api_key.revoked_at else None,
    )


__all__ = [
    "ApiKeyNotFoundError",
    "ApiKeyAlreadyRevokedError",
    "ApiKeyActionResult",
    "revoke_api_key_admin",
]
