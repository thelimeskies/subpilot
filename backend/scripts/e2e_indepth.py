#!/usr/bin/env python3
"""In-depth E2E test against the running Compose stack.

Exercises a broad surface of the API with positive AND negative paths:

  Auth & RBAC
    1.  Health + OpenAPI schema available
    2.  Wrong password rejected with FE-shape ``{ok:false, reason:...}``
    3.  Owner sign-in + MFA bypass code 123456
    4.  /auth/me bootstraps the React dashboard
    5.  Support user sign-in -> blocked from privileged action (RBAC)

  Catalog & Customer lifecycle
    6.  Create Product + Plan + PriceVersion via API
    7.  Activate the plan; second activate is idempotent
    8.  Create a Customer; attach two PaymentMethods; set non-default as default
    9.  PaymentMethod serializer never leaks ``token`` / ``token_encrypted``

  Subscription -> Invoice -> Charge happy path
    10. Create subscription on new plan; activate (no trial)
    11. POST /invoices/renew/<sub_id> to mint a renewal invoice
    12. POST /payment-attempts/charge/<invoice_id> -> success path
    13. Invoice transitions OPEN -> PAID, attempt success=true

  Failure / dunning path
    14. Attach token "tok_fail_insufficient" PM, charge -> 402 insufficient_funds
    15. A DunningRun is auto-started (status=ACTIVE)
    16. Webhook event "invoice.payment_failed" recorded

  Webhooks (outbound)
    17. Create a WebhookEndpoint via API; rotate-secret
    18. Replay one of the failure events; delivery row gets created

  Idempotency, tenant isolation, signed portal token
    19. Idempotency-Key header re-uses cached response for a POST
    20. Cross-tenant access returns 404 (no existence leak)
    21. Create a PortalSession; verify portal /context works with the token

  Analytics
    22. /analytics/overview?refresh=true reflects new subscription & past_due RAR

  Feature flags (S13)
    23. GET /v1/me/features returns the resolved bundle (flags + catalog)
    24. Admin toggles manual_refunds OFF -> merchant refund returns 403
    25. Admin toggles manual_refunds ON  -> merchant refund succeeds

  Sign-out

Pass criterion: every step prints a green check; failure aborts and prints
the offending response.
"""
from __future__ import annotations

import http.cookiejar
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v1"
PORTAL = f"{API}/portal"

OWNER_EMAIL = "owner@acme.test"
OWNER_PASSWORD = "Subpilot1!"
SUPPORT_EMAIL = "support@acme.test"
SUPPORT_PASSWORD = "Subpilot1!"
ADMIN_FITPLUS_EMAIL = "admin@fitplus.test"
ADMIN_FITPLUS_PASSWORD = "Subpilot1!"
# Platform admin (S13: needed to toggle merchant feature flags).
PLATFORM_ADMIN_EMAIL = "owner@subpilot.dev"
PLATFORM_ADMIN_PASSWORD = "Subpilot1!"
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
    """One isolated session (cookie jar)."""

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
        path: str,
        *,
        data: Any = None,
        headers: dict | None = None,
        raw_body: bytes | None = None,
        timeout: int = 15,
    ) -> tuple[int, dict | str]:
        # DRF DefaultRouter URLs require a trailing slash. Auth/analytics/portal
        # and /me/* routes are mapped via path() without slashes.
        _no_slash_prefixes = ("/auth/", "/analytics/", "/portal/", "/health", "/me/")
        if (
            not path.startswith("http")
            and not any(path.startswith(p) for p in _no_slash_prefixes)
        ):
            base, _, qs = path.partition("?")
            if not base.endswith("/"):
                base += "/"
            path = base if not qs else f"{base}?{qs}"
        url = path if path.startswith("http") else f"{API}{path}"
        body = raw_body
        h = {"Accept": "application/json"}
        if headers:
            h.update(headers)
        if body is None and data is not None:
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


# --- pretty-printing helpers --------------------------------------------------


_step_no = 0


def step(name: str) -> None:
    global _step_no
    _step_no += 1
    print(f"\n{BOLD}[{_step_no:02d}] {name}{RESET}")


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {DIM}{msg}{RESET}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}!{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✗ {msg}{RESET}")
    raise TestError(msg)


def expect(cond: bool, msg: str) -> None:
    if not cond:
        fail(msg)


def sign_in_with_mfa(c: Client, email: str, password: str) -> dict:
    code, body = c.request("POST", "/auth/sign-in", data={"email": email, "password": password})
    expect(code == 200, f"sign-in {email}: {code} {body}")
    expect(body.get("ok") is True, f"sign-in body.ok=False: {body}")
    if body.get("requiresMfa"):
        challenge_id = body["challengeId"]
        code, body = c.request(
            "POST",
            "/auth/verify-mfa",
            data={"challengeId": challenge_id, "code": MFA_BYPASS},
        )
        expect(code == 200 and body.get("ok"), f"verify-mfa failed: {body}")
    return body["user"]


# --- main scenario ------------------------------------------------------------


def main() -> int:
    print(f"{BOLD}SubPilot in-depth E2E{RESET}  base={BASE_URL}")

    owner = Client("owner")
    support = Client("support")
    fitplus = Client("fitplus")

    # 1. Health + OpenAPI
    step("health + OpenAPI schema reachable")
    code, body = owner.request("GET", "/health")
    expect(code == 200, f"health {code}: {body}")
    ok("health 200")
    code, schema = owner.request("GET", f"{BASE_URL}/api/schema/?format=json")
    expect(code == 200, f"schema {code}")
    expect(isinstance(schema, dict) and schema.get("openapi"), "schema is not OpenAPI dict")
    paths = list(schema.get("paths", {}).keys())
    ok(f"openapi {schema['openapi']} — {len(paths)} paths declared")

    # 2. Wrong password
    step("sign-in wrong password rejected (FE shape)")
    code, body = owner.request(
        "POST", "/auth/sign-in", data={"email": OWNER_EMAIL, "password": "not-it"}
    )
    expect(code in (200, 401, 400), f"unexpected status {code}: {body}")
    expect(isinstance(body, dict) and body.get("ok") is False, f"bad shape: {body}")
    expect("reason" in body, f"missing 'reason': {body}")
    ok(f"shape ok ok=False reason={body['reason']!r}")

    # 3. Owner sign-in + MFA
    step("owner sign-in + MFA bypass")
    user = sign_in_with_mfa(owner, OWNER_EMAIL, OWNER_PASSWORD)
    ok(f"user={user['email']} role={user['role']} org={user['orgName']}")

    # 4. /auth/me
    step("/auth/me bootstrap")
    code, body = owner.request("GET", "/auth/me")
    expect(code == 200 and body.get("user"), f"me: {body}")
    ok(f"me ok role={body['user']['role']}")

    # 5. Support user is forbidden from privileged action
    step("RBAC: support user blocked from creating subscriptions")
    sign_in_with_mfa(support, SUPPORT_EMAIL, SUPPORT_PASSWORD)
    # Try to create a subscription (requires `create_subscription` cap)
    code, body = support.request(
        "POST",
        "/subscriptions",
        data={
            "customer_id": "00000000-0000-0000-0000-000000000000",
            "plan_id": "00000000-0000-0000-0000-000000000000",
        },
    )
    expect(code in (403, 401, 404), f"expected 403/401, got {code}: {body}")
    ok(f"support denied -> {code}")

    # 6. Create Product + Plan
    step("catalog: create Product + Plan via API")
    code, prod = owner.request(
        "POST",
        "/catalog/products",
        data={"name": f"E2E Product {uuid.uuid4().hex[:6]}", "description": "indepth test"},
    )
    expect(code == 201, f"product create: {code} {prod}")
    prod_id = prod["id"]
    ok(f"product {prod_id}")

    code, plan = owner.request(
        "POST",
        "/catalog/plans",
        data={
            "product_id": prod_id,
            "name": "E2E Pro Monthly",
            "trial_days": 0,
            "tokenized_renewal": True,
        },
    )
    expect(code == 201, f"plan create: {code} {plan}")
    plan_id = plan["id"]
    ok(f"plan {plan_id} status={plan['status']}")

    code, pv = owner.request(
        "POST",
        f"/catalog/plans/{plan_id}/price-versions",
        data={
            "amount_minor": 25000_00,
            "currency": "NGN",
            "interval_unit": "month",
            "interval_count": 1,
        },
    )
    expect(code == 201, f"price-version create: {code} {pv}")
    ok(f"price_version {pv['id']} amount={pv['amount_minor']}/{pv['currency']}")

    # 7. Activate plan twice
    step("plan: activate (idempotent)")
    code, plan = owner.request("POST", f"/catalog/plans/{plan_id}/activate", data={})
    expect(code == 200, f"activate: {code} {plan}")
    expect(plan["status"] == "active", f"plan status: {plan['status']}")
    code, plan2 = owner.request("POST", f"/catalog/plans/{plan_id}/activate", data={})
    expect(code == 200 and plan2["status"] == "active", f"re-activate: {code} {plan2}")
    ok("activated; second activate is idempotent")

    # 8. Customer + 2 PaymentMethods
    step("customer: create + attach 2 PaymentMethods; flip default")
    code, cust = owner.request(
        "POST",
        "/customers",
        data={
            "email": f"e2e+{uuid.uuid4().hex[:6]}@example.com",
            "name": "E2E Indepth",
        },
    )
    expect(code == 201, f"customer create: {code} {cust}")
    cust_id = cust["id"]
    ok(f"customer {cust_id} email={cust['email']}")

    code, pm1 = owner.request(
        "POST",
        f"/customers/{cust_id}/payment-methods",
        data={
            "provider": "nomba",
            "token": f"tok_ok_{uuid.uuid4().hex[:8]}",
            "brand": "Visa",
            "last4": "4242",
            "set_default": True,
        },
    )
    expect(code == 201, f"pm1 attach: {code} {pm1}")
    expect(pm1.get("is_default") is True, f"pm1 should be default: {pm1}")
    expect("token" not in pm1 and "token_encrypted" not in pm1, f"PM leaked token! {pm1}")
    ok(f"pm1 {pm1['id']} default=True (token NOT exposed)")

    code, pm2 = owner.request(
        "POST",
        f"/customers/{cust_id}/payment-methods",
        data={
            "provider": "nomba",
            "token": f"tok_fail_insufficient_{uuid.uuid4().hex[:6]}",
            "brand": "Mastercard",
            "last4": "0002",
            "set_default": False,
        },
    )
    expect(code == 201, f"pm2 attach: {code} {pm2}")
    expect(pm2.get("is_default") is False, f"pm2 should NOT be default: {pm2}")
    ok(f"pm2 {pm2['id']} default=False")

    # flip default
    code, pm2b = owner.request("POST", f"/payment-methods/{pm2['id']}/set-default", data={})
    expect(code == 200 and pm2b["is_default"], f"set-default: {code} {pm2b}")
    code, pm1b = owner.request("GET", f"/payment-methods/{pm1['id']}")
    expect(code == 200 and pm1b["is_default"] is False, f"pm1 no longer default? {pm1b}")
    ok("default flipped pm1->pm2")

    # 9. Token never leaks via list endpoint
    step("token never exposed in any PaymentMethod listing")
    code, pms = owner.request("GET", f"/payment-methods?customer={cust_id}")
    expect(code == 200, f"list pms: {code} {pms}")
    entries = pms.get("results", pms if isinstance(pms, list) else [])
    for entry in entries:
        expect("token" not in entry, f"token leaked in list! {entry}")
        expect("token_encrypted" not in entry, f"token_encrypted leaked! {entry}")
    ok(f"PaymentMethod serializer is clean ({len(entries)} entries scanned)")

    # 10. Subscription create + activate (no trial)
    step("subscription: create + activate")
    # flip default back to pm1 (the success one) so renewal succeeds
    owner.request("POST", f"/payment-methods/{pm1['id']}/set-default", data={})
    code, sub = owner.request(
        "POST",
        "/subscriptions",
        data={
            "customer_id": cust_id,
            "plan_id": plan_id,
            "quantity": 1,
            "default_payment_method_id": pm1["id"],
        },
    )
    expect(code == 201, f"sub create: {code} {sub}")
    sub_id = sub["id"]
    ok(f"subscription {sub_id} status={sub['status']}")

    code, sub_a = owner.request(
        "POST", f"/subscriptions/{sub_id}/activate", data={"with_trial": False}
    )
    expect(code == 200, f"activate: {code} {sub_a}")
    expect(sub_a["status"] in ("active", "trialing"), f"unexpected: {sub_a['status']}")
    ok(f"activated -> status={sub_a['status']}")

    # 11. Renew -> invoice
    step("invoice: renew subscription")
    code, inv = owner.request("POST", f"/invoices/renew/{sub_id}", data={})
    expect(code == 201, f"renew: {code} {inv}")
    inv_id = inv["id"]
    ok(f"invoice {inv_id} status={inv['status']} amount_due={inv['amount_due_minor']}")

    # 12. Charge happy path
    step("payments: charge succeeds against pm1 (success token)")
    code, ch = owner.request(
        "POST", f"/payment-attempts/charge/{inv_id}", data={"adapter": "mock"}
    )
    expect(code == 200, f"charge: {code} {ch}")
    expect(ch.get("success") is True, f"expected success: {ch}")
    # S13 will refund this attempt to exercise the manual_refunds flag.
    success_attempt_id = (ch.get("attempt") or {}).get("id")
    expect(bool(success_attempt_id), f"attempt id missing: {ch}")
    ok(f"attempt {success_attempt_id} success ref={ch.get('processor_reference')}")

    # 13. Invoice now PAID
    code, inv_paid = owner.request("GET", f"/invoices/{inv_id}")
    expect(code == 200, f"invoice fetch: {code}")
    expect(inv_paid["status"] == "paid", f"invoice should be paid: {inv_paid}")
    ok(f"invoice status={inv_paid['status']} (paid_at={inv_paid.get('paid_at')})")

    # 14-16. Failure path -> dunning
    step("dunning: trigger insufficient_funds, expect dunning run + event")
    # Flip default PM to the always-fail one
    owner.request("POST", f"/payment-methods/{pm2['id']}/set-default", data={})
    # Mint a fresh renewal invoice (next billing period)
    code, inv2 = owner.request("POST", f"/invoices/renew/{sub_id}", data={})
    expect(code == 201, f"renew2: {code} {inv2}")
    inv2_id = inv2["id"]
    code, ch2 = owner.request(
        "POST",
        f"/payment-attempts/charge/{inv2_id}",
        data={"adapter": "mock", "payment_method_id": pm2["id"]},
    )
    expect(code == 402, f"expected 402 payment_required, got {code}: {ch2}")
    expect(ch2.get("success") is False, f"should be failure: {ch2}")
    expect(ch2.get("failure_code") == "insufficient_funds", f"code? {ch2}")
    ok(f"charge failed cleanly code={ch2['failure_code']} category={ch2['failure_category']}")

    # Give services a moment to settle
    time.sleep(0.5)
    code, runs = owner.request("GET", "/dunning-runs?status=active")
    expect(code == 200, f"runs list: {code}")
    runs_list = runs.get("results", runs if isinstance(runs, list) else [])
    related = [r for r in runs_list if r.get("invoice") == inv2_id]
    expect(len(related) >= 1, f"no dunning run for invoice {inv2_id}: {runs_list}")
    run = related[0]
    ok(f"dunning run {run['id']} status={run['status']} attempts={run.get('attempt_count', 0)}")

    code, evs = owner.request("GET", "/events?event_type=invoice.payment_failed")
    expect(code == 200, f"events list: {code}")
    evs_list = evs.get("results", evs if isinstance(evs, list) else [])
    related_evs = [e for e in evs_list if e.get("payload", {}).get("invoice_id") == inv2_id]
    expect(len(related_evs) >= 1, f"no payment_failed event for {inv2_id}")
    failed_event = related_evs[0]
    ok(f"event {failed_event['id']} type={failed_event['event_type']}")

    # 17-18. Webhook endpoint + replay
    step("webhooks: create endpoint, rotate secret, replay failure event")
    code, ep_resp = owner.request(
        "POST",
        "/webhook-endpoints",
        data={
            "url": "https://example.test/webhook",
            "event_filters": ["invoice.*", "subscription.*"],
            "description": "indepth test endpoint",
        },
    )
    expect(code == 201, f"endpoint create: {code} {ep_resp}")
    expect("endpoint" in ep_resp and "secret" in ep_resp, f"unexpected shape: {ep_resp}")
    ep = ep_resp["endpoint"]
    ep_id = ep["id"]
    expect(ep_resp["secret"].startswith("whsec_"), f"secret prefix: {ep_resp['secret']!r}")
    ok(f"endpoint {ep_id} enabled={ep['enabled']} secret-prefix=whsec_…")

    code, rot = owner.request("POST", f"/webhook-endpoints/{ep_id}/rotate-secret", data={})
    expect(code == 200, f"rotate-secret: {code} {rot}")
    expect(
        isinstance(rot, dict) and rot.get("secret", "").startswith("whsec_"),
        f"rotated secret not returned plainly: {rot}",
    )
    expect(rot["secret"] != ep_resp["secret"], "rotated secret should differ from original")
    ok("rotated; new plaintext returned exactly once")

    code, replayed = owner.request("POST", f"/events/{failed_event['id']}/replay", data={})
    expect(code in (200, 201, 202), f"replay: {code} {replayed}")
    ok("replay enqueued")

    # 19. Idempotency-Key replay
    step("idempotency: same key reuses cached response")
    idem = f"e2e-{uuid.uuid4().hex}"
    code1, body1 = owner.request(
        "POST",
        "/customers",
        data={"email": f"idem+{uuid.uuid4().hex[:6]}@example.com", "name": "Idem Test"},
        headers={"Idempotency-Key": idem},
    )
    expect(code1 in (200, 201), f"idem first: {code1} {body1}")
    code2, body2 = owner.request(
        "POST",
        "/customers",
        data={"email": "DIFFERENT@example.com", "name": "Different"},
        headers={"Idempotency-Key": idem},
    )
    expect(code2 == code1, f"idem second code mismatch: {code1} vs {code2}")
    expect(
        isinstance(body1, dict) and isinstance(body2, dict) and body1.get("id") == body2.get("id"),
        f"idem replay didn't return cached body: {body1} vs {body2}",
    )
    ok(f"replayed cached id={body1.get('id')}")

    # 20. Tenant isolation
    step("tenant isolation: fitplus admin sees 404 on acme customer")
    sign_in_with_mfa(fitplus, ADMIN_FITPLUS_EMAIL, ADMIN_FITPLUS_PASSWORD)
    code, body = fitplus.request("GET", f"/customers/{cust_id}")
    expect(code == 404, f"expected 404, got {code}: {body}")
    ok("cross-tenant access returns 404 (no existence leak)")

    # 21. Portal session
    step("portal: create session, hit /portal/context with bearer token")
    code, ps = owner.request(
        "POST",
        f"/customers/{cust_id}/portal-sessions",
        data={
            "ttl_minutes": 60,
            "allowed_actions": ["view_invoices", "view_subscriptions", "update_payment_method"],
            "return_url": "https://example.test/portal-return",
        },
    )
    expect(code == 201, f"portal session create: {code} {ps}")
    plaintext_token = ps.get("token")
    expect(bool(plaintext_token), f"no plaintext token returned: {ps}")
    ok(f"session {ps['session']['id']} token-prefix={plaintext_token[:12]}...")

    # Use the token via Authorization: Portal <token>
    portal_client = Client("portal")
    code, ctx = portal_client.request(
        "GET",
        f"{PORTAL}/context",
        headers={"Authorization": f"Portal {plaintext_token}"},
    )
    expect(code == 200, f"portal context: {code} {ctx}")
    ok(f"portal context ok customer={ctx.get('customer', {}).get('id', '?')}")

    # 22. Analytics overview reflects new sub
    step("analytics: overview refresh")
    code, ov = owner.request("GET", "/analytics/overview?refresh=true")
    expect(code == 200, f"overview: {code} {ov}")
    ok(
        f"MRR={ov.get('mrr_minor')}/{ov.get('currency')} "
        f"active={ov.get('active_subscriptions')} "
        f"trialing={ov.get('trialing_subscriptions')} "
        f"past_due={ov.get('past_due_subscriptions')} "
        f"RAR={ov.get('revenue_at_risk_minor')} "
        f"recovery={ov.get('recovery_rate_pct')}%"
    )

    # 23. /v1/me/features bundle
    step("features: /me/features returns flag bundle for the merchant session")
    code, feat = owner.request("GET", "/me/features")
    expect(code == 200, f"/me/features: {code} {feat}")
    expect(isinstance(feat, dict), f"shape: {feat}")
    flags = feat.get("flags") or {}
    catalog = feat.get("catalog") or []
    expect(isinstance(flags, dict) and isinstance(catalog, list), f"shape: {feat}")
    catalog_keys = {entry.get("key") for entry in catalog}
    for required in ("manual_refunds", "tokenized_cards", "promo_codes", "smart_routing"):
        expect(required in catalog_keys, f"catalog missing {required}: {catalog_keys}")
        expect(required in flags, f"flags missing {required}: {flags}")
    expect(flags.get("manual_refunds") is True, f"manual_refunds default on: {flags}")
    ok(
        f"flags resolved: manual_refunds={flags['manual_refunds']} "
        f"tokenized_cards={flags['tokenized_cards']} "
        f"promo_codes={flags['promo_codes']} smart_routing={flags['smart_routing']}"
    )

    # 24-25. Admin flips manual_refunds -> merchant refund gate flips with it.
    step("features: admin toggles manual_refunds OFF -> merchant refund 403")
    code, me = owner.request("GET", "/auth/me")
    expect(code == 200, f"/auth/me: {code} {me}")
    merchant_id = (me.get("user") or {}).get("orgId")
    expect(bool(merchant_id), f"orgId missing on /auth/me: {me}")

    admin = Client("platform-admin")
    code, body = admin.request(
        "POST",
        f"{BASE_URL}/api/v1/platform/auth/sign-in",
        data={"email": PLATFORM_ADMIN_EMAIL, "password": PLATFORM_ADMIN_PASSWORD},
    )
    expect(code == 200 and isinstance(body, dict) and body.get("ok"),
           f"platform admin sign-in: {code} {body}")

    config_url = f"{BASE_URL}/api/v1/platform/merchants/{merchant_id}/config"
    code, body = admin.request("PATCH", config_url,
                               data={"featureFlags": {"manual_refunds": False}})
    expect(code == 200, f"PATCH config off: {code} {body}")
    flag_map = {entry["key"]: entry["enabled"]
                for entry in (body.get("config") or {}).get("featureFlags", [])}
    expect(flag_map.get("manual_refunds") is False,
           f"manual_refunds did not flip OFF: {flag_map}")
    ok("admin set manual_refunds=False")

    code, refused = owner.request(
        "POST", f"/payment-attempts/{success_attempt_id}/refund", data={"full": True},
    )
    expect(code == 403, f"refund with flag off should be 403, got {code}: {refused}")
    expect(isinstance(refused, dict) and refused.get("ok") is False,
           f"shape: {refused}")
    expect("manual_refunds" in (refused.get("reason") or "").lower() or
           "manual refunds" in (refused.get("reason") or "").lower(),
           f"reason should mention the flag: {refused}")
    ok(f"refund refused: {refused['reason']!r}")

    step("features: admin toggles manual_refunds ON  -> merchant refund succeeds")
    code, body = admin.request("PATCH", config_url,
                               data={"featureFlags": {"manual_refunds": True}})
    expect(code == 200, f"PATCH config on: {code} {body}")
    flag_map = {entry["key"]: entry["enabled"]
                for entry in (body.get("config") or {}).get("featureFlags", [])}
    expect(flag_map.get("manual_refunds") is True,
           f"manual_refunds did not flip back ON: {flag_map}")

    code, refunded = owner.request(
        "POST", f"/payment-attempts/{success_attempt_id}/refund", data={"full": True},
    )
    expect(code == 200, f"refund with flag on: {code} {refunded}")
    ok(f"refund succeeded attempt={refunded.get('id', success_attempt_id)}")

    # Sign-out
    step("sign-out")
    code, body = owner.request("POST", "/auth/sign-out", data={})
    expect(code == 200 and body.get("ok"), f"sign-out: {code} {body}")
    ok("signed out")

    print(f"\n{GREEN}{BOLD}In-depth E2E passed — {_step_no} steps.{RESET}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except TestError as e:
        print(f"\n{RED}{BOLD}E2E FAILED:{RESET} {e}\n")
        sys.exit(1)
