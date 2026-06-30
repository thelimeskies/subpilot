from __future__ import annotations

import base64
import hashlib
import hmac
import json

import pytest
from django.test import override_settings
from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant
from apps.payments.models import ProcessorEvent

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
    environment.save(update_fields=["webhook_secret_encrypted", "updated_at"])
    return merchant, environment


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
