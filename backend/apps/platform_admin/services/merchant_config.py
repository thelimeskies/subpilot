"""Read + write actions for the per-merchant operational config (S13).

A ``MerchantConfig`` row is one-to-one with ``Merchant`` and stores:

* ``feature_flags`` — sparse override map on top of the server-defined
  :data:`apps.platform_admin.feature_flags.FEATURE_FLAGS` catalog
* ``limits`` — operational caps (monthly volume, max ticket, MCC tier, …)
* ``retry_policy`` — outbound dunning / webhook retry behaviour

The bundle returned to the admin FE always includes the **resolved** flag
map (catalog defaults merged with overrides) so the UI can stay flag-shape
agnostic.

Writes are Owner-only. The view layer enforces the role gate; we
defensively guard inside ``update_merchant_config`` too so direct callers
(scripts, future internal jobs) cannot bypass it.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.http import HttpRequest

from apps.accounts.models import Merchant
from apps.audit.services.log_event import log_event
from apps.events.models import WebhookEndpoint

from ..feature_flags import FEATURE_FLAGS, catalog, is_known_flag, resolved_flags
from ..models import MerchantConfig, PlatformAdmin, PlatformAdminRole


class MerchantNotFoundError(LookupError):
    pass


class OwnerRequiredError(PermissionError):
    pass


class UnknownFeatureFlagError(ValueError):
    pass


# --- Defaults (mirror seed_demo so empty rows render sensibly) -------------


_DEFAULT_LIMITS: dict[str, Any] = {
    "monthly_volume_cap_minor": 5_000_000_000,  # NGN 50m
    "max_ticket_minor": 25_000_000,  # NGN 250,000
    "high_risk_mcc": False,
    "payout_cadence": "daily",
    "notification_channels": ["email", "slack"],
    "currency": "NGN",
}

_DEFAULT_RETRY: dict[str, Any] = {
    "attempts": 4,
    "backoff": "exponential",
    "cooldown_hours": 6,
}

_PAYOUT_LABEL = {"daily": "Daily", "weekly": "Weekly", "tplus2": "T+2"}
_BACKOFF_LABEL = {"linear": "Linear", "exponential": "Exponential"}
_CHANNEL_LABEL = {"email": "Email", "slack": "Slack", "sms": "SMS"}


# --- Resolution ------------------------------------------------------------


def _resolve(merchant_id: str) -> Merchant:
    try:
        return Merchant.objects.get(pk=merchant_id)
    except (Merchant.DoesNotExist, ValueError) as exc:
        raise MerchantNotFoundError(str(merchant_id)) from exc


def _get_or_default(merchant: Merchant) -> tuple[dict, dict, dict]:
    """Return (limits, retry_policy, feature_overrides) — always populated."""
    config = getattr(merchant, "config", None)
    if config is None:
        return dict(_DEFAULT_LIMITS), dict(_DEFAULT_RETRY), {}
    limits = {**_DEFAULT_LIMITS, **(config.limits or {})}
    retry = {**_DEFAULT_RETRY, **(config.retry_policy or {})}
    return limits, retry, dict(config.feature_flags or {})


def _project_limits(limits: dict, currency: str) -> dict[str, Any]:
    from .formatting import format_compact_money

    cur = (currency or limits.get("currency") or "NGN").upper()
    cap_minor = int(limits.get("monthly_volume_cap_minor") or 0)
    ticket_minor = int(limits.get("max_ticket_minor") or 0)
    channels = limits.get("notification_channels") or []
    channel_labels = [_CHANNEL_LABEL.get(str(c).lower(), str(c).title()) for c in channels]
    return {
        "monthlyVolumeCap": format_compact_money(cap_minor, cur),
        "monthlyVolumeCapMinor": cap_minor,
        "maxTicketSize": format_compact_money(ticket_minor, cur),
        "maxTicketMinor": ticket_minor,
        "highRiskMcc": bool(limits.get("high_risk_mcc") or False),
        "payoutCadence": _PAYOUT_LABEL.get(
            str(limits.get("payout_cadence") or "daily").lower(), "Daily"
        ),
        "notificationChannel": " + ".join(channel_labels) if channel_labels else "Email",
        "notificationChannels": [str(c).lower() for c in channels],
        "currency": cur,
    }


def _project_retry(retry: dict) -> dict[str, Any]:
    return {
        "attempts": int(retry.get("attempts") or 0),
        "backoff": _BACKOFF_LABEL.get(
            str(retry.get("backoff") or "exponential").lower(), "Exponential"
        ),
        "cooldownHours": int(retry.get("cooldown_hours") or 0),
    }


def _project_flags(overrides: dict) -> list[dict[str, Any]]:
    """Catalog × overrides → ordered list of {key, label, description, default, enabled}."""
    return [
        {
            "key": key,
            "label": spec["label"],
            "description": spec["description"],
            "default": bool(spec["default"]),
            "enabled": bool(overrides.get(key, spec["default"])),
        }
        for key, spec in FEATURE_FLAGS.items()
    ]


def _project_endpoints(merchant: Merchant) -> list[dict[str, Any]]:
    rows = WebhookEndpoint.objects.filter(merchant=merchant).order_by("-created_at")
    out: list[dict[str, Any]] = []
    for ep in rows:
        out.append(
            {
                "id": str(ep.id),
                "url": ep.url,
                "events": list(ep.event_filters or []),
                "status": "Active" if ep.enabled else "Disabled",
                "description": ep.description or "",
            }
        )
    return out


# --- Public read API -------------------------------------------------------


def get_merchant_config_bundle(merchant_id: str) -> dict[str, Any] | None:
    """Return the full FE-facing config bundle for ``merchant_id`` or None."""
    try:
        merchant = _resolve(merchant_id)
    except MerchantNotFoundError:
        return None
    limits, retry, overrides = _get_or_default(merchant)
    currency = merchant.default_currency or limits.get("currency") or "NGN"
    return {
        "merchantId": str(merchant.id),
        "limits": _project_limits(limits, currency),
        "retryPolicy": _project_retry(retry),
        "featureFlags": _project_flags(overrides),
        "webhookEndpoints": _project_endpoints(merchant),
        "catalog": catalog(),
    }


def get_resolved_flags(merchant: Merchant) -> dict[str, bool]:
    """Thin wrapper around :func:`feature_flags.resolved_flags` for ergonomics."""
    return resolved_flags(merchant)


# --- Public write API ------------------------------------------------------


def _actor_label(admin: PlatformAdmin | None) -> str:
    if admin is None:
        return "platform_admin"
    return admin.email or admin.display_name or "platform_admin"


def _ensure_owner(admin: PlatformAdmin | None) -> None:
    role = getattr(admin, "role", None)
    if role != PlatformAdminRole.OWNER:
        raise OwnerRequiredError("Owner role required to edit merchant config.")


def _coerce_flags(payload: Any) -> dict[str, bool]:
    if not isinstance(payload, dict):
        raise UnknownFeatureFlagError("featureFlags must be an object of {key: bool}.")
    cleaned: dict[str, bool] = {}
    for raw_key, raw_val in payload.items():
        key = str(raw_key)
        if not is_known_flag(key):
            raise UnknownFeatureFlagError(f"Unknown feature flag: {key!r}.")
        cleaned[key] = bool(raw_val)
    return cleaned


def _coerce_limits(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("limits must be an object.")
    out: dict[str, Any] = {}
    if "monthly_volume_cap_minor" in payload or "monthlyVolumeCapMinor" in payload:
        out["monthly_volume_cap_minor"] = int(
            payload.get("monthly_volume_cap_minor", payload.get("monthlyVolumeCapMinor")) or 0
        )
    if "max_ticket_minor" in payload or "maxTicketMinor" in payload:
        out["max_ticket_minor"] = int(
            payload.get("max_ticket_minor", payload.get("maxTicketMinor")) or 0
        )
    if "high_risk_mcc" in payload or "highRiskMcc" in payload:
        out["high_risk_mcc"] = bool(
            payload.get("high_risk_mcc", payload.get("highRiskMcc"))
        )
    if "payout_cadence" in payload or "payoutCadence" in payload:
        val = str(payload.get("payout_cadence", payload.get("payoutCadence")) or "daily").lower()
        # Accept both display labels and lowercase tokens.
        val = {"daily": "daily", "weekly": "weekly", "t+2": "tplus2", "tplus2": "tplus2"}.get(
            val, "daily"
        )
        out["payout_cadence"] = val
    if "notification_channels" in payload or "notificationChannels" in payload:
        channels = payload.get("notification_channels", payload.get("notificationChannels")) or []
        if not isinstance(channels, (list, tuple)):
            raise ValueError("notificationChannels must be a list.")
        out["notification_channels"] = [str(c).lower() for c in channels]
    if "currency" in payload:
        out["currency"] = str(payload["currency"] or "NGN").upper()[:8]
    return out


def _coerce_retry(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("retryPolicy must be an object.")
    out: dict[str, Any] = {}
    if "attempts" in payload:
        out["attempts"] = max(0, int(payload.get("attempts") or 0))
    if "backoff" in payload:
        val = str(payload.get("backoff") or "exponential").lower()
        if val not in {"linear", "exponential"}:
            raise ValueError("backoff must be one of: linear, exponential.")
        out["backoff"] = val
    if "cooldown_hours" in payload or "cooldownHours" in payload:
        out["cooldown_hours"] = max(
            0, int(payload.get("cooldown_hours", payload.get("cooldownHours")) or 0)
        )
    return out


@dataclass(frozen=True)
class MerchantConfigUpdateResult:
    merchant_id: str
    changed_keys: list[str]


@transaction.atomic
def update_merchant_config(
    *,
    merchant_id: str,
    admin: PlatformAdmin | None,
    feature_flags: Any = None,
    limits: Any = None,
    retry_policy: Any = None,
    request: HttpRequest | None = None,
) -> MerchantConfigUpdateResult:
    """Sparse-merge config patches. Owner-only. Emits an audit log row."""
    _ensure_owner(admin)
    merchant = _resolve(merchant_id)

    config, _created = MerchantConfig.objects.select_for_update().get_or_create(
        merchant=merchant
    )

    changed: list[str] = []

    if feature_flags is not None:
        patch = _coerce_flags(feature_flags)
        if patch:
            current = dict(config.feature_flags or {})
            current.update(patch)
            config.feature_flags = current
            changed.append("feature_flags")
    if limits is not None:
        patch = _coerce_limits(limits)
        if patch:
            current = dict(config.limits or {})
            current.update(patch)
            config.limits = current
            changed.append("limits")
    if retry_policy is not None:
        patch = _coerce_retry(retry_policy)
        if patch:
            current = dict(config.retry_policy or {})
            current.update(patch)
            config.retry_policy = current
            changed.append("retry_policy")

    if changed:
        config.updated_by = admin
        config.save()

    log_event(
        action="platform.merchant.config.update",
        actor_user=None,
        actor_label=_actor_label(admin),
        actor_role="platform_admin",
        merchant=merchant,
        target_type="merchant_config",
        target_id=str(merchant.id),
        metadata={"changed": changed},
        request=request,
    )

    return MerchantConfigUpdateResult(
        merchant_id=str(merchant.id), changed_keys=changed
    )


__all__ = [
    "MerchantNotFoundError",
    "OwnerRequiredError",
    "UnknownFeatureFlagError",
    "MerchantConfigUpdateResult",
    "get_merchant_config_bundle",
    "get_resolved_flags",
    "update_merchant_config",
]
