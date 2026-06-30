"""Write actions for the platform-wide settings singleton (S10).

The single ``PlatformSetting`` row stores ``policy`` (dict) and
``adapter_status`` (list). Only platform Owners may update either field.
Each successful patch emits ``platform.settings.update`` to the audit log.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction

from apps.audit.services.log_event import log_event

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


@transaction.atomic
def update_settings(
    *,
    actor: PlatformAdmin | None,
    request=None,
    policy: dict[str, Any] | None = None,
    adapter_status: list[dict[str, Any]] | None = None,
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
