"""Dunning notification logging service."""
from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from apps.common.email import (
    format_email_datetime,
    merchant_email_context,
    send_templated_email,
)
from apps.common.exceptions import ServiceError
from apps.common.money import format_money
from apps.customers.services.create_portal_session import (
    DEFAULT_ALLOWED_ACTIONS,
    create_portal_session,
    portal_session_url,
)
from apps.events.services.create_event import emit as _emit_event

from ..models import DunningRun, NotificationLog


@transaction.atomic
def record_notification(
    *,
    run: DunningRun,
    channel: str,
    template_key: str = "",
    status: str = NotificationLog.Status.SENT,
    failure_message: str = "",
) -> NotificationLog:
    if channel not in NotificationLog.Channel.values:
        raise ServiceError(f"Unknown notification channel: {channel!r}.")
    sent_at = timezone.now() if status == NotificationLog.Status.SENT else None
    log = NotificationLog.objects.create(
        merchant=run.merchant,
        environment=run.environment,
        dunning_run=run,
        channel=channel,
        status=status,
        template_key=template_key,
        sent_at=sent_at,
        failure_message=failure_message[:400],
    )
    if status == NotificationLog.Status.SENT:
        _emit_event(
            merchant=run.merchant,
            environment=run.environment,
            event_type="dunning.notification_sent",
            aggregate_type="dunning_run",
            aggregate_id=str(run.id),
            payload={
                "run_id": str(run.id),
                "invoice_id": str(run.invoice_id),
                "channel": channel,
                "template_key": template_key,
            },
        )
    return log


def send_recovery_notification(
    *, run: DunningRun, actor_user=None, request=None
) -> NotificationLog | None:
    """Email a customer a secure recovery link for an active dunning run."""
    run = (
        DunningRun.objects.select_related(
            "invoice",
            "invoice__customer",
            "merchant",
            "environment",
            "policy",
            "subscription",
        )
        .get(pk=run.pk)
    )
    if not run.policy.notify_email:
        return None

    invoice = run.invoice
    customer = invoice.customer
    session, token = create_portal_session(
        customer=customer,
        subscription=run.subscription,
        invoice=invoice,
        allowed_actions=[
            *DEFAULT_ALLOWED_ACTIONS,
            "resolve_failed_payment",
            "retry_invoice",
        ],
        actor_user=actor_user,
        request=request,
    )
    recovery_link = portal_session_url(token)
    next_retry_at = format_email_datetime(run.next_retry_at)
    try:
        send_templated_email(
            to=customer.email,
            subject=f"Action needed: payment for invoice {invoice.number}",
            template="dunning_recovery",
            context=merchant_email_context(
                run.merchant,
                email_label="Payment recovery",
                recipient_name=customer.name or customer.email,
                invoice_number=invoice.number,
                amount_due=format_money(invoice.amount_due_minor, invoice.currency),
                recovery_link=recovery_link,
                next_retry_at=next_retry_at,
                expires_at=format_email_datetime(session.expires_at),
            ),
        )
    except Exception as exc:
        return record_notification(
            run=run,
            channel=NotificationLog.Channel.EMAIL,
            template_key="dunning_recovery",
            status=NotificationLog.Status.FAILED,
            failure_message=str(exc),
        )

    return record_notification(
        run=run,
        channel=NotificationLog.Channel.EMAIL,
        template_key="dunning_recovery",
        status=NotificationLog.Status.SENT,
    )
