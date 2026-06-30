"""Tests for the platform-admin team management endpoints (S9)."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Merchant, Role, TeamMember, User
from apps.audit.models import AuditLog
from apps.platform_admin.models import (
    PlatformAdmin,
    PlatformAdminRole,
    PlatformAdminStatus,
    PlatformInviteToken,
)

pytestmark = pytest.mark.django_db


# --- Helpers ---------------------------------------------------------------


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


def _seed_merchant_user(*, name: str = "Acme", slug: str = "acme") -> User:
    m = Merchant.objects.create(name=name, slug=slug, default_currency="NGN")
    user = User.objects.create(email=f"owner@{slug}.test", is_active=True)
    user.set_password("Subpilot1!")
    user.save()
    TeamMember.objects.create(merchant=m, user=user, role=Role.OWNER)
    return user


# --- List / GET ------------------------------------------------------------


def test_team_list_requires_session():
    client = APIClient()
    resp = client.get("/api/v1/platform/team")
    assert resp.status_code in (401, 403)


def test_team_list_blocks_merchant_user(platform_admin_owner):
    _seed_merchant_user()
    client = APIClient()
    # Sign in as the merchant user via the merchant auth path; even if that
    # somehow puts a session cookie, the platform endpoints reject it.
    resp = client.post(
        "/api/v1/auth/sign-in",
        data={"email": "owner@acme.test", "password": "Subpilot1!"},
        format="json",
    )
    # Some envs require MFA bypass; ignore status. We just need the cookie.
    resp = client.get("/api/v1/platform/team")
    assert resp.status_code in (401, 403)


def test_team_list_returns_fe_shape(platform_admin_owner, platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/team")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert isinstance(body["results"], list)
    assert body["total"] >= 2
    row = body["results"][0]
    for key in (
        "id", "rawId", "name", "email", "role", "rawRole",
        "status", "rawStatus", "mfa", "lastActive", "invitedBy", "initials",
    ):
        assert key in row, f"missing {key} in row"
    # FE labels normalized
    assert row["role"] in ("Owner", "Operator", "Support", "Read-only")
    assert row["status"] in ("Active", "Invited", "Suspended")


def test_team_list_filter_by_role_and_q(platform_admin_owner, platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    # Filter role=owner -> only owners
    resp = client.get("/api/v1/platform/team?role=owner")
    assert resp.status_code == 200
    rows = resp.json()["results"]
    assert all(r["rawRole"] == "owner" for r in rows)
    assert any(r["email"] == platform_admin_owner.email for r in rows)
    # q=ops -> just the operator
    resp = client.get("/api/v1/platform/team?q=ops")
    assert resp.status_code == 200
    rows = resp.json()["results"]
    assert any("ops" in r["email"] for r in rows)


# --- Invite ----------------------------------------------------------------


def test_invite_owner_creates_admin_and_token(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/team/invite",
        data={
            "email": "newbie@subpilot.dev",
            "display_name": "New Bie",
            "role": "operator",
        },
        format="json",
    )
    assert resp.status_code == 201, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["admin"]["email"] == "newbie@subpilot.dev"
    assert body["admin"]["rawStatus"] == "invited"
    assert body["admin"]["rawRole"] == "operator"
    assert body["invite"]["token"]
    assert body["invite"]["expiresAt"]
    # DB rows present.
    new_admin = PlatformAdmin.objects.get(email="newbie@subpilot.dev")
    assert new_admin.status == PlatformAdminStatus.INVITED
    token = PlatformInviteToken.objects.get(admin=new_admin)
    assert token.token == body["invite"]["token"]
    # Audit log emitted
    assert AuditLog.objects.filter(
        action="platform.team.invite", target_id=str(new_admin.id)
    ).exists()


def test_invite_blocked_for_non_owner(platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_operator.email)
    resp = client.post(
        "/api/v1/platform/team/invite",
        data={"email": "blocked@subpilot.dev", "role": "operator"},
        format="json",
    )
    assert resp.status_code == 403, resp.content
    assert PlatformAdmin.objects.filter(email="blocked@subpilot.dev").count() == 0


def test_invite_duplicate_email_rejected(platform_admin_owner, platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/team/invite",
        data={"email": platform_admin_operator.email, "role": "operator"},
        format="json",
    )
    assert resp.status_code == 400, resp.content
    body = resp.json()
    assert body["ok"] is False


def test_invite_invalid_email_rejected(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/team/invite",
        data={"email": "not-an-email", "role": "support"},
        format="json",
    )
    assert resp.status_code == 400, resp.content


# --- Accept invite ---------------------------------------------------------


def test_accept_invite_activates_admin(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/team/invite",
        data={"email": "accept@subpilot.dev", "display_name": "Accept Me", "role": "support"},
        format="json",
    )
    assert resp.status_code == 201
    token = resp.json()["invite"]["token"]
    # Anonymous client accepts
    anon = APIClient()
    resp = anon.post(
        "/api/v1/platform/team/accept-invite",
        data={"token": token, "password": "ABcd1234!", "display_name": "Acceptor"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    assert body["admin"]["rawStatus"] == "active"
    admin = PlatformAdmin.objects.get(email="accept@subpilot.dev")
    assert admin.status == PlatformAdminStatus.ACTIVE
    assert admin.check_password("ABcd1234!")
    token_row = PlatformInviteToken.objects.get(token=token)
    assert token_row.accepted_at is not None


def test_accept_invite_invalid_token_rejected():
    anon = APIClient()
    resp = anon.post(
        "/api/v1/platform/team/accept-invite",
        data={"token": "nope-not-a-real-token", "password": "ABcd1234!"},
        format="json",
    )
    assert resp.status_code == 400


def test_accept_invite_short_password_rejected(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/team/invite",
        data={"email": "weak@subpilot.dev", "role": "support"},
        format="json",
    )
    token = resp.json()["invite"]["token"]
    anon = APIClient()
    resp = anon.post(
        "/api/v1/platform/team/accept-invite",
        data={"token": token, "password": "short"},
        format="json",
    )
    assert resp.status_code == 400


def test_accept_invite_twice_rejected(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/team/invite",
        data={"email": "double@subpilot.dev", "role": "support"},
        format="json",
    )
    token = resp.json()["invite"]["token"]
    anon = APIClient()
    resp1 = anon.post(
        "/api/v1/platform/team/accept-invite",
        data={"token": token, "password": "ABcd1234!"},
        format="json",
    )
    assert resp1.status_code == 200
    resp2 = anon.post(
        "/api/v1/platform/team/accept-invite",
        data={"token": token, "password": "DiffPwd1!"},
        format="json",
    )
    assert resp2.status_code == 400


# --- Detail / Update -------------------------------------------------------


def test_team_detail_returns_admin(platform_admin_owner, platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(f"/api/v1/platform/team/{platform_admin_operator.id}")
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["admin"]["rawId"] == str(platform_admin_operator.id)


def test_team_detail_unknown_404(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get("/api/v1/platform/team/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404


def test_team_update_role_and_audits(platform_admin_owner, platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        f"/api/v1/platform/team/{platform_admin_operator.id}",
        data={"role": "support", "display_name": "Updated Name"},
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["admin"]["rawRole"] == "support"
    assert body["admin"]["name"] == "Updated Name"
    platform_admin_operator.refresh_from_db()
    assert platform_admin_operator.role == PlatformAdminRole.SUPPORT
    assert AuditLog.objects.filter(
        action="platform.team.update", target_id=str(platform_admin_operator.id)
    ).exists()


def test_team_update_blocked_for_non_owner(platform_admin_owner, platform_admin_operator):
    # Operator tries to update Owner — must 403.
    client = APIClient()
    _sign_in(client, platform_admin_operator.email)
    resp = client.patch(
        f"/api/v1/platform/team/{platform_admin_owner.id}",
        data={"role": "support"},
        format="json",
    )
    assert resp.status_code == 403


def test_team_update_invalid_role_400(platform_admin_owner, platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.patch(
        f"/api/v1/platform/team/{platform_admin_operator.id}",
        data={"role": "wizard"},
        format="json",
    )
    assert resp.status_code == 400


# --- Suspend / Reactivate --------------------------------------------------


def test_team_suspend_flips_status_and_audits(platform_admin_owner, platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/team/{platform_admin_operator.id}/suspend",
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["admin"]["rawStatus"] == "suspended"
    platform_admin_operator.refresh_from_db()
    assert platform_admin_operator.status == PlatformAdminStatus.SUSPENDED
    assert AuditLog.objects.filter(
        action="platform.team.suspend", target_id=str(platform_admin_operator.id)
    ).exists()


def test_team_suspend_self_rejected(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/team/{platform_admin_owner.id}/suspend",
        format="json",
    )
    assert resp.status_code == 400


def test_team_suspend_blocked_for_non_owner(platform_admin_owner, platform_admin_operator):
    client = APIClient()
    _sign_in(client, platform_admin_operator.email)
    resp = client.post(
        f"/api/v1/platform/team/{platform_admin_owner.id}/suspend",
        format="json",
    )
    assert resp.status_code == 403


def test_team_reactivate_restores_status(platform_admin_owner, platform_admin_operator):
    platform_admin_operator.status = PlatformAdminStatus.SUSPENDED
    platform_admin_operator.save()
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        f"/api/v1/platform/team/{platform_admin_operator.id}/reactivate",
        format="json",
    )
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["admin"]["rawStatus"] == "active"
    assert AuditLog.objects.filter(
        action="platform.team.reactivate", target_id=str(platform_admin_operator.id)
    ).exists()


def test_team_suspend_unknown_404(platform_admin_owner):
    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.post(
        "/api/v1/platform/team/00000000-0000-0000-0000-000000000000/suspend",
        format="json",
    )
    assert resp.status_code == 404
