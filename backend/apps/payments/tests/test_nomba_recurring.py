from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone

from apps.accounts.models import Environment, Merchant
from apps.catalog.models import Plan, PriceVersion, Product
from apps.customers.models import Customer, PaymentMethod
from apps.invoices.models import InvoiceLineItem
from apps.invoices.services.create_invoice import create_invoice
from apps.invoices.services.lifecycle import finalize_invoice
from apps.payments.models import PaymentAttempt
from apps.payments.services import charge_invoice
from apps.subscriptions.models import Subscription, SubscriptionItem

pytestmark = pytest.mark.django_db


class _Response:
    def __init__(self, payload: dict):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return json.dumps(self.payload).encode()


def _billing_workspace():
    merchant = Merchant.objects.create(name="Recurring Co", slug="recurring-co")
    environment = Environment.objects.create(
        merchant=merchant,
        mode=Environment.Mode.TEST,
        nomba_integration_mode=Environment.NombaIntegrationMode.BYOK,
        nomba_account_id="acct_123",
        nomba_client_id="client_123",
    )
    environment.nomba_client_secret = "secret_123"
    environment.nomba_access_token = "access-token"
    environment.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    environment.save(
        update_fields=[
            "nomba_client_secret_encrypted",
            "nomba_access_token_encrypted",
            "nomba_token_expires_at",
            "updated_at",
        ]
    )
    customer = Customer.objects.create(
        merchant=merchant,
        environment=environment,
        email="ada@example.test",
        name="Ada Example",
    )
    product = Product.objects.create(
        merchant=merchant,
        environment=environment,
        name="Membership",
        status=Product.Status.ACTIVE,
    )
    plan = Plan.objects.create(
        merchant=merchant,
        environment=environment,
        product=product,
        name="Monthly",
        status=Plan.Status.ACTIVE,
    )
    price = PriceVersion.objects.create(
        plan=plan,
        amount_minor=5000,
        currency="NGN",
        interval_unit=PriceVersion.IntervalUnit.MONTH,
        interval_count=1,
        active_from=timezone.now(),
    )
    payment_method = PaymentMethod.objects.create(
        merchant=merchant,
        environment=environment,
        customer=customer,
        provider=PaymentMethod.Provider.NOMBA,
        brand="Visa",
        last4="4242",
        is_default=True,
    )
    payment_method.token = "tok_nomba_saved_card"
    payment_method.save(update_fields=["token_encrypted"])
    subscription = Subscription.objects.create(
        merchant=merchant,
        environment=environment,
        customer=customer,
        plan=plan,
        status=Subscription.Status.ACTIVE,
        default_payment_method=payment_method,
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )
    SubscriptionItem.objects.create(subscription=subscription, price_version=price, quantity=1)
    invoice = create_invoice(
        merchant=merchant,
        environment=environment,
        customer=customer,
        currency="NGN",
        line_items=[
            {
                "type": InvoiceLineItem.Type.SUBSCRIPTION,
                "description": "Monthly renewal",
                "amount_minor": 5000,
                "quantity": 1,
                "currency": "NGN",
            }
        ],
        subscription=subscription,
        metadata={"renewal": True},
    )
    invoice = finalize_invoice(invoice=invoice)
    return invoice, payment_method


@override_settings(NOMBA_CHECKOUT_CALLBACK_URL="https://example.test/nomba/callback")
def test_nomba_recurring_charge_uses_tokenized_card_payment(monkeypatch):
    invoice, payment_method = _billing_workspace()
    seen = {}

    def fake_urlopen(req, timeout):
        seen["method"] = req.get_method()
        seen["url"] = req.full_url
        seen["headers"] = dict(req.header_items())
        seen["body"] = json.loads(req.data.decode())
        return _Response(
            {
                "code": "00",
                "description": "payment successful",
                "data": {
                    "status": True,
                    "message": "success",
                    "transactionId": "txn_123",
                },
            }
        )

    monkeypatch.setattr("apps.payments.integrations.nomba.client.request.urlopen", fake_urlopen)

    outcome = charge_invoice(invoice=invoice, payment_method=payment_method)

    assert outcome.result.success is True
    assert seen["method"] == "POST"
    assert seen["url"] == "https://sandbox.nomba.com/v1/checkout/tokenized-card-payment"
    assert seen["body"]["tokenKey"] == "tok_nomba_saved_card"
    assert seen["body"]["order"]["amount"] == "50.00"
    assert seen["body"]["order"]["callbackUrl"] == "https://example.test/nomba/callback"
    assert seen["body"]["order"]["orderMetaData"]["invoice_id"] == str(invoice.id)
    assert seen["body"]["order"]["orderMetaData"]["subscription_id"] == str(invoice.subscription_id)
    attempt = PaymentAttempt.objects.get(invoice=invoice)
    assert attempt.status == PaymentAttempt.Status.SUCCEEDED
    assert attempt.processor_reference == "txn_123"
