from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import timedelta

import pytest
from django.test import override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant
from apps.catalog.models import Plan, PriceVersion, Product
from apps.customers.models import Customer, PaymentMethod
from apps.invoices.models import Invoice, InvoiceLineItem
from apps.invoices.services.create_invoice import create_invoice
from apps.invoices.services.lifecycle import finalize_invoice
from apps.payments.models import PaymentAttempt, ProcessorEvent
from apps.subscriptions.models import Subscription, SubscriptionItem

pytestmark = pytest.mark.django_db


def _payload() -> dict:
    return {
        "event_type": "payment_success",
        "requestId": "45f2dc2d-d559-4773-bba3-2d5ec17b2e20",
        "data": {
            "merchant": {
                "walletId": "6756ff80aafe04a795f18b38",
                "walletBalance": 6052,
                "userId": "b7b10e81-e57d-41d0-8fdc-f4e23a132bbf",
            },
            "terminal": {},
            "transaction": {
                "aliasAccountNumber": "5343270516",
                "fee": 5,
                "sessionId": "IFAP-TRANSFER-46501-e0339485-1a2f-4b43-9bd5-fec9649e5928",
                "type": "vact_transfer",
                "transactionId": "API-VACT_TRA-B7B10-0435b274-807a-4bc7-8abe-9dbb4548fd7a",
                "aliasAccountName": "SAMPLE/JOHN DOE",
                "responseCode": "",
                "originatingFrom": "api",
                "transactionAmount": 10,
                "narration": "John Doe Transfer 10.00",
                "time": "2025-09-29T10:51:44Z",
                "aliasAccountReference": "654f7c80bd4a510c90fb7f92",
                "aliasAccountType": "VIRTUAL",
            },
            "customer": {
                "bankCode": "090645",
                "senderName": "John Doe",
                "bankName": "Nombank",
                "accountNumber": "0000000000",
            },
        },
    }


def _signature(payload: dict, secret: str, timestamp: str) -> str:
    merchant = payload["data"]["merchant"]
    transaction = payload["data"]["transaction"]
    signed = ":".join(
        [
            payload["event_type"],
            payload["requestId"],
            merchant["userId"],
            merchant["walletId"],
            transaction["transactionId"],
            transaction["type"],
            transaction["time"],
            transaction["responseCode"],
            timestamp,
        ]
    )
    digest = hmac.new(secret.encode(), signed.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _workspace():
    merchant = Merchant.objects.create(name="Webhook Co", slug="webhook-co")
    environment = Environment.objects.create(
        merchant=merchant,
        mode=Environment.Mode.TEST,
        nomba_account_id="6756ff80aafe04a795f18b38",
    )
    environment.webhook_secret = "test_nomba_webhook_secret"
    environment.nomba_access_token = "access-token"
    environment.nomba_token_expires_at = timezone.now() + timedelta(hours=1)
    environment.save(
        update_fields=[
            "webhook_secret_encrypted",
            "nomba_access_token_encrypted",
            "nomba_token_expires_at",
            "updated_at",
        ]
    )
    return merchant, environment


def _subscription_workspace():
    merchant, environment = _workspace()
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
        amount_minor=1000,
        currency="NGN",
        interval_unit=PriceVersion.IntervalUnit.MONTH,
        interval_count=1,
        active_from=timezone.now(),
    )
    subscription = Subscription.objects.create(
        merchant=merchant,
        environment=environment,
        customer=customer,
        plan=plan,
        status=Subscription.Status.INCOMPLETE,
    )
    SubscriptionItem.objects.create(
        subscription=subscription,
        price_version=price,
        quantity=1,
    )
    invoice = create_invoice(
        merchant=merchant,
        environment=environment,
        customer=customer,
        currency="NGN",
        line_items=[
            {
                "type": InvoiceLineItem.Type.SUBSCRIPTION,
                "description": "Initial subscription payment",
                "amount_minor": 1000,
                "quantity": 1,
                "currency": "NGN",
            }
        ],
        subscription=subscription,
        metadata={
            "initial_subscription_checkout": True,
            "subscription_id": str(subscription.id),
        },
    )
    invoice = finalize_invoice(invoice=invoice)
    return merchant, environment, customer, subscription, invoice


def test_nomba_webhook_accepts_documented_signature():
    merchant, environment = _workspace()
    payload = _payload()
    timestamp = "2025-09-29T10:51:44Z"
    body = json.dumps(payload).encode()

    response = APIClient().post(
        f"/api/v1/payments/webhooks/nomba/{merchant.id}/{environment.mode}/",
        data=body,
        content_type="application/json",
        HTTP_NOMBA_SIGNATURE=_signature(payload, environment.webhook_secret, timestamp),
        HTTP_NOMBA_SIGNATURE_ALGORITHM="HmacSHA256",
        HTTP_NOMBA_SIGNATURE_VERSION="1.0.0",
        HTTP_NOMBA_TIMESTAMP=timestamp,
    )

    assert response.status_code == 200
    assert response.json()["received"] is True
    event = ProcessorEvent.objects.get()
    assert event.provider == "nomba"
    assert event.provider_event_id == payload["requestId"]
    assert event.event_type == "payment.succeeded"
    assert event.processor_reference == payload["data"]["transaction"]["transactionId"]


def test_nomba_webhook_get_probe_returns_ok_without_processing():
    merchant, environment = _workspace()

    response = APIClient().get(
        f"/api/v1/payments/webhooks/nomba/{merchant.id}/{environment.mode}/"
    )

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "provider": "nomba",
        "mode": environment.mode,
        "merchant_id": str(merchant.id),
        "accepts": ["POST"],
    }
    assert ProcessorEvent.objects.count() == 0


def test_nomba_success_webhook_attaches_token_and_activates_subscription():
    merchant, environment, customer, subscription, invoice = _subscription_workspace()
    payload = _payload()
    payload["data"]["orderMetaData"] = {
        "invoice_id": str(invoice.id),
        "subscription_id": str(subscription.id),
        "customer_id": str(customer.id),
    }
    payload["data"]["tokenizedCardData"] = {
        "tokenKey": "tok_nomba_saved_card",
        "cardType": "Visa",
        "cardPan": "411111******4242",
        "tokenExpirationDate": "12/30",
    }
    timestamp = "2025-09-29T10:51:44Z"
    body = json.dumps(payload).encode()

    response = APIClient().post(
        f"/api/v1/payments/webhooks/nomba/{merchant.id}/{environment.mode}/",
        data=body,
        content_type="application/json",
        HTTP_NOMBA_SIGNATURE=_signature(payload, environment.webhook_secret, timestamp),
        HTTP_NOMBA_TIMESTAMP=timestamp,
    )

    assert response.status_code == 200
    payment_method = PaymentMethod.objects.get(customer=customer)
    assert payment_method.provider == PaymentMethod.Provider.NOMBA
    assert payment_method.token == "tok_nomba_saved_card"
    assert payment_method.is_default is True
    assert payment_method.last4 == "4242"
    subscription.refresh_from_db()
    invoice.refresh_from_db()
    assert subscription.status == Subscription.Status.ACTIVE
    assert subscription.default_payment_method == payment_method
    assert invoice.status == Invoice.Status.PAID
    attempt = PaymentAttempt.objects.get(invoice=invoice)
    assert attempt.status == PaymentAttempt.Status.SUCCEEDED
    assert attempt.processor_reference == payload["data"]["transaction"]["transactionId"]
    assert attempt.amount_minor == 1000


def test_nomba_webhook_matches_pending_checkout_attempt_by_order_reference():
    merchant, environment, customer, subscription, invoice = _subscription_workspace()
    order_reference = "48933b85-b994-45b7-abf7-e46e007b3d4f"
    pending_attempt = PaymentAttempt.objects.create(
        merchant=merchant,
        environment=environment,
        invoice=invoice,
        attempt_number=1,
        status=PaymentAttempt.Status.PENDING,
        amount_minor=invoice.amount_due_minor,
        currency=invoice.currency,
        processor_reference=order_reference,
        idempotency_key=f"checkout:{invoice.id}",
        metadata={"source": "nomba_hosted_checkout"},
    )
    payload = _payload()
    payload["data"]["orderReference"] = order_reference
    payload["data"]["tokenizedCardData"] = {
        "tokenKey": "tok_nomba_saved_card",
        "cardType": "Visa",
        "cardPan": "411111******4242",
        "tokenExpirationDate": "12/30",
    }
    timestamp = "2025-09-29T10:51:44Z"
    body = json.dumps(payload).encode()

    response = APIClient().post(
        f"/api/v1/payments/webhooks/nomba/{merchant.id}/{environment.mode}/",
        data=body,
        content_type="application/json",
        HTTP_NOMBA_SIGNATURE=_signature(payload, environment.webhook_secret, timestamp),
        HTTP_NOMBA_TIMESTAMP=timestamp,
    )

    assert response.status_code == 200, response.content
    pending_attempt.refresh_from_db()
    subscription.refresh_from_db()
    assert pending_attempt.status == PaymentAttempt.Status.SUCCEEDED
    assert pending_attempt.processor_reference == payload["data"]["transaction"]["transactionId"]
    assert pending_attempt.payment_method == subscription.default_payment_method
    assert invoice.payment_attempts.count() == 1


@override_settings(NOMBA_WEBHOOK_SECRET="platform_nomba_webhook_secret")
def test_central_nomba_webhook_routes_by_nomba_account_id():
    merchant, environment = _workspace()
    payload = _payload()
    timestamp = "2025-09-29T10:51:44Z"
    body = json.dumps(payload).encode()

    response = APIClient().post(
        "/api/v1/payments/webhooks/nomba/",
        data=body,
        content_type="application/json",
        HTTP_NOMBA_SIGNATURE=_signature(
            payload,
            "platform_nomba_webhook_secret",
            timestamp,
        ),
        HTTP_NOMBA_SIGNATURE_ALGORITHM="HmacSHA256",
        HTTP_NOMBA_SIGNATURE_VERSION="1.0.0",
        HTTP_NOMBA_TIMESTAMP=timestamp,
    )

    assert response.status_code == 200
    assert response.json()["received"] is True
    event = ProcessorEvent.objects.get()
    assert event.merchant == merchant
    assert event.environment == environment
    assert event.provider == "nomba"


def test_central_nomba_webhook_get_probe_returns_ok_without_processing():
    response = APIClient().get("/api/v1/payments/webhooks/nomba/")

    assert response.status_code == 200
    assert response.json() == {
        "ok": True,
        "provider": "nomba",
        "mode": "platform",
        "merchant_id": "",
        "accepts": ["POST"],
    }
    assert ProcessorEvent.objects.count() == 0


@override_settings(NOMBA_WEBHOOK_SECRET="platform_nomba_webhook_secret")
def test_central_nomba_webhook_routes_by_order_metadata_invoice_id():
    merchant, environment, _customer, _subscription, invoice = _subscription_workspace()
    payload = _payload()
    payload["data"]["merchant"]["walletId"] = "unknown-wallet"
    payload["data"]["merchant"]["userId"] = "unknown-user"
    payload["data"]["orderMetaData"] = {
        "invoice_id": str(invoice.id),
        "subscription_id": str(invoice.subscription_id),
    }
    timestamp = "2025-09-29T10:51:44Z"
    body = json.dumps(payload).encode()

    response = APIClient().post(
        "/api/v1/payments/webhooks/nomba/",
        data=body,
        content_type="application/json",
        HTTP_NOMBA_SIGNATURE=_signature(
            payload,
            "platform_nomba_webhook_secret",
            timestamp,
        ),
        HTTP_NOMBA_SIGNATURE_ALGORITHM="HmacSHA256",
        HTTP_NOMBA_SIGNATURE_VERSION="1.0.0",
        HTTP_NOMBA_TIMESTAMP=timestamp,
    )

    assert response.status_code == 200, response.content
    event = ProcessorEvent.objects.get()
    assert event.merchant == merchant
    assert event.environment == environment


@override_settings(NOMBA_WEBHOOK_SECRET="platform_nomba_webhook_secret")
def test_central_nomba_webhook_rejects_unroutable_event():
    _workspace()
    payload = _payload()
    payload["data"]["merchant"]["walletId"] = "unknown-wallet"
    timestamp = "2025-09-29T10:51:44Z"
    body = json.dumps(payload).encode()

    response = APIClient().post(
        "/api/v1/payments/webhooks/nomba/",
        data=body,
        content_type="application/json",
        HTTP_NOMBA_SIGNATURE=_signature(
            payload,
            "platform_nomba_webhook_secret",
            timestamp,
        ),
        HTTP_NOMBA_TIMESTAMP=timestamp,
    )

    assert response.status_code == 404
    assert ProcessorEvent.objects.count() == 0


def test_nomba_webhook_rejects_tampered_signature():
    merchant, environment = _workspace()
    payload = _payload()
    timestamp = "2025-09-29T10:51:44Z"
    body = json.dumps(payload).encode()

    response = APIClient().post(
        f"/api/v1/payments/webhooks/nomba/{merchant.id}/{environment.mode}/",
        data=body,
        content_type="application/json",
        HTTP_NOMBA_SIGNATURE=(
            _signature(payload, environment.webhook_secret, timestamp)[:-2] + "xx"
        ),
        HTTP_NOMBA_TIMESTAMP=timestamp,
    )

    assert response.status_code == 401
    assert ProcessorEvent.objects.count() == 0


def test_nomba_webhook_rejects_missing_timestamp():
    merchant, environment = _workspace()
    payload = _payload()
    timestamp = "2025-09-29T10:51:44Z"
    body = json.dumps(payload).encode()

    response = APIClient().post(
        f"/api/v1/payments/webhooks/nomba/{merchant.id}/{environment.mode}/",
        data=body,
        content_type="application/json",
        HTTP_NOMBA_SIGNATURE=_signature(payload, environment.webhook_secret, timestamp),
    )

    assert response.status_code == 401
    assert ProcessorEvent.objects.count() == 0
