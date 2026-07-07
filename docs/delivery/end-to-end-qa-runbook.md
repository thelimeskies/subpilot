# End-to-End QA Runbook

This runbook is the manual demo and release-readiness checklist for SubPilot. It complements the automated [End-to-End Test Plan](./end-to-end-test-plan.md) by covering deployed URLs, seeded accounts, product-surface walkthroughs, Nomba sandbox routing, portal behavior, platform-admin visibility, and go/no-go evidence.

## Primary Goal

Prove that a seeded merchant can configure Nomba sandbox credentials, route requests through the assigned Nomba sub-account, operate subscriptions, trigger billing and recovery workflows, and use customer, merchant, platform-admin, SDK, and landing-page surfaces without deployment regressions.

## Product Surfaces Under Test

| Surface | Purpose | Must prove |
|---|---|---|
| Landing page | Public product entry point | CTAs route to the merchant app, portal documentation, and developer content without broken links. |
| Merchant dashboard | Primary billing workspace | Merchant can sign in, inspect dashboard metrics, manage plans, customers, subscriptions, invoices, dunning, webhooks, API keys, and Nomba settings. |
| Customer portal | Subscriber self-service | Customer can open a valid portal session, view invoices and subscriptions, manage payment methods, pay open invoices, and change/cancel allowed subscriptions. |
| Platform admin | Internal SubPilot control plane | Operator can inspect merchants, payments, webhook health, support/KYC state, settings, analytics, and audit logs. |
| Portal SDK demo | Embedded portal example | Merchant frontend can render `@subpilot/portal-js` and load portal data through the backend proxy. |
| Python SDK | Backend integration package | Secret-key API flows can create customers and portal sessions without exposing credentials to browser code. |
| Nomba adapter | Payment infrastructure boundary | Sandbox credentials validate, calls use the correct account/sub-account values, and webhook callbacks route to the right merchant environment. |

## Pass Criteria

| Area | Required evidence before demo |
|---|---|
| Deployment | Backend, merchant app, platform admin, portal, and landing page deploy cleanly with HTTPS domains. |
| Nomba sandbox | Credential validation succeeds and sandbox calls use the configured test sub-account where applicable. |
| Merchant product | Plans, customers, subscriptions, invoices, recovery, portal links, and developer settings work end to end. |
| Customer portal | A customer can view context, invoices, subscriptions, and payment methods through a valid portal session. |
| Platform admin | Platform admin can inspect merchants, support/KYC state, payments, webhook events, settings, analytics, and audit logs. |
| Security | Auth, MFA bypass for demo, CSRF/CORS, role permissions, API keys, signing secrets, and webhook validation behave as expected. |
| Auditability | Money-impacting state changes emit internal events and audit records. |

## Environment Checklist

Use one environment variable per line in the deployment platform. Do not join unrelated CORS, frontend, or Nomba values into one field.

Required deployed domains:

| Service | URL |
|---|---|
| Backend API | `https://api.subpilot.kylodo.com` |
| Merchant dashboard | `https://app.subpilot.kylodo.com` |
| Customer portal | `https://portal.subpilot.kylodo.com` |
| Platform admin | `https://platform-admin.subpilot.kylodo.com` |

Required backend configuration:

| Variable group | Expected state |
|---|---|
| Django | `DJANGO_SETTINGS_MODULE`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and `DJANGO_SECURE_SSL_REDIRECT` are set for the deployed environment. |
| CORS/CSRF | `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` include the merchant, portal, platform-admin, and API domains. |
| Frontend URLs | `FRONTEND_MERCHANT_URL`, `FRONTEND_CUSTOMER_URL`, and `FRONTEND_PLATFORM_URL` point at the deployed frontend domains. |
| Database/Redis | Postgres and Redis variables point at reachable services; migrations have run. |
| Email | Mailpit or SMTP variables are configured for invite, reset, recovery, and receipt emails. |
| Encryption | `FIELD_ENCRYPTION_KEY` is set and stable across restarts. |
| Nomba sandbox | Test account id, test sub-account id, test client id, and test client secret are set only in the deployment environment. |
| Nomba webhooks | `NOMBA_WEBHOOK_SECRET` is configured as an environment variable. Do not commit the value. |
| Nomba live | Live variables remain blank or inactive for hackathon testing unless live mode is intentionally activated. |

Frontend deployment checks:

| Frontend | Required config |
|---|---|
| Merchant dashboard | API proxy or `VITE_BACKEND_URL` reaches the backend API and does not loop back to the frontend host. |
| Platform admin | API proxy reaches the backend API; platform auth uses `/api/v1/platform/auth/*`. |
| Customer portal | Portal API requests use `/api/v1/portal/*` and require portal tokens. |
| Landing page | Product URLs point to the merchant, portal, and platform-admin production domains. |

## Seed Data and Demo Accounts

Seed in this order for a clean local or deployed test environment:

```bash
python manage.py create_platform_admin
python manage.py seed_auth --password 'YourDemoPassword123!'
python manage.py seed_platform_admins --password 'YourDemoPassword123!'
python manage.py seed_demo --password 'YourDemoPassword123!'
```

For the current local demo values, see the root `README.md` Auth Credentials section. Do not hard-code production passwords or Nomba credentials in docs.

Expected seeded merchant:

| Field | Value |
|---|---|
| Merchant | Acme Learning Hub |
| Currency | NGN |
| Environment | Test |
| Plans | Starter, Pro, Business |
| Main recovery customer | Chinedu Bello |
| Active demo customers | Ada Okafor, Kemi Lawal |
| Trial demo customer | Zainab Musa |
| Canceling demo customer | Tunde Martins |

## Backend Smoke Tests

Run the merchant API smoke:

```bash
cd backend
python scripts/e2e_smoke.py
```

Expected result:

- Health endpoint returns `200`.
- Owner sign-in succeeds.
- MFA challenge accepts the configured demo bypass code.
- `/auth/me` returns Acme owner context.
- Products, plans, customers, subscriptions, invoices, dunning runs, webhook endpoints, events, and analytics overview return valid payloads.

Run the platform-admin E2E:

```bash
cd backend
python scripts/platform_admin_e2e.py
```

Expected result:

- Platform owner sign-in succeeds.
- Auth/session isolation holds between platform and merchant users.
- Overview, merchants, payments, webhooks, API keys, tickets, KYC, team, settings, analytics, audit, and merchant-tab endpoints return expected FE-shaped payloads.
- Owner-gated mutations reject lower-privilege roles.

## Manual Demo Script

1. Open the landing page and click the primary console CTA.
2. Sign into the merchant dashboard as the seeded Acme owner.
3. Complete MFA with the configured demo bypass code.
4. Confirm overview metrics render without API errors.
5. Inspect plans and verify active price versions.
6. Inspect customers and open the Chinedu Bello record.
7. Inspect subscriptions and invoices; confirm seeded statuses match the demo scenario.
8. Open developer settings and show publishable keys, API keys, signing keys, and webhook endpoints.
9. Open Nomba integration settings; validate sandbox credentials and confirm the effective test sub-account.
10. Show webhook/event/audit trail for billing or recovery state changes.
11. Open a customer portal session in a private browser context and confirm customer-scoped invoices/subscriptions/payment methods.
12. Switch to platform admin and inspect merchant, payment, webhook, support/KYC, analytics, and audit views.
13. Close with the architecture, ERD, state-machine docs, and Nomba integration contract.

## Nomba Sandbox Validation

| Step | Action | Expected |
|---|---|---|
| 1 | Save sandbox credentials in merchant Nomba settings. | Secrets are encrypted and not echoed back in full. |
| 2 | Validate credentials. | Backend reaches Nomba sandbox and returns a clear success or failure. |
| 3 | Sync accounts if available. | Available account/sub-account data is recorded or displayed without leaking secrets. |
| 4 | Confirm sub-account mapping. | Merchant environment points at the intended Nomba test sub-account. |
| 5 | Create checkout or payment-method session if credentials allow. | Request includes merchant/invoice/customer metadata needed for webhook routing. |
| 6 | Receive or simulate webhook callback. | Event verifies, dedupes, maps to the merchant environment, and updates payment/invoice/subscription state. |

Use the central callback for platform-managed Nomba mode:

```text
POST /api/v1/payments/webhooks/nomba/
```

Use the merchant-scoped callback for BYOK mode:

```text
POST /api/v1/payments/webhooks/nomba/<merchant_id>/<mode>/
```

For local testing with real Nomba callbacks, expose the backend over public HTTPS. Nomba cannot call `localhost`.

## Customer Portal Checks

| Check | Expected |
|---|---|
| Portal token required | Portal APIs reject missing or invalid tokens. |
| Context | Portal context shows only the scoped customer and merchant environment. |
| Invoices | Customer sees their own invoices and can open invoice details. |
| Payment methods | Customer can view masked payment methods only. Raw token values never appear. |
| Pay invoice | Open invoice payment flow creates or uses the correct Nomba/payment attempt path. |
| Change plan | Preview endpoint returns proration data before mutation. |
| Cancel subscription | Allowed cancellation updates subscription state and records an event. |

## Platform Admin Checks

| Check | Expected |
|---|---|
| Auth isolation | Merchant users cannot access `/api/v1/platform/*`. |
| Merchant list/detail | Operator can inspect merchant health, status, and recent activity. |
| Payments | Refund or payment actions are role-gated and audited. |
| Webhooks | Delivery health, retry, and rotate-key actions work according to role. |
| API keys | Key list and revoke actions are visible to authorized roles only. |
| Support/KYC | Ticket and KYC updates persist and audit. |
| Team | Owner-only team actions reject Operator/Support users. |
| Settings | Owner-only settings updates reject lower roles. |
| Analytics | Range filters return stable FE-shaped payloads. |
| Audit log | Cross-tenant audit entries are visible in platform context only. |

## Security and Failure Tests

- CSRF: unsafe requests from untrusted origins fail; trusted frontend origins succeed.
- CORS: browser requests from merchant/platform/portal domains succeed; random origins fail.
- Secrets: Nomba client secrets, webhook secrets, refresh tokens, payment tokens, and MFA secrets are encrypted or not exposed.
- Permissions: finance/support users cannot rotate API keys or activate live Nomba unless role permits.
- Tenant isolation: one merchant cannot read another merchant's customers, invoices, subscriptions, or keys.
- Webhook replay attack: timestamp/signature mismatch is rejected.
- Bad Nomba credentials: validation returns a clear error and does not mark credentials validated.
- Backend restart: encrypted credentials survive restart without requiring reseed.

## Sign-Off Matrix

| Gate | Owner | Status | Notes |
|---|---|---|---|
| Backend deploy and migrations | Engineering | Not run / Pass / Fail | |
| Frontend routing/proxy | Engineering | Not run / Pass / Fail | |
| Nomba sandbox credential validation | Engineering | Not run / Pass / Fail | |
| Nomba sub-account routing evidence | Engineering | Not run / Pass / Fail | |
| Merchant billing workflow | Product QA | Not run / Pass / Fail | |
| Customer portal workflow | Product QA | Not run / Pass / Fail | |
| Webhooks/idempotency | Engineering | Not run / Pass / Fail | |
| Platform admin visibility | Ops QA | Not run / Pass / Fail | |
| Security/roles/CORS/CSRF | Engineering | Not run / Pass / Fail | |
| Demo rehearsal | Team lead | Not run / Pass / Fail | |

## Final Go/No-Go

Do not demo live mode for hackathon judging. A successful test-mode flow with validated sandbox credentials, assigned sub-account routing, visible local ledger/audit records, and a customer portal session is sufficient.
