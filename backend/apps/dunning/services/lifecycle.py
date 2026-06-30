"""Dunning lifecycle services.

A :class:`DunningRun` is opened when a charge against an open invoice fails.
The run schedules retries according to the policy's ``retry_offsets_days``
schedule and either ``recovers`` (invoice paid), is ``suspended`` (hard
failure that requires payment-method replacement), or is ``exhausted`` (final
action applied: cancel, pause, mark uncollectible, or do nothing).
"""
from __future__ import annotations

from datetime import timedelta
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.exceptions import ConflictError, ServiceError
from apps.events.services.create_event import emit as _emit_event
from apps.invoices.models import Invoice
from apps.invoices.services.lifecycle import mark_uncollectible
from apps.payments.adapters import HARD_FAILURES, classify_failure

from ..models import DunningPolicy, DunningRun


def _next_retry_at(policy: DunningPolicy, attempt_count: int) -> "timezone.datetime | None":
    offsets: list[int] = list(policy.retry_offsets_days or [])
    if attempt_count >= len(offsets):
        return None
    return timezone.now() + timedelta(days=int(offsets[attempt_count]))


@transaction.atomic
def start_dunning_run(
    *,
    invoice: Invoice,
    policy: DunningPolicy | None = None,
    failure_code: str = "",
    actor_user=None,
    request=None,
) -> DunningRun:
    """Open (or return) the active dunning run for an invoice."""
    if invoice.status not in {Invoice.Status.OPEN, Invoice.Status.UNCOLLECTIBLE}:
        raise ServiceError("Only open invoices can enter dunning.")

    existing = DunningRun.objects.filter(
        invoice=invoice, status=DunningRun.Status.ACTIVE
    ).first()
    if existing is not None:
        return existing

    resolved_policy = policy or _resolve_policy(invoice)
    if resolved_policy is None:
        raise ServiceError("No dunning policy is configured for this subscription/merchant.")

    next_retry = _next_retry_at(resolved_policy, attempt_count=0)
    suspended = bool(failure_code) and classify_failure(failure_code) in HARD_FAILURES \
        and resolved_policy.hard_failure_behavior == DunningPolicy.HardFailureBehavior.STOP

    run = DunningRun.objects.create(
        merchant=invoice.merchant,
        environment=invoice.environment,
        invoice=invoice,
        subscription=invoice.subscription,
        policy=resolved_policy,
        status=(
            DunningRun.Status.SUSPENDED if suspended else DunningRun.Status.ACTIVE
        ),
        attempt_count=0,
        next_retry_at=None if suspended else next_retry,
    )
    log_event(
        action="dunning.run_started",
        actor_user=actor_user,
        merchant=invoice.merchant,
        environment=invoice.environment,
        target_type="dunning_run",
        target_id=str(run.id),
        metadata={
            "invoice_id": str(invoice.id),
            "policy": resolved_policy.name,
            "failure_code": failure_code,
            "suspended": suspended,
        },
        request=request,
    )
    _emit_event(
        merchant=invoice.merchant,
        environment=invoice.environment,
        event_type="dunning.started",
        aggregate_type="dunning_run",
        aggregate_id=str(run.id),
        payload={
            "run_id": str(run.id),
            "invoice_id": str(invoice.id),
            "subscription_id": str(invoice.subscription_id) if invoice.subscription_id else "",
            "policy": resolved_policy.name,
            "failure_code": failure_code,
            "suspended": suspended,
        },
        actor_user=actor_user,
        request=request,
    )
    return run


def _resolve_policy(invoice: Invoice) -> DunningPolicy | None:
    sub = invoice.subscription
    if sub is not None and sub.dunning_policy_id:
        return sub.dunning_policy
    return (
        DunningPolicy.objects.filter(
            merchant=invoice.merchant, environment=invoice.environment
        )
        .order_by("created_at")
        .first()
    )


@transaction.atomic
def record_attempt_outcome(
    *,
    run: DunningRun,
    success: bool,
    failure_code: str = "",
    actor_user=None,
    request=None,
) -> DunningRun:
    """Advance a run after a retry attempt finished.

    On success: marks the run RECOVERED.
    On hard failure with STOP policy: SUSPENDED.
    On soft failure: schedules the next retry; if exhausted, applies final action.
    """
    if run.status != DunningRun.Status.ACTIVE:
        raise ConflictError(f"Cannot advance dunning run in status {run.status!r}.")

    run.attempt_count += 1

    if success:
        run.status = DunningRun.Status.RECOVERED
        run.recovered_at = timezone.now()
        run.next_retry_at = None
        run.save(update_fields=["status", "attempt_count", "recovered_at", "next_retry_at", "updated_at"])
        log_event(
            action="dunning.run_recovered",
            actor_user=actor_user,
            merchant=run.merchant,
            environment=run.environment,
            target_type="dunning_run",
            target_id=str(run.id),
            metadata={"invoice_id": str(run.invoice_id)},
            request=request,
        )
        _emit_event(
            merchant=run.merchant,
            environment=run.environment,
            event_type="dunning.recovered",
            aggregate_type="dunning_run",
            aggregate_id=str(run.id),
            payload={
                "run_id": str(run.id),
                "invoice_id": str(run.invoice_id),
                "attempt_count": run.attempt_count,
            },
            actor_user=actor_user,
            request=request,
        )
        return run

    category = classify_failure(failure_code) if failure_code else ""
    if (
        category in HARD_FAILURES
        and run.policy.hard_failure_behavior == DunningPolicy.HardFailureBehavior.STOP
    ):
        run.status = DunningRun.Status.SUSPENDED
        run.next_retry_at = None
        run.save(update_fields=["status", "attempt_count", "next_retry_at", "updated_at"])
        log_event(
            action="dunning.run_suspended",
            actor_user=actor_user,
            merchant=run.merchant,
            environment=run.environment,
            target_type="dunning_run",
            target_id=str(run.id),
            metadata={"failure_code": failure_code, "category": category},
            request=request,
        )
        return run

    next_retry = _next_retry_at(run.policy, attempt_count=run.attempt_count)
    if next_retry is None:
        return _exhaust_run(run=run, actor_user=actor_user, request=request)

    run.next_retry_at = next_retry
    run.save(update_fields=["attempt_count", "next_retry_at", "updated_at"])
    log_event(
        action="dunning.attempt_recorded",
        actor_user=actor_user,
        merchant=run.merchant,
        environment=run.environment,
        target_type="dunning_run",
        target_id=str(run.id),
        metadata={
            "attempt_count": run.attempt_count,
            "next_retry_at": run.next_retry_at.isoformat() if run.next_retry_at else None,
            "failure_code": failure_code,
        },
        request=request,
    )
    _emit_event(
        merchant=run.merchant,
        environment=run.environment,
        event_type="dunning.retry_scheduled",
        aggregate_type="dunning_run",
        aggregate_id=str(run.id),
        payload={
            "run_id": str(run.id),
            "invoice_id": str(run.invoice_id),
            "attempt_count": run.attempt_count,
            "next_retry_at": run.next_retry_at.isoformat() if run.next_retry_at else None,
            "failure_code": failure_code,
        },
        actor_user=actor_user,
        request=request,
    )
    return run


def _exhaust_run(*, run: DunningRun, actor_user=None, request=None) -> DunningRun:
    """Apply the policy's final action and close the run."""
    from apps.subscriptions.services.lifecycle import (  # local import — avoid cycles
        cancel_subscription,
        pause_subscription,
    )

    final = run.policy.final_action
    invoice = run.invoice

    if final == DunningPolicy.FinalAction.CANCEL and run.subscription_id:
        cancel_subscription(
            subscription=run.subscription,
            at_period_end=False,
            reason="dunning_exhausted",
            actor_user=actor_user,
            request=request,
        )
    elif final == DunningPolicy.FinalAction.PAUSE and run.subscription_id:
        try:
            pause_subscription(
                subscription=run.subscription,
                actor_user=actor_user,
                request=request,
            )
        except ServiceError:
            pass
    elif final == DunningPolicy.FinalAction.MARK_UNCOLLECTIBLE:
        if invoice.status == Invoice.Status.OPEN:
            mark_uncollectible(
                invoice=invoice,
                reason="dunning_exhausted",
                actor_user=actor_user,
                request=request,
            )

    run.status = DunningRun.Status.EXHAUSTED
    run.exhausted_at = timezone.now()
    run.next_retry_at = None
    run.save(update_fields=["status", "exhausted_at", "next_retry_at", "updated_at"])
    log_event(
        action="dunning.run_exhausted",
        actor_user=actor_user,
        merchant=run.merchant,
        environment=run.environment,
        target_type="dunning_run",
        target_id=str(run.id),
        metadata={
            "final_action": final,
            "invoice_id": str(run.invoice_id),
            "subscription_id": str(run.subscription_id) if run.subscription_id else "",
        },
        request=request,
    )
    _emit_event(
        merchant=run.merchant,
        environment=run.environment,
        event_type="dunning.exhausted",
        aggregate_type="dunning_run",
        aggregate_id=str(run.id),
        payload={
            "run_id": str(run.id),
            "invoice_id": str(run.invoice_id),
            "subscription_id": str(run.subscription_id) if run.subscription_id else "",
            "final_action": final,
            "attempt_count": run.attempt_count,
        },
        actor_user=actor_user,
        request=request,
    )
    return run


@transaction.atomic
def cancel_dunning_run(*, run: DunningRun, reason: str = "", actor_user=None, request=None) -> DunningRun:
    run.refresh_from_db()
    if run.status not in {DunningRun.Status.ACTIVE, DunningRun.Status.SUSPENDED}:
        raise ServiceError("Run is not in a cancellable state.")
    run.status = DunningRun.Status.CANCELED
    run.next_retry_at = None
    run.save(update_fields=["status", "next_retry_at", "updated_at"])
    log_event(
        action="dunning.run_canceled",
        actor_user=actor_user,
        merchant=run.merchant,
        environment=run.environment,
        target_type="dunning_run",
        target_id=str(run.id),
        metadata={"reason": reason},
        request=request,
    )
    return run


@transaction.atomic
def pause_dunning_run(
    *,
    run: DunningRun,
    reason: str = "",
    paused_until=None,
    actor_user=None,
    request=None,
) -> DunningRun:
    """Suspend an active run until an operator resumes it."""
    run.refresh_from_db()
    if run.status != DunningRun.Status.ACTIVE:
        raise ServiceError("Only active dunning runs can be paused.")
    run.status = DunningRun.Status.SUSPENDED
    run.next_retry_at = paused_until
    run.save(update_fields=["status", "next_retry_at", "updated_at"])
    log_event(
        action="dunning.run_paused",
        actor_user=actor_user,
        merchant=run.merchant,
        environment=run.environment,
        target_type="dunning_run",
        target_id=str(run.id),
        metadata={
            "reason": reason,
            "attempt_count": run.attempt_count,
            "paused_until": paused_until.isoformat() if paused_until else None,
        },
        request=request,
    )
    _emit_event(
        merchant=run.merchant,
        environment=run.environment,
        event_type="dunning.paused",
        aggregate_type="dunning_run",
        aggregate_id=str(run.id),
        payload={
            "run_id": str(run.id),
            "invoice_id": str(run.invoice_id),
            "reason": reason,
            "attempt_count": run.attempt_count,
            "paused_until": paused_until.isoformat() if paused_until else None,
        },
        actor_user=actor_user,
        request=request,
    )
    return run


@transaction.atomic
def resume_dunning_run(*, run: DunningRun, actor_user=None, request=None) -> DunningRun:
    """Bring a SUSPENDED run back to ACTIVE, e.g. after a new payment method."""
    run.refresh_from_db()
    if run.status != DunningRun.Status.SUSPENDED:
        raise ServiceError("Only suspended runs can be resumed.")
    run.status = DunningRun.Status.ACTIVE
    run.next_retry_at = _next_retry_at(run.policy, attempt_count=run.attempt_count)
    run.save(update_fields=["status", "next_retry_at", "updated_at"])
    log_event(
        action="dunning.run_resumed",
        actor_user=actor_user,
        merchant=run.merchant,
        environment=run.environment,
        target_type="dunning_run",
        target_id=str(run.id),
        metadata={"attempt_count": run.attempt_count},
        request=request,
    )
    return run
