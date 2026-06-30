"""Tests for the platform admin profile-update PATCH /auth/me endpoint."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.audit.models import AuditLog
from apps.platform_admin.models import PlatformAdmin

pytestmark = pytest.mark.django_db

URL = "/api/v1/platform/auth/me"


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


# --- Auth gate -------------------------------------------------------------


def test_profile_patch_requires_session():
    client = APIClient()
    resp = client.patch(URL, data={"display_name": "Anything"}, format="json")
    assert resp.status_code in (401, 403)


# --- Display name update ---------------------------------------------------


def test_profile_patch_updates_display_name(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(URL, data={"display_name": "Ada Owner"}, format="json")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["user"]["name"] == "Ada Owner"

    platform_admin_owner.refresh_from_db()
    assert platform_admin_owner.display_name == "Ada Owner"


def test_profile_patch_camelcase_alias(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(URL, data={"displayName": "Camel Case"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["user"]["name"] == "Camel Case"


def test_profile_patch_rejects_empty_display_name(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(URL, data={"display_name": "   "}, format="json")
    assert resp.status_code == 400
    body = resp.json()
    assert body["ok"] is False
    assert "empty" in body["reason"].lower()


def test_profile_patch_rejects_too_long_display_name(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(URL, data={"display_name": "x" * 200}, format="json")
    assert resp.status_code == 400


# --- Email update ----------------------------------------------------------


def test_profile_patch_updates_email(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(URL, data={"email": "new-email@subpilot.dev"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "new-email@subpilot.dev"

    platform_admin_owner.refresh_from_db()
    assert platform_admin_owner.email == "new-email@subpilot.dev"


def test_profile_patch_normalises_email_lowercase(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(URL, data={"email": "MIXED@Subpilot.Dev"}, format="json")
    assert resp.status_code == 200
    assert resp.json()["user"]["email"] == "mixed@subpilot.dev"


def test_profile_patch_rejects_invalid_email(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(URL, data={"email": "not-an-email"}, format="json")
    assert resp.status_code == 400
    assert "valid email" in resp.json()["reason"].lower()


def test_profile_patch_rejects_duplicate_email(platform_admin_owner, platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(URL, data={"email": platform_admin_operator.email}, format="json")
    assert resp.status_code == 400
    assert "already in use" in resp.json()["reason"].lower()


def test_profile_patch_keeps_existing_email_idempotent(platform_admin_owner):
    """Sending the same email back is a no-op, not a duplicate-error."""
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(URL, data={"email": platform_admin_owner.email}, format="json")
    assert resp.status_code == 200


# --- Audit -----------------------------------------------------------------


def test_profile_patch_emits_audit_log(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    AuditLog.objects.filter(action="platform_admin.profile.update").delete()

    client.patch(URL, data={"display_name": "Ada O."}, format="json")

    log = AuditLog.objects.filter(action="platform_admin.profile.update").first()
    assert log is not None
    assert log.target_id == str(platform_admin_owner.id)
    assert "display_name" in (log.metadata or {}).get("changes", {})


def test_profile_patch_no_change_no_audit(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    AuditLog.objects.filter(action="platform_admin.profile.update").delete()

    # Send the same display_name that's already on the row.
    current = platform_admin_owner.display_name or platform_admin_owner.email
    client.patch(URL, data={"display_name": current}, format="json")

    assert AuditLog.objects.filter(action="platform_admin.profile.update").count() == 0


# --- Role / status are NOT editable on this endpoint ----------------------


def test_profile_patch_ignores_role_and_status(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(URL, data={"role": "operator", "status": "suspended"}, format="json")
    assert resp.status_code == 200

    platform_admin_owner.refresh_from_db()
    # Role unchanged.
    assert platform_admin_owner.role == "owner"
    assert platform_admin_owner.status == "active"
