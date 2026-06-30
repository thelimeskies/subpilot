"""Tests for the cross-tenant Webhooks list + retry endpoints (S6)."""
from __future__ import annotations

from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant
from apps.audit.models import AuditLog
from apps.events.models import WebhookDelivery, WebhookEndpoint, WebhookEvent

pytestmark = pytest.mark.django_db


# --- Helpers ---------------------------------------------------------------


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def _seed_merchant(*, name: str, slug: str) -> tuple[Merchant, Environment]:
    m = Merchant.objects.create(name=name, slug=slug, default_currency="NGN")
    env = Environment.objects.create(merchant=m, mode=Environment.Mode.LIVE)
    return m, env


def _seed_endpoint(merchant: Merchant, env: Environment, *, url: str = "https://hooks.example/test") -> WebhookEndpoint:
    return WebhookEndpoint.objects.create(
        merchant=merchant,
        environment=env,
        url=url,
        description="test endpoint",
        enabled=True,
        event_filters=[],
    )


def _seed_event(
    merchant: Merchant,
    env: Environment,
    *,
    event_type: str = "subscription.activated",
    payload: dict | None = None,
) -> WebhookEvent:
    return WebhookEvent.objects.create(
        merchant=merchant,
        environment=env,
        event_type=event_type,
        aggregate_type="subscription",
        aggregate_id="sub_test",
        payload=payload or {"k": "v"},
    )


def _seed_delivery(
    merchant: Merchant,
    env: Environment,
    *,
    status: str = WebhookDelivery.Status.DELIVERED,
    attempt_count: int = 1,
    last_status_code: int = 200,
    event_type: str = "subscription.activated",
    endpoint_url: str = "https://hooks.example/test",
    next_attempt_at=None,
) -> WebhookDelivery:
    endpoint = _seed_endpoint(merchant, env, url=endpoint_url)
    event = _seed_event(merchant, env, event_type=event_type)
    return WebhookDelivery.objects.create(
        webhook_event=event,
        endpoint=endpoint,
        status=status,
        attempt_count=attempt_count,
        last_status_code=last_status_code,
        last_response_body="ok" if last_status_code < 400 else "boom",
        next_attempt_at=next_attempt_at,
        delivered_at=timezone.now() if status == WebhookDelivery.Status.DELIVERED else None,
    )


# --- Permission gate -------------------------------------------------------


def test_webhooks_list_requires_session():
    resp = APIClient().get("/api/v1/platform/webhooks/deliveries")
    assert resp.status_code in (401, 403)


def test_webhooks_list_blocks_merchant_user(django_user_model):
    user = django_user_model.objects.create(
        username="m@acme.test", email="m@acme.test", is_staff=True
    )
    user.set_password("Subpilot1!")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get("/api/v1/platform/webhooks/deliveries")
    assert resp.status_code in (401, 403)


def test_webhooks_retry_blocks_merchant_user(platform_admin_owner, django_user_model):
    m, env = _seed_merchant(name="Acme", slug="acme")
    delivery = _seed_delivery(m, env, status=WebhookDelivery.Status.FAILED, attempt_count=2)
    user = django_user_model.objects.create(
        username="m@acme.test", email="m@acme.test", is_staff=True
    )
    user.set_password("Subpilot1!")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(
        f"/api/v1/platform/webhooks/deliveries/{delivery.id}/retry",
        format="json",
    )
    assert resp.status_code in (401, 403)


def test_webhooks_health_blocks_merchant_user(django_user_model):
    user = django_user_model.objects.create(
        username="m@acme.test", email="m@acme.test", is_staff=True
    )
    user.set_password("Subpilot1!")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get("/api/v1/platform/webhooks/health")
    assert resp.status_code in (401, 403)


# --- List ------------------------------------------------------------------


def test_webhooks_list_returns_fe_shape(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    _seed_delivery(m, env, status=WebhookDelivery.Status.DELIVERED, attempt_count=1, last_status_code=200)
    _seed_delivery(
        m, env,
        status=WebhookDelivery.Status.FAILED,
        attempt_count=3,
        last_status_code=503,
        event_type="invoice.payment_failed",
        endpoint_url="https://hooks.example/fail",
        next_attempt_at=timezone.now() + timedelta(minutes=5),
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/webhooks/deliveries?page_size=20")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["total"] >= 2
    row = body["results"][0]
    for key in (
        "id", "rawId", "merchantId", "merchant", "event", "endpoint",
        "status", "rawStatus", "attempts", "lastAttempt", "responseCode",
    ):
        assert key in row, f"missing key {key!r}"
    statuses = {r["status"] for r in body["results"]}
    assert {"Delivered", "Retrying"} & statuses


def test_webhooks_list_filter_status_failed_returns_abandoned(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    _seed_delivery(m, env, status=WebhookDelivery.Status.DELIVERED)
    _seed_delivery(
        m, env,
        status=WebhookDelivery.Status.ABANDONED,
        attempt_count=7,
        last_status_code=500,
        event_type="dunning.abandoned",
        endpoint_url="https://hooks.example/abandon",
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/webhooks/deliveries?status=failed&page_size=20")
    body = resp.json()
    assert resp.status_code == 200
    assert body["results"]
    assert all(r["status"] == "Failed" for r in body["results"])


def test_webhooks_list_filter_status_retrying(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    _seed_delivery(m, env, status=WebhookDelivery.Status.DELIVERED)
    _seed_delivery(
        m, env,
        status=WebhookDelivery.Status.PENDING,
        attempt_count=1,
        last_status_code=0,
        event_type="invoice.payment_failed",
        endpoint_url="https://hooks.example/p",
        next_attempt_at=timezone.now() + timedelta(minutes=1),
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/webhooks/deliveries?status=retrying&page_size=20")
    body = resp.json()
    assert resp.status_code == 200
    assert body["results"]
    assert all(r["status"] == "Retrying" for r in body["results"])


def test_webhooks_list_filter_by_merchant(platform_admin_owner):
    m1, e1 = _seed_merchant(name="Acme", slug="acme")
    m2, e2 = _seed_merchant(name="Other", slug="other")
    _seed_delivery(m1, e1, status=WebhookDelivery.Status.DELIVERED)
    _seed_delivery(m2, e2, status=WebhookDelivery.Status.DELIVERED, endpoint_url="https://hooks.example/o")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/webhooks/deliveries?merchant_id={m1.id}&page_size=20")
    body = resp.json()
    assert resp.status_code == 200
    assert body["results"]
    assert all(r["merchantId"] == str(m1.id) for r in body["results"])


def test_webhooks_list_filter_by_event_type(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    _seed_delivery(m, env, event_type="subscription.activated")
    _seed_delivery(
        m, env,
        event_type="invoice.payment_failed",
        endpoint_url="https://hooks.example/x",
        status=WebhookDelivery.Status.FAILED,
        attempt_count=2,
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(
        "/api/v1/platform/webhooks/deliveries?event_type=invoice.payment_failed&page_size=20"
    )
    body = resp.json()
    assert resp.status_code == 200
    assert body["results"]
    assert all(r["event"] == "invoice.payment_failed" for r in body["results"])


# --- Retry -----------------------------------------------------------------


def test_retry_flips_status_and_audits(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    delivery = _seed_delivery(
        m, env,
        status=WebhookDelivery.Status.FAILED,
        attempt_count=2,
        last_status_code=503,
        next_attempt_at=timezone.now() + timedelta(minutes=15),
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/webhooks/deliveries/{delivery.id}/retry",
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == WebhookDelivery.Status.PENDING
    assert body["nextAttemptAt"]

    delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.PENDING
    assert delivery.next_attempt_at is not None

    log = AuditLog.objects.filter(
        action="platform.webhook.retry", target_id=str(delivery.id)
    ).first()
    assert log is not None
    assert log.actor_role == "platform_admin"


def test_retry_unknown_404(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/webhooks/deliveries/00000000-0000-0000-0000-000000000000/retry",
        format="json",
    )
    assert resp.status_code == 404
    assert resp.json()["ok"] is False


def test_retry_delivered_returns_409(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    delivery = _seed_delivery(m, env, status=WebhookDelivery.Status.DELIVERED)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/webhooks/deliveries/{delivery.id}/retry",
        format="json",
    )
    assert resp.status_code == 409
    assert resp.json()["ok"] is False


def test_retry_abandoned_succeeds(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    delivery = _seed_delivery(
        m, env,
        status=WebhookDelivery.Status.ABANDONED,
        attempt_count=7,
        last_status_code=500,
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/webhooks/deliveries/{delivery.id}/retry",
        format="json",
    )
    assert resp.status_code == 200, resp.content
    delivery.refresh_from_db()
    assert delivery.status == WebhookDelivery.Status.PENDING


# --- Health ----------------------------------------------------------------


def test_health_returns_counts(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    _seed_delivery(m, env, status=WebhookDelivery.Status.DELIVERED)
    _seed_delivery(
        m, env,
        status=WebhookDelivery.Status.FAILED,
        attempt_count=2,
        last_status_code=503,
        endpoint_url="https://hooks.example/f",
    )
    _seed_delivery(
        m, env,
        status=WebhookDelivery.Status.ABANDONED,
        attempt_count=7,
        last_status_code=500,
        endpoint_url="https://hooks.example/a",
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/webhooks/health")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["windowHours"] == 24
    assert body["delivered"] >= 1
    assert body["retrying"] >= 1
    assert body["failed"] >= 1
    assert body["total"] >= 3
    assert 0 <= body["successRate"] <= 100
