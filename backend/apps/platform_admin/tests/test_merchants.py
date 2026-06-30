"""Tests for the cross-tenant merchants list endpoint."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant, Role, TeamMember

pytestmark = pytest.mark.django_db


# --- Helpers -----------------------------------------------------------


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def _make_merchant(
    *,
    name: str,
    slug: str,
    status: str = Merchant.Status.ACTIVE,
    industry: str = "",
) -> Merchant:
    return Merchant.objects.create(
        name=name, slug=slug, status=status, industry=industry, default_currency="NGN"
    )


def _attach_owner(merchant: Merchant, *, email: str, name: str, django_user_model) -> None:
    user = django_user_model.objects.create(
        username=email, email=email, display_name=name, is_active=True
    )
    user.set_password("Subpilot1!")
    user.save()
    TeamMember.objects.create(
        merchant=merchant, user=user, role=Role.OWNER, status=TeamMember.Status.ACTIVE
    )


def _add_env(merchant: Merchant, *, mode: str) -> Environment:
    return Environment.objects.create(merchant=merchant, mode=mode)


# --- Permission gate ---------------------------------------------------


def test_merchants_requires_session():
    resp = APIClient().get("/api/v1/platform/merchants")
    assert resp.status_code in (401, 403)


def test_merchants_blocks_merchant_user(django_user_model):
    user = django_user_model.objects.create(
        username="merchant@acme.test", email="merchant@acme.test", is_staff=True
    )
    user.set_password("Subpilot1!")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get("/api/v1/platform/merchants")
    assert resp.status_code in (401, 403)


# --- Happy path --------------------------------------------------------


def test_merchants_returns_fe_shape(platform_admin_owner, django_user_model):
    m1 = _make_merchant(name="Acme Co", slug="acme-co")
    _attach_owner(m1, email="ada@acme.test", name="Ada Okafor", django_user_model=django_user_model)
    _add_env(m1, mode=Environment.Mode.LIVE)

    m2 = _make_merchant(name="FitPlus", slug="fitplus", industry="fitness")
    _add_env(m2, mode=Environment.Mode.TEST)

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get("/api/v1/platform/merchants?page_size=10")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["total"] >= 2
    by_id = {r["id"]: r for r in body["results"]}
    row = by_id[str(m1.id)]
    for key in (
        "id", "name", "owner", "ownerEmail", "plan", "mrr", "status",
        "failedInvoices", "recoveryRate", "environment", "createdAt",
        "region", "monthlyVolume", "activeSubscriptions", "raw",
    ):
        assert key in row, f"missing key {key!r}"
    assert row["name"] == "Acme Co"
    assert row["owner"] == "Ada Okafor"
    assert row["ownerEmail"] == "ada@acme.test"
    assert row["environment"] == "Live"
    assert row["status"] in {"Healthy", "At risk", "Suspended"}
    # Industry-derived region
    assert "Nigeria · Fitness" in by_id[str(m2.id)]["region"]


def test_merchants_search_filters_by_name(platform_admin_owner):
    _make_merchant(name="Apple Pay Co", slug="apple-pay")
    _make_merchant(name="Banana Bread", slug="banana-bread")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get("/api/v1/platform/merchants?q=apple")
    body = resp.json()
    assert resp.status_code == 200
    assert any("Apple" in r["name"] for r in body["results"])
    assert all("Banana" not in r["name"] for r in body["results"])


def test_merchants_filter_by_suspended(platform_admin_owner):
    _make_merchant(name="Live Co", slug="live-co", status=Merchant.Status.ACTIVE)
    _make_merchant(name="Down Co", slug="down-co", status=Merchant.Status.SUSPENDED)
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get("/api/v1/platform/merchants?status=suspended")
    body = resp.json()
    assert resp.status_code == 200
    names = [r["name"] for r in body["results"]]
    assert "Down Co" in names
    assert "Live Co" not in names


def test_merchants_pagination(platform_admin_owner):
    for i in range(5):
        _make_merchant(name=f"Merchant {i}", slug=f"merchant-{i}")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get("/api/v1/platform/merchants?page=1&page_size=2")
    body = resp.json()
    assert resp.status_code == 200
    assert body["page"] == 1
    assert body["pageSize"] == 2
    assert len(body["results"]) == 2
    assert body["total"] >= 5


def test_merchants_empty_when_no_data(platform_admin_owner):
    Merchant.objects.all().delete()
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get("/api/v1/platform/merchants")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["total"] == 0
    assert body["results"] == []
