"""Tests for the cross-tenant Payments list + refund endpoints (S5)."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant
from apps.audit.models import AuditLog
from apps.customers.models import Customer, PaymentMethod
from apps.invoices.models import Invoice
from apps.payments.models import BalanceTransaction, PaymentAttempt

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


def _seed_payment(
    merchant: Merchant,
    env: Environment,
    *,
    status: str = PaymentAttempt.Status.SUCCEEDED,
    attempt_number: int = 1,
    amount_minor: int = 5_000_00,
    customer_email: str = "buyer@example.com",
    failure_code: str = "",
    failure_message: str = "",
    provider: str = "nomba",
    invoice_metadata: dict | None = None,
) -> PaymentAttempt:
    customer = Customer.objects.create(
        merchant=merchant, environment=env, email=customer_email, name=customer_email
    )
    method = PaymentMethod.objects.create(
        merchant=merchant,
        environment=env,
        customer=customer,
        provider=provider,
        brand="Visa",
        last4="4242",
    )
    invoice = Invoice.objects.create(
        merchant=merchant,
        environment=env,
        customer=customer,
        number=f"INV-{merchant.slug}-{attempt_number:04d}",
        status=Invoice.Status.OPEN,
        subtotal_minor=amount_minor,
        total_minor=amount_minor,
        amount_due_minor=amount_minor,
        currency="NGN",
        metadata=invoice_metadata or {},
    )
    return PaymentAttempt.objects.create(
        merchant=merchant,
        environment=env,
        invoice=invoice,
        payment_method=method,
        attempt_number=attempt_number,
        status=status,
        amount_minor=amount_minor,
        currency="NGN",
        failure_code=failure_code,
        failure_message=failure_message,
        processor_reference=f"ref_{merchant.slug}_{attempt_number}",
    )


# --- Permission gate -------------------------------------------------------


def test_payments_list_requires_session():
    resp = APIClient().get("/api/v1/platform/payments")
    assert resp.status_code in (401, 403)


def test_payments_list_blocks_merchant_user(django_user_model):
    user = django_user_model.objects.create(
        username="m@acme.test", email="m@acme.test", is_staff=True
    )
    user.set_password("Subpilot1!")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get("/api/v1/platform/payments")
    assert resp.status_code in (401, 403)


def test_payments_refund_blocks_merchant_user(platform_admin_owner, django_user_model):
    m, env = _seed_merchant(name="Acme", slug="acme")
    attempt = _seed_payment(m, env)
    user = django_user_model.objects.create(
        username="m@acme.test", email="m@acme.test", is_staff=True
    )
    user.set_password("Subpilot1!")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(
        f"/api/v1/platform/payments/{attempt.id}/refund",
        data={"reason": "x"},
        format="json",
    )
    assert resp.status_code in (401, 403)


# --- List ------------------------------------------------------------------


def test_payments_list_returns_fe_shape(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    _seed_payment(m, env, status=PaymentAttempt.Status.SUCCEEDED, attempt_number=1)
    _seed_payment(
        m,
        env,
        status=PaymentAttempt.Status.FAILED,
        attempt_number=2,
        amount_minor=1_000_00,
        failure_code="card_declined",
        failure_message="Insufficient funds",
        customer_email="failed@example.com",
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get("/api/v1/platform/payments?page_size=20")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["total"] >= 2
    row = body["results"][0]
    for key in (
        "id", "rawId", "merchantId", "merchant", "customer", "amount",
        "status", "rawStatus", "method", "occurredAt", "gateway", "raw",
    ):
        assert key in row, f"missing key {key!r}"
    statuses = {r["status"] for r in body["results"]}
    assert {"Captured", "Failed"} & statuses


def test_payments_list_filters_by_status(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    _seed_payment(m, env, status=PaymentAttempt.Status.SUCCEEDED, attempt_number=1)
    _seed_payment(
        m,
        env,
        status=PaymentAttempt.Status.FAILED,
        attempt_number=2,
        customer_email="bad@example.com",
        failure_code="card_declined",
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get("/api/v1/platform/payments?status=failed&page_size=20")
    body = resp.json()
    assert resp.status_code == 200
    assert body["results"]
    assert all(r["status"] == "Failed" for r in body["results"])


def test_payments_list_filters_by_merchant(platform_admin_owner):
    m1, e1 = _seed_merchant(name="Acme", slug="acme")
    m2, e2 = _seed_merchant(name="Other", slug="other")
    _seed_payment(m1, e1, attempt_number=1, customer_email="a1@example.com")
    _seed_payment(m2, e2, attempt_number=1, customer_email="b1@example.com")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get(f"/api/v1/platform/payments?merchant_id={m1.id}&page_size=20")
    body = resp.json()
    assert resp.status_code == 200
    assert body["results"]
    assert all(r["merchantId"] == str(m1.id) for r in body["results"])


def test_payments_list_recovered_status_for_attempt_two(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    _seed_payment(
        m, env, status=PaymentAttempt.Status.SUCCEEDED, attempt_number=2,
        customer_email="rec@example.com",
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/payments?page_size=20")
    body = resp.json()
    assert resp.status_code == 200
    assert any(r["status"] == "Recovered" for r in body["results"])


def test_payments_list_q_search(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    _seed_payment(m, env, customer_email="needle-found@example.com", attempt_number=1)
    _seed_payment(m, env, customer_email="other@example.com", attempt_number=2,
                  status=PaymentAttempt.Status.FAILED)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/payments?q=needle-found")
    body = resp.json()
    assert resp.status_code == 200
    assert body["results"]
    assert all("needle-found" in r["customer"] for r in body["results"])


# --- Refund ----------------------------------------------------------------


def test_refund_payment_marks_invoice_metadata_and_audits(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    attempt = _seed_payment(m, env, status=PaymentAttempt.Status.SUCCEEDED)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.post(
        f"/api/v1/platform/payments/{attempt.id}/refund",
        data={"reason": "duplicate charge", "note": "tier 1 escalation"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == "refunded"
    assert body["refundedAt"]

    attempt.invoice.refresh_from_db()
    meta = attempt.invoice.metadata
    assert meta.get("refunded_at")
    assert meta.get("refund_reason") == "duplicate charge"
    tx = BalanceTransaction.objects.get(
        payment_attempt=attempt,
        type=BalanceTransaction.Type.REFUND,
    )
    assert tx.signed_amount_minor == -attempt.amount_minor
    assert tx.merchant_id == attempt.merchant_id
    assert tx.environment_id == attempt.environment_id

    log = AuditLog.objects.filter(
        action="platform.payment.refund", target_id=str(attempt.id)
    ).first()
    assert log is not None
    assert log.actor_role == "platform_admin"


def test_refund_unknown_payment_404(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/payments/00000000-0000-0000-0000-000000000000/refund",
        data={"reason": "ghost"},
        format="json",
    )
    assert resp.status_code == 404
    assert resp.json()["ok"] is False


def test_refund_failed_payment_returns_409(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    attempt = _seed_payment(
        m, env, status=PaymentAttempt.Status.FAILED, failure_code="card_declined"
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/payments/{attempt.id}/refund",
        data={"reason": "no"},
        format="json",
    )
    assert resp.status_code == 409
    assert resp.json()["ok"] is False


def test_refund_idempotent(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    attempt = _seed_payment(m, env, status=PaymentAttempt.Status.SUCCEEDED)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp1 = client.post(
        f"/api/v1/platform/payments/{attempt.id}/refund",
        data={"reason": "first"},
        format="json",
    )
    assert resp1.status_code == 200
    first_at = resp1.json()["refundedAt"]
    # Second call with different reason still returns 200; refunded_at preserved.
    resp2 = client.post(
        f"/api/v1/platform/payments/{attempt.id}/refund",
        data={"reason": "second"},
        format="json",
    )
    assert resp2.status_code == 200
    assert resp2.json()["refundedAt"] == first_at
    # Two audit rows recorded (one per attempt).
    assert (
        AuditLog.objects.filter(
            action="platform.payment.refund", target_id=str(attempt.id)
        ).count()
        == 2
    )
