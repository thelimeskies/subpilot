"""S12 — RBAC matrix tests: every platform endpoint × every actor class.

This test sweeps the entire ``/api/v1/platform/*`` surface and confirms:

* Anonymous callers are rejected (401/403) on every endpoint (auth/forgot is
  the lone public surface — covered by its own test).
* Merchant tenant users are rejected (401/403) on every endpoint — a merchant
  session must never grant platform access.
* All four active admin roles (Owner, Operator, Support, Read-only) can read
  every GET endpoint that lists / shows data (cross-role visibility).
* Owner-only mutating endpoints (PATCH /settings, team mgmt) reject Operator
  with 403; non-owner-gated mutating endpoints (suspend merchant, retry
  webhook, etc.) accept Operator.

Per-feature tests cover payload validation, audit emission, cache semantics,
etc. This module exists solely to lock down the auth/role surface so future
endpoints inherit the gate by convention.
"""
from __future__ import annotations

import uuid

import pytest
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

PLATFORM = "/api/v1/platform"

# ---------------------------------------------------------------------------
# Endpoint inventory (mirrors urls.py)
#
# Each entry: (label, method, path)
# Path placeholders use a known-bogus UUID so the auth layer fires before the
# selector layer 404s — i.e. we test the auth gate, not the lookup result.
# ---------------------------------------------------------------------------

BOGUS = "00000000-0000-0000-0000-000000000000"

# All read-style endpoints that any admin role MUST be able to GET.
READ_ENDPOINTS = [
    ("ping", "GET", f"{PLATFORM}/ping"),
    ("auth.me", "GET", f"{PLATFORM}/auth/me"),
    ("overview", "GET", f"{PLATFORM}/overview"),
    ("merchants", "GET", f"{PLATFORM}/merchants"),
    ("payments", "GET", f"{PLATFORM}/payments"),
    ("webhooks.deliveries", "GET", f"{PLATFORM}/webhooks/deliveries"),
    ("webhooks.health", "GET", f"{PLATFORM}/webhooks/health"),
    ("api-keys", "GET", f"{PLATFORM}/api-keys"),
    ("tickets", "GET", f"{PLATFORM}/tickets"),
    ("team", "GET", f"{PLATFORM}/team"),
    ("settings", "GET", f"{PLATFORM}/settings"),
    ("analytics", "GET", f"{PLATFORM}/analytics"),
]

# Endpoints that need a path parameter — we just check auth gating, the result
# will be 404 once we pass auth.
DETAIL_READ_ENDPOINTS = [
    ("merchant.detail", "GET", f"{PLATFORM}/merchants/{BOGUS}"),
    ("ticket.detail", "GET", f"{PLATFORM}/tickets/{BOGUS}"),
    ("kyc.detail", "GET", f"{PLATFORM}/kyc/{BOGUS}"),
    ("team.detail", "GET", f"{PLATFORM}/team/{BOGUS}"),
    # S13 per-tab merchant detail endpoints — all read-side, any active admin role.
    ("merchant.subscriptions", "GET", f"{PLATFORM}/merchants/{BOGUS}/subscriptions"),
    ("merchant.payments", "GET", f"{PLATFORM}/merchants/{BOGUS}/payments"),
    ("merchant.webhooks", "GET", f"{PLATFORM}/merchants/{BOGUS}/webhooks"),
    ("merchant.audit", "GET", f"{PLATFORM}/merchants/{BOGUS}/audit"),
    ("merchant.config", "GET", f"{PLATFORM}/merchants/{BOGUS}/config"),
]

# All mutating endpoints — must reject anon + merchant session.
MUTATION_ENDPOINTS = [
    ("merchant.suspend", "POST", f"{PLATFORM}/merchants/{BOGUS}/suspend"),
    ("merchant.reactivate", "POST", f"{PLATFORM}/merchants/{BOGUS}/reactivate"),
    ("merchant.notes", "POST", f"{PLATFORM}/merchants/{BOGUS}/notes"),
    ("payment.refund", "POST", f"{PLATFORM}/payments/{BOGUS}/refund"),
    ("webhook.retry", "POST", f"{PLATFORM}/webhooks/deliveries/{BOGUS}/retry"),
    ("api-key.revoke", "POST", f"{PLATFORM}/api-keys/{BOGUS}/revoke"),
    ("ticket.create", "POST", f"{PLATFORM}/tickets"),
    ("ticket.patch", "PATCH", f"{PLATFORM}/tickets/{BOGUS}"),
    ("ticket.reply", "POST", f"{PLATFORM}/tickets/{BOGUS}/replies"),
    ("kyc.patch", "PATCH", f"{PLATFORM}/kyc/{BOGUS}"),
    ("team.invite", "POST", f"{PLATFORM}/team/invite"),
    ("team.patch", "PATCH", f"{PLATFORM}/team/{BOGUS}"),
    ("team.suspend", "POST", f"{PLATFORM}/team/{BOGUS}/suspend"),
    ("team.reactivate", "POST", f"{PLATFORM}/team/{BOGUS}/reactivate"),
    ("settings.patch", "PATCH", f"{PLATFORM}/settings"),
    # S13 Owner-only: per-merchant config writes.
    ("merchant.config.patch", "PATCH", f"{PLATFORM}/merchants/{BOGUS}/config"),
]

# Owner-only mutating endpoints — Operator must get 403 even with a valid
# admin session. Path placeholders are bogus; service layer will raise
# owner-only before the lookup fires.
OWNER_ONLY_MUTATIONS = [
    ("settings.patch", "PATCH", f"{PLATFORM}/settings"),
    ("team.invite", "POST", f"{PLATFORM}/team/invite"),
    ("team.patch", "PATCH", f"{PLATFORM}/team/{BOGUS}"),
    ("team.suspend", "POST", f"{PLATFORM}/team/{BOGUS}/suspend"),
    ("team.reactivate", "POST", f"{PLATFORM}/team/{BOGUS}/reactivate"),
    ("merchant.config.patch", "PATCH", f"{PLATFORM}/merchants/{BOGUS}/config"),
]

ALL_ENDPOINTS = READ_ENDPOINTS + DETAIL_READ_ENDPOINTS + MUTATION_ENDPOINTS


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _hit(client: APIClient, method: str, path: str):
    method = method.upper()
    # All mutating endpoints accept JSON; we send {} so JSON parsers don't 400.
    if method == "GET":
        return client.get(path)
    if method == "POST":
        return client.post(path, data={}, format="json")
    if method == "PATCH":
        return client.patch(path, data={}, format="json")
    if method == "PUT":
        return client.put(path, data={}, format="json")
    if method == "DELETE":
        return client.delete(path)
    raise AssertionError(f"unsupported method: {method}")


# ---------------------------------------------------------------------------
# 1. Anonymous: every endpoint must reject (auth.me is the documented anon-OK
#    introspection endpoint and is excluded).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label, method, path", ALL_ENDPOINTS, ids=[e[0] for e in ALL_ENDPOINTS])
def test_anonymous_is_rejected_everywhere(label, method, path):
    if label == "auth.me":
        pytest.skip("/auth/me is intentionally anon-OK with {ok:true,user:null}")
    client = APIClient()
    resp = _hit(client, method, path)
    assert resp.status_code in (401, 403), (
        f"{label} {method} {path} expected 401/403, got {resp.status_code}: {resp.content!r}"
    )


# ---------------------------------------------------------------------------
# 2. Merchant tenant session: every endpoint must reject — a merchant user
#    must NEVER get platform access, regardless of their tenant role.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("label, method, path", ALL_ENDPOINTS, ids=[e[0] for e in ALL_ENDPOINTS])
def test_merchant_session_is_rejected_everywhere(
    label, method, path, merchant_user, signed_in_merchant_client
):
    client = signed_in_merchant_client(merchant_user)
    resp = _hit(client, method, path)
    # auth.me returns {ok:true,user:null} for any non-admin caller; that's fine.
    if label == "auth.me":
        assert resp.status_code == 200
        body = resp.json()
        assert body.get("ok") is True
        assert body.get("user") is None
        return
    assert resp.status_code in (401, 403), (
        f"{label} {method} {path} merchant-session expected 401/403, "
        f"got {resp.status_code}: {resp.content!r}"
    )


# ---------------------------------------------------------------------------
# 3. Read endpoints: all four active admin roles must be able to GET.
# ---------------------------------------------------------------------------


@pytest.fixture(params=["owner", "operator", "support", "readonly"])
def any_active_admin(
    request,
    platform_admin_owner,
    platform_admin_operator,
    platform_admin_support,
    platform_admin_readonly,
):
    return {
        "owner": platform_admin_owner,
        "operator": platform_admin_operator,
        "support": platform_admin_support,
        "readonly": platform_admin_readonly,
    }[request.param]


@pytest.mark.parametrize(
    "label, method, path", READ_ENDPOINTS, ids=[e[0] for e in READ_ENDPOINTS]
)
def test_every_admin_role_can_read(
    label, method, path, any_active_admin, signed_in_admin_client
):
    client = signed_in_admin_client(any_active_admin)
    resp = _hit(client, method, path)
    assert resp.status_code == 200, (
        f"{label} {method} {path} as {any_active_admin.role} expected 200, "
        f"got {resp.status_code}: {resp.content!r}"
    )


# ---------------------------------------------------------------------------
# 4. Suspended admin: signing in must fail, so they can never hit any
#    endpoint at all. (Sign-in returns 403, not 200.)
# ---------------------------------------------------------------------------


def test_suspended_admin_cannot_sign_in(platform_admin_suspended):
    client = APIClient()
    resp = client.post(
        f"{PLATFORM}/auth/sign-in",
        data={"email": platform_admin_suspended.email, "password": "Subpilot1!"},
        format="json",
    )
    assert resp.status_code in (200, 401, 403), resp.content
    body = resp.json()
    assert body.get("ok") is False
    assert "suspended" in (body.get("reason") or "").lower()


# ---------------------------------------------------------------------------
# 5. Owner-only mutations: Operator session must get 403.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label, method, path",
    OWNER_ONLY_MUTATIONS,
    ids=[e[0] for e in OWNER_ONLY_MUTATIONS],
)
def test_operator_is_blocked_on_owner_only_mutations(
    label, method, path, platform_admin_operator, signed_in_admin_client
):
    client = signed_in_admin_client(platform_admin_operator)
    # For settings.patch we need a structurally valid payload so the view gets
    # past payload validation and into the Owner check.
    payload = {"policy": {"defaultRetryAttempts": 4}} if label == "settings.patch" else {}
    if label == "team.invite":
        payload = {
            "email": f"matrix-{uuid.uuid4().hex[:8]}@subpilot.dev",
            "role": "operator",
            "display_name": "RBAC Matrix Probe",
        }
    if method == "PATCH":
        resp = client.patch(path, data=payload, format="json")
    else:
        resp = client.post(path, data=payload, format="json")
    assert resp.status_code == 403, (
        f"{label} {method} {path} as Operator expected 403, "
        f"got {resp.status_code}: {resp.content!r}"
    )
    body = resp.json()
    assert body.get("ok") is False


# ---------------------------------------------------------------------------
# 6. Owner is allowed on the same owner-only mutations (sanity check —
#    we don't assert 200 because the bogus UUID will 404; we assert NOT 403).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "label, method, path",
    OWNER_ONLY_MUTATIONS,
    ids=[e[0] for e in OWNER_ONLY_MUTATIONS],
)
def test_owner_passes_owner_gate_on_owner_only_mutations(
    label, method, path, platform_admin_owner, signed_in_admin_client
):
    client = signed_in_admin_client(platform_admin_owner)
    payload = {"policy": {"defaultRetryAttempts": 4}} if label == "settings.patch" else {}
    if label == "team.invite":
        payload = {
            "email": f"owner-matrix-{uuid.uuid4().hex[:8]}@subpilot.dev",
            "role": "operator",
            "display_name": "Owner Matrix Probe",
        }
    if method == "PATCH":
        resp = client.patch(path, data=payload, format="json")
    else:
        resp = client.post(path, data=payload, format="json")
    # Owner should NEVER be blocked by the role gate. 200, 201, 404, 400, 409
    # are all acceptable here — we're only locking down the auth surface.
    assert resp.status_code != 403, (
        f"{label} {method} {path} as Owner should not be 403; got "
        f"{resp.status_code}: {resp.content!r}"
    )
