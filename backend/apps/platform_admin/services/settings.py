"""Write actions for the platform-wide settings singleton (S10).

The single ``PlatformSetting`` row stores ``policy`` (dict) and
``adapter_status`` (list). Only platform Owners may update either field.
Each successful patch emits ``platform.settings.update`` to the audit log.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.audit.services.log_event import log_event
from apps.common.crypto import encrypt

from ..models import PlatformAdmin, PlatformAdminRole, PlatformSetting
from ..selectors.settings import (
    DEFAULT_ADAPTER_STATUS,
    DEFAULT_POLICY,
    get_settings_row,
)


class SettingFieldError(ValueError):
    """Raised on bad input or insufficient privileges."""


def _ensure_owner(actor: PlatformAdmin | None) -> None:
    if actor is None or actor.role != PlatformAdminRole.OWNER:
        raise SettingFieldError("Only platform Owners can update settings.")


def _actor_label(admin: PlatformAdmin | None) -> str:
    if admin is None:
        return "platform-admin"
    return admin.display_name or admin.email or "platform-admin"


def _diff_policy(before: dict[str, Any], after: dict[str, Any]) -> dict[str, dict[str, Any]]:
    changes: dict[str, dict[str, Any]] = {}
    for key in set(before.keys()) | set(after.keys()):
        if before.get(key) != after.get(key):
            changes[key] = {"from": before.get(key), "to": after.get(key)}
    return changes


def _clean_str(value: Any) -> str:
    return str(value or "").strip()


def _merge_nomba_platform_config(before_policy: dict[str, Any], payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SettingFieldError("nomba_platform must be an object.")
    merged = dict(before_policy)
    active_mode = payload.get("activeMode", payload.get("active_mode"))
    if active_mode is not None:
        if active_mode not in {"test", "live"}:
            raise SettingFieldError("nomba_platform.activeMode must be test or live.")
        merged["nombaPlatformActiveMode"] = active_mode
    live_active = payload.get("liveActive", payload.get("live_active"))
    if live_active is not None:
        merged["nombaPlatformLiveActive"] = bool(live_active)

    for mode in ("test", "live"):
        source = payload.get(mode)
        if source is None:
            continue
        if not isinstance(source, dict):
            raise SettingFieldError(f"nomba_platform.{mode} must be an object.")
        prefix = "Live" if mode == "live" else "Test"
        mapping = {
            "baseUrl": f"nombaPlatform{prefix}BaseUrl",
            "base_url": f"nombaPlatform{prefix}BaseUrl",
            "accountId": f"nombaPlatform{prefix}AccountId",
            "account_id": f"nombaPlatform{prefix}AccountId",
            "subAccountId": f"nombaPlatform{prefix}SubAccountId",
            "sub_account_id": f"nombaPlatform{prefix}SubAccountId",
            "clientId": f"nombaPlatform{prefix}ClientId",
            "client_id": f"nombaPlatform{prefix}ClientId",
        }
        for incoming_key, policy_key in mapping.items():
            if incoming_key in source:
                merged[policy_key] = _clean_str(source[incoming_key])
        if source.get("clientSecret") or source.get("client_secret"):
            merged[f"nombaPlatform{prefix}ClientSecretEncrypted"] = encrypt(
                _clean_str(source.get("clientSecret") or source.get("client_secret"))
            )
        if source.get("webhookSecret") or source.get("webhook_secret"):
            merged[f"nombaPlatform{prefix}WebhookSecretEncrypted"] = encrypt(
                _clean_str(source.get("webhookSecret") or source.get("webhook_secret"))
            )
    return merged


@transaction.atomic
def update_settings(
    *,
    actor: PlatformAdmin | None,
    request=None,
    policy: dict[str, Any] | None = None,
    adapter_status: list[dict[str, Any]] | None = None,
    nomba_platform: dict[str, Any] | None = None,
) -> PlatformSetting:
    """Owner-only patch of policy + adapter_status.

    Policy patches are MERGED over existing values (so the FE can ship a
    sparse payload). Unknown keys are accepted but warned about via the
    audit metadata. ``adapter_status`` is REPLACED wholesale when provided.
    """
    _ensure_owner(actor)

    if policy is not None and not isinstance(policy, dict):
        raise SettingFieldError("policy must be an object.")
    if adapter_status is not None and not isinstance(adapter_status, list):
        raise SettingFieldError("adapter_status must be a list.")

    row = PlatformSetting.objects.select_for_update().get(pk=get_settings_row().pk)

    before_policy = {**DEFAULT_POLICY, **(row.policy or {})}
    before_adapters = list(row.adapter_status) if isinstance(row.adapter_status, list) else list(DEFAULT_ADAPTER_STATUS)

    update_fields: list[str] = []
    changed_metadata: dict[str, Any] = {}

    if policy is not None:
        merged = dict(before_policy)
        for key, value in policy.items():
            merged[str(key)] = value
        if merged != before_policy:
            row.policy = merged
            update_fields.append("policy")
            changed_metadata["policy"] = _diff_policy(before_policy, merged)

    if adapter_status is not None:
        # Validate adapter shape lightly — every item must be a dict with a name.
        for idx, item in enumerate(adapter_status):
            if not isinstance(item, dict):
                raise SettingFieldError(f"adapter_status[{idx}] must be an object.")
            if not (item.get("name") or "").strip():
                raise SettingFieldError(f"adapter_status[{idx}].name is required.")
        if adapter_status != before_adapters:
            row.adapter_status = list(adapter_status)
            update_fields.append("adapter_status")
            changed_metadata["adapter_status"] = {
                "from_count": len(before_adapters),
                "to_count": len(adapter_status),
            }

    if nomba_platform is not None:
        merged = _merge_nomba_platform_config(row.policy or {}, nomba_platform)
        if merged != (row.policy or {}):
            row.policy = merged
            if "policy" not in update_fields:
                update_fields.append("policy")
            changed_metadata["nomba_platform"] = {
                "active_mode": merged.get("nombaPlatformActiveMode", "test"),
                "live_active": bool(merged.get("nombaPlatformLiveActive")),
                "test_configured": bool(
                    merged.get("nombaPlatformTestAccountId")
                    and merged.get("nombaPlatformTestClientId")
                    and merged.get("nombaPlatformTestClientSecretEncrypted")
                ),
                "live_configured": bool(
                    merged.get("nombaPlatformLiveAccountId")
                    and merged.get("nombaPlatformLiveClientId")
                    and merged.get("nombaPlatformLiveClientSecretEncrypted")
                ),
            }

    if update_fields:
        update_fields.append("updated_at")
        row.save(update_fields=update_fields)
        log_event(
            action="platform.settings.update",
            actor_user=None,
            actor_label=_actor_label(actor),
            actor_role="platform_admin",
            merchant=None,
            target_type="platform_setting",
            target_id=str(row.id),
            metadata={"changes": changed_metadata, "fields": update_fields[:-1]},
            request=request,
        )

    return row


__all__ = [
    "SettingFieldError",
    "update_settings",
]
