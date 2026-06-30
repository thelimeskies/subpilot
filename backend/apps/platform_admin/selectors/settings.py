"""Read-side helpers for the platform settings singleton (S10).

The :class:`apps.platform_admin.models.PlatformSetting` table holds a single
canonical row keyed by ``key='default'``. The selector returns FE-shape JSON
that mirrors the previous seed-only ``platformPolicy`` constant in
``apps/subpilot-admin/src/data/seed.ts`` so the FE shape stays stable.
"""
from __future__ import annotations

from typing import Any

from ..models import PlatformSetting

DEFAULT_KEY = "default"

# Defaults below intentionally mirror the FE seed values so a fresh
# install renders the policy panel without a flash of empty fields.
DEFAULT_POLICY: dict[str, Any] = {
    "defaultRetryAttempts": 4,
    "defaultBackoff": "Exponential",
    "defaultCooldownHours": 6,
    "webhookSignatureHeader": "X-SubPilot-Signature",
    "webhookSignatureKeyAge": "Rolled 12 days ago",
    "passwordMinLength": 12,
    "sessionLifetimeHours": 12,
    "ipAllowlistEnabled": False,
    "enforcedMfa": True,
    "dataRetentionDays": 540,
    "readOnlyMode": False,
    "blockNewSignups": False,
    "webhookDeliveriesEnabled": True,
    "cardTokenizationEnabled": True,
    "bankTransferRecoveryEnabled": True,
    # --- Security tab extras ---
    "ssoGoogleEnabled": True,
    "sessionTimeoutEnabled": True,
    "blockNewCountriesEnabled": False,
    "passwordRotationDays": 90,
    "passwordHistoryCount": 5,
    "passwordLockoutThreshold": 6,
    "verifyHmacOnReceipts": True,
    "enforceTls13": True,
    "requireIdempotencyKey": True,
    "allowSelfSignedDevEndpoints": False,
    # --- Data tab extras ---
    "webhookDeliveryRetentionDays": 30,
    "tokenizedCardRetentionDays": 730,
    "customerProfileRetention": "forever",
    # --- Branding tab ---
    "brandDisplayName": "SubPilot",
    "brandSupportEmail": "support@subpilot.dev",
    "brandPrimaryColor": "#0BBF85",
    "brandAccentColor": "#0F2A2E",
    # --- Adapters tab routing ---
    "routingStrategy": "smart",
    "autoFailoverOn5xx": True,
    "retryOnDifferentAdapter": True,
    "forceFailoverOverride": False,
    # --- Webhooks tab signing + delivery defaults ---
    "webhookSignatureAlgorithm": "hmac-sha256",
    "webhookTimestampToleranceSeconds": 300,
    "webhookReplayWindowMinutes": 10,
    "webhookTimeoutSeconds": 20,
    "webhookConcurrencyPerMerchant": 16,
    "subscribedEventTypes": [
        "subscription.created",
        "subscription.updated",
        "subscription.canceled",
        "invoice.paid",
        "invoice.failed",
        "invoice.recovered",
        "payment.captured",
        "payment.refunded",
        "customer.card_updated",
    ],
    # --- Dunning cadence ---
    "dunningEmailD1": True,
    "dunningEmailSmsD3": True,
    "dunningFinalNoticeD7": True,
    "dunningAutoPauseD10": True,
}

DEFAULT_ADAPTER_STATUS: list[dict[str, Any]] = [
    {
        "name": "Adapter A",
        "role": "Primary card processor",
        "uptime": "99.97%",
        "latencyP95": "412 ms",
        "failoverTrigger": "5xx > 4% over 3 minutes",
        "region": "Lagos · Frankfurt",
        "status": "Operational",
    },
    {
        "name": "Adapter B",
        "role": "Backup + bank transfer",
        "uptime": "99.91%",
        "latencyP95": "684 ms",
        "failoverTrigger": "5xx > 6% over 5 minutes",
        "region": "Lagos · Dublin",
        "status": "Monitoring",
    },
    {
        "name": "Tokenization vault",
        "role": "Card tokenization (PCI scope)",
        "uptime": "99.99%",
        "latencyP95": "118 ms",
        "failoverTrigger": "n/a",
        "region": "Lagos · Frankfurt",
        "status": "Operational",
    },
]


def get_settings_row() -> PlatformSetting:
    """Return the singleton row, lazily creating it with defaults."""
    row, created = PlatformSetting.objects.get_or_create(
        key=DEFAULT_KEY,
        defaults={
            "policy": dict(DEFAULT_POLICY),
            "adapter_status": list(DEFAULT_ADAPTER_STATUS),
        },
    )
    if not created and not row.policy:
        row.policy = dict(DEFAULT_POLICY)
        row.save(update_fields=["policy"])
    if not created and not row.adapter_status:
        row.adapter_status = list(DEFAULT_ADAPTER_STATUS)
        row.save(update_fields=["adapter_status"])
    return row


def project_settings(row: PlatformSetting) -> dict[str, Any]:
    """Return the FE-shape settings payload."""
    policy = {**DEFAULT_POLICY, **(row.policy or {})}
    adapter_status = row.adapter_status or list(DEFAULT_ADAPTER_STATUS)
    return {
        "id": str(row.id),
        "key": row.key,
        "policy": policy,
        "adapterStatus": adapter_status,
        "updatedAt": row.updated_at.isoformat() if getattr(row, "updated_at", None) else "",
    }


__all__ = [
    "DEFAULT_ADAPTER_STATUS",
    "DEFAULT_KEY",
    "DEFAULT_POLICY",
    "get_settings_row",
    "project_settings",
]
