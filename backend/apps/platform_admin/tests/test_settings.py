"""Tests for the platform-admin settings endpoint (S10)."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Merchant, Role, TeamMember, User
from apps.audit.models import AuditLog
from apps.platform_admin.models import PlatformSetting
from apps.platform_admin.selectors.settings import (
    DEFAULT_ADAPTER_STATUS,
    DEFAULT_KEY,
    DEFAULT_POLICY,
)

pytestmark = pytest.mark.django_db

URL = "/api/v1/platform/settings"


# --- Helpers ---------------------------------------------------------------


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def _seed_merchant_user() -> User:
    m = Merchant.objects.create(name="Acme", slug="acme", default_currency="NGN")
    user = User.objects.create(email="owner@acme.test", is_active=True)
    user.set_password("Subpilot1!")
    user.save()
    TeamMember.objects.create(merchant=m, user=user, role=Role.OWNER)
    return user


# --- Auth / RBAC -----------------------------------------------------------


def test_settings_requires_session():
    client = APIClient()
    resp = client.get(URL)
    assert resp.status_code in (401, 403)


def test_settings_blocks_merchant_user():
    _seed_merchant_user()
    client = APIClient()
    client.post(
        "/api/v1/auth/sign-in",
        data={"email": "owner@acme.test", "password": "Subpilot1!"},
        format="json",
    )
    resp = client.get(URL)
    assert resp.status_code in (401, 403)


# --- GET -------------------------------------------------------------------


def test_settings_get_creates_singleton_with_defaults(platform_admin_owner):
    assert PlatformSetting.objects.count() == 0
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)

    resp = client.get(URL)
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    settings = body["settings"]
    # Singleton row created lazily.
    assert PlatformSetting.objects.filter(key=DEFAULT_KEY).count() == 1
    # Shape
    for key in ("id", "key", "policy", "adapterStatus", "updatedAt"):
        assert key in settings, f"missing {key}"
    # Defaults match selector constants.
    for k in (
        "defaultRetryAttempts",
        "passwordMinLength",
        "enforcedMfa",
        "ipAllowlistEnabled",
        "dataRetentionDays",
    ):
        assert settings["policy"][k] == DEFAULT_POLICY[k]
    assert isinstance(settings["adapterStatus"], list)
    assert len(settings["adapterStatus"]) == len(DEFAULT_ADAPTER_STATUS)


def test_settings_get_is_open_to_any_admin_role(platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_operator.email)
    resp = client.get(URL)
    assert resp.status_code == 200, resp.content
    assert resp.json()["ok"] is True


def test_settings_get_idempotent(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    r1 = client.get(URL)
    r2 = client.get(URL)
    assert r1.status_code == 200 and r2.status_code == 200
    assert r1.json()["settings"]["id"] == r2.json()["settings"]["id"]
    assert PlatformSetting.objects.count() == 1


# --- PATCH (Owner-only) ----------------------------------------------------


def test_settings_patch_owner_updates_policy(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    payload = {
        "policy": {
            "defaultRetryAttempts": 7,
            "ipAllowlistEnabled": True,
            "readOnlyMode": True,
        }
    }
    resp = client.patch(URL, data=payload, format="json")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    pol = body["settings"]["policy"]
    assert pol["defaultRetryAttempts"] == 7
    assert pol["ipAllowlistEnabled"] is True
    assert pol["readOnlyMode"] is True
    # Untouched defaults preserved (merge semantics)
    assert pol["passwordMinLength"] == DEFAULT_POLICY["passwordMinLength"]


def test_settings_patch_writes_audit_log(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        URL,
        data={"policy": {"defaultRetryAttempts": 9}},
        format="json",
    )
    assert resp.status_code == 200
    log = AuditLog.objects.filter(action="platform.settings.update").first()
    assert log is not None
    assert log.actor_role == "platform_admin"
    assert log.actor_label == platform_admin_owner.display_name or log.actor_label == platform_admin_owner.email
    assert "policy" in (log.metadata or {}).get("changes", {})


def test_settings_patch_no_change_no_audit(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    # First create row with defaults.
    client.get(URL)
    AuditLog.objects.filter(action="platform.settings.update").delete()

    # Send the same defaults — should be a no-op.
    resp = client.patch(
        URL,
        data={"policy": {"defaultRetryAttempts": DEFAULT_POLICY["defaultRetryAttempts"]}},
        format="json",
    )
    assert resp.status_code == 200
    assert AuditLog.objects.filter(action="platform.settings.update").count() == 0


def test_settings_patch_operator_forbidden(platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_operator.email)
    resp = client.patch(
        URL,
        data={"policy": {"defaultRetryAttempts": 9}},
        format="json",
    )
    assert resp.status_code == 403, resp.content
    body = resp.json()
    assert body["ok"] is False
    assert "Owner" in body["reason"]


def test_settings_patch_support_forbidden(platform_admin_support):
    client = APIClient()
    _sign_in(client, platform_admin_support.email)
    resp = client.patch(
        URL,
        data={"policy": {"enforcedMfa": False}},
        format="json",
    )
    assert resp.status_code == 403


def test_settings_patch_rejects_bad_policy_type(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(URL, data={"policy": "not-an-object"}, format="json")
    assert resp.status_code == 400


def test_settings_patch_rejects_bad_adapter_type(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        URL,
        data={"adapter_status": {"not": "a list"}},
        format="json",
    )
    assert resp.status_code == 400


def test_settings_patch_replaces_adapter_status(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    new_adapters = [
        {"name": "Adapter X", "role": "Test", "uptime": "100%", "latencyP95": "10 ms",
         "failoverTrigger": "n/a", "region": "Lagos", "status": "Operational"},
    ]
    resp = client.patch(
        URL,
        data={"adapter_status": new_adapters},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["settings"]["adapterStatus"]) == 1
    assert body["settings"]["adapterStatus"][0]["name"] == "Adapter X"


def test_settings_patch_adapter_requires_name(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        URL,
        data={"adapter_status": [{"role": "no name"}]},
        format="json",
    )
    assert resp.status_code == 400
    assert "name" in resp.json()["reason"]


def test_settings_patch_camelcase_adapter_alias(platform_admin_owner):
    """FE may send `adapterStatus` (camelCase). Backend accepts both."""
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    new_adapters = [
        {"name": "Adapter Y", "role": "Test", "uptime": "100%", "latencyP95": "9 ms",
         "failoverTrigger": "n/a", "region": "Lagos", "status": "Operational"},
    ]
    resp = client.patch(URL, data={"adapterStatus": new_adapters}, format="json")
    assert resp.status_code == 200
    assert resp.json()["settings"]["adapterStatus"][0]["name"] == "Adapter Y"
