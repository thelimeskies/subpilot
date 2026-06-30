"""Cross-tenant webhook delivery actions (S6).

Wraps :func:`apps.events.services.retry_delivery` with platform-admin
auth context + audit logging under the ``platform.webhook.retry``
namespace. Idempotent for already-PENDING deliveries.
"""
from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timezone

from django.db import transaction
from django.http import HttpRequest

from apps.audit.services.log_event import log_event
from apps.events.models import WebhookDelivery
from apps.events.services import retry_delivery as _retry_delivery_service

from ..models import PlatformAdmin, PlatformAdminRole
from ..selectors.settings import get_settings_row


class DeliveryNotFoundError(LookupError):
    pass


class DeliveryNotRetriableError(ValueError):
    pass


@dataclass(frozen=True)
class DeliveryActionResult:
    delivery_id: str
    status: str
    next_attempt_at: str | None = None
    attempts: int = 0


def _resolve(delivery_id) -> WebhookDelivery:
    try:
        return (
            WebhookDelivery.objects.select_related(
                "webhook_event__merchant",
                "webhook_event__environment",
                "endpoint",
            ).get(pk=delivery_id)
        )
    except (WebhookDelivery.DoesNotExist, ValueError) as exc:
        raise DeliveryNotFoundError(str(delivery_id)) from exc


def _actor_label(admin: PlatformAdmin | None) -> str:
    if admin is None:
        return "platform_admin"
    return admin.email or admin.display_name or "platform_admin"


@transaction.atomic
def retry_delivery_admin(
    *,
    delivery_id,
    admin: PlatformAdmin | None,
    request: HttpRequest | None = None,
) -> DeliveryActionResult:
    """Re-queue a failed/abandoned delivery for an immediate attempt.

    Delegates the state transition to the existing tenant service
    :func:`apps.events.services.retry_delivery` and emits a platform-
    audit row tagged ``platform.webhook.retry``.
    """
    delivery = _resolve(delivery_id)
    pre_status = delivery.status

    if delivery.status == WebhookDelivery.Status.DELIVERED:
        raise DeliveryNotRetriableError(
            "Delivery already succeeded; nothing to retry.",
        )
    if delivery.status not in {
        WebhookDelivery.Status.PENDING,
        WebhookDelivery.Status.FAILED,
        WebhookDelivery.Status.ABANDONED,
    }:
        raise DeliveryNotRetriableError(
            f"Cannot retry a {delivery.status} delivery.",
        )

    delivery = _retry_delivery_service(delivery=delivery, request=request)

    log_event(
        action="platform.webhook.retry",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=getattr(delivery.webhook_event, "merchant", None),
        target_type="webhook_delivery",
        target_id=str(delivery.id),
        metadata={
            "previous_status": pre_status,
            "new_status": delivery.status,
            "attempt_count": delivery.attempt_count,
            "event_type": getattr(delivery.webhook_event, "event_type", ""),
            "endpoint_id": str(delivery.endpoint_id),
        },
        request=request,
    )

    return DeliveryActionResult(
        delivery_id=str(delivery.id),
        status=delivery.status,
        next_attempt_at=(
            delivery.next_attempt_at.isoformat()
            if delivery.next_attempt_at
            else None
        ),
        attempts=int(delivery.attempt_count or 0),
    )


class OwnerRequiredError(PermissionError):
    """Raised when a non-Owner attempts an Owner-only webhook action."""


@dataclass(frozen=True)
class SigningKeyRotationResult:
    fingerprint: str
    rotated_at: str
    grace_period: str


@transaction.atomic
def rotate_platform_signing_key(
    *,
    admin: PlatformAdmin | None,
    grace_period: str = "24h",
    notify_channel: str = "email-webhook",
    request: HttpRequest | None = None,
) -> SigningKeyRotationResult:
    """Rotate the platform-wide webhook signing key.

    Generates a new fingerprint, resets the keyAge label, and emits a
    ``platform.webhook.rotate_key`` audit row. Owner-only.
    """
    if admin is None or admin.role != PlatformAdminRole.OWNER:
        raise OwnerRequiredError("Only platform Owners can rotate the signing key.")

    row = get_settings_row()
    fingerprint = secrets.token_hex(8)
    rotated_at = datetime.now(timezone.utc).isoformat()
    policy = dict(row.policy or {})
    policy["webhookSignatureKeyAge"] = "Rotated just now"
    policy["webhookSignatureFingerprint"] = fingerprint
    policy["webhookSignatureRotatedAt"] = rotated_at
    policy["webhookSignatureGracePeriod"] = grace_period
    row.policy = policy
    row.save(update_fields=["policy", "updated_at"])

    log_event(
        action="platform.webhook.rotate_key",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=None,
        target_type="platform_setting",
        target_id=str(row.id),
        metadata={
            "fingerprint": fingerprint,
            "grace_period": grace_period,
            "notify_channel": notify_channel,
        },
        request=request,
    )
    return SigningKeyRotationResult(
        fingerprint=fingerprint,
        rotated_at=rotated_at,
        grace_period=grace_period,
    )


__all__ = [
    "DeliveryNotFoundError",
    "DeliveryNotRetriableError",
    "DeliveryActionResult",
    "OwnerRequiredError",
    "SigningKeyRotationResult",
    "retry_delivery_admin",
    "rotate_platform_signing_key",
]
