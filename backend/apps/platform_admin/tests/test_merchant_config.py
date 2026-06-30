"""Tests for the per-merchant config endpoint + service (S13).

Covers:
* GET returns catalog defaults when no row exists.
* GET reflects sparse overrides once set.
* PATCH merges feature_flags / limits / retry_policy and emits an audit log row.
* PATCH validates the flag key against the catalog.
* PATCH as Operator returns 403 (Owner-only).
* PATCH as Owner is accepted (status != 403).
"""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Environment, Merchant
from apps.audit.models import AuditLog

from apps.platform_admin.feature_flags import FEATURE_FLAGS
from apps.platform_admin.models import MerchantConfig

pytestmark = pytest.mark.django_db


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def _make_merchant(slug: str = "cfg-merchant") -> Merchant:
    m = Merchant.objects.create(name="Config Co", slug=slug, default_currency="NGN")
    Environment.objects.create(merchant=m, mode=Environment.Mode.TEST)
    return m


# --- GET -------------------------------------------------------------------


def test_config_get_returns_catalog_defaults_without_row(platform_admin_owner):
    m = _make_merchant("cfg-default")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/merchants/{m.id}/config")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    cfg = body["config"]
    # Bundle shape
    for k in ("limits", "retryPolicy", "featureFlags", "webhookEndpoints", "catalog"):
        assert k in cfg, f"missing config key {k!r}"
    # Every catalog flag is surfaced with its default.
    flag_keys = {f["key"] for f in cfg["featureFlags"]}
    assert flag_keys == set(FEATURE_FLAGS.keys())
    for flag in cfg["featureFlags"]:
        spec = FEATURE_FLAGS[flag["key"]]
        assert flag["enabled"] == spec["default"]
        assert flag["default"] == spec["default"]


def test_config_get_404_for_unknown(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(
        "/api/v1/platform/merchants/00000000-0000-0000-0000-000000000000/config"
    )
    assert resp.status_code == 404


# --- PATCH happy path ------------------------------------------------------


def test_config_patch_merges_flags_and_audits(platform_admin_owner):
    m = _make_merchant("cfg-patch-flags")
    before = AuditLog.objects.filter(action="platform.merchant.config.update").count()

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        f"/api/v1/platform/merchants/{m.id}/config",
        data={"featureFlags": {"promo_codes": True, "tokenized_cards": False}},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert "feature_flags" in body["changed"]

    # Persisted on the model.
    cfg = MerchantConfig.objects.get(merchant=m)
    assert cfg.feature_flags == {"promo_codes": True, "tokenized_cards": False}

    # Resolved bundle reflects the override.
    resolved = {f["key"]: f["enabled"] for f in body["config"]["featureFlags"]}
    assert resolved["promo_codes"] is True
    assert resolved["tokenized_cards"] is False
    # Untouched flags fall back to catalog defaults.
    assert resolved["manual_refunds"] == FEATURE_FLAGS["manual_refunds"]["default"]

    assert (
        AuditLog.objects.filter(action="platform.merchant.config.update").count()
        == before + 1
    )


def test_config_patch_sparse_merge_preserves_existing(platform_admin_owner):
    m = _make_merchant("cfg-patch-merge")
    MerchantConfig.objects.create(
        merchant=m,
        feature_flags={"tokenized_cards": False},
        limits={"high_risk_mcc": True},
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        f"/api/v1/platform/merchants/{m.id}/config",
        data={"featureFlags": {"promo_codes": True}},
        format="json",
    )
    assert resp.status_code == 200, resp.content

    cfg = MerchantConfig.objects.get(merchant=m)
    # Both the pre-existing override AND the new one are present.
    assert cfg.feature_flags == {"tokenized_cards": False, "promo_codes": True}
    # Limits were untouched.
    assert cfg.limits == {"high_risk_mcc": True}


def test_config_patch_limits_and_retry_policy(platform_admin_owner):
    m = _make_merchant("cfg-patch-limits")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        f"/api/v1/platform/merchants/{m.id}/config",
        data={
            "limits": {"monthlyVolumeCapMinor": 1_000_000, "highRiskMcc": True},
            "retryPolicy": {"attempts": 7, "backoff": "linear", "cooldownHours": 12},
        },
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert "limits" in body["changed"]
    assert "retry_policy" in body["changed"]
    cfg = MerchantConfig.objects.get(merchant=m)
    assert cfg.limits["monthly_volume_cap_minor"] == 1_000_000
    assert cfg.limits["high_risk_mcc"] is True
    assert cfg.retry_policy == {
        "attempts": 7,
        "backoff": "linear",
        "cooldown_hours": 12,
    }
    # FE shape reflects the change.
    assert body["config"]["limits"]["highRiskMcc"] is True
    assert body["config"]["retryPolicy"]["attempts"] == 7
    assert body["config"]["retryPolicy"]["backoff"] == "Linear"


# --- PATCH validation ------------------------------------------------------


def test_config_patch_rejects_unknown_flag(platform_admin_owner):
    m = _make_merchant("cfg-patch-bogus")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        f"/api/v1/platform/merchants/{m.id}/config",
        data={"featureFlags": {"unknown_flag": True}},
        format="json",
    )
    assert resp.status_code == 400, resp.content
    body = resp.json()
    assert body["ok"] is False
    assert "unknown_flag" in body["reason"].lower()


def test_config_patch_rejects_bad_backoff(platform_admin_owner):
    m = _make_merchant("cfg-patch-backoff")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        f"/api/v1/platform/merchants/{m.id}/config",
        data={"retryPolicy": {"backoff": "geometric"}},
        format="json",
    )
    assert resp.status_code == 400
    assert "backoff" in resp.json()["reason"].lower()


# --- RBAC ------------------------------------------------------------------


def test_operator_can_read_config_but_not_patch(
    platform_admin_operator, signed_in_admin_client
):
    m = _make_merchant("cfg-operator")
    client = signed_in_admin_client(platform_admin_operator)

    # GET is fine.
    resp_get = client.get(f"/api/v1/platform/merchants/{m.id}/config")
    assert resp_get.status_code == 200, resp_get.content

    # PATCH is blocked.
    resp_patch = client.patch(
        f"/api/v1/platform/merchants/{m.id}/config",
        data={"featureFlags": {"promo_codes": True}},
        format="json",
    )
    assert resp_patch.status_code == 403, resp_patch.content
    body = resp_patch.json()
    assert body["ok"] is False
    assert "owner" in body["reason"].lower()


def test_owner_can_patch_config(platform_admin_owner, signed_in_admin_client):
    m = _make_merchant("cfg-owner")
    client = signed_in_admin_client(platform_admin_owner)
    resp = client.patch(
        f"/api/v1/platform/merchants/{m.id}/config",
        data={"featureFlags": {"promo_codes": True}},
        format="json",
    )
    assert resp.status_code == 200, resp.content
