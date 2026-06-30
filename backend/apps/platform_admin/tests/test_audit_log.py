"""Tests for the cross-tenant platform audit log endpoint."""
from __future__ import annotations

import pytest
from rest_framework.test import APIClient

from apps.accounts.models import Merchant
from apps.audit.services.log_event import log_event

pytestmark = pytest.mark.django_db

URL = "/api/v1/platform/audit-log"


def _sign_in(client: APIClient, email: str) -> None:
    resp = client.post(
        "/api/v1/platform/auth/sign-in",
        data={"email": email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code == 200, resp.content


# --- Auth gate -------------------------------------------------------------


def test_audit_log_requires_session():
    client = APIClient()
    resp = client.get(URL)
    assert resp.status_code in (401, 403)


# --- Listing ---------------------------------------------------------------


def test_audit_log_returns_recent_events(platform_admin_owner):
    # Seed a few audit rows representing different categories.
    log_event(action="platform.settings.update", actor_label="ada@subpilot.dev", actor_role="platform_admin")
    log_event(action="auth.sign_in", actor_label="ada@subpilot.dev", actor_role="platform_admin")
    m = Merchant.objects.create(name="Acme", slug="acme", default_currency="NGN")
    log_event(action="merchant.suspend", actor_label="ada@subpilot.dev", actor_role="platform_admin", merchant=m)

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(URL)
    assert resp.status_code == 200, resp.content
    body = resp.json()
    assert body["ok"] is True
    rows = body["rows"]
    # Sign-in itself emits an audit event, plus the three above.
    assert len(rows) >= 4
    # Newest-first ordering — the action of the most recent row should be one
    # of the events above.
    actions = [r["action"] for r in rows]
    assert "platform.settings.update" in actions
    assert "merchant.suspend" in actions
    assert "auth.sign_in" in actions
    # Shape sanity.
    sample = rows[0]
    for key in ("id", "actor", "action", "detail", "category", "occurredAt"):
        assert key in sample, f"missing {key}"


def test_audit_log_categorizes_actions(platform_admin_owner):
    log_event(action="auth.sign_in", actor_label="x", actor_role="platform_admin")
    log_event(action="platform.settings.update", actor_label="x", actor_role="platform_admin")
    log_event(action="team_member.invite", actor_label="x", actor_role="platform_admin")
    m = Merchant.objects.create(name="Beta", slug="beta", default_currency="NGN")
    log_event(action="merchant.suspend", actor_label="x", actor_role="platform_admin", merchant=m)

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(URL)
    assert resp.status_code == 200
    by_action = {r["action"]: r for r in resp.json()["rows"]}
    assert by_action["auth.sign_in"]["category"] == "security"
    assert by_action["platform.settings.update"]["category"] == "platform"
    assert by_action["team_member.invite"]["category"] == "team"
    assert by_action["merchant.suspend"]["category"] == "merchant"


def test_audit_log_filters_by_category(platform_admin_owner):
    log_event(action="auth.sign_in", actor_label="x", actor_role="platform_admin")
    log_event(action="platform.settings.update", actor_label="x", actor_role="platform_admin")

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(URL, {"category": "security"})
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert len(rows) >= 1
    assert all(r["category"] == "security" for r in rows)
    assert all(r["action"] != "platform.settings.update" for r in rows)


def test_audit_log_search_matches_action_or_actor(platform_admin_owner):
    log_event(action="merchant.kyc_approved", actor_label="ada@subpilot.dev", actor_role="platform_admin")
    log_event(action="invoice.retry", actor_label="zainab@subpilot.dev", actor_role="platform_admin")

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(URL, {"search": "kyc"})
    assert resp.status_code == 200
    rows = resp.json()["rows"]
    assert all("kyc" in r["action"].lower() or "kyc" in r["actor"].lower() for r in rows)


def test_audit_log_paginates(platform_admin_owner):
    for i in range(7):
        log_event(action=f"platform.test.event_{i}", actor_label="x", actor_role="platform_admin")

    client = APIClient()
    _sign_in(client, platform_admin_owner.email)
    resp = client.get(URL, {"pageSize": 3, "page": 1})
    assert resp.status_code == 200
    body = resp.json()
    assert body["page"] == 1
    assert body["pageSize"] == 3
    assert len(body["rows"]) == 3
    assert body["total"] >= 7


def test_audit_log_open_to_any_admin_role(platform_admin_readonly):
    log_event(action="platform.settings.update", actor_label="x", actor_role="platform_admin")
    client = APIClient()
    _sign_in(client, platform_admin_readonly.email)
    resp = client.get(URL)
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
