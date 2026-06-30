"""Tests for the cross-tenant API keys list + revoke endpoints (S7)."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import ApiKey, Environment, Merchant
from apps.audit.models import AuditLog

pytestmark = pytest.mark.django_db


# --- Helpers ---------------------------------------------------------------


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def _seed_merchant(*, name: str, slug: str, mode: str = Environment.Mode.LIVE) -> tuple[Merchant, Environment]:
    m = Merchant.objects.create(name=name, slug=slug, default_currency="NGN")
    env = Environment.objects.create(merchant=m, mode=mode)
    return m, env


def _seed_api_key(
    merchant: Merchant,
    env: Environment,
    *,
    name: str = "Service key",
    status: str = ApiKey.Status.ACTIVE,
    prefix: str = "nse_live_abcd",
    key_hash: str | None = None,
) -> ApiKey:
    return ApiKey.objects.create(
        merchant=merchant,
        environment=env,
        name=name,
        key_prefix=prefix,
        key_hash=key_hash or f"hash_{prefix}_{status}",
        scopes=["read", "write"],
        status=status,
    )


# --- Permission gate -------------------------------------------------------


def test_api_keys_list_requires_session():
    resp = APIClient().get("/api/v1/platform/api-keys")
    assert resp.status_code in (401, 403)


def test_api_keys_list_blocks_merchant_user(django_user_model):
    user = django_user_model.objects.create(
        username="m@acme.test", email="m@acme.test", is_staff=True
    )
    user.set_password("Subpilot1!")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.get("/api/v1/platform/api-keys")
    assert resp.status_code in (401, 403)


def test_api_key_revoke_blocks_merchant_user(django_user_model):
    m, env = _seed_merchant(name="Acme", slug="acme")
    k = _seed_api_key(m, env)
    user = django_user_model.objects.create(
        username="m@acme.test", email="m@acme.test", is_staff=True
    )
    user.set_password("Subpilot1!")
    user.save()
    client = APIClient()
    client.force_authenticate(user=user)
    resp = client.post(f"/api/v1/platform/api-keys/{k.id}/revoke", format="json")
    assert resp.status_code in (401, 403)


# --- List ------------------------------------------------------------------


def test_api_keys_list_returns_fe_shape(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    _seed_api_key(m, env, name="Service A", prefix="nse_live_aaaa", key_hash="hash_a")
    _seed_api_key(
        m, env,
        name="Service B",
        prefix="nse_live_bbbb",
        key_hash="hash_b",
        status=ApiKey.Status.REVOKED,
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/api-keys?page_size=20")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["total"] >= 2
    row = body["results"][0]
    for key in (
        "id", "rawId", "label", "prefix", "scope", "rawScope",
        "createdBy", "createdAt", "lastUsed", "status", "rawStatus",
        "merchantId", "merchant", "environmentId",
    ):
        assert key in row, f"missing key {key!r}"
    statuses = {r["status"] for r in body["results"]}
    assert {"Active", "Revoked"} & statuses
    scopes = {r["scope"] for r in body["results"]}
    assert "Live" in scopes


def test_api_keys_list_filter_status_revoked(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    _seed_api_key(m, env, name="Live", prefix="nse_live_act", key_hash="hash_live_act")
    _seed_api_key(
        m, env,
        name="Old",
        prefix="nse_live_old",
        key_hash="hash_live_old",
        status=ApiKey.Status.REVOKED,
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/api-keys?status=revoked&page_size=20")
    body = resp.json()
    assert resp.status_code == 200
    assert body["results"]
    assert all(r["status"] == "Revoked" for r in body["results"])


def test_api_keys_list_filter_scope_test(platform_admin_owner):
    m, env_live = _seed_merchant(name="Acme", slug="acme", mode=Environment.Mode.LIVE)
    env_test = Environment.objects.create(merchant=m, mode=Environment.Mode.TEST)
    _seed_api_key(m, env_live, name="Live key", prefix="nse_live_l", key_hash="hash_live_only")
    _seed_api_key(m, env_test, name="Test key", prefix="nse_test_t", key_hash="hash_test_only")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/api-keys?scope=test&page_size=20")
    body = resp.json()
    assert resp.status_code == 200
    assert body["results"]
    assert all(r["scope"] == "Test" for r in body["results"])


def test_api_keys_list_filter_by_merchant(platform_admin_owner):
    m1, e1 = _seed_merchant(name="Acme", slug="acme")
    m2, e2 = _seed_merchant(name="Other", slug="other")
    _seed_api_key(m1, e1, name="Acme key", prefix="nse_live_acme", key_hash="hash_acme")
    _seed_api_key(m2, e2, name="Other key", prefix="nse_live_other", key_hash="hash_other")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/api-keys?merchant_id={m1.id}&page_size=20")
    body = resp.json()
    assert resp.status_code == 200
    assert body["results"]
    assert all(r["merchantId"] == str(m1.id) for r in body["results"])


def test_api_keys_list_q_search(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    _seed_api_key(m, env, name="Recovery worker", prefix="nse_live_rec", key_hash="hash_rec")
    _seed_api_key(m, env, name="Admin tool", prefix="nse_live_adm", key_hash="hash_adm")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/api-keys?q=recovery&page_size=20")
    body = resp.json()
    assert resp.status_code == 200
    assert body["results"]
    assert any("Recovery" in r["label"] for r in body["results"])


# --- Revoke ----------------------------------------------------------------


def test_revoke_flips_status_and_audits(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    k = _seed_api_key(m, env, name="To revoke", prefix="nse_live_tor", key_hash="hash_tor")
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(f"/api/v1/platform/api-keys/{k.id}/revoke", format="json")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["status"] == ApiKey.Status.REVOKED
    assert body["revokedAt"]

    k.refresh_from_db()
    assert k.status == ApiKey.Status.REVOKED
    assert k.revoked_at is not None

    log = AuditLog.objects.filter(
        action="platform.api_key.revoke", target_id=str(k.id)
    ).first()
    assert log is not None
    assert log.actor_role == "platform_admin"
    assert log.merchant_id == m.id


def test_revoke_unknown_404(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/api-keys/00000000-0000-0000-0000-000000000000/revoke",
        format="json",
    )
    assert resp.status_code == 404
    assert resp.json()["ok"] is False


def test_revoke_already_revoked_returns_409(platform_admin_owner):
    m, env = _seed_merchant(name="Acme", slug="acme")
    k = _seed_api_key(
        m, env,
        name="Already gone",
        prefix="nse_live_gone",
        key_hash="hash_gone",
        status=ApiKey.Status.REVOKED,
    )
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(f"/api/v1/platform/api-keys/{k.id}/revoke", format="json")
    assert resp.status_code == 409
    assert resp.json()["ok"] is False
