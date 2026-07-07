"""Read-side helpers for the platform settings singleton (S10).

The :class:`apps.platform_admin.models.PlatformSetting` table holds a single
canonical row keyed by ``key='default'``. The selector returns FE-shape JSON
that mirrors the previous seed-only ``platformPolicy`` constant in
``apps/subpilot-admin/src/data/seed.ts`` so the FE shape stays stable.
"""
from __future__ import annotations

from typing import Any

from django.conf import settings

from apps.common.crypto import decrypt

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
    # --- Platform-managed Nomba credentials ---
    "nombaPlatformActiveMode": "test",
    "nombaPlatformTestBaseUrl": "https://sandbox.nomba.com",
    "nombaPlatformTestAccountId": "",
    "nombaPlatformTestSubAccountId": "",
    "nombaPlatformTestClientId": "",
    "nombaPlatformTestClientSecretEncrypted": "",
    "nombaPlatformTestWebhookSecretEncrypted": "",
    "nombaPlatformLiveBaseUrl": "https://api.nomba.com",
    "nombaPlatformLiveAccountId": "",
    "nombaPlatformLiveSubAccountId": "",
    "nombaPlatformLiveClientId": "",
    "nombaPlatformLiveClientSecretEncrypted": "",
    "nombaPlatformLiveWebhookSecretEncrypted": "",
    "nombaPlatformLiveActive": False,
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
    safe_policy = {
        key: value
        for key, value in policy.items()
        if not key.startswith("nombaPlatform") or not key.endswith("SecretEncrypted")
    }
    adapter_status = row.adapter_status or list(DEFAULT_ADAPTER_STATUS)
    return {
        "id": str(row.id),
        "key": row.key,
        "policy": safe_policy,
        "nombaPlatform": project_nomba_platform_settings(policy),
        "adapterStatus": adapter_status,
        "updatedAt": row.updated_at.isoformat() if getattr(row, "updated_at", None) else "",
    }


def _policy_secret(policy: dict[str, Any], key: str, fallback: str = "") -> str:
    encrypted = str(policy.get(key) or "")
    if encrypted:
        return decrypt(encrypted)
    return fallback


def _mode_prefix(mode: str) -> str:
    return "Live" if mode == "live" else "Test"


def project_nomba_platform_settings(policy: dict[str, Any]) -> dict[str, Any]:
    """Return platform-owned Nomba config without exposing stored secrets."""
    test_secret = str(policy.get("nombaPlatformTestClientSecretEncrypted") or "")
    test_webhook_secret = str(policy.get("nombaPlatformTestWebhookSecretEncrypted") or "")
    live_secret = str(policy.get("nombaPlatformLiveClientSecretEncrypted") or "")
    live_webhook_secret = str(policy.get("nombaPlatformLiveWebhookSecretEncrypted") or "")
    return {
        "activeMode": "live" if policy.get("nombaPlatformActiveMode") == "live" else "test",
        "test": {
            "baseUrl": policy.get("nombaPlatformTestBaseUrl") or getattr(settings, "NOMBA_SANDBOX_BASE_URL", "https://sandbox.nomba.com"),
            "accountId": policy.get("nombaPlatformTestAccountId") or getattr(settings, "NOMBA_PLATFORM_TEST_ACCOUNT_ID", ""),
            "subAccountId": policy.get("nombaPlatformTestSubAccountId") or getattr(settings, "NOMBA_PLATFORM_TEST_SUB_ACCOUNT_ID", ""),
            "clientId": policy.get("nombaPlatformTestClientId") or getattr(settings, "NOMBA_PLATFORM_TEST_CLIENT_ID", ""),
            "hasClientSecret": bool(test_secret or getattr(settings, "NOMBA_PLATFORM_TEST_CLIENT_SECRET", "")),
            "hasWebhookSecret": bool(test_webhook_secret or getattr(settings, "NOMBA_WEBHOOK_SECRET", "")),
        },
        "live": {
            "baseUrl": policy.get("nombaPlatformLiveBaseUrl") or getattr(settings, "NOMBA_LIVE_BASE_URL", "https://api.nomba.com"),
            "accountId": policy.get("nombaPlatformLiveAccountId") or getattr(settings, "NOMBA_PLATFORM_LIVE_ACCOUNT_ID", ""),
            "subAccountId": policy.get("nombaPlatformLiveSubAccountId") or getattr(settings, "NOMBA_PLATFORM_LIVE_SUB_ACCOUNT_ID", ""),
            "clientId": policy.get("nombaPlatformLiveClientId") or getattr(settings, "NOMBA_PLATFORM_LIVE_CLIENT_ID", ""),
            "hasClientSecret": bool(live_secret or getattr(settings, "NOMBA_PLATFORM_LIVE_CLIENT_SECRET", "")),
            "hasWebhookSecret": bool(live_webhook_secret or getattr(settings, "NOMBA_WEBHOOK_SECRET", "")),
            "liveActive": bool(policy.get("nombaPlatformLiveActive")),
        },
    }


def get_platform_nomba_config(mode: str) -> dict[str, Any]:
    """Return effective platform Nomba credentials for a mode.

    Values stored in Platform Admin settings override server environment
    variables. Secrets are stored encrypted inside the singleton policy JSON.
    """
    policy = {**DEFAULT_POLICY, **(get_settings_row().policy or {})}
    normalized = "live" if mode == "live" else "test"
    prefix = _mode_prefix(normalized)
    if normalized == "live":
        fallback_base_url = getattr(settings, "NOMBA_LIVE_BASE_URL", "https://api.nomba.com")
        fallback_account_id = getattr(settings, "NOMBA_PLATFORM_LIVE_ACCOUNT_ID", "")
        fallback_sub_account_id = getattr(settings, "NOMBA_PLATFORM_LIVE_SUB_ACCOUNT_ID", "")
        fallback_client_id = getattr(settings, "NOMBA_PLATFORM_LIVE_CLIENT_ID", "")
        fallback_client_secret = getattr(settings, "NOMBA_PLATFORM_LIVE_CLIENT_SECRET", "")
        fallback_webhook_secret = getattr(settings, "NOMBA_WEBHOOK_SECRET", "")
    else:
        fallback_base_url = getattr(settings, "NOMBA_SANDBOX_BASE_URL", "https://sandbox.nomba.com")
        fallback_account_id = getattr(settings, "NOMBA_PLATFORM_TEST_ACCOUNT_ID", "")
        fallback_sub_account_id = getattr(settings, "NOMBA_PLATFORM_TEST_SUB_ACCOUNT_ID", "")
        fallback_client_id = getattr(settings, "NOMBA_PLATFORM_TEST_CLIENT_ID", "")
        fallback_client_secret = getattr(settings, "NOMBA_PLATFORM_TEST_CLIENT_SECRET", "")
        fallback_webhook_secret = getattr(settings, "NOMBA_WEBHOOK_SECRET", "")
    return {
        "active_mode": "live" if policy.get("nombaPlatformActiveMode") == "live" else "test",
        "base_url": policy.get(f"nombaPlatform{prefix}BaseUrl") or fallback_base_url,
        "account_id": policy.get(f"nombaPlatform{prefix}AccountId") or fallback_account_id,
        "sub_account_id": policy.get(f"nombaPlatform{prefix}SubAccountId") or fallback_sub_account_id,
        "client_id": policy.get(f"nombaPlatform{prefix}ClientId") or fallback_client_id,
        "client_secret": _policy_secret(
            policy,
            f"nombaPlatform{prefix}ClientSecretEncrypted",
            fallback_client_secret,
        ),
        "webhook_secret": _policy_secret(
            policy,
            f"nombaPlatform{prefix}WebhookSecretEncrypted",
            fallback_webhook_secret,
        ),
        "live_active": bool(policy.get("nombaPlatformLiveActive")),
    }


def platform_nomba_webhook_secrets() -> list[str]:
    secrets = [
        get_platform_nomba_config("test").get("webhook_secret") or "",
        get_platform_nomba_config("live").get("webhook_secret") or "",
        getattr(settings, "NOMBA_WEBHOOK_SECRET", "") or "",
    ]
    seen = set()
    result = []
    for secret in secrets:
        if secret and secret not in seen:
            seen.add(secret)
            result.append(secret)
    return result


__all__ = [
    "DEFAULT_ADAPTER_STATUS",
    "DEFAULT_KEY",
    "DEFAULT_POLICY",
    "get_platform_nomba_config",
    "get_settings_row",
    "platform_nomba_webhook_secrets",
    "project_nomba_platform_settings",
    "project_settings",
]
