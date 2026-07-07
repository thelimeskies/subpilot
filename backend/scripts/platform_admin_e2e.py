#!/usr/bin/env python3
"""End-to-end test for the SubPilot Platform Admin API.

Exercises the platform admin auth + ping surface against a running Compose
stack. Each slice (S1-S11) appends a step here as it lands. Steps cover:

  Step 1: Sign-in success returns FE-shape user payload
  Step 2: /auth/me returns the same admin while signed-in
  Step 3: /ping is reachable while signed-in
  Step 4: Sign-out clears session
  Step 5: /ping after sign-out is rejected (401/403)
  Step 6: Wrong password rejected with FE-shape ``{ok:false, reason:...}``
  Step 7: Unknown email rejected with same shape
  Step 8: Anonymous /auth/me returns ``{ok:true, user:null}``
  Step 9: Tenant isolation \u2014 a merchant user CANNOT access /ping
  Step 10: Forgot-password always 202
  Step 11: Overview snapshot returns FE shape (S2)
  Step 12: Overview ?refresh=true bypasses cache (S2)
  Step 13: Merchant user blocked from /platform/overview (S2)
  Step 14: Merchants list returns paginated FE-shape rows (S3)
  Step 15: Merchants list filters by q=acme (S3)
  Step 16: Merchant user blocked from /platform/merchants (S3)
  Step 17: Merchant detail returns FE-shape nested payload (S4)
  Step 18: POST /merchants/<id>/notes creates a row + audit (S4)
  Step 19: POST /merchants/<id>/suspend flips status + audits (S4)
  Step 20: POST /merchants/<id>/reactivate restores status + audits (S4)
  Step 21: Merchant user blocked from detail/suspend/notes (S4)
  Step 22: Payments list returns paginated FE-shape rows (S5)
  Step 23: Payments list filters by merchant_id (S5)
  Step 24: POST /payments/<id>/refund flips status + audits (S5)
  Step 25: Refund unknown payment returns 404 (S5)
  Step 26: Merchant user blocked from /platform/payments + refund (S5)
  Step 27: Webhooks list returns paginated FE-shape rows (S6)
  Step 28: Webhooks list filters by merchant_id (S6)
  Step 29: Webhooks health endpoint returns FE-shape counts (S6)
  Step 30: POST /webhooks/deliveries/<id>/retry flips status + audits (S6)
  Step 31: Retry unknown delivery returns 404; delivered returns 409 (S6)
  Step 32: Merchant user blocked from /platform/webhooks/* (S6)
  Step 33: API keys list returns paginated FE-shape rows (S7)
  Step 34: API keys list filters by merchant_id and status (S7)
  Step 35: POST /api-keys/<id>/revoke flips status + audits (S7)
  Step 36: Revoke unknown id returns 404; already-revoked returns 409 (S7)
  Step 37: Merchant user blocked from /platform/api-keys + revoke (S7)
  Step 38: Tickets list returns paginated FE-shape rows (S8)
  Step 39: Tickets list filters by status/priority/merchant_id (S8)
  Step 40: POST /tickets creates a row + audits (S8)
  Step 41: GET /tickets/<id> returns detail with replies (S8)
  Step 42: PATCH /tickets/<id> updates status + priority + audits (S8)
  Step 43: POST /tickets/<id>/replies creates a reply + audits (S8)
  Step 44: GET /kyc/<merchant_id> returns FE-shape (lazy-creates if missing) (S8)
  Step 45: PATCH /kyc/<merchant_id> updates status/level + audits (S8)
  Step 46: Tickets/KYC unknowns return 404 (S8)
  Step 47: Merchant user blocked from /platform/tickets + /platform/kyc (S8)
  Step 48: Team list returns paginated FE-shape rows (S9)
  Step 49: Team list filters by role and q (S9)
  Step 50: POST /team/invite as Owner creates Invited admin + token (S9)
  Step 51: POST /team/accept-invite activates the admin (S9)
  Step 52: PATCH /team/<id> as Owner updates role + audits (S9)
  Step 53: POST /team/<id>/suspend flips status + audits (S9)
  Step 54: POST /team/<id>/reactivate restores status + audits (S9)
  Step 55: Tickets/Team unknowns return 404 (S9)
  Step 56: Operator gets 403 on invite / update / suspend (Owner-gated) (S9)
  Step 57: Merchant user blocked from /platform/team (S9)
  Step 58: GET /platform/settings returns FE-shape singleton (S10)
  Step 59: GET /platform/settings open to any admin role (S10)
  Step 60: PATCH /platform/settings as Owner merges policy + audits (S10)
  Step 61: PATCH /platform/settings replaces adapter_status via camelCase (S10)
  Step 62: PATCH /platform/settings as Operator returns 403 (Owner-gated) (S10)
  Step 63: PATCH /platform/settings rejects bad payloads (400) (S10)
  Step 64: Merchant user blocked from /platform/settings (S10)
  Step 65: GET /platform/analytics returns FE-shape bundle (S11)
  Step 66: Range filter (3m/6m/12m) controls revenueSeries length (S11)
  Step 67: Invalid range falls back to default (S11)
  Step 68: ?refresh=true bypasses cache + audits refresh (S11)
  Step 69: /platform/analytics open to any admin role (S11)
  Step 70: Merchant user blocked from /platform/analytics (S11)
  Step 71: Per-tab merchant endpoints (subs/payments/webhooks/audit) (S13)
  Step 72: Config GET defaults + PATCH merge as Owner (S13)
  Step 73: Config PATCH as Operator returns 403 (S13)
  Step 74: Un-authed sweep — every protected endpoint returns 401/403 (S12)

Pass criterion: every step prints a green check; failure aborts and prints
the offending response.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Any

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v1"
PLATFORM = f"{API}/platform"

ADMIN_OWNER_EMAIL = "owner@subpilot.dev"
ADMIN_OWNER_PASSWORD = "Subpilot1!"
ADMIN_OPS_EMAIL = "ops@subpilot.dev"
ADMIN_OPS_PASSWORD = "Subpilot1!"
ADMIN_SUPPORT_EMAIL = "support@subpilot.dev"
ADMIN_SUPPORT_PASSWORD = "Subpilot1!"

# Merchant user (provisioned by `seed_demo`) used for cross-domain isolation tests.
MERCHANT_OWNER_EMAIL = "owner@acme.test"
MERCHANT_OWNER_PASSWORD = "Subpilot1!"
MFA_BYPASS = "123456"

GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


class TestError(Exception):
    pass


class Client:
    """Isolated session (cookie jar)."""

    def __init__(self, label: str = "default") -> None:
        self.label = label
        self.cj = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cj)
        )

    def csrf(self) -> str | None:
        for c in self.cj:
            if c.name in ("subpilot_csrf", "csrftoken"):
                return c.value
        return None

    def request(
        self,
        method: str,
        url: str,
        *,
        data: Any = None,
        headers: dict | None = None,
        timeout: int = 15,
    ) -> tuple[int, dict | str]:
        if not url.startswith("http"):
            url = f"{API}{url}" if url.startswith("/") else f"{API}/{url}"
        body: bytes | None = None
        h = {"Accept": "application/json"}
        if headers:
            h.update(headers)
        if data is not None:
            body = json.dumps(data).encode("utf-8")
            h.setdefault("Content-Type", "application/json")
        if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            tok = self.csrf()
            if tok and "X-CSRFToken" not in h:
                h["X-CSRFToken"] = tok
                h.setdefault("Referer", BASE_URL)
        req = urllib.request.Request(url, data=body, method=method, headers=h)
        try:
            with self.opener.open(req, timeout=timeout) as resp:
                raw = resp.read()
                try:
                    payload = json.loads(raw) if raw else {}
                except json.JSONDecodeError:
                    payload = raw.decode("utf-8", errors="replace")
                return resp.status, payload
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                payload = json.loads(raw)
            except Exception:
                payload = raw.decode("utf-8", errors="replace")
            return e.code, payload


# --- pretty-printing ---------------------------------------------------------


_step_no = 0


def step(name: str) -> None:
    global _step_no
    _step_no += 1
    print(f"\n{BOLD}[{_step_no:02d}] {name}{RESET}")


def ok(msg: str) -> None:
    print(f"  {GREEN}\u2713{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {DIM}{msg}{RESET}")


def fail(msg: str, payload: Any = None) -> None:
    print(f"  {RED}\u2717 {msg}{RESET}")
    if payload is not None:
        print(f"  {DIM}{json.dumps(payload, indent=2, default=str) if isinstance(payload, (dict, list)) else payload}{RESET}")
    raise TestError(msg)


def expect(cond: bool, msg: str, payload: Any = None) -> None:
    if not cond:
        fail(msg, payload)
    ok(msg)


# --- helpers -----------------------------------------------------------------


def platform_url(path: str) -> str:
    return f"{PLATFORM}{path if path.startswith('/') else '/' + path}"


def sign_in_admin(client: Client, email: str, password: str) -> dict:
    status, body = client.request(
        "POST",
        platform_url("/auth/sign-in"),
        data={"email": email, "password": password},
    )
    if status != 200 or not isinstance(body, dict) or not body.get("ok"):
        fail(f"sign-in failed for {email} (status={status})", body)
    return body  # type: ignore[return-value]


def sign_in_merchant(client: Client, email: str, password: str) -> dict:
    """Sign in a regular merchant User via the merchant auth surface."""
    status, body = client.request(
        "POST",
        f"{API}/auth/sign-in",
        data={"email": email, "password": password},
    )
    if status != 200 or not isinstance(body, dict) or not body.get("ok"):
        fail(f"merchant sign-in failed for {email} (status={status})", body)
    if isinstance(body, dict) and body.get("requires_mfa"):
        cid = body.get("challenge_id") or body.get("challengeId")
        status, body = client.request(
            "POST",
            f"{API}/auth/mfa/verify",
            data={"challenge_id": cid, "code": MFA_BYPASS},
        )
        if status != 200:
            fail("mfa challenge could not be completed", body)
    return body  # type: ignore[return-value]


# --- steps -------------------------------------------------------------------


def run() -> None:
    print(f"{BOLD}SubPilot Platform Admin E2E{RESET} \u2014 base={BASE_URL}")

    owner = Client("owner")

    # 1. Sign-in success.
    step("Owner sign-in returns FE-shape user payload")
    body = sign_in_admin(owner, ADMIN_OWNER_EMAIL, ADMIN_OWNER_PASSWORD)
    user = body.get("user", {}) if isinstance(body, dict) else {}
    expect(user.get("email") == ADMIN_OWNER_EMAIL, f"user.email == {ADMIN_OWNER_EMAIL}", body)
    expect(user.get("role") == "Owner", "user.role == 'Owner'", body)
    expect(isinstance(user.get("id"), str) and len(user["id"]) > 0, "user.id present", body)
    expect(isinstance(user.get("name"), str) and len(user["name"]) > 0, "user.name present", body)
    expect(isinstance(user.get("initials"), str), "user.initials present", body)

    # 2. /auth/me reflects session.
    step("/auth/me returns the same admin while signed-in")
    status, body = owner.request("GET", platform_url("/auth/me"))
    expect(status == 200, f"GET /auth/me \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
    me = body.get("user") if isinstance(body, dict) else None
    expect(isinstance(me, dict) and me.get("email") == ADMIN_OWNER_EMAIL, "me.user.email matches", body)

    # 3. /ping reachable while signed-in.
    step("/ping reachable while signed-in")
    status, body = owner.request("GET", platform_url("/ping"))
    expect(status == 200, f"GET /ping \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ping ok=true", body)

    # 4. Sign-out.
    step("Sign-out clears session")
    status, body = owner.request("POST", platform_url("/auth/sign-out"))
    expect(status == 200, f"POST /auth/sign-out \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)

    # 5. /ping rejected after sign-out.
    step("/ping rejected after sign-out")
    status, body = owner.request("GET", platform_url("/ping"))
    expect(status in (401, 403), f"GET /ping after sign-out \u2192 401/403 (got {status})", body)

    # 6. Wrong password rejected.
    step("Wrong password rejected with FE-shape error")
    bad = Client("bad-password")
    status, body = bad.request(
        "POST",
        platform_url("/auth/sign-in"),
        data={"email": ADMIN_OWNER_EMAIL, "password": "definitely-wrong"},
    )
    expect(status == 200, f"sign-in with wrong password \u2192 200 envelope (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is False, "ok=false", body)
    expect(isinstance(body, dict) and isinstance(body.get("reason"), str), "reason present", body)

    # 7. Unknown email rejected (no enumeration leak).
    step("Unknown email rejected with same shape")
    status, body = bad.request(
        "POST",
        platform_url("/auth/sign-in"),
        data={"email": "ghost@subpilot.dev", "password": "Subpilot1!"},
    )
    expect(status == 200, f"sign-in with unknown email \u2192 200 envelope (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is False, "ok=false", body)

    # 8. Anonymous /auth/me returns null user (so the SPA bootstrap call is non-throwing).
    step("Anonymous /auth/me returns ok=true with user=null")
    anon = Client("anonymous")
    status, body = anon.request("GET", platform_url("/auth/me"))
    expect(status == 200, f"GET /auth/me anonymous \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
    expect(isinstance(body, dict) and body.get("user") is None, "user is null", body)

    # 9. Tenant isolation: merchant user signs in via the merchant API and is
    # then rejected when probing the platform admin surface.
    step("Merchant user CANNOT access platform /ping (tenant isolation)")
    merchant = Client("merchant")
    sign_in_merchant(merchant, MERCHANT_OWNER_EMAIL, MERCHANT_OWNER_PASSWORD)
    status, body = merchant.request("GET", platform_url("/ping"))
    expect(
        status in (401, 403),
        f"GET /platform/ping with merchant session \u2192 401/403 (got {status})",
        body,
    )

    # 10. Forgot-password endpoint always 202 (no enumeration).
    step("Forgot-password returns 202 regardless of email")
    status, body = anon.request(
        "POST",
        platform_url("/auth/forgot"),
        data={"email": "anyone@example.test"},
    )
    expect(status == 202, f"POST /auth/forgot \u2192 202 (got {status})", body)

    # 11. Cross-tenant overview snapshot (S2).
    step("Overview returns FE-shape stats with non-zero merchant count")
    s2_owner = Client("s2-owner")
    sign_in_admin(s2_owner, ADMIN_OWNER_EMAIL, ADMIN_OWNER_PASSWORD)
    status, body = s2_owner.request("GET", platform_url("/overview"))
    expect(status == 200, f"GET /platform/overview \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
    stats = body.get("stats") if isinstance(body, dict) else None
    expect(isinstance(stats, dict), "stats object present", body)
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
        expect(key in stats, f"stats.{key} present", stats)
    raw = stats.get("raw") if isinstance(stats, dict) else None
    expect(isinstance(raw, dict) and "mrrMinor" in raw, "raw.mrrMinor present", stats)
    expect(
        isinstance(stats.get("liveMerchants"), int) and stats["liveMerchants"] >= 1,
        f"liveMerchants \u2265 1 after seed_demo (got {stats.get('liveMerchants')})",
        stats,
    )

    # 12. Forced refresh bypasses cache and audits the refresh.
    step("Overview ?refresh=true bypasses cache")
    status, body = s2_owner.request("GET", platform_url("/overview?refresh=true"))
    expect(status == 200, f"GET /overview?refresh=true \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)

    # 13. Tenant isolation for the overview endpoint.
    step("Merchant user CANNOT access /platform/overview")
    iso = Client("iso")
    sign_in_merchant(iso, MERCHANT_OWNER_EMAIL, MERCHANT_OWNER_PASSWORD)
    status, body = iso.request("GET", platform_url("/overview"))
    expect(
        status in (401, 403),
        f"GET /platform/overview with merchant session \u2192 401/403 (got {status})",
        body,
    )

    # 14. Merchants list (S3) — shape, search, isolation.
    step("Merchants list returns paginated FE-shape rows")
    s3_owner = Client("s3-owner")
    sign_in_admin(s3_owner, ADMIN_OWNER_EMAIL, ADMIN_OWNER_PASSWORD)
    status, body = s3_owner.request("GET", platform_url("/merchants?page_size=10"))
    expect(status == 200, f"GET /platform/merchants \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
    expect(isinstance(body.get("results"), list), "results is a list", body)
    expect(isinstance(body.get("total"), int) and body["total"] >= 1, f"total \u2265 1 (got {body.get('total')})", body)
    if body["results"]:
        row = body["results"][0]
        for key in (
            "id", "name", "owner", "ownerEmail", "plan", "mrr", "status",
            "failedInvoices", "recoveryRate", "environment", "createdAt",
            "region", "monthlyVolume", "activeSubscriptions", "raw",
        ):
            expect(key in row, f"row.{key} present", row)

    step("Merchants search filters by name (q=acme)")
    status, body = s3_owner.request("GET", platform_url("/merchants?q=acme"))
    expect(status == 200, f"GET /platform/merchants?q=acme \u2192 200 (got {status})", body)
    names = [r.get("name", "") for r in (body.get("results") or [])]
    expect(any("acme" in n.lower() for n in names) or len(names) == 0,
           "search returns acme matches (or empty)", body)

    step("Merchant user CANNOT access /platform/merchants")
    status, body = iso.request("GET", platform_url("/merchants"))
    expect(
        status in (401, 403),
        f"GET /platform/merchants with merchant session \u2192 401/403 (got {status})",
        body,
    )

    # 17-21. Merchant detail (S4) — detail shape, suspend, reactivate, notes, isolation.
    step("Merchant detail returns FE-shape nested payload")
    s4_owner = Client("s4-owner")
    sign_in_admin(s4_owner, ADMIN_OWNER_EMAIL, ADMIN_OWNER_PASSWORD)
    status, listing = s4_owner.request("GET", platform_url("/merchants?page_size=5"))
    expect(status == 200 and isinstance(listing, dict) and listing.get("results"),
           "list merchants for detail probe", listing)
    target = None
    for row in listing["results"]:
        if isinstance(row, dict) and "acme" in (row.get("name", "").lower()):
            target = row
            break
    if target is None:
        target = listing["results"][0]
    merchant_id = target["id"]
    info(f"target merchant: {target.get('name')} ({merchant_id})")

    status, body = s4_owner.request("GET", platform_url(f"/merchants/{merchant_id}"))
    expect(status == 200, f"GET /platform/merchants/<id> \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
    detail = body.get("merchant") if isinstance(body, dict) else None
    expect(isinstance(detail, dict), "merchant object present", body)
    for key in (
        "id", "name", "slug", "owner", "ownerEmail", "plan", "mrr", "status",
        "rawStatus", "environment", "createdAt", "region", "monthlyVolume",
        "activeSubscriptions", "subscriptionStats", "environments",
        "recentPayments", "recentAudit", "kyc", "notes", "raw",
    ):
        expect(key in detail, f"detail.{key} present", detail)
    expect(isinstance(detail["subscriptionStats"], dict), "subscriptionStats is dict", detail)
    expect(isinstance(detail["environments"], list), "environments is list", detail)
    expect(isinstance(detail["recentPayments"], list), "recentPayments is list", detail)
    expect(isinstance(detail["recentAudit"], list), "recentAudit is list", detail)
    expect(isinstance(detail["notes"], list), "notes is list", detail)

    step("Add merchant note creates row + audit")
    status, body = s4_owner.request(
        "POST",
        platform_url(f"/merchants/{merchant_id}/notes"),
        data={"body": "E2E note from platform admin", "visibility": "internal"},
    )
    expect(status == 201, f"POST /merchants/<id>/notes \u2192 201 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True and isinstance(body.get("noteId"), str),
           "noteId returned", body)

    step("Suspend merchant flips status + audits")
    status, body = s4_owner.request(
        "POST",
        platform_url(f"/merchants/{merchant_id}/suspend"),
        data={"reason": "E2E suspend probe", "note": "automated"},
    )
    expect(status == 200, f"POST /merchants/<id>/suspend \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
    expect(body.get("status") == "suspended", "status=suspended", body)

    # Verify the change is visible via detail re-fetch.
    status, body = s4_owner.request("GET", platform_url(f"/merchants/{merchant_id}"))
    expect(status == 200, "re-fetch detail after suspend \u2192 200", body)
    expect(body.get("merchant", {}).get("rawStatus") == "suspended",
           "detail.rawStatus == suspended", body)

    step("Reactivate merchant restores active status + audits")
    status, body = s4_owner.request(
        "POST",
        platform_url(f"/merchants/{merchant_id}/reactivate"),
        data={"note": "E2E reactivate"},
    )
    expect(status == 200, f"POST /merchants/<id>/reactivate \u2192 200 (got {status})", body)
    expect(body.get("status") == "active", "status=active", body)

    step("Merchant user CANNOT access /platform/merchants/<id> + actions")
    status, _ = iso.request("GET", platform_url(f"/merchants/{merchant_id}"))
    expect(status in (401, 403),
           f"GET detail with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request(
        "POST",
        platform_url(f"/merchants/{merchant_id}/suspend"),
        data={"reason": "nope"},
    )
    expect(status in (401, 403),
           f"POST suspend with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request(
        "POST",
        platform_url(f"/merchants/{merchant_id}/notes"),
        data={"body": "nope"},
    )
    expect(status in (401, 403),
           f"POST notes with merchant session \u2192 401/403 (got {status})")

    # 22-26. Payments (S5) — list, filter, refund, isolation.
    step("Payments list returns paginated FE-shape rows")
    s5_owner = Client("s5-owner")
    sign_in_admin(s5_owner, ADMIN_OWNER_EMAIL, ADMIN_OWNER_PASSWORD)
    status, body = s5_owner.request("GET", platform_url("/payments?page_size=20"))
    expect(status == 200, f"GET /platform/payments \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
    expect(isinstance(body.get("results"), list), "results is a list", body)
    expect(isinstance(body.get("total"), int), "total is int", body)
    if body["results"]:
        row = body["results"][0]
        for key in (
            "id", "rawId", "merchantId", "merchant", "customer", "amount",
            "status", "rawStatus", "method", "occurredAt", "gateway", "raw",
        ):
            expect(key in row, f"row.{key} present", row)

    step("Payments list filters by merchant_id")
    status, mlisting = s5_owner.request("GET", platform_url("/merchants?page_size=5"))
    expect(status == 200 and mlisting.get("results"), "list merchants for payments filter", mlisting)
    target_mid = None
    for r in mlisting["results"]:
        if "acme" in (r.get("name", "").lower()):
            target_mid = r["id"]
            break
    if target_mid is None:
        target_mid = mlisting["results"][0]["id"]
    status, body = s5_owner.request(
        "GET", platform_url(f"/payments?merchant_id={target_mid}&page_size=10")
    )
    expect(status == 200, f"GET /payments?merchant_id=<id> \u2192 200 (got {status})", body)
    if body.get("results"):
        expect(
            all(r.get("merchantId") == target_mid for r in body["results"]),
            "all results match merchant_id filter",
            body,
        )

    step("POST /payments/<id>/refund flips status + audits")
    # Find a captured/recovered payment to refund.
    status, body = s5_owner.request("GET", platform_url("/payments?status=captured&page_size=10"))
    target_payment = None
    if status == 200 and body.get("results"):
        target_payment = body["results"][0]
    else:
        # Fall back to recovered.
        status, body = s5_owner.request("GET", platform_url("/payments?status=recovered&page_size=10"))
        if status == 200 and body.get("results"):
            target_payment = body["results"][0]
    if target_payment is None:
        info("no captured/recovered payment available - skipping refund probe")
        ok("refund step skipped (no eligible seed payment)")
    else:
        info(f"target payment: {target_payment.get('id')} ({target_payment.get('rawId')})")
        status, body = s5_owner.request(
            "POST",
            platform_url(f"/payments/{target_payment['rawId']}/refund"),
            data={"reason": "E2E refund probe", "note": "automated"},
        )
        expect(status == 200, f"POST /payments/<id>/refund \u2192 200 (got {status})", body)
        expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
        expect(body.get("status") == "refunded", "status=refunded", body)
        expect(isinstance(body.get("refundedAt"), str), "refundedAt present", body)

    step("Refund unknown payment returns 404")
    status, body = s5_owner.request(
        "POST",
        platform_url("/payments/00000000-0000-0000-0000-000000000000/refund"),
        data={"reason": "ghost"},
    )
    expect(status == 404, f"POST refund unknown id \u2192 404 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is False, "ok=false", body)

    step("Merchant user CANNOT access /platform/payments + refund")
    status, _ = iso.request("GET", platform_url("/payments"))
    expect(status in (401, 403), f"GET /payments with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request(
        "POST",
        platform_url("/payments/00000000-0000-0000-0000-000000000000/refund"),
        data={"reason": "nope"},
    )
    expect(status in (401, 403),
           f"POST refund with merchant session \u2192 401/403 (got {status})")

    # 27-32. Webhooks (S6) — list, filter, health, retry, isolation.
    step("Webhooks list returns paginated FE-shape rows")
    s6_owner = Client("s6-owner")
    sign_in_admin(s6_owner, ADMIN_OWNER_EMAIL, ADMIN_OWNER_PASSWORD)
    status, body = s6_owner.request("GET", platform_url("/webhooks/deliveries?page_size=20"))
    expect(status == 200, f"GET /platform/webhooks/deliveries \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
    expect(isinstance(body.get("results"), list), "results is a list", body)
    expect(isinstance(body.get("total"), int), "total is int", body)
    if body["results"]:
        row = body["results"][0]
        for key in (
            "id", "rawId", "merchantId", "merchant", "event", "endpoint",
            "status", "rawStatus", "attempts", "lastAttempt", "responseCode",
        ):
            expect(key in row, f"row.{key} present", row)

    step("Webhooks list filters by merchant_id")
    status, mlisting = s6_owner.request("GET", platform_url("/merchants?page_size=5"))
    expect(status == 200 and mlisting.get("results"), "list merchants for webhooks filter", mlisting)
    target_mid = None
    for r in mlisting["results"]:
        if "acme" in (r.get("name", "").lower()):
            target_mid = r["id"]
            break
    if target_mid is None:
        target_mid = mlisting["results"][0]["id"]
    status, body = s6_owner.request(
        "GET", platform_url(f"/webhooks/deliveries?merchant_id={target_mid}&page_size=20")
    )
    expect(status == 200, f"GET /webhooks/deliveries?merchant_id=<id> \u2192 200 (got {status})", body)
    if body.get("results"):
        expect(
            all(r.get("merchantId") == target_mid for r in body["results"]),
            "all results match merchant_id filter",
            body,
        )

    step("Webhooks health endpoint returns FE-shape counts")
    status, body = s6_owner.request("GET", platform_url("/webhooks/health"))
    expect(status == 200, f"GET /webhooks/health \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
    for key in ("windowHours", "delivered", "retrying", "failed", "total", "successRate"):
        expect(key in body, f"health.{key} present", body)
    expect(isinstance(body["total"], int) and body["total"] >= 0, "total is non-negative int", body)
    expect(0 <= body["successRate"] <= 100, "successRate in [0,100]", body)

    step("POST /webhooks/deliveries/<id>/retry flips status + audits")
    # Find a non-Delivered delivery to retry.
    status, body = s6_owner.request(
        "GET", platform_url("/webhooks/deliveries?status=retrying&page_size=10")
    )
    target_delivery = None
    if status == 200 and body.get("results"):
        target_delivery = body["results"][0]
    else:
        status, body = s6_owner.request(
            "GET", platform_url("/webhooks/deliveries?status=failed&page_size=10")
        )
        if status == 200 and body.get("results"):
            target_delivery = body["results"][0]
    if target_delivery is None:
        info("no retryable delivery available - skipping retry probe")
        ok("retry step skipped (no eligible seed delivery)")
    else:
        info(f"target delivery: {target_delivery.get('id')} ({target_delivery.get('rawId')})")
        status, body = s6_owner.request(
            "POST",
            platform_url(f"/webhooks/deliveries/{target_delivery['rawId']}/retry"),
            data={},
        )
        expect(status == 200, f"POST /webhooks/deliveries/<id>/retry \u2192 200 (got {status})", body)
        expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
        expect(body.get("status") == "pending", "status=pending after retry", body)
        expect(isinstance(body.get("nextAttemptAt"), str), "nextAttemptAt present", body)

    step("Retry unknown delivery returns 404; delivered returns 409")
    status, body = s6_owner.request(
        "POST",
        platform_url("/webhooks/deliveries/00000000-0000-0000-0000-000000000000/retry"),
        data={},
    )
    expect(status == 404, f"POST retry unknown id \u2192 404 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is False, "ok=false on 404", body)
    # Try retrying a Delivered row -> 409.
    status, listed = s6_owner.request(
        "GET", platform_url("/webhooks/deliveries?status=delivered&page_size=5")
    )
    if status == 200 and listed.get("results"):
        delivered_id = listed["results"][0]["rawId"]
        status, body = s6_owner.request(
            "POST",
            platform_url(f"/webhooks/deliveries/{delivered_id}/retry"),
            data={},
        )
        expect(status == 409, f"POST retry delivered \u2192 409 (got {status})", body)
        expect(isinstance(body, dict) and body.get("ok") is False, "ok=false on 409", body)
    else:
        info("no Delivered delivery available - skipping 409 probe")

    step("Merchant user CANNOT access /platform/webhooks/*")
    status, _ = iso.request("GET", platform_url("/webhooks/deliveries"))
    expect(status in (401, 403),
           f"GET /webhooks/deliveries with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request("GET", platform_url("/webhooks/health"))
    expect(status in (401, 403),
           f"GET /webhooks/health with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request(
        "POST",
        platform_url("/webhooks/deliveries/00000000-0000-0000-0000-000000000000/retry"),
        data={},
    )
    expect(status in (401, 403),
           f"POST retry with merchant session \u2192 401/403 (got {status})")

    # 33-37. API keys (S7) — list, filter, revoke, isolation.
    step("API keys list returns paginated FE-shape rows")
    s7_owner = Client("s7-owner")
    sign_in_admin(s7_owner, ADMIN_OWNER_EMAIL, ADMIN_OWNER_PASSWORD)
    status, body = s7_owner.request("GET", platform_url("/api-keys?page_size=20"))
    expect(status == 200, f"GET /platform/api-keys \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
    expect(isinstance(body.get("results"), list), "results is a list", body)
    expect(isinstance(body.get("total"), int) and body["total"] >= 1,
           "total \u2265 1 (seed creates keys)", body)
    if body["results"]:
        row = body["results"][0]
        for key in (
            "id", "rawId", "label", "prefix", "scope", "rawScope",
            "createdBy", "createdAt", "lastUsed", "status", "rawStatus",
            "merchantId", "merchant", "environmentId",
        ):
            expect(key in row, f"row.{key} present", row)
        expect(row["status"] in ("Active", "Revoked"),
               f"row.status normalized (got {row.get('status')})", row)
        expect(row["scope"] in ("Live", "Test"),
               f"row.scope normalized (got {row.get('scope')})", row)

    step("API keys list filters by merchant_id and status")
    status, mlisting = s7_owner.request("GET", platform_url("/merchants?page_size=5"))
    expect(status == 200 and mlisting.get("results"), "list merchants for api-keys filter", mlisting)
    target_mid = None
    for r in mlisting["results"]:
        if "acme" in (r.get("name", "").lower()):
            target_mid = r["id"]
            break
    if target_mid is None:
        target_mid = mlisting["results"][0]["id"]
    status, body = s7_owner.request(
        "GET", platform_url(f"/api-keys?merchant_id={target_mid}&page_size=20")
    )
    expect(status == 200, f"GET /api-keys?merchant_id=<id> \u2192 200 (got {status})", body)
    if body.get("results"):
        expect(
            all(r.get("merchantId") == target_mid for r in body["results"]),
            "all results match merchant_id filter",
            body,
        )
    # status=active filter
    status, body = s7_owner.request(
        "GET", platform_url("/api-keys?status=active&page_size=20")
    )
    expect(status == 200, f"GET /api-keys?status=active \u2192 200 (got {status})", body)
    if body.get("results"):
        expect(
            all(r.get("rawStatus") == "active" for r in body["results"]),
            "all results active",
            body,
        )

    step("POST /api-keys/<id>/revoke flips status + audits")
    # Find an Active key to revoke (prefer one on target merchant for clean isolation).
    status, listed = s7_owner.request(
        "GET",
        platform_url(f"/api-keys?merchant_id={target_mid}&status=active&page_size=10"),
    )
    target_key = None
    if status == 200 and listed.get("results"):
        target_key = listed["results"][0]
    else:
        status, listed = s7_owner.request(
            "GET", platform_url("/api-keys?status=active&page_size=10")
        )
        if status == 200 and listed.get("results"):
            target_key = listed["results"][0]
    expect(target_key is not None, "an Active API key exists to revoke", listed)
    info(f"target key: {target_key.get('rawId')} ({target_key.get('label')})")
    status, body = s7_owner.request(
        "POST",
        platform_url(f"/api-keys/{target_key['rawId']}/revoke"),
        data={},
    )
    expect(status == 200, f"POST /api-keys/<id>/revoke \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
    expect(body.get("status") == "revoked", "status=revoked", body)
    expect(isinstance(body.get("revokedAt"), str) and body["revokedAt"],
           "revokedAt timestamp present", body)

    step("Revoke unknown id returns 404; already-revoked returns 409")
    status, body = s7_owner.request(
        "POST",
        platform_url("/api-keys/00000000-0000-0000-0000-000000000000/revoke"),
        data={},
    )
    expect(status == 404, f"POST revoke unknown id \u2192 404 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is False, "ok=false on 404", body)
    # Re-revoke the same key -> 409.
    status, body = s7_owner.request(
        "POST",
        platform_url(f"/api-keys/{target_key['rawId']}/revoke"),
        data={},
    )
    expect(status == 409, f"POST revoke already-revoked \u2192 409 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is False, "ok=false on 409", body)

    step("Merchant user CANNOT access /platform/api-keys + revoke")
    status, _ = iso.request("GET", platform_url("/api-keys"))
    expect(status in (401, 403),
           f"GET /api-keys with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request(
        "POST",
        platform_url("/api-keys/00000000-0000-0000-0000-000000000000/revoke"),
        data={},
    )
    expect(status in (401, 403),
           f"POST revoke with merchant session \u2192 401/403 (got {status})")

    # ----------------------------------------------------------------------
    # S8 - Support (Tickets + KYC)
    # ----------------------------------------------------------------------
    step("Tickets list returns paginated FE-shape rows")
    s8_owner = Client("s8-owner")
    sign_in_admin(s8_owner, ADMIN_OWNER_EMAIL, ADMIN_OWNER_PASSWORD)
    status, body = s8_owner.request("GET", platform_url("/tickets?page_size=20"))
    expect(status == 200, f"GET /platform/tickets \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true", body)
    expect(isinstance(body.get("results"), list), "results is a list", body)
    expect(isinstance(body.get("total"), int) and body["total"] >= 1,
           "total \u2265 1 (seed creates tickets)", body)
    if body["results"]:
        row = body["results"][0]
        for key in (
            "id", "rawId", "subject", "merchant", "merchantId",
            "priority", "rawPriority", "status", "rawStatus",
            "assignee", "assigneeId", "updatedAt", "createdAt",
        ):
            expect(key in row, f"row.{key} present", row)
        expect(row["status"] in ("Open", "Awaiting", "Resolved", "Closed"),
               f"row.status normalized (got {row.get('status')})", row)
        expect(row["priority"] in ("Low", "Normal", "High", "Urgent"),
               f"row.priority normalized (got {row.get('priority')})", row)

    step("Tickets list filters by status/priority/merchant_id")
    status, mlisting = s8_owner.request("GET", platform_url("/merchants?page_size=5"))
    expect(status == 200 and mlisting.get("results"), "list merchants for tickets filter", mlisting)
    target_mid = None
    for r in mlisting["results"]:
        if "acme" in (r.get("name", "").lower()):
            target_mid = r["id"]
            break
    if target_mid is None:
        target_mid = mlisting["results"][0]["id"]
    status, body = s8_owner.request(
        "GET", platform_url(f"/tickets?merchant_id={target_mid}&page_size=20")
    )
    expect(status == 200, f"GET /tickets?merchant_id=<id> \u2192 200 (got {status})", body)
    if body.get("results"):
        expect(
            all(r.get("merchantId") == target_mid for r in body["results"]),
            "all results match merchant_id filter",
            body,
        )
    status, body = s8_owner.request("GET", platform_url("/tickets?status=open&page_size=20"))
    expect(status == 200, f"GET /tickets?status=open \u2192 200 (got {status})", body)
    if body.get("results"):
        expect(
            all(r.get("rawStatus") == "open" for r in body["results"]),
            "all results status=open",
            body,
        )
    status, body = s8_owner.request("GET", platform_url("/tickets?priority=high&page_size=20"))
    expect(status == 200, f"GET /tickets?priority=high \u2192 200 (got {status})", body)
    if body.get("results"):
        expect(
            all(r.get("rawPriority") == "high" for r in body["results"]),
            "all results priority=high",
            body,
        )

    step("POST /tickets creates a row + audits")
    status, body = s8_owner.request(
        "POST",
        platform_url("/tickets"),
        data={
            "merchant_id": target_mid,
            "subject": "E2E platform-admin ticket",
            "body": "Created by platform_admin_e2e.py",
            "priority": "high",
            "requester_email": "owner@acme.test",
        },
    )
    expect(status == 201, f"POST /tickets \u2192 201 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true on create", body)
    ticket = body.get("ticket")
    expect(isinstance(ticket, dict) and ticket.get("rawId"),
           "ticket payload returned with rawId", body)
    new_ticket_id = ticket["rawId"]
    expect(ticket.get("subject") == "E2E platform-admin ticket", "subject persisted", ticket)
    expect(ticket.get("rawPriority") == "high", "priority persisted", ticket)
    expect(ticket.get("merchantId") == target_mid, "merchantId persisted", ticket)

    step("GET /tickets/<id> returns detail with replies")
    status, body = s8_owner.request("GET", platform_url(f"/tickets/{new_ticket_id}"))
    expect(status == 200, f"GET /tickets/<id> \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true on detail", body)
    detail = body.get("ticket")
    expect(isinstance(detail, dict), "ticket detail is dict", body)
    expect("body" in detail, "detail.body present", detail)
    expect(isinstance(detail.get("replies"), list), "detail.replies is list", detail)

    step("PATCH /tickets/<id> updates status + priority + audits")
    status, body = s8_owner.request(
        "PATCH",
        platform_url(f"/tickets/{new_ticket_id}"),
        data={"status": "in_progress", "priority": "urgent"},
    )
    expect(status == 200, f"PATCH /tickets/<id> \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true on patch", body)
    patched = body.get("ticket")
    expect(patched.get("rawStatus") == "in_progress", "status flipped", patched)
    expect(patched.get("rawPriority") == "urgent", "priority flipped", patched)

    step("POST /tickets/<id>/replies creates a reply + audits")
    status, body = s8_owner.request(
        "POST",
        platform_url(f"/tickets/{new_ticket_id}/replies"),
        data={"body": "E2E reply from owner@subpilot.dev"},
    )
    expect(status == 201, f"POST /tickets/<id>/replies \u2192 201 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true on reply", body)
    reply = body.get("reply")
    expect(isinstance(reply, dict) and reply.get("id"), "reply has id", body)
    expect(reply.get("body") == "E2E reply from owner@subpilot.dev", "reply.body persisted", reply)
    # Verify reply visible on detail.
    status, body = s8_owner.request("GET", platform_url(f"/tickets/{new_ticket_id}"))
    expect(status == 200 and isinstance(body.get("ticket", {}).get("replies"), list)
           and len(body["ticket"]["replies"]) >= 1,
           "reply appears in ticket detail", body)

    step("GET /kyc/<merchant_id> returns FE-shape (lazy-creates if missing)")
    status, body = s8_owner.request("GET", platform_url(f"/kyc/{target_mid}"))
    expect(status == 200, f"GET /kyc/<merchant_id> \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true on kyc get", body)
    kyc = body.get("kyc")
    expect(isinstance(kyc, dict), "kyc is dict", body)
    for key in ("merchantId", "status", "level", "documents", "flags",
                "notes", "submittedAt", "reviewedAt", "reviewer"):
        expect(key in kyc, f"kyc.{key} present", kyc)
    expect(kyc["merchantId"] == target_mid, "kyc.merchantId matches", kyc)

    step("PATCH /kyc/<merchant_id> updates status/level + audits")
    status, body = s8_owner.request(
        "PATCH",
        platform_url(f"/kyc/{target_mid}"),
        data={
            "status": "verified",
            "level": "tier_3",
            "notes": "E2E platform-admin verification",
        },
    )
    expect(status == 200, f"PATCH /kyc/<merchant_id> \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true on kyc patch", body)
    kyc = body.get("kyc")
    expect(kyc.get("status") == "Verified", "status normalized to Verified", kyc)
    expect(kyc.get("level") == "Tier 3", "level normalized to Tier 3", kyc)
    expect(kyc.get("notes") == "E2E platform-admin verification", "notes persisted", kyc)
    expect(isinstance(kyc.get("reviewedAt"), str) and kyc["reviewedAt"],
           "reviewedAt populated", kyc)

    step("Tickets/KYC unknowns return 404")
    status, body = s8_owner.request(
        "GET", platform_url("/tickets/00000000-0000-0000-0000-000000000000")
    )
    expect(status == 404, f"GET unknown ticket \u2192 404 (got {status})", body)
    status, body = s8_owner.request(
        "PATCH",
        platform_url("/tickets/00000000-0000-0000-0000-000000000000"),
        data={"status": "open"},
    )
    expect(status == 404, f"PATCH unknown ticket \u2192 404 (got {status})", body)
    status, body = s8_owner.request(
        "POST",
        platform_url("/tickets/00000000-0000-0000-0000-000000000000/replies"),
        data={"body": "unknown"},
    )
    expect(status == 404, f"POST reply unknown ticket \u2192 404 (got {status})", body)
    status, body = s8_owner.request(
        "GET", platform_url("/kyc/00000000-0000-0000-0000-000000000000")
    )
    expect(status == 404, f"GET kyc unknown merchant \u2192 404 (got {status})", body)

    step("Merchant user CANNOT access /platform/tickets + /platform/kyc")
    status, _ = iso.request("GET", platform_url("/tickets"))
    expect(status in (401, 403),
           f"GET /tickets with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request(
        "POST",
        platform_url("/tickets"),
        data={"merchant_id": target_mid, "subject": "blocked"},
    )
    expect(status in (401, 403),
           f"POST /tickets with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request("GET", platform_url(f"/tickets/{new_ticket_id}"))
    expect(status in (401, 403),
           f"GET /tickets/<id> with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request(
        "PATCH",
        platform_url(f"/tickets/{new_ticket_id}"),
        data={"status": "closed"},
    )
    expect(status in (401, 403),
           f"PATCH /tickets/<id> with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request(
        "POST",
        platform_url(f"/tickets/{new_ticket_id}/replies"),
        data={"body": "blocked"},
    )
    expect(status in (401, 403),
           f"POST reply with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request("GET", platform_url(f"/kyc/{target_mid}"))
    expect(status in (401, 403),
           f"GET /kyc with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request(
        "PATCH",
        platform_url(f"/kyc/{target_mid}"),
        data={"status": "rejected"},
    )
    expect(status in (401, 403),
           f"PATCH /kyc with merchant session \u2192 401/403 (got {status})")

    # ------------------------------------------------------------------ S9
    # Team management — Owner-gated invite/update/suspend, plus public
    # accept-invite path.

    s9_owner = Client("s9-owner")
    sign_in_admin(s9_owner, ADMIN_OWNER_EMAIL, ADMIN_OWNER_PASSWORD)
    s9_ops = Client("s9-ops")
    sign_in_admin(s9_ops, ADMIN_OPS_EMAIL, ADMIN_OPS_PASSWORD)

    step("Team list returns paginated FE-shape rows")
    status, body = s9_owner.request("GET", platform_url("/team"))
    expect(status == 200, f"GET /team \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "ok=true on team list", body)
    rows = body.get("results") if isinstance(body, dict) else None
    expect(isinstance(rows, list) and len(rows) >= 3, "team list has >= 3 admins (seeded)", body)
    sample = rows[0]
    for key in ("id", "rawId", "name", "email", "role", "rawRole",
                "status", "rawStatus", "mfa", "lastActive", "invitedBy",
                "initials", "createdAt"):
        expect(key in sample, f"team row has {key}", sample)
    expect(sample.get("role") in {"Owner", "Operator", "Support", "Read-only"},
           "team row role is FE-label", sample)

    step("Team list filters by role and q")
    status, body = s9_owner.request("GET", platform_url("/team?role=owner"))
    expect(status == 200, f"GET /team?role=owner \u2192 200 (got {status})", body)
    rows = body.get("results", [])
    expect(all(r.get("role") == "Owner" for r in rows),
           "every result has role=Owner when filtered", rows)
    status, body = s9_owner.request("GET", platform_url("/team?q=ops"))
    expect(status == 200, f"GET /team?q=ops \u2192 200 (got {status})", body)
    expect(any("ops" in (r.get("email") or "").lower() for r in body.get("results", [])),
           "q=ops returns ops admin", body)

    invitee_email = "newhire@subpilot.dev"
    step("POST /team/invite as Owner creates Invited admin + token")
    status, body = s9_owner.request(
        "POST",
        platform_url("/team/invite"),
        data={
            "email": invitee_email,
            "display_name": "New Hire",
            "role": "support",
        },
    )
    if status not in (200, 201):
        # If the address already exists from an earlier run, surface it cleanly.
        expect(False, f"POST /team/invite \u2192 201 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "invite ok=true", body)
    invited_admin = body.get("admin", {}) if isinstance(body, dict) else {}
    invite = body.get("invite", {}) if isinstance(body, dict) else {}
    expect(invited_admin.get("email") == invitee_email, "admin.email matches", body)
    expect(invited_admin.get("status") == "Invited", "admin.status == Invited", body)
    expect(invited_admin.get("role") == "Support", "admin.role normalized", body)
    invitee_raw_id = invited_admin.get("rawId")
    expect(isinstance(invitee_raw_id, str) and len(invitee_raw_id) > 0,
           "admin.rawId present", body)
    invite_token = invite.get("token")
    expect(isinstance(invite_token, str) and len(invite_token) > 16,
           "invite.token present", body)
    expect(isinstance(invite.get("expiresAt"), str), "invite.expiresAt present", body)
    expect(isinstance(invite.get("url"), str) and invite_token in invite["url"],
           "invite.url contains token", body)

    step("POST /team/accept-invite activates the admin")
    public = Client("s9-public")
    status, body = public.request(
        "POST",
        platform_url("/team/accept-invite"),
        data={"token": invite_token, "password": "Subpilot1!"},
    )
    expect(status == 200, f"POST /team/accept-invite \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "accept ok=true", body)
    accepted = body.get("admin", {}) if isinstance(body, dict) else {}
    expect(accepted.get("status") == "Active", "admin.status == Active after accept", body)
    # Replaying the token should now fail.
    status, body = public.request(
        "POST",
        platform_url("/team/accept-invite"),
        data={"token": invite_token, "password": "Subpilot1!"},
    )
    expect(status == 400, f"replaying accept token \u2192 400 (got {status})", body)
    # New admin can sign in.
    invited_client = Client("s9-invited")
    status, body = invited_client.request(
        "POST",
        platform_url("/auth/sign-in"),
        data={"email": invitee_email, "password": "Subpilot1!"},
    )
    expect(status == 200 and isinstance(body, dict) and body.get("ok") is True,
           "newly-accepted admin can sign in", body)

    step("PATCH /team/<id> as Owner updates role + audits")
    status, body = s9_owner.request(
        "PATCH",
        platform_url(f"/team/{invitee_raw_id}"),
        data={"role": "operator", "display_name": "New Hire (Promoted)"},
    )
    expect(status == 200, f"PATCH /team/<id> \u2192 200 (got {status})", body)
    updated = body.get("admin", {}) if isinstance(body, dict) else {}
    expect(updated.get("role") == "Operator", "role flipped to Operator", body)
    expect(updated.get("name") == "New Hire (Promoted)", "display_name updated", body)

    step("POST /team/<id>/suspend flips status + audits")
    status, body = s9_owner.request(
        "POST",
        platform_url(f"/team/{invitee_raw_id}/suspend"),
    )
    expect(status == 200, f"POST /team/<id>/suspend \u2192 200 (got {status})", body)
    suspended = body.get("admin", {}) if isinstance(body, dict) else {}
    expect(suspended.get("status") == "Suspended", "status flipped to Suspended", body)

    step("POST /team/<id>/reactivate restores status + audits")
    status, body = s9_owner.request(
        "POST",
        platform_url(f"/team/{invitee_raw_id}/reactivate"),
    )
    expect(status == 200, f"POST /team/<id>/reactivate \u2192 200 (got {status})", body)
    reactivated = body.get("admin", {}) if isinstance(body, dict) else {}
    expect(reactivated.get("status") == "Active", "status restored to Active", body)

    step("Team unknowns return 404")
    unknown = "00000000-0000-0000-0000-000000000000"
    status, _ = s9_owner.request("GET", platform_url(f"/team/{unknown}"))
    expect(status == 404, f"GET unknown team member \u2192 404 (got {status})")
    status, _ = s9_owner.request(
        "PATCH",
        platform_url(f"/team/{unknown}"),
        data={"role": "operator"},
    )
    expect(status == 404, f"PATCH unknown team member \u2192 404 (got {status})")
    status, _ = s9_owner.request("POST", platform_url(f"/team/{unknown}/suspend"))
    expect(status == 404, f"POST suspend unknown member \u2192 404 (got {status})")

    step("Operator gets 403 on invite / update / suspend (Owner-gated)")
    status, body = s9_ops.request(
        "POST",
        platform_url("/team/invite"),
        data={"email": "blocked@subpilot.dev", "role": "support"},
    )
    expect(status == 403, f"POST /team/invite as ops \u2192 403 (got {status})", body)
    status, body = s9_ops.request(
        "PATCH",
        platform_url(f"/team/{invitee_raw_id}"),
        data={"role": "support"},
    )
    expect(status == 403, f"PATCH /team/<id> as ops \u2192 403 (got {status})", body)
    status, body = s9_ops.request(
        "POST",
        platform_url(f"/team/{invitee_raw_id}/suspend"),
    )
    expect(status == 403, f"POST /team/<id>/suspend as ops \u2192 403 (got {status})", body)
    status, body = s9_ops.request(
        "POST",
        platform_url(f"/team/{invitee_raw_id}/reactivate"),
    )
    expect(status == 403, f"POST /team/<id>/reactivate as ops \u2192 403 (got {status})", body)
    # Operator can still LIST.
    status, body = s9_ops.request("GET", platform_url("/team"))
    expect(status == 200, f"GET /team as ops \u2192 200 (got {status})", body)

    step("Merchant user CANNOT access /platform/team")
    status, _ = iso.request("GET", platform_url("/team"))
    expect(status in (401, 403),
           f"GET /team with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request(
        "POST",
        platform_url("/team/invite"),
        data={"email": "blocked@subpilot.dev"},
    )
    expect(status in (401, 403),
           f"POST /team/invite with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request("GET", platform_url(f"/team/{invitee_raw_id}"))
    expect(status in (401, 403),
           f"GET /team/<id> with merchant session \u2192 401/403 (got {status})")

    # ----------------------------------------------------------------- S10
    # Settings singleton — Owner-gated PATCH, GET open to any admin.

    s10_owner = Client("s10-owner")
    sign_in_admin(s10_owner, ADMIN_OWNER_EMAIL, ADMIN_OWNER_PASSWORD)
    s10_ops = Client("s10-ops")
    sign_in_admin(s10_ops, ADMIN_OPS_EMAIL, ADMIN_OPS_PASSWORD)

    step("GET /platform/settings returns FE-shape singleton")
    status, body = s10_owner.request("GET", platform_url("/settings"))
    expect(status == 200, f"GET /settings \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "settings ok=true", body)
    settings = body.get("settings") if isinstance(body, dict) else None
    expect(isinstance(settings, dict), "settings object present", body)
    for key in ("id", "key", "policy", "adapterStatus", "updatedAt"):
        expect(key in settings, f"settings has {key}", settings)
    policy = settings.get("policy", {})
    expect(isinstance(policy, dict) and "defaultRetryAttempts" in policy,
           "policy.defaultRetryAttempts present", settings)
    expect(isinstance(policy.get("enforcedMfa"), bool),
           "policy.enforcedMfa is bool", settings)
    adapters = settings.get("adapterStatus", [])
    expect(isinstance(adapters, list) and len(adapters) >= 1,
           "adapterStatus list has >= 1 row", settings)
    if adapters:
        for key in ("name", "role", "uptime", "status"):
            expect(key in adapters[0], f"adapter row has {key}", adapters[0])

    step("GET /platform/settings open to any admin role")
    status, body = s10_ops.request("GET", platform_url("/settings"))
    expect(status == 200, f"GET /settings as ops \u2192 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True,
           "ops can read settings", body)

    step("PATCH /platform/settings as Owner merges policy + audits")
    original_attempts = policy.get("defaultRetryAttempts", 4)
    new_attempts = int(original_attempts) + 1
    status, body = s10_owner.request(
        "PATCH",
        platform_url("/settings"),
        data={"policy": {"defaultRetryAttempts": new_attempts,
                          "defaultCooldownHours": 9}},
    )
    expect(status == 200, f"PATCH /settings \u2192 200 (got {status})", body)
    updated = body.get("settings", {}) if isinstance(body, dict) else {}
    upd_policy = updated.get("policy", {})
    expect(upd_policy.get("defaultRetryAttempts") == new_attempts,
           "policy.defaultRetryAttempts updated", updated)
    expect(upd_policy.get("defaultCooldownHours") == 9,
           "policy.defaultCooldownHours updated", updated)
    # Merge semantics — untouched defaults are preserved.
    expect(upd_policy.get("webhookSignatureHeader") == policy.get("webhookSignatureHeader"),
           "untouched policy keys preserved (merge semantics)", updated)
    expect(isinstance(upd_policy.get("enforcedMfa"), bool),
           "policy.enforcedMfa retained", updated)
    # Idempotency — re-sending same value should not error.
    status, body = s10_owner.request(
        "PATCH",
        platform_url("/settings"),
        data={"policy": {"defaultRetryAttempts": new_attempts}},
    )
    expect(status == 200, f"PATCH /settings (no-op) \u2192 200 (got {status})", body)

    step("PATCH /platform/settings replaces adapter_status via camelCase")
    new_adapters = [
        {
            "name": "Adapter A",
            "role": "Primary card processor",
            "uptime": "99.99%",
            "latencyP95": "402 ms",
            "failoverTrigger": "5xx > 4% over 3 minutes",
            "region": "Lagos · Frankfurt",
            "status": "Operational",
        },
        {
            "name": "Adapter B",
            "role": "Backup",
            "uptime": "99.80%",
            "latencyP95": "701 ms",
            "failoverTrigger": "5xx > 6% over 5 minutes",
            "region": "Lagos · Dublin",
            "status": "Monitoring",
        },
    ]
    status, body = s10_owner.request(
        "PATCH",
        platform_url("/settings"),
        data={"adapterStatus": new_adapters},
    )
    expect(status == 200, f"PATCH /settings adapterStatus \u2192 200 (got {status})", body)
    after = body.get("settings", {}) if isinstance(body, dict) else {}
    after_adapters = after.get("adapterStatus", [])
    expect(isinstance(after_adapters, list) and len(after_adapters) == 2,
           "adapterStatus replaced (length == 2)", after)
    expect(after_adapters[0].get("uptime") == "99.99%",
           "adapterStatus[0].uptime updated", after)

    step("PATCH /platform/settings as Operator returns 403")
    status, body = s10_ops.request(
        "PATCH",
        platform_url("/settings"),
        data={"policy": {"defaultRetryAttempts": 99}},
    )
    expect(status == 403, f"PATCH /settings as ops \u2192 403 (got {status})", body)

    step("PATCH /platform/settings rejects bad payloads")
    status, body = s10_owner.request(
        "PATCH",
        platform_url("/settings"),
        data={"policy": "not-an-object"},
    )
    expect(status == 400, f"PATCH bad policy \u2192 400 (got {status})", body)
    status, body = s10_owner.request(
        "PATCH",
        platform_url("/settings"),
        data={"adapter_status": [{"role": "Missing name"}]},
    )
    expect(status == 400, f"PATCH adapter without name \u2192 400 (got {status})", body)

    step("Merchant user CANNOT access /platform/settings")
    status, _ = iso.request("GET", platform_url("/settings"))
    expect(status in (401, 403),
           f"GET /settings with merchant session \u2192 401/403 (got {status})")
    status, _ = iso.request(
        "PATCH",
        platform_url("/settings"),
        data={"policy": {"defaultRetryAttempts": 1}},
    )
    expect(status in (401, 403),
           f"PATCH /settings with merchant session \u2192 401/403 (got {status})")

    # ----------------------------------------------------------------- S11
    # Analytics bundled snapshot — cross-tenant revenue, retention, funnels.

    s11_owner = Client("s11-owner")
    sign_in_admin(s11_owner, ADMIN_OWNER_EMAIL, ADMIN_OWNER_PASSWORD)
    s11_ops = Client("s11-ops")
    sign_in_admin(s11_ops, ADMIN_OPS_EMAIL, ADMIN_OPS_PASSWORD)

    step("GET /platform/analytics returns FE-shape bundle")
    status, body = s11_owner.request("GET", platform_url("/analytics"))
    expect(status == 200, f"GET /analytics \u2192 200 (got {status})", body)
    expect(body.get("ok") is True, "ok=True", body)
    analytics = body.get("analytics") or {}
    expect(isinstance(analytics, dict), "analytics is object", body)
    expected_keys = {
        "range", "revenueSeries", "planRevenue", "regionRevenue",
        "retentionCohorts", "acquisitionFunnel", "paymentMethodMix",
        "recoveryFunnel", "topMerchantsByRevenue",
    }
    missing = expected_keys - set(analytics.keys())
    expect(not missing, f"analytics has all FE keys (missing={missing})", analytics)
    revenue_series = analytics.get("revenueSeries") or []
    expect(isinstance(revenue_series, list) and len(revenue_series) == 12,
           f"revenueSeries length=12 default (got {len(revenue_series)})", revenue_series)
    sample_point = revenue_series[-1]
    for k in ("month", "mrr", "newMrr", "churnMrr", "expansionMrr", "gmv", "activeSubs"):
        expect(k in sample_point, f"revenueSeries[-1] has '{k}'", sample_point)
    cohorts = analytics.get("retentionCohorts") or []
    expect(len(cohorts) == 6 and len(cohorts[0].get("retention") or []) == 6,
           "retentionCohorts is 6x6 triangle", cohorts)
    funnel = analytics.get("recoveryFunnel") or {}
    for k in ("failedThisMonth", "recovered", "pending", "lost",
              "recoveryRate", "recoveredMrr", "byChannel"):
        expect(k in funnel, f"recoveryFunnel has '{k}'", funnel)
    expect(len(funnel.get("byChannel") or []) == 4,
           "recoveryFunnel.byChannel has 4 rows", funnel)

    step("Range filter (3m/6m/12m) controls revenueSeries length")
    for rng, expected_len in (("3m", 3), ("6m", 6), ("12m", 12)):
        status, body = s11_owner.request("GET", platform_url(f"/analytics?range={rng}"))
        expect(status == 200, f"GET /analytics?range={rng} \u2192 200 (got {status})", body)
        got = body.get("analytics", {}).get("revenueSeries") or []
        expect(len(got) == expected_len,
               f"range={rng} \u2192 revenueSeries len={expected_len} (got {len(got)})", body)
        expect(body.get("analytics", {}).get("range") == rng,
               f"echoes range={rng}", body)

    step("Invalid range falls back to default (12m)")
    status, body = s11_owner.request("GET", platform_url("/analytics?range=bogus"))
    expect(status == 200, f"GET /analytics?range=bogus \u2192 200 (got {status})", body)
    fallback = body.get("analytics", {})
    expect(fallback.get("range") == "12m",
           f"invalid range falls back to 12m (got {fallback.get('range')})", fallback)
    expect(len(fallback.get("revenueSeries") or []) == 12,
           "fallback returns 12 points", fallback)

    step("?refresh=true bypasses cache and recomputes snapshot")
    status, body = s11_owner.request("GET", platform_url("/analytics?range=6m&refresh=true"))
    expect(status == 200, f"GET /analytics?refresh=true \u2192 200 (got {status})", body)
    expect(len(body.get("analytics", {}).get("revenueSeries") or []) == 6,
           "refresh preserves range", body)

    step("/platform/analytics open to any admin role (Operator)")
    status, body = s11_ops.request("GET", platform_url("/analytics?range=3m"))
    expect(status == 200, f"Operator GET /analytics \u2192 200 (got {status})", body)
    expect(body.get("ok") is True, "Operator gets ok=True", body)

    step("Merchant user CANNOT access /platform/analytics")
    status, _ = iso.request("GET", platform_url("/analytics"))
    expect(status in (401, 403),
           f"GET /analytics with merchant session → 401/403 (got {status})")
    
    # ----------------------------------------------------------------- S13
    # Per-tab merchant endpoints + per-merchant feature flag config.
    step("Subscriptions tab returns paginated FE-shape rows")
    status, body = s11_owner.request(
        "GET", platform_url(f"/merchants/{merchant_id}/subscriptions?page=1&pageSize=10")
    )
    expect(status == 200, f"GET /merchants/<id>/subscriptions → 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "subs ok=true", body)
    for key in ("rows", "stats", "planMix", "total", "page", "pageSize"):
        expect(key in body, f"subs.{key} present", body)
    expect(isinstance(body["rows"], list), "subs.rows is list", body)
    expect(isinstance(body["stats"], dict), "subs.stats is dict", body)

    step("Payments tab returns paginated FE-shape rows")
    status, body = s11_owner.request(
        "GET", platform_url(f"/merchants/{merchant_id}/payments?page=1&pageSize=10")
    )
    expect(status == 200, f"GET /merchants/<id>/payments → 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "payments ok=true", body)
    for key in ("rows", "total", "page", "pageSize"):
        expect(key in body, f"payments.{key} present", body)

    step("Webhooks tab returns paginated FE-shape rows")
    status, body = s11_owner.request(
        "GET", platform_url(f"/merchants/{merchant_id}/webhooks?page=1&pageSize=10")
    )
    expect(status == 200, f"GET /merchants/<id>/webhooks → 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "webhooks ok=true", body)
    for key in ("rows", "total", "page", "pageSize"):
        expect(key in body, f"webhooks.{key} present", body)

    step("Audit tab returns paginated FE-shape rows")
    status, body = s11_owner.request(
        "GET", platform_url(f"/merchants/{merchant_id}/audit?page=1&pageSize=10")
    )
    expect(status == 200, f"GET /merchants/<id>/audit → 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "audit ok=true", body)
    for key in ("rows", "total", "page", "pageSize"):
        expect(key in body, f"audit.{key} present", body)

    step("Config GET returns defaults + catalog")
    status, body = s11_owner.request("GET", platform_url(f"/merchants/{merchant_id}/config"))
    expect(status == 200, f"GET /merchants/<id>/config → 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "config ok=true", body)
    cfg = body.get("config") or {}
    for key in ("merchantId", "limits", "retryPolicy", "featureFlags", "catalog"):
        expect(key in cfg, f"config.{key} present", body)
    expect(isinstance(cfg["featureFlags"], list), "featureFlags is list", body)
    catalog_keys = {entry["key"] for entry in cfg["catalog"]}
    expect({"tokenized_cards", "manual_refunds", "promo_codes", "smart_routing"} <= catalog_keys,
           "all known catalog entries present", body)

    step("Config PATCH merges flags + limits as Owner")
    status, body = s11_owner.request(
        "PATCH",
        platform_url(f"/merchants/{merchant_id}/config"),
        data={
            "featureFlags": {"manual_refunds": False},
            "limits": {"monthlyVolumeCapMinor": 12345600},
        },
    )
    expect(status == 200, f"PATCH /merchants/<id>/config → 200 (got {status})", body)
    expect(isinstance(body, dict) and body.get("ok") is True, "patch ok=true", body)
    new_cfg = body.get("config") or {}
    flag_map = {entry["key"]: entry["enabled"] for entry in new_cfg.get("featureFlags", [])}
    expect(flag_map.get("manual_refunds") is False, "manual_refunds toggled off", body)
    expect(new_cfg.get("limits", {}).get("monthlyVolumeCapMinor") == 12345600,
           "limits.monthlyVolumeCapMinor persisted", body)
    # Restore for downstream cleanliness.
    s11_owner.request(
        "PATCH",
        platform_url(f"/merchants/{merchant_id}/config"),
        data={"featureFlags": {"manual_refunds": True}},
    )

    step("Config PATCH as Operator returns 403 (Owner-only)")
    status, body = s11_ops.request(
        "PATCH",
        platform_url(f"/merchants/{merchant_id}/config"),
        data={"featureFlags": {"manual_refunds": False}},
    )
    expect(status == 403, f"Operator PATCH config → 403 (got {status})", body)

    # ----------------------------------------------------------------- S12
    # Un-authed sweep: every protected endpoint must reject anonymous callers
    # with 401/403. Uses a fresh Client (no cookies). Excludes the few routes
    # that are intentionally anon-accessible:
    #   - POST /auth/sign-in, POST /auth/sign-out, POST /auth/forgot,
    #     POST /team/accept-invite (all AllowAny by design — idempotent or
    #     credential-bearing)
    #   - GET  /auth/me (returns 200 with {user: null})
    step("Un-authed sweep — every protected endpoint returns 401/403")
    anon = Client("anon-sweep")
    bogus = "00000000-0000-0000-0000-000000000000"
    unauthed_targets: list[tuple[str, str]] = [
        # Health
        ("GET",  "/ping"),
        # Overview
        ("GET",  "/overview"),
        # Merchants
        ("GET",  "/merchants"),
        ("GET",  f"/merchants/{bogus}"),
        ("POST", f"/merchants/{bogus}/suspend"),
        ("POST", f"/merchants/{bogus}/reactivate"),
        ("POST", f"/merchants/{bogus}/notes"),
        # Payments
        ("GET",  "/payments"),
        ("POST", f"/payments/{bogus}/refund"),
        # Webhooks
        ("GET",  "/webhooks/deliveries"),
        ("POST", f"/webhooks/deliveries/{bogus}/retry"),
        ("GET",  "/webhooks/health"),
        # API keys
        ("GET",  "/api-keys"),
        ("POST", f"/api-keys/{bogus}/revoke"),
        # Support
        ("GET",  "/tickets"),
        ("POST", "/tickets"),
        ("GET",  f"/tickets/{bogus}"),
        ("PATCH", f"/tickets/{bogus}"),
        ("POST", f"/tickets/{bogus}/replies"),
        ("GET",  f"/kyc/{bogus}"),
        ("PATCH", f"/kyc/{bogus}"),
        # Team
        ("GET",  "/team"),
        ("POST", "/team/invite"),
        ("GET",  f"/team/{bogus}"),
        ("PATCH", f"/team/{bogus}"),
        ("POST", f"/team/{bogus}/suspend"),
        ("POST", f"/team/{bogus}/reactivate"),
        # Settings
        ("GET",  "/settings"),
        ("PATCH", "/settings"),
        # Analytics
        ("GET",  "/analytics"),
        # S13: per-tab + per-merchant config
        ("GET",  f"/merchants/{bogus}/subscriptions"),
        ("GET",  f"/merchants/{bogus}/payments"),
        ("GET",  f"/merchants/{bogus}/webhooks"),
        ("GET",  f"/merchants/{bogus}/audit"),
        ("GET",  f"/merchants/{bogus}/config"),
        ("PATCH", f"/merchants/{bogus}/config"),
    ]
    blocked = 0
    for method, path in unauthed_targets:
        payload = {} if method in ("POST", "PATCH") else None
        status, body = anon.request(method, platform_url(path), data=payload)
        expect(
            status in (401, 403),
            f"{method} {path} anon → 401/403 (got {status})",
            body,
        )
        blocked += 1
    print(f"    {DIM}swept {blocked} endpoints{RESET}")
    
    print(f"\n{GREEN}{BOLD}All platform-admin E2E steps passed.{RESET}\n")


if __name__ == "__main__":
    try:
        run()
    except TestError as exc:
        print(f"\n{RED}{BOLD}E2E aborted:{RESET} {exc}", file=sys.stderr)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001
        print(f"\n{RED}{BOLD}Unexpected error:{RESET} {exc!r}", file=sys.stderr)
        sys.exit(2)
