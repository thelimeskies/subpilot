"""Tests for the cross-tenant Merchant detail + write actions (S4)."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant, Role, TeamMember
from apps.audit.models import AuditLog

from apps.platform_admin.models import PlatformMerchantNote

pytestmark = pytest.mark.django_db


# --- Helpers -----------------------------------------------------------


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def _make_merchant(*, name: str, slug: str, status: str = Merchant.Status.ACTIVE) -> Merchant:
    return Merchant.objects.create(
        name=name, slug=slug, status=status, default_currency="NGN"
    )


def _attach_owner(merchant: Merchant, *, email: str, name: str, django_user_model):
    user = django_user_model.objects.create(
        username=email, email=email, display_name=name, is_active=True
    )
    user.set_password("Subpilot1!")
    user.save()
    TeamMember.objects.create(
        merchant=merchant, user=user, role=Role.OWNER, status=TeamMember.Status.ACTIVE
    )
    return user


# --- Permission gate ----------------------------------------------------


def test_detail_requires_session():
    m = _make_merchant(name="Acme", slug="acme")
    resp = APIClient().get(f"/api/v1/platform/merchants/{m.id}")
    assert resp.status_code in (401, 403)


def test_detail_blocks_merchant_user(django_user_model):
    m = _make_merchant(name="Acme", slug="acme")
    user = django_user_model.objects.create(
        username="x@acme.test", email="x@acme.test", is_staff=True
    )
    user.set_password("Subpilot1!")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get(f"/api/v1/platform/merchants/{m.id}")
    assert resp.status_code in (401, 403)


# --- Detail GET ---------------------------------------------------------


def test_detail_returns_fe_shape(platform_admin_owner, django_user_model):
    m = _make_merchant(name="Acme Hub", slug="acme-hub")
    _attach_owner(m, email="owner@acme.test", name="Ada Owner", django_user_model=django_user_model)
    Environment.objects.create(merchant=m, mode=Environment.Mode.LIVE)
    Environment.objects.create(merchant=m, mode=Environment.Mode.TEST)

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/merchants/{m.id}")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    detail = body["merchant"]
    for key in (
        "id", "name", "slug", "owner", "ownerEmail", "plan", "mrr", "status",
        "failedInvoices", "recoveryRate", "environment", "createdAt", "region",
        "monthlyVolume", "activeSubscriptions", "subscriptionStats",
        "environments", "recentPayments", "recentAudit", "kyc", "notes", "raw",
    ):
        assert key in detail, f"missing detail key {key!r}"
    assert detail["id"] == str(m.id)
    assert detail["name"] == "Acme Hub"
    assert detail["owner"] == "Ada Owner"
    assert detail["environment"] == "Live"
    # Subs stats has all the buckets.
    for k in ("active", "trialing", "paused", "pastDue", "canceledMtd", "churnRate", "topPlan", "arpu"):
        assert k in detail["subscriptionStats"], k
    # Both envs surfaced.
    assert len(detail["environments"]) == 2


def test_detail_hydrates_kyc_from_onboarding_metadata(platform_admin_owner, django_user_model):
    m = _make_merchant(name="Zylodo Tech", slug="zylodo-tech")
    m.metadata = {
        "kyc": {
            "director_id_name": "passport.jpg",
            "director_id_data": "data:image/jpeg;base64,passport",
            "address_proof_name": "utility.pdf",
            "address_proof_data": "data:application/pdf;base64,utility",
            "submitted_at": "2026-07-02T01:37:35.230455+00:00",
        }
    }
    m.save(update_fields=["metadata", "updated_at"])
    _attach_owner(m, email="owner@zylodo.test", name="Asikhalaye Samuel", django_user_model=django_user_model)
    Environment.objects.create(merchant=m, mode=Environment.Mode.LIVE)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get(f"/api/v1/platform/merchants/{m.id}")

    assert resp.status_code == 200, resp.content
    kyc = resp.json()["merchant"]["kyc"]
    assert kyc["status"] == "In review"
    assert kyc["submittedAt"].startswith("2026-07-02T01:37:35")
    assert kyc["documents"][0]["fileName"] == "passport.jpg"
    assert kyc["documents"][0]["dataUrl"] == "data:image/jpeg;base64,passport"


def test_detail_404_for_unknown_id(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/merchants/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    body = resp.json()
    assert body["ok"] is False


# --- Suspend / Reactivate ----------------------------------------------


def test_suspend_changes_status_and_audits(platform_admin_owner):
    m = _make_merchant(name="Acme", slug="acme")
    before = AuditLog.objects.filter(action="platform.merchant.suspend").count()

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/merchants/{m.id}/suspend",
        data={"reason": "risk", "note": "high chargeback"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == Merchant.Status.SUSPENDED
    m.refresh_from_db()
    assert m.status == Merchant.Status.SUSPENDED
    assert AuditLog.objects.filter(action="platform.merchant.suspend").count() == before + 1


def test_reactivate_changes_status_and_audits(platform_admin_owner):
    m = _make_merchant(name="Acme", slug="acme", status=Merchant.Status.SUSPENDED)
    before = AuditLog.objects.filter(action="platform.merchant.reactivate").count()

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/merchants/{m.id}/reactivate",
        data={"note": "compliance cleared"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == Merchant.Status.ACTIVE
    m.refresh_from_db()
    assert m.status == Merchant.Status.ACTIVE
    assert AuditLog.objects.filter(action="platform.merchant.reactivate").count() == before + 1


def test_reactivate_closed_returns_409(platform_admin_owner):
    m = _make_merchant(name="Closed Co", slug="closed-co", status=Merchant.Status.CLOSED)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(f"/api/v1/platform/merchants/{m.id}/reactivate", data={}, format="json")
    assert resp.status_code == 409
    body = resp.json()
    assert body["ok"] is False


# --- Notes --------------------------------------------------------------


def test_add_note_creates_row_and_audits(platform_admin_owner):
    m = _make_merchant(name="Acme", slug="acme")
    before = AuditLog.objects.filter(action="platform.merchant.note").count()

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/merchants/{m.id}/notes",
        data={"body": "first internal note", "visibility": "ops"},
        format="json",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["noteId"]
    assert PlatformMerchantNote.objects.filter(merchant=m, body="first internal note").exists()
    assert AuditLog.objects.filter(action="platform.merchant.note").count() == before + 1


def test_add_note_rejects_empty_body(platform_admin_owner):
    m = _make_merchant(name="Acme", slug="acme")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/merchants/{m.id}/notes",
        data={"body": "   "},
        format="json",
    )
    assert resp.status_code == 400


def test_suspend_unknown_merchant_returns_404(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/merchants/00000000-0000-0000-0000-000000000000/suspend",
        data={},
        format="json",
    )
    assert resp.status_code == 404
