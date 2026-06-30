from __future__ import annotations

import pytest

from apps.accounts.models import Environment, Merchant
from apps.customers.models import Customer, PaymentMethod
from apps.invoices.models import Invoice
from apps.invoices.services import apply_credit_note
from apps.payments.models import BalanceTransaction, PaymentAttempt, ProcessorEvent
from apps.payments.services import (
    charge_invoice,
    process_processor_event,
    record_refund_transaction,
)

pytestmark = pytest.mark.django_db


def _workspace(slug: str = "ledger"):
    merchant = Merchant.objects.create(name=f"{slug.title()} Co", slug=slug, default_currency="NGN")
    environment = Environment.objects.create(merchant=merchant, mode=Environment.Mode.TEST)
    customer = Customer.objects.create(
        merchant=merchant,
        environment=environment,
        email=f"customer@{slug}.test",
        name="Customer",
    )
    method = PaymentMethod.objects.create(
        merchant=merchant,
        environment=environment,
        customer=customer,
        provider=PaymentMethod.Provider.MOCK,
        brand="Visa",
        last4="4242",
        is_default=True,
    )
    method.token = "tok_success"
    method.save(update_fields=["token_encrypted"])
    invoice = Invoice.objects.create(
        merchant=merchant,
        environment=environment,
        customer=customer,
        number=f"INV-{slug.upper()}-001",
        status=Invoice.Status.OPEN,
        subtotal_minor=10_000,
        total_minor=10_000,
        amount_due_minor=10_000,
        currency="NGN",
    )
    return merchant, environment, customer, method, invoice


def test_charge_invoice_records_positive_balance_transaction():
    _merchant, _environment, _customer, method, invoice = _workspace()

    outcome = charge_invoice(invoice=invoice, payment_method=method, adapter_name="mock")

    assert outcome.result.success is True
    invoice.refresh_from_db()
    assert invoice.status == Invoice.Status.PAID
    tx = BalanceTransaction.objects.get(payment_attempt=outcome.attempt)
    assert tx.type == BalanceTransaction.Type.CHARGE
    assert tx.signed_amount_minor == 10_000
    assert tx.merchant_id == invoice.merchant_id
    assert tx.environment_id == invoice.environment_id


def test_processor_events_are_deduped_per_tenant_and_create_ledger_attempts():
    m1, e1, _c1, _pm1, inv1 = _workspace("tenant-a")
    m2, e2, _c2, _pm2, inv2 = _workspace("tenant-b")

    event_id = "evt_same_provider_id"
    for merchant, environment, invoice in ((m1, e1, inv1), (m2, e2, inv2)):
        process_processor_event(
            merchant=merchant,
            environment=environment,
            parsed={
                "provider": "mock",
                "provider_event_id": event_id,
                "event_type": "charge.succeeded",
                "processor_reference": f"ref_{merchant.slug}",
                "amount_minor": invoice.amount_due_minor,
                "currency": invoice.currency,
                "raw": {"metadata": {"invoice_id": str(invoice.id)}},
            },
        )

    assert ProcessorEvent.objects.filter(provider_event_id=event_id).count() == 2
    assert PaymentAttempt.objects.filter(status=PaymentAttempt.Status.SUCCEEDED).count() == 2
    assert BalanceTransaction.objects.filter(type=BalanceTransaction.Type.CHARGE).count() == 2
    assert {
        tx.merchant_id for tx in BalanceTransaction.objects.filter(type=BalanceTransaction.Type.CHARGE)
    } == {m1.id, m2.id}


def test_credits_and_refunds_are_separate_negative_movements():
    merchant, environment, customer, method, invoice = _workspace()
    outcome = charge_invoice(invoice=invoice, payment_method=method, adapter_name="mock")
    credit_invoice = Invoice.objects.create(
        merchant=merchant,
        environment=environment,
        customer=customer,
        number="INV-LEDGER-CREDIT",
        status=Invoice.Status.OPEN,
        subtotal_minor=5_000,
        total_minor=5_000,
        amount_due_minor=5_000,
        currency="NGN",
    )

    credited_invoice, credit_note = apply_credit_note(
        invoice=credit_invoice,
        amount_minor=2_500,
        reason="other",
        note="service credit",
    )
    refund_tx = record_refund_transaction(
        attempt=outcome.attempt,
        amount_minor=1_000,
        metadata={"reason": "partial refund"},
    )

    credit_tx = BalanceTransaction.objects.get(credit_note=credit_note)
    assert credited_invoice.id == credit_invoice.id
    assert credit_tx.type == BalanceTransaction.Type.CREDIT
    assert credit_tx.signed_amount_minor == -2_500
    assert refund_tx.type == BalanceTransaction.Type.REFUND
    assert refund_tx.signed_amount_minor == -1_000
