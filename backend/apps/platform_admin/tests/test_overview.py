"""Tests for the cross-tenant overview endpoint and cache wrapper."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from django.core.cache import cache
from rest_framework.test import APIClient

from apps.platform_admin.services.overview import (
    _CACHE_KEY,
    get_or_refresh_overview,
    refresh_platform_overview,
)

pytestmark = pytest.mark.django_db


# --- Helpers -----------------------------------------------------------


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.delete(_CACHE_KEY)
    yield
    cache.delete(_CACHE_KEY)


# --- Permission gate ----------------------------------------------------


def test_overview_requires_session():
    client = APIClient()
    resp = client.get("/api/v1/platform/overview")
    assert resp.status_code in (401, 403)


def test_overview_blocks_merchant_user(django_user_model):
    """A logged-in merchant user — even is_staff — must not see the platform overview."""
    user = django_user_model.objects.create(
        username="merchant@acme.test",
        email="merchant@acme.test",
        is_staff=True,
    )
    user.set_password("Subpilot1!")
    user.save()

    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get("/api/v1/platform/overview")
    assert resp.status_code in (401, 403), resp.content


# --- Happy path ---------------------------------------------------------


def test_overview_returns_fe_shape(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get("/api/v1/platform/overview")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    stats = body["stats"]
    # All FE-shape keys present.
    for key in (
        "liveMerchants",
        "liveMerchantsDelta",
        "mrr",
        "mrrDelta",
        "revenueAtRisk",
        "revenueAtRiskDelta",
        "webhookHealth",
        "webhookHealthDelta",
        "recoveredThisMonth",
        "recoveryRate",
        "raw",
    ):
        assert key in stats, f"missing key {key!r}: {stats}"

    # Raw bag carries minor units / floats for power callers.
    assert "mrrMinor" in stats["raw"]
    assert "collectedThisMonthMinor" in stats["raw"]
    assert "netRevenueThisMonthMinor" in stats["raw"]
    assert "currency" in stats["raw"]


# --- Cache behaviour ----------------------------------------------------


def test_overview_uses_cache_on_second_call(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    with patch(
        "apps.platform_admin.services.overview.platform_overview"
    ) as mock_compute:
        mock_compute.side_effect = [
            _make_snapshot(live=7),
            _make_snapshot(live=99),  # would be returned if cache missed
        ]
        first = client.get("/api/v1/platform/overview").json()
        second = client.get("/api/v1/platform/overview").json()

    assert first["stats"]["liveMerchants"] == 7
    # Second call MUST come from cache and ignore the second mock value.
    assert second["stats"]["liveMerchants"] == 7
    assert mock_compute.call_count == 1


def test_overview_refresh_query_param_bypasses_cache(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    with patch(
        "apps.platform_admin.services.overview.platform_overview"
    ) as mock_compute:
        mock_compute.side_effect = [
            _make_snapshot(live=3),
            _make_snapshot(live=10),
        ]
        client.get("/api/v1/platform/overview")
        forced = client.get("/api/v1/platform/overview?refresh=true").json()

    assert forced["stats"]["liveMerchants"] == 10
    assert mock_compute.call_count == 2


# --- Direct service tests ----------------------------------------------


def test_refresh_writes_audit_log():
    from apps.audit.models import AuditLog

    before = AuditLog.objects.filter(action="platform.overview.refreshed").count()
    refresh_platform_overview(actor_label="ops@subpilot.dev")
    after = AuditLog.objects.filter(action="platform.overview.refreshed").count()
    assert after == before + 1


def test_get_or_refresh_caches_payload():
    payload = get_or_refresh_overview(actor_label="test")
    assert "raw" in payload
    cached = cache.get(_CACHE_KEY)
    assert cached == payload


# --- Helpers ------------------------------------------------------------


def _make_snapshot(*, live: int):
    from apps.platform_admin.selectors.overview import PlatformOverview

    return PlatformOverview(
        live_merchants=live,
        live_merchants_delta=0,
        mrr_minor=0,
        mrr_delta_pct=0.0,
        revenue_at_risk_minor=0,
        failed_invoice_count=0,
        webhook_health_pct=100.0,
        webhook_retries_in_flight=0,
        recovered_this_month_minor=0,
        collected_this_month_minor=0,
        net_revenue_this_month_minor=0,
        recovery_rate_pct=0.0,
        currency="NGN",
    )
