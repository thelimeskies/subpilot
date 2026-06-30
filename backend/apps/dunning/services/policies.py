"""Dunning policy management services."""
from __future__ import annotations

from typing import Iterable

from django.db import transaction

from apps.audit.services.log_event import log_event
from apps.common.exceptions import ServiceError

from ..models import DunningPolicy


_VALID_OFFSET_RANGE = range(0, 366)


def _validate_offsets(offsets: Iterable[int]) -> list[int]:
    out: list[int] = []
    last = -1
    for raw in offsets:
        if not isinstance(raw, int) or raw not in _VALID_OFFSET_RANGE:
            raise ServiceError("retry_offsets_days entries must be integers in [0, 365].")
        if raw <= last:
            raise ServiceError("retry_offsets_days must be strictly increasing.")
        out.append(raw)
        last = raw
    return out


@transaction.atomic
def create_dunning_policy(
    *,
    merchant,
    environment,
    name: str,
    retry_offsets_days: Iterable[int],
    grace_period_days: int = 0,
    final_action: str = DunningPolicy.FinalAction.CANCEL,
    notify_email: bool = True,
    notify_sms: bool = False,
    notify_webhook: bool = True,
    hard_failure_behavior: str = DunningPolicy.HardFailureBehavior.STOP,
    actor_user=None,
    request=None,
) -> DunningPolicy:
    if not name.strip():
        raise ServiceError("Policy name cannot be empty.")
    offsets = _validate_offsets(retry_offsets_days)
    if grace_period_days < 0:
        raise ServiceError("grace_period_days cannot be negative.")
    if final_action not in DunningPolicy.FinalAction.values:
        raise ServiceError(f"Unknown final_action: {final_action!r}.")
    if hard_failure_behavior not in DunningPolicy.HardFailureBehavior.values:
        raise ServiceError(f"Unknown hard_failure_behavior: {hard_failure_behavior!r}.")

    policy = DunningPolicy.objects.create(
        merchant=merchant,
        environment=environment,
        name=name.strip(),
        retry_offsets_days=offsets,
        grace_period_days=grace_period_days,
        final_action=final_action,
        notify_email=notify_email,
        notify_sms=notify_sms,
        notify_webhook=notify_webhook,
        hard_failure_behavior=hard_failure_behavior,
    )
    log_event(
        action="dunning.policy_created",
        actor_user=actor_user,
        merchant=merchant,
        environment=environment,
        target_type="dunning_policy",
        target_id=str(policy.id),
        metadata={"name": policy.name, "final_action": final_action},
        request=request,
    )
    return policy


@transaction.atomic
def update_dunning_policy(
    *,
    policy: DunningPolicy,
    actor_user=None,
    request=None,
    **fields,
) -> DunningPolicy:
    """Patch-style update. Only known fields are accepted."""
    allowed = {
        "name",
        "retry_offsets_days",
        "grace_period_days",
        "final_action",
        "notify_email",
        "notify_sms",
        "notify_webhook",
        "hard_failure_behavior",
    }
    changed: list[str] = []
    if "retry_offsets_days" in fields:
        fields["retry_offsets_days"] = _validate_offsets(fields["retry_offsets_days"])
    for key, value in fields.items():
        if key not in allowed:
            raise ServiceError(f"Unknown policy field: {key!r}.")
        setattr(policy, key, value)
        changed.append(key)
    policy.save(update_fields=[*changed, "updated_at"])
    log_event(
        action="dunning.policy_updated",
        actor_user=actor_user,
        merchant=policy.merchant,
        environment=policy.environment,
        target_type="dunning_policy",
        target_id=str(policy.id),
        metadata={"changed": changed},
        request=request,
    )
    return policy
