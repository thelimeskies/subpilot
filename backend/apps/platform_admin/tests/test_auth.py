"""Tests for platform admin auth endpoints."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db


# --- Helpers ----------------------------------------------------------


def sign_in(client: APIClient, email: str, password: str):
    return client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": password},
        format="json",
    )


# --- Sign-in ----------------------------------------------------------


def test_sign_in_success(platform_admin_owner):
    client = APIClient()
    resp = sign_in(client, platform_admin_owner.email, "Subpilot1!")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["user"]["email"] == platform_admin_owner.email
    assert body["user"]["role"] == "Owner"
    # Last-login is now populated.
    platform_admin_owner.refresh_from_db()
    assert platform_admin_owner.last_login_at is not None


def test_sign_in_wrong_password(platform_admin_owner):
    client = APIClient()
    resp = sign_in(client, platform_admin_owner.email, "not-it")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "did not match" in body["reason"].lower()


def test_sign_in_unknown_email():
    client = APIClient()
    resp = sign_in(client, "nope@subpilot.dev", "Subpilot1!")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False


def test_sign_in_suspended_admin(platform_admin_suspended):
    client = APIClient()
    resp = sign_in(client, platform_admin_suspended.email, "Subpilot1!")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "suspended" in body["reason"].lower()


def test_sign_in_invalid_payload():
    client = APIClient()
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": "not-an-email"},
        format="json",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False


# --- /me ----------------------------------------------------------------


def test_me_anonymous_returns_null_user():
    client = APIClient()
    resp = client.get("/api/v1/platform/auth/me")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "user": None}


def test_me_returns_admin_after_sign_in(platform_admin_operator):
    client = APIClient()
    sign_in(client, platform_admin_operator.email, "Subpilot1!")
    resp = client.get("/api/v1/platform/auth/me")
    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["email"] == platform_admin_operator.email
    assert body["user"]["role"] == "Operator"


# --- /ping (IsPlatformAdmin gate) --------------------------------------


def test_ping_requires_session():
    client = APIClient()
    resp = client.get("/api/v1/platform/ping")
    # DRF returns 401 when no auth credentials are provided, 403 when authed
    # but lacking permission. Both are valid "rejected" outcomes.
    assert resp.status_code in (401, 403)


def test_ping_works_after_sign_in(platform_admin_owner):
    client = APIClient()
    sign_in(client, platform_admin_owner.email, "Subpilot1!")
    resp = client.get("/api/v1/platform/ping")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


# --- Sign-out -----------------------------------------------------------


def test_sign_out_clears_session(platform_admin_owner):
    client = APIClient()
    sign_in(client, platform_admin_owner.email, "Subpilot1!")
    # Pre-condition: ping works.
    assert client.get("/api/v1/platform/ping").status_code == 200
    resp = client.post("/api/v1/platform/auth/sign-out")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    # Post-condition: ping rejected.
    assert client.get("/api/v1/platform/ping").status_code in (401, 403)


def test_sign_out_anonymous_is_idempotent():
    client = APIClient()
    resp = client.post("/api/v1/platform/auth/sign-out")
    assert resp.status_code == 200


# --- Tenant isolation: a merchant user cannot reach platform endpoints --


def test_merchant_user_cannot_access_platform_ping(django_user_model):
    """The crucial guarantee: a logged-in merchant ``User`` (even staff)
    must never satisfy ``IsPlatformAdmin``."""
    merchant_user = django_user_model.objects.create(
        username="merchant@acme.test",
        email="merchant@acme.test",
        is_staff=True,  # even with is_staff!
    )
    merchant_user.set_password("Subpilot1!")
    merchant_user.save()

    client = APIClient()
    client.force_authenticate(user=merchant_user)
    resp = client.get("/api/v1/platform/ping")
    # Either 401 (DRF auth rejects) or 403 (permission rejects). Never 200.
    assert resp.status_code in (401, 403), resp.content


# --- Forgot password stub -----------------------------------------------


def test_forgot_password_returns_202():
    client = APIClient()
    resp = client.post(
        "/api/v1/platform/auth/forgot",
        data={"email": "anyone@subpilot.dev"},
        format="json",
    )
    assert resp.status_code == 202
    assert resp.json()["ok"] is True
