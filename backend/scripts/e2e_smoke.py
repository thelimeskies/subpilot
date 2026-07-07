#!/usr/bin/env python3
"""End-to-end smoke test against the running Compose stack.

Walks the happy-path through the dashboard API:

    1. health endpoint
    2. sign-in (Owner of Acme, MFA challenge -> bypass code 123456)
    3. /auth/me with the resulting session cookie
    4. list customers, plans, subscriptions, invoices
    5. dashboard analytics overview (forces refresh)
    6. list webhook endpoints + recent events
    7. list dunning runs

Pass criterion: every step prints a green line. Failure aborts.

Usage:
    python scripts/e2e_smoke.py                   # against http://localhost:8000
    BASE_URL=http://web:8000 python scripts/e2e_smoke.py
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

import urllib.request
import urllib.error
import http.cookiejar


BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000").rstrip("/")
API = f"{BASE_URL}/api/v1"

OWNER_EMAIL = "owner@acme.test"
OWNER_PASSWORD = "Subpilot1!"
MFA_BYPASS = "123456"

GREEN = "\033[32m"
RED = "\033[31m"
DIM = "\033[2m"
RESET = "\033[0m"
BOLD = "\033[1m"


class SmokeError(Exception):
    pass


def _opener() -> tuple[urllib.request.OpenerDirector, http.cookiejar.CookieJar]:
    cj = http.cookiejar.CookieJar()
    return urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj)), cj


_OPENER, _COOKIES = _opener()


def _csrf_token() -> str | None:
    for c in _COOKIES:
        if c.name in ("subpilot_csrf", "csrftoken"):
            return c.value
    return None


def _request(method: str, path: str, *, data: Any = None, headers: dict | None = None) -> tuple[int, dict]:
    url = path if path.startswith("http") else f"{API}{path}"
    body = None
    h = {"Accept": "application/json"}
    if headers:
        h.update(headers)
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        h.setdefault("Content-Type", "application/json")
    if method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        token = _csrf_token()
        if token and "X-CSRFToken" not in h:
            h["X-CSRFToken"] = token
            h.setdefault("Referer", BASE_URL)
    req = urllib.request.Request(url, data=body, method=method, headers=h)
    try:
        with _OPENER.open(req, timeout=10) as resp:
            raw = resp.read()
            payload = json.loads(raw) if raw else {}
            return resp.status, payload
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            payload = json.loads(raw)
        except Exception:
            payload = {"_raw": raw.decode("utf-8", errors="replace")}
        return e.code, payload


def step(num: int, name: str) -> None:
    print(f"{BOLD}[{num:02d}] {name}{RESET}")


def ok(msg: str) -> None:
    print(f"  {GREEN}✓{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {DIM}{msg}{RESET}")


def fail(msg: str) -> None:
    print(f"  {RED}✗ {msg}{RESET}")
    raise SmokeError(msg)


def expect(condition: bool, msg: str) -> None:
    if not condition:
        fail(msg)


def main() -> int:
    print(f"{BOLD}SubPilot E2E smoke{RESET}  base={BASE_URL}\n")

    # 1) Health
    step(1, "health")
    code, body = _request("GET", "/health")
    expect(code == 200, f"health returned {code}: {body}")
    ok(f"health 200 -> {body}")

    # 2) Sign in (Owner) -> MFA challenge
    step(2, "sign-in (owner@acme.test)")
    code, body = _request(
        "POST", "/auth/sign-in",
        data={"email": OWNER_EMAIL, "password": OWNER_PASSWORD},
    )
    expect(code == 200, f"sign-in returned {code}: {body}")
    expect(body.get("ok") is True, f"sign-in body.ok=False: {body}")
    if body.get("requiresMfa"):
        info(f"MFA required, challengeId={body.get('challengeId')}")
        step(3, "verify-mfa (bypass 123456)")
        code, body = _request(
            "POST", "/auth/verify-mfa",
            data={"challengeId": body["challengeId"], "code": MFA_BYPASS},
        )
        expect(code == 200 and body.get("ok"), f"verify-mfa failed: {body}")
        ok(f"MFA verified, user={body['user']['email']} role={body['user']['role']}")
    else:
        ok(f"signed in as {body['user']['email']} role={body['user']['role']}")

    # 4) /auth/me
    step(4, "/auth/me")
    code, body = _request("GET", "/auth/me")
    expect(code == 200 and body.get("user"), f"/auth/me failed: {code} {body}")
    user = body["user"]
    ok(f"me: {user['name']} <{user['email']}> {user['orgName']} role={user['role']}")

    # 5) Catalog: products + plans
    step(5, "catalog (products + plans)")
    code, products = _request("GET", "/catalog/products")
    expect(code == 200, f"products list: {code} {products}")
    ok(f"products: {products.get('count', len(products.get('results', [])))} entries")
    code, plans = _request("GET", "/catalog/plans")
    expect(code == 200, f"plans list: {code} {plans}")
    plan_count = plans.get("count", len(plans.get("results", [])))
    ok(f"plans: {plan_count} entries")

    # 6) Customers
    step(6, "customers")
    code, customers = _request("GET", "/customers")
    expect(code == 200, f"customers list: {code}")
    cust_count = customers.get("count", len(customers.get("results", [])))
    ok(f"customers: {cust_count} entries")

    # 7) Subscriptions
    step(7, "subscriptions")
    code, subs = _request("GET", "/subscriptions")
    expect(code == 200, f"subscriptions list: {code}")
    sub_count = subs.get("count", len(subs.get("results", [])))
    ok(f"subscriptions: {sub_count} entries")
    if subs.get("results"):
        statuses = sorted({s["status"] for s in subs["results"]})
        info(f"subscription statuses present: {', '.join(statuses)}")

    # 8) Invoices
    step(8, "invoices")
    code, invoices = _request("GET", "/invoices")
    expect(code == 200, f"invoices list: {code}")
    inv_count = invoices.get("count", len(invoices.get("results", [])))
    ok(f"invoices: {inv_count} entries")

    # 9) Dunning runs
    step(9, "dunning")
    code, runs = _request("GET", "/dunning-runs")
    expect(code == 200, f"dunning runs list: {code}")
    run_count = runs.get("count", len(runs.get("results", [])))
    ok(f"dunning runs: {run_count} entries")

    # 10) Webhook endpoints + recent events
    step(10, "events (endpoints + recent)")
    code, eps = _request("GET", "/webhook-endpoints")
    expect(code == 200, f"endpoints list: {code} {eps}")
    ep_count = eps.get("count", len(eps.get("results", [])))
    ok(f"webhook endpoints: {ep_count} entries")
    code, evs = _request("GET", "/events")
    expect(code == 200, f"events list: {code}")
    ev_count = evs.get("count", len(evs.get("results", [])))
    ok(f"webhook events: {ev_count} emitted")
    if evs.get("results"):
        types = sorted({e["event_type"] for e in evs["results"][:25]})
        info(f"event types (sample): {', '.join(types[:10])}")

    # 11) Analytics overview (force refresh)
    step(11, "analytics overview (?refresh=true)")
    code, overview = _request("GET", "/analytics/overview?refresh=true")
    expect(code == 200, f"analytics overview: {code} {overview}")
    ok(
        "overview: "
        f"MRR={overview.get('mrr_minor')}/{overview.get('currency')}  "
        f"active={overview.get('active_subscriptions')} "
        f"trialing={overview.get('trialing_subscriptions')} "
        f"past_due={overview.get('past_due_subscriptions')} "
        f"RAR={overview.get('revenue_at_risk_minor')} "
        f"recovery={overview.get('recovery_rate_pct')}%"
    )

    # 12) Sign out
    step(12, "sign-out")
    code, body = _request("POST", "/auth/sign-out", data={})
    expect(code == 200 and body.get("ok"), f"sign-out failed: {code} {body}")
    ok("signed out")

    print(f"\n{GREEN}{BOLD}E2E smoke passed.{RESET}\n")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SmokeError:
        sys.exit(1)
