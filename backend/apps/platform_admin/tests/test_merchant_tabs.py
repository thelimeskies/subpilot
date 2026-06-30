"""Tests for the per-merchant tab endpoints (S13).

Covers:
* `GET /platform/merchants/<id>/subscriptions`
* `GET /platform/merchants/<id>/payments`
* `GET /platform/merchants/<id>/webhooks`
* `GET /platform/merchants/<id>/audit`

Plus 404 and isolation (cross-merchant scoping) per tab.
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant
from apps.audit.models import AuditLog
from apps.customers.models import Customer
from apps.events.models import WebhookDelivery, WebhookEndpoint, WebhookEvent
from apps.invoices.models import Invoice
from apps.payments.models import PaymentAttempt
from apps.subscriptions.models import Subscription

pytestmark = pytest.mark.django_db


# --- Helpers ---------------------------------------------------------------


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def _make_merchant(*, name: str, slug: str) -> Merchant:
    m = Merchant.objects.create(name=name, slug=slug, default_currency="NGN")
    Environment.objects.create(merchant=m, mode=Environment.Mode.TEST)
    return m


def _seed_payment(merchant: Merchant, *, amount_minor: int = 12_345) -> PaymentAttempt:
    env = Environment.objects.filter(merchant=merchant).first()
    customer = Customer.objects.create(
        merchant=merchant,
        environment=env,
        email=f"buyer-{amount_minor}@example.test",
        name=f"Buyer {amount_minor}",
    )
    invoice = Invoice.objects.create(
        merchant=merchant,
        environment=env,
        customer=customer,
        number=f"INV-{amount_minor}",
        status=Invoice.Status.OPEN,
        amount_due_minor=amount_minor,
        currency="NGN",
    )
    return PaymentAttempt.objects.create(
        merchant=merchant,
        environment=env,
        invoice=invoice,
        amount_minor=amount_minor,
        currency="NGN",
        status=PaymentAttempt.Status.SUCCEEDED,
        attempt_number=1,
    )


def _seed_webhook(merchant: Merchant) -> WebhookDelivery:
    env = Environment.objects.filter(merchant=merchant).first()
    endpoint = WebhookEndpoint.objects.create(
        merchant=merchant,
        environment=env,
        url="https://hooks.example.test/hook",
        enabled=True,
        event_filters=["*"],
    )
    event = WebhookEvent.objects.create(
        merchant=merchant, environment=env, event_type="invoice.paid"
    )
    return WebhookDelivery.objects.create(
        webhook_event=event,
        endpoint=endpoint,
        status=WebhookDelivery.Status.DELIVERED,
        attempt_count=1,
        last_status_code=200,
    )


def _seed_audit(merchant: Merchant, action: str = "platform.merchant.note") -> AuditLog:
    return AuditLog.objects.create(
        merchant=merchant,
        action=action,
        actor_label="ops@subpilot.dev",
        actor_role="platform_admin",
        target_type="merchant_note",
        target_id=str(merchant.id),
        metadata={"note": "seed"},
    )


# --- Auth gate -------------------------------------------------------------


@pytest.mark.parametrize(
    "suffix",
    ["subscriptions", "payments", "webhooks", "audit"],
)
def test_tab_endpoints_require_session(suffix):
    m = _make_merchant(name="Acme", slug="acme-anon")
    resp = APIClient().get(f"/api/v1/platform/merchants/{m.id}/{suffix}")
    assert resp.status_code in (401, 403)


@pytest.mark.parametrize(
    "suffix",
    ["subscriptions", "payments", "webhooks", "audit"],
)
def test_tab_endpoints_404_for_unknown_id(suffix, platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(
        f"/api/v1/platform/merchants/00000000-0000-0000-0000-000000000000/{suffix}"
    )
    assert resp.status_code == 404


# --- Subscriptions ---------------------------------------------------------


def test_subscriptions_returns_stats_and_rows(platform_admin_owner):
    m = _make_merchant(name="Subs Co", slug="subs-co")

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/merchants/{m.id}/subscriptions")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    for k in ("rows", "total", "page", "pageSize", "stats", "planMix"):
        assert k in body, f"missing key {k!r}"
    # Stats shape — every bucket present even with zero subs.
    stats = body["stats"]
    for k in (
        "active",
        "trialing",
        "paused",
        "pastDue",
        "canceledMtd",
        "topPlan",
        "arpu",
        "mrr",
        "currency",
    ):
        assert k in stats, f"missing stats key {k!r}"


def test_subscriptions_status_filter(platform_admin_owner, django_user_model):
    """Status filter restricts the rows page (zero subs → still 200)."""
    m = _make_merchant(name="Subs Filter", slug="subs-filter")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(
        f"/api/v1/platform/merchants/{m.id}/subscriptions?status=active"
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    # All returned rows (if any) must match the requested status.
    for row in body["rows"]:
        assert row["rawStatus"] == Subscription.Status.ACTIVE


# --- Payments --------------------------------------------------------------


def test_payments_returns_paginated_rows(platform_admin_owner):
    m = _make_merchant(name="Pay Co", slug="pay-co")
    _seed_payment(m, amount_minor=1000)
    _seed_payment(m, amount_minor=2000)

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/merchants/{m.id}/payments?pageSize=10")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["total"] == 2
    assert len(body["rows"]) == 2
    # Each row has the FE Payment shape.
    sample = body["rows"][0]
    for k in ("id", "merchant", "customer", "amount", "status", "method"):
        assert k in sample, f"missing payment key {k!r}"


def test_payments_isolation_between_merchants(platform_admin_owner):
    a = _make_merchant(name="A", slug="iso-a")
    b = _make_merchant(name="B", slug="iso-b")
    _seed_payment(a, amount_minor=100)
    _seed_payment(b, amount_minor=200)
    _seed_payment(b, amount_minor=300)

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp_a = client.get(f"/api/v1/platform/merchants/{a.id}/payments")
    assert resp_a.status_code == 200
    assert resp_a.json()["total"] == 1

    resp_b = client.get(f"/api/v1/platform/merchants/{b.id}/payments")
    assert resp_b.status_code == 200
    assert resp_b.json()["total"] == 2


# --- Webhooks --------------------------------------------------------------


def test_webhooks_returns_deliveries(platform_admin_owner):
    m = _make_merchant(name="Hook Co", slug="hook-co")
    _seed_webhook(m)

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/merchants/{m.id}/webhooks")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["total"] == 1
    row = body["rows"][0]
    assert row["event"] == "invoice.paid"
    assert row["status"] == "Delivered"
    assert row["responseCode"] == 200


def test_webhooks_isolation_between_merchants(platform_admin_owner):
    a = _make_merchant(name="A", slug="hook-iso-a")
    b = _make_merchant(name="B", slug="hook-iso-b")
    _seed_webhook(a)
    _seed_webhook(b)
    _seed_webhook(b)

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp_a = client.get(f"/api/v1/platform/merchants/{a.id}/webhooks")
    resp_b = client.get(f"/api/v1/platform/merchants/{b.id}/webhooks")
    assert resp_a.json()["total"] == 1
    assert resp_b.json()["total"] == 2


# --- Audit -----------------------------------------------------------------


def test_audit_returns_rows(platform_admin_owner):
    m = _make_merchant(name="Audit Co", slug="audit-co")
    _seed_audit(m, action="platform.merchant.suspend")
    _seed_audit(m, action="platform.merchant.note")

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/merchants/{m.id}/audit")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["total"] == 2
    sample = body["rows"][0]
    for k in ("id", "action", "actor", "occurredAt"):
        assert k in sample, f"missing audit key {k!r}"


def test_audit_action_filter(platform_admin_owner):
    m = _make_merchant(name="Audit Filter", slug="audit-filter")
    _seed_audit(m, action="platform.merchant.suspend")
    _seed_audit(m, action="platform.merchant.note")
    _seed_audit(m, action="platform.merchant.note")

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/merchants/{m.id}/audit?action=note")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2  # Only the two note rows
    for row in body["rows"]:
        assert "note" in row["action"]


def test_audit_isolation_between_merchants(platform_admin_owner):
    a = _make_merchant(name="A", slug="audit-iso-a")
    b = _make_merchant(name="B", slug="audit-iso-b")
    _seed_audit(a)
    _seed_audit(b)
    _seed_audit(b)

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    assert client.get(f"/api/v1/platform/merchants/{a.id}/audit").json()["total"] == 1
    assert client.get(f"/api/v1/platform/merchants/{b.id}/audit").json()["total"] == 2
