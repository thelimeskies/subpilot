"""Process an inbound (verified) processor webhook.

Steps:
1. Persist (or fetch) the :class:`ProcessorEvent` row, deduplicating on
   ``(provider, provider_event_id)``.
2. Route on canonical event type:
   - ``charge.succeeded`` -> mark the matching invoice paid, log audit row.
   - ``charge.failed`` -> mark latest pending attempt failed, log audit row.
   - ``charge.refunded`` -> log audit row (refund handling lives in Sprint 3+).
3. Mark the event ``processed_at`` timestamp.
"""
from __future__ import annotations

from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.crypto import hash_secret
from apps.customers.models import PaymentMethod
from apps.customers.services.payment_methods import (
    attach_payment_method,
    set_default_payment_method,
)
from apps.invoices.models import Invoice
from apps.invoices.services.lifecycle import mark_paid
from apps.subscriptions.models import Subscription
from apps.subscriptions.services.activate_subscription import activate_subscription

from ..models import PaymentAttempt, ProcessorEvent
from .ledger import record_charge_transaction


@transaction.atomic
def process_processor_event(
    *,
    merchant,
    environment,
    parsed: dict[str, Any],
    request=None,
) -> ProcessorEvent:
    """Idempotently apply a webhook event to local state."""
    provider = parsed.get("provider", "nomba")
    provider_event_id = parsed.get("provider_event_id") or ""
    event_type = parsed.get("event_type") or "unknown"
    raw = parsed.get("raw") or {}

    if not provider_event_id:
        # Nothing to dedupe on; still record but do not let routing run.
        ev = ProcessorEvent.objects.create(
            merchant=merchant,
            environment=environment,
            provider=provider,
            provider_event_id="",
            event_type=event_type,
            payload=raw,
        )
        return ev

    ev, created = ProcessorEvent.objects.get_or_create(
        merchant=merchant,
        environment=environment,
        provider=provider,
        provider_event_id=provider_event_id,
        defaults={
            "event_type": event_type,
            "payload": raw,
            "processor_reference": parsed.get("processor_reference", "")[:128],
        },
    )
    if not created and ev.processed_at is not None:
        # Already handled — return as-is, do not re-run side effects.
        return ev

    _apply_tokenized_card_handoff(
        merchant=merchant,
        environment=environment,
        parsed=parsed,
        request=request,
    )

    _route_event(
        merchant=merchant,
        environment=environment,
        parsed=parsed,
        event_type=event_type,
        request=request,
    )

    ev.processed_at = timezone.now()
    ev.save(update_fields=["processed_at"])
    return ev


def _route_event(
    *,
    merchant,
    environment,
    parsed: dict[str, Any],
    event_type: str,
    request=None,
) -> None:
    reference = parsed.get("processor_reference") or ""
    invoice = _find_invoice_for_event(merchant, environment, parsed)

    if event_type in {"charge.succeeded", "payment.succeeded"}:
        if invoice is None:
            return
        attempt = _latest_pending_attempt(invoice)
        if attempt is None and invoice.status == Invoice.Status.PAID:
            if PaymentAttempt.objects.filter(
                invoice=invoice,
                status=PaymentAttempt.Status.SUCCEEDED,
            ).exists():
                return
        if attempt is not None:
            attempt.status = PaymentAttempt.Status.SUCCEEDED
            if reference:
                attempt.processor_reference = reference[:128]
            attempt.save(
                update_fields=["status", "processor_reference", "updated_at"]
            )
        else:
            amount_minor = _event_amount_minor(parsed, invoice)
            attempt = PaymentAttempt.objects.create(
                merchant=merchant,
                environment=environment,
                invoice=invoice,
                payment_method=getattr(invoice.subscription, "default_payment_method", None),
                attempt_number=_next_attempt_number(invoice),
                status=PaymentAttempt.Status.SUCCEEDED,
                amount_minor=amount_minor,
                currency=(parsed.get("currency") or invoice.currency).upper(),
                processor_reference=reference[:128],
                idempotency_key=f"webhook:{parsed.get('provider_event_id') or reference}",
                metadata={"source": "processor_webhook"},
            )
        record_charge_transaction(attempt=attempt)
        if invoice.status not in {Invoice.Status.PAID, Invoice.Status.VOID}:
            mark_paid(invoice=invoice, paid_amount_minor=attempt.amount_minor, request=request)
        log_event(
            action="payments.webhook_charge_succeeded",
            merchant=merchant,
            environment=environment,
            target_type="invoice",
            target_id=str(invoice.id),
            metadata={"reference": reference, "event_type": event_type},
            request=request,
        )
        return

    if event_type in {"charge.failed", "payment.failed"}:
        if invoice is None:
            return
        attempt = _latest_pending_attempt(invoice)
        if attempt is not None:
            attempt.status = PaymentAttempt.Status.FAILED
            attempt.failure_code = (parsed.get("failure_code") or "processor_error")[:64]
            attempt.failure_message = (parsed.get("failure_message") or "")[:400]
            if reference:
                attempt.processor_reference = reference[:128]
            attempt.save(
                update_fields=[
                    "status",
                    "failure_code",
                    "failure_message",
                    "processor_reference",
                    "updated_at",
                ]
            )
        log_event(
            action="payments.webhook_charge_failed",
            merchant=merchant,
            environment=environment,
            target_type="invoice",
            target_id=str(invoice.id),
            metadata={
                "reference": reference,
                "failure_code": parsed.get("failure_code") or "",
                "event_type": event_type,
            },
            request=request,
        )
        return

    # Unknown / unsupported event type: log audit row, do nothing else.
    log_event(
        action="payments.webhook_unhandled",
        merchant=merchant,
        environment=environment,
        target_type="processor_event",
        target_id=parsed.get("provider_event_id", ""),
        metadata={"event_type": event_type, "reference": reference},
        request=request,
    )


def _apply_tokenized_card_handoff(
    *,
    merchant,
    environment,
    parsed: dict[str, Any],
    request=None,
) -> None:
    token_key = str(parsed.get("token_key") or "").strip()
    if not token_key:
        return

    invoice = _find_invoice_for_event(merchant, environment, parsed)
    subscription = _find_subscription_for_event(merchant, environment, parsed, invoice=invoice)
    customer = getattr(invoice, "customer", None) or getattr(subscription, "customer", None)
    if customer is None:
        return

    fingerprint = hash_secret(f"nomba:{token_key}")
    payment_method = PaymentMethod.objects.filter(
        customer=customer,
        provider=PaymentMethod.Provider.NOMBA,
        fingerprint=fingerprint,
    ).first()
    if payment_method is None:
        exp_month, exp_year = _parse_token_expiry(parsed.get("token_expiration_date") or "")
        payment_method = attach_payment_method(
            customer=customer,
            provider=PaymentMethod.Provider.NOMBA,
            token=token_key,
            brand=str(parsed.get("card_type") or ""),
            last4=_last4_from_pan(str(parsed.get("card_pan") or "")),
            exp_month=exp_month,
            exp_year=exp_year,
            fingerprint=fingerprint,
            set_default=True,
            metadata={
                "source": "nomba_webhook",
                "provider_event_id": parsed.get("provider_event_id") or "",
            },
            request=request,
        )
    else:
        set_default_payment_method(customer=customer, payment_method=payment_method, request=request)

    if subscription is not None:
        subscription.default_payment_method = payment_method
        subscription.save(update_fields=["default_payment_method", "updated_at"])
        if subscription.status in {
            Subscription.Status.INCOMPLETE,
            Subscription.Status.TRIALING,
        }:
            activate_subscription(subscription=subscription, request=request)


def _find_subscription_for_event(
    merchant,
    environment,
    parsed: dict[str, Any],
    *,
    invoice: Invoice | None = None,
) -> Subscription | None:
    if invoice is not None and invoice.subscription_id:
        return invoice.subscription
    metadata = _webhook_metadata(parsed)
    subscription_id = metadata.get("subscription_id") if isinstance(metadata, dict) else None
    if subscription_id:
        try:
            return Subscription.objects.get(
                id=subscription_id,
                merchant=merchant,
                environment=environment,
            )
        except (Subscription.DoesNotExist, ValueError):
            pass
    return None


def _find_invoice_for_event(merchant, environment, parsed: dict[str, Any]) -> Invoice | None:
    metadata = _webhook_metadata(parsed)
    invoice_id = metadata.get("invoice_id") if isinstance(metadata, dict) else None
    qs = Invoice.objects.filter(merchant=merchant, environment=environment)
    if invoice_id:
        try:
            return qs.get(id=invoice_id)
        except Invoice.DoesNotExist:
            pass
    reference = parsed.get("processor_reference") or ""
    if reference:
        attempt = (
            PaymentAttempt.objects.filter(
                merchant=merchant,
                environment=environment,
                processor_reference=reference,
            )
            .order_by("-created_at")
            .first()
        )
        if attempt is not None:
            return attempt.invoice
    return None


def _webhook_metadata(parsed: dict[str, Any]) -> dict:
    raw = parsed.get("raw") or {}
    data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
    transaction = data.get("transaction") if isinstance(data.get("transaction"), dict) else {}
    for value in (
        raw.get("metadata"),
        raw.get("orderMetaData"),
        data.get("metadata"),
        data.get("orderMetaData"),
        transaction.get("metadata"),
        transaction.get("orderMetaData"),
    ):
        if isinstance(value, dict):
            return value
    return {}


def _last4_from_pan(value: str) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    return digits[-4:]


def _parse_token_expiry(value: str) -> tuple[int | None, int | None]:
    if not value or "/" not in value:
        return None, None
    month_raw, year_raw = value.split("/", 1)
    try:
        month = int(month_raw)
        year = int(year_raw)
    except ValueError:
        return None, None
    if not 1 <= month <= 12:
        month = None
    if year and year < 100:
        year += 2000
    return month, year or None


def _latest_pending_attempt(invoice: Invoice) -> PaymentAttempt | None:
    return (
        PaymentAttempt.objects.filter(invoice=invoice, status=PaymentAttempt.Status.PENDING)
        .order_by("-attempt_number")
        .first()
    )


def _next_attempt_number(invoice: Invoice) -> int:
    last = (
        PaymentAttempt.objects.filter(invoice=invoice)
        .order_by("-attempt_number")
        .values_list("attempt_number", flat=True)
        .first()
    )
    return (last or 0) + 1


def _event_amount_minor(parsed: dict[str, Any], invoice: Invoice) -> int:
    try:
        amount = int(parsed.get("amount_minor") or 0)
    except (TypeError, ValueError):
        amount = 0
    if amount > 0:
        return amount
    return max(1, int(invoice.amount_due_minor or invoice.total_minor or 0))
