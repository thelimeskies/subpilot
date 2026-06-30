"""Write actions for the merchant-detail surface (S4).

Each action runs inside a single transaction, mutates Merchant or
PlatformMerchantNote, and emits an audit log entry under the
``platform.merchant.<verb>`` namespace.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction
from django.http import HttpRequest

from apps.accounts.models import Merchant
from apps.audit.services.log_event import log_event

from ..models import PlatformAdmin, PlatformAdminRole, PlatformMerchantNote


class MerchantNotFoundError(LookupError):
    pass


class InvalidStatusTransitionError(ValueError):
    pass


@dataclass(frozen=True)
class MerchantActionResult:
    merchant_id: str
    status: str
    note_id: str | None = None


def _resolve(merchant_id: str) -> Merchant:
    try:
        return Merchant.objects.get(pk=merchant_id)
    except Merchant.DoesNotExist as exc:
        raise MerchantNotFoundError(merchant_id) from exc


def _actor_label(admin: PlatformAdmin | None) -> str:
    if admin is None:
        return "platform_admin"
    return admin.email or admin.display_name or "platform_admin"


@transaction.atomic
def suspend_merchant(
    *,
    merchant_id: str,
    admin: PlatformAdmin | None,
    reason: str = "",
    note: str = "",
    request: HttpRequest | None = None,
) -> MerchantActionResult:
    m = _resolve(merchant_id)
    if m.status == Merchant.Status.SUSPENDED:
        # Idempotent — log a no-op note and return current state.
        return MerchantActionResult(merchant_id=str(m.id), status=m.status)
    m.status = Merchant.Status.SUSPENDED
    m.save(update_fields=["status", "updated_at"])
    log_event(
        action="platform.merchant.suspend",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=m,
        target_type="merchant",
        target_id=str(m.id),
        metadata={"reason": reason, "note": note},
        request=request,
    )
    return MerchantActionResult(merchant_id=str(m.id), status=m.status)


@transaction.atomic
def reactivate_merchant(
    *,
    merchant_id: str,
    admin: PlatformAdmin | None,
    note: str = "",
    request: HttpRequest | None = None,
) -> MerchantActionResult:
    m = _resolve(merchant_id)
    if m.status == Merchant.Status.ACTIVE:
        return MerchantActionResult(merchant_id=str(m.id), status=m.status)
    if m.status == Merchant.Status.CLOSED:
        raise InvalidStatusTransitionError("Cannot reactivate a closed merchant.")
    m.status = Merchant.Status.ACTIVE
    m.save(update_fields=["status", "updated_at"])
    log_event(
        action="platform.merchant.reactivate",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=m,
        target_type="merchant",
        target_id=str(m.id),
        metadata={"note": note},
        request=request,
    )
    return MerchantActionResult(merchant_id=str(m.id), status=m.status)


@transaction.atomic
def add_merchant_note(
    *,
    merchant_id: str,
    admin: PlatformAdmin | None,
    body: str,
    visibility: str = "ops",
    request: HttpRequest | None = None,
) -> MerchantActionResult:
    body = (body or "").strip()
    if not body:
        raise ValueError("Note body cannot be empty.")
    m = _resolve(merchant_id)
    note = PlatformMerchantNote.objects.create(merchant=m, author=admin, body=body)
    log_event(
        action="platform.merchant.note",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=m,
        target_type="merchant_note",
        target_id=str(note.id),
        metadata={"note": body[:200], "visibility": visibility},
        request=request,
    )
    return MerchantActionResult(merchant_id=str(m.id), status=m.status, note_id=str(note.id))


class OwnerRequiredError(PermissionError):
    """Raised when a non-Owner attempts an Owner-only merchant action."""


@dataclass(frozen=True)
class SecretRotationResult:
    merchant_id: str
    fingerprint: str
    rotated_at: str
    grace_period: str


def _ensure_owner(admin: PlatformAdmin | None) -> None:
    if admin is None or admin.role != PlatformAdminRole.OWNER:
        raise OwnerRequiredError("Only platform Owners can perform this action.")


@transaction.atomic
def rotate_merchant_webhook_secret(
    *,
    merchant_id: str,
    admin: PlatformAdmin | None,
    grace_period: str = "24h",
    request: HttpRequest | None = None,
) -> SecretRotationResult:
    """Rotate the per-merchant outbound webhook signing secret.

    The current implementation emits an audit row and returns a fresh
    fingerprint that the FE can show to operators. Endpoints continue to
    sign with the platform key during the grace period.
    """
    _ensure_owner(admin)
    m = _resolve(merchant_id)
    fingerprint = secrets.token_hex(8)
    rotated_at = datetime.now(timezone.utc).isoformat()
    log_event(
        action="platform.merchant.rotate_webhook_secret",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=m,
        target_type="merchant",
        target_id=str(m.id),
        metadata={
            "fingerprint": fingerprint,
            "grace_period": grace_period,
            "rotated_at": rotated_at,
        },
        request=request,
    )
    return SecretRotationResult(
        merchant_id=str(m.id),
        fingerprint=fingerprint,
        rotated_at=rotated_at,
        grace_period=grace_period,
    )


@transaction.atomic
def force_close_merchant(
    *,
    merchant_id: str,
    admin: PlatformAdmin | None,
    note: str = "",
    request: HttpRequest | None = None,
) -> MerchantActionResult:
    """Force a merchant into the terminal CLOSED state.

    Owner-only. Emits ``platform.merchant.force_close``.
    """
    _ensure_owner(admin)
    m = _resolve(merchant_id)
    if m.status == Merchant.Status.CLOSED:
        return MerchantActionResult(merchant_id=str(m.id), status=m.status)
    m.status = Merchant.Status.CLOSED
    m.save(update_fields=["status", "updated_at"])
    log_event(
        action="platform.merchant.force_close",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=m,
        target_type="merchant",
        target_id=str(m.id),
        metadata={"note": note},
        request=request,
    )
    return MerchantActionResult(merchant_id=str(m.id), status=m.status)
