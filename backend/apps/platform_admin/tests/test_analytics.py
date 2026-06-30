"""Tests for the platform-admin analytics endpoint (S11)."""
from __future__ import annotations

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.accounts.models import Merchant, Role, TeamMember, User
from apps.audit.models import AuditLog
from apps.platform_admin.selectors.analytics import (
    DEFAULT_RANGE,
    RANGE_KEYS,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/platform/analytics"


# --- Helpers ---------------------------------------------------------------


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def _seed_merchant_user() -> User:
    m = Merchant.objects.create(name="Acme", slug="acme-analytics", default_currency="NGN")
    user = User.objects.create(email="owner@acme-analytics.test", is_active=True)
    user.set_password("Subpilot1!")
    user.save()
    TeamMember.objects.create(merchant=m, user=user, role=Role.OWNER)
    return user


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()


# --- Auth / RBAC -----------------------------------------------------------


def test_analytics_requires_session():
    client = APIClient()
    resp = client.get(URL)
    assert resp.status_code in (401, 403)


def test_analytics_blocks_merchant_user():
    _seed_merchant_user()
    client = APIClient()
    client.post(
        "/api/v1/auth/sign-in",
        data={"email": "owner@acme-analytics.test", "password": "Subpilot1!"},
        format="json",
    )
    resp = client.get(URL)
    assert resp.status_code in (401, 403)


# --- GET -------------------------------------------------------------------


def test_analytics_get_returns_fe_shape(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get(URL)
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    payload = body["analytics"]
    # Top-level shape
    for key in (
        "range",
        "revenueSeries",
        "planRevenue",
        "regionRevenue",
        "retentionCohorts",
        "acquisitionFunnel",
        "paymentMethodMix",
        "recoveryFunnel",
        "topMerchantsByRevenue",
    ):
        assert key in payload, f"missing {key}"
    assert payload["range"] == DEFAULT_RANGE

    # revenueSeries shape
    assert isinstance(payload["revenueSeries"], list) and len(payload["revenueSeries"]) == 12
    rev = payload["revenueSeries"][0]
    for key in ("month", "mrr", "newMrr", "expansionMrr", "churnMrr", "gmv", "activeSubs"):
        assert key in rev, f"revenueSeries missing {key}"

    # planRevenue shape
    assert isinstance(payload["planRevenue"], list) and len(payload["planRevenue"]) >= 1
    plan = payload["planRevenue"][0]
    for key in ("plan", "merchants", "activeSubs", "mrr", "share", "arpu", "churn"):
        assert key in plan, f"planRevenue missing {key}"

    # regionRevenue shape
    assert isinstance(payload["regionRevenue"], list) and len(payload["regionRevenue"]) >= 1
    region = payload["regionRevenue"][0]
    for key in ("region", "mrr", "share", "merchants", "growth", "topAdapter"):
        assert key in region, f"regionRevenue missing {key}"

    # retentionCohorts shape
    assert isinstance(payload["retentionCohorts"], list) and len(payload["retentionCohorts"]) == 6
    cohort = payload["retentionCohorts"][0]
    for key in ("cohort", "size", "retention"):
        assert key in cohort, f"retentionCohorts missing {key}"
    assert isinstance(cohort["retention"], list) and len(cohort["retention"]) == 6

    # acquisitionFunnel shape
    assert isinstance(payload["acquisitionFunnel"], list) and len(payload["acquisitionFunnel"]) == 5
    step = payload["acquisitionFunnel"][0]
    assert "label" in step and "count" in step

    # paymentMethodMix shape
    assert isinstance(payload["paymentMethodMix"], list) and len(payload["paymentMethodMix"]) >= 4
    method = payload["paymentMethodMix"][0]
    for key in ("method", "share", "successRate", "avgTicket"):
        assert key in method, f"paymentMethodMix missing {key}"

    # recoveryFunnel shape
    rf = payload["recoveryFunnel"]
    assert isinstance(rf, dict)
    for key in (
        "failedThisMonth",
        "recovered",
        "pending",
        "lost",
        "recoveryRate",
        "recoveredMrr",
        "byChannel",
    ):
        assert key in rf, f"recoveryFunnel missing {key}"
    assert isinstance(rf["byChannel"], list) and len(rf["byChannel"]) == 4

    # topMerchantsByRevenue shape (may be empty when no subs exist)
    assert isinstance(payload["topMerchantsByRevenue"], list)


def test_analytics_get_range_filter(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    for range_key, expected_points in (("3m", 3), ("6m", 6), ("12m", 12)):
        resp = client.get(URL, {"range": range_key})
        assert resp.status_code == 200, resp.content
        payload = resp.json()["analytics"]
        assert payload["range"] == range_key
        assert len(payload["revenueSeries"]) == expected_points


def test_analytics_get_range_invalid_falls_back_to_default(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get(URL, {"range": "99x"})
    assert resp.status_code == 200
    payload = resp.json()["analytics"]
    assert payload["range"] == DEFAULT_RANGE


def test_analytics_open_to_any_admin_role(platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_operator.email)

    resp = client.get(URL)
    assert resp.status_code == 200


def test_analytics_uses_cache_on_second_read(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    AuditLog.objects.all().delete()
    # First call computes + audits.
    resp1 = client.get(URL)
    assert resp1.status_code == 200
    audits_after_first = AuditLog.objects.filter(action="platform.analytics.refreshed").count()
    assert audits_after_first == 1
    # Second call served from cache — no new audit row.
    resp2 = client.get(URL)
    assert resp2.status_code == 200
    audits_after_second = AuditLog.objects.filter(action="platform.analytics.refreshed").count()
    assert audits_after_second == 1
    # And the payload is byte-stable.
    assert resp1.json() == resp2.json()


def test_analytics_refresh_bypasses_cache(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    AuditLog.objects.all().delete()
    resp1 = client.get(URL)
    assert resp1.status_code == 200
    assert AuditLog.objects.filter(action="platform.analytics.refreshed").count() == 1

    resp2 = client.get(URL, {"refresh": "true"})
    assert resp2.status_code == 200
    # Force-refresh adds another audit row.
    assert AuditLog.objects.filter(action="platform.analytics.refreshed").count() == 2


def test_analytics_cache_keys_independent_per_range(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    AuditLog.objects.all().delete()
    for range_key in RANGE_KEYS:
        resp = client.get(URL, {"range": range_key})
        assert resp.status_code == 200
    # Three distinct ranges → three refresh audit rows.
    audits = AuditLog.objects.filter(action="platform.analytics.refreshed").count()
    assert audits == len(RANGE_KEYS)
