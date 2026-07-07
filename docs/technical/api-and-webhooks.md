
# API and Webhooks

## API Design Principles

- RESTful resources with predictable plural nouns.
- Idempotency required for mutations.
- Cursor pagination for lists.
- Stable event names.
- Metadata supported on customer, plan, subscription, and invoice objects.
- Test and live environments separated by API key.
- All money amounts use minor units, for example kobo.

## Authentication

Merchant API:

```http
Authorization: Bearer nse_live_xxx
Idempotency-Key: 9f95d7c9-5b2a-4f22-8ef7-9acaa7b26819
```

Internal Nomba API usage:

- OAuth2 client credentials.
- Keep client secrets server-side.
- Refresh token before expiry.
- Include Nomba account id where required by Nomba APIs.

## Core Endpoints

### Products

```http
POST /v1/products
GET /v1/products
GET /v1/products/{product_id}
PATCH /v1/products/{product_id}
```

### Plans

```http
POST /v1/plans
GET /v1/plans
GET /v1/plans/{plan_id}
PATCH /v1/plans/{plan_id}
POST /v1/plans/{plan_id}/activate
POST /v1/plans/{plan_id}/archive
POST /v1/plans/{plan_id}/clone
```

Create plan example:

```json
{
  "product_id": "prod_123",
  "name": "Pro",
  "description": "For growing teams",
  "amount_minor": 1500000,
  "currency": "NGN",
  "interval_unit": "month",
  "interval_count": 1,
  "trial_days": 14,
  "features": [
    {"key": "seats", "name": "Seats", "limit": 10},
    {"key": "reports", "name": "Advanced reports", "included": true}
  ],
  "dunning_policy_id": "dun_123"
}
```

### Customers

```http
POST /v1/customers
GET /v1/customers
GET /v1/customers/{customer_id}
PATCH /v1/customers/{customer_id}
GET /v1/customers/{customer_id}/timeline
```

### Subscriptions

```http
POST /v1/subscriptions
GET /v1/subscriptions
GET /v1/subscriptions/{subscription_id}
POST /v1/subscriptions/{subscription_id}/preview-change
POST /v1/subscriptions/{subscription_id}/change
POST /v1/subscriptions/{subscription_id}/pause
POST /v1/subscriptions/{subscription_id}/resume
POST /v1/subscriptions/{subscription_id}/cancel
```

Create subscription example:

```json
{
  "customer": {
    "email": "customer@example.com",
    "name": "Ada Customer",
    "external_id": "cus_merchant_001"
  },
  "items": [
    {
      "plan_id": "plan_pro_monthly",
      "quantity": 1
    }
  ],
  "collection_method": "checkout",
  "success_url": "https://merchant.app/billing/success",
  "cancel_url": "https://merchant.app/billing/cancel",
  "metadata": {
    "workspace_id": "wk_001"
  }
}
```

Response:

```json
{
  "id": "sub_123",
  "status": "incomplete",
  "customer_id": "cus_123",
  "checkout_url": "https://checkout.nomba.com/sandbox/ref",
  "current_period_start": null,
  "current_period_end": null,
  "latest_invoice_id": "inv_123"
}
```

### Invoices

```http
GET /v1/invoices
GET /v1/invoices/{invoice_id}
POST /v1/invoices/{invoice_id}/retry
POST /v1/invoices/{invoice_id}/void
POST /v1/invoices/{invoice_id}/mark-uncollectible
POST /v1/invoices/{invoice_id}/payment-link
```

### Payment Methods

```http
GET /v1/customers/{customer_id}/payment-methods
POST /v1/customers/{customer_id}/payment-methods/portal-session
DELETE /v1/payment-methods/{payment_method_id}
```

### Customer Portal

```http
POST /v1/portal/sessions
GET /portal/{portal_session_token}
```

Create portal session:

```json
{
  "customer_id": "cus_123",
  "return_url": "https://merchant.app/account",
  "allowed_actions": ["update_payment_method", "pay_invoice", "cancel"]
}
```

### Dunning Policies

```http
POST /v1/dunning-policies
GET /v1/dunning-policies
GET /v1/dunning-policies/{policy_id}
PATCH /v1/dunning-policies/{policy_id}
```

Policy example:

```json
{
  "name": "Default SaaS Recovery",
  "retry_offsets_days": [0, 1, 3, 7, 14],
  "grace_period_days": 7,
  "final_action": "pause",
  "notifications": {
    "email": true,
    "sms": true,
    "webhook": true
  }
}
```

### Webhook Endpoints and Events

```http
POST /v1/webhook-endpoints
GET /v1/webhook-endpoints
PATCH /v1/webhook-endpoints/{endpoint_id}
GET /v1/events
GET /v1/events/{event_id}
POST /v1/events/{event_id}/replay
```

## Webhook Signature

Outbound webhook headers:

```http
NSE-Event-Id: evt_123
NSE-Timestamp: 2026-07-05T10:00:00Z
NSE-Signature: hmac_sha256_signature
NSE-Signature-Version: v1
```

Signature base:

```text
timestamp + "." + raw_body
```

## Webhook Payload Example

```json
{
  "id": "evt_123",
  "type": "subscription.activated",
  "livemode": false,
  "merchant_id": "mch_123",
  "occurred_at": "2026-07-05T10:00:00Z",
  "data": {
    "subscription": {
      "id": "sub_123",
      "status": "active",
      "customer_id": "cus_123",
      "current_period_start": "2026-07-05T10:00:00Z",
      "current_period_end": "2026-08-05T10:00:00Z"
    },
    "customer": {
      "id": "cus_123",
      "email": "customer@example.com"
    },
    "plan": {
      "id": "plan_pro_monthly",
      "name": "Pro"
    },
    "invoice": {
      "id": "inv_123",
      "status": "paid",
      "total_minor": 1500000,
      "currency": "NGN"
    }
  }
}
```

## Required Events

Subscription:

- `subscription.created`
- `subscription.trialing`
- `subscription.activated`
- `subscription.changed`
- `subscription.past_due`
- `subscription.paused`
- `subscription.resumed`
- `subscription.canceling`
- `subscription.canceled`

Invoice:

- `invoice.created`
- `invoice.finalized`
- `invoice.payment_succeeded`
- `invoice.payment_failed`
- `invoice.voided`
- `invoice.marked_uncollectible`
- `invoice.refunded`

Payment method:

- `payment_method.attached`
- `payment_method.updated`
- `payment_method.expired`
- `payment_method.revoked`

Dunning:

- `dunning.started`
- `dunning.retry_scheduled`
- `dunning.notification_sent`
- `dunning.recovered`
- `dunning.exhausted`

## API Error Shape

```json
{
  "error": {
    "type": "validation_error",
    "code": "invalid_interval",
    "message": "interval_count must be greater than 0",
    "request_id": "req_123",
    "details": [
      {
        "field": "interval_count",
        "issue": "must be greater than 0"
      }
    ]
  }
}
```

## Pagination

```http
GET /v1/subscriptions?limit=25&starting_after=sub_123
```

Response:

```json
{
  "data": [],
  "has_more": true,
  "next_cursor": "sub_456"
}
```

## Platform Admin API

Internal control plane for SubPilot operators. Mounted under
`/api/v1/platform/` and isolated from the merchant API:

- **Auth**: cookie-based session (`platform_admin_session`) issued by
  `POST /platform/auth/sign-in`. Bearer API keys are NOT accepted.
- **Permission class**: `IsPlatformAdmin` on every route below.
- **Tenancy**: cross-tenant — selectors operate over all merchants.
- **OpenAPI tag**: every operation is grouped under `Platform Admin`.
- **Roles**: `Owner`, `Operator`, `Support`, `ReadOnly`. Owner-only routes
  are flagged explicitly; all other routes are open to every active admin.
- **Suspended admins**: sign-in returns `200 {"ok": false, "reason": "...suspended..."}`
  and no session cookie is issued.
- **Error shape**: standard `{"ok": false, "reason": "..."}` for 4xx; pagination
  uses `{"results": [...], "page": N, "pageSize": N, "total": N}`.

### Auth & session

| Method | Path                          | Roles    | Description                          |
|--------|-------------------------------|----------|--------------------------------------|
| POST   | `/platform/auth/sign-in`      | anon     | Issue session cookie from email/pw   |
| POST   | `/platform/auth/sign-out`     | any      | Clear session cookie                 |
| GET    | `/platform/auth/me`           | any/anon | Current admin or `{user: null}`      |
| POST   | `/platform/auth/forgot`       | anon     | Stub: always 200 (no enumeration)    |
| GET    | `/platform/ping`              | any      | Health probe; isolation negative test|

### Overview (S2)

| Method | Path                  | Roles | Description                                  |
|--------|-----------------------|-------|----------------------------------------------|
| GET    | `/platform/overview`  | any   | Cached KPI bundle for dashboard (60s TTL)    |

### Merchants (S3 + S4)

| Method | Path                                                | Roles  | Description                          |
|--------|-----------------------------------------------------|--------|--------------------------------------|
| GET    | `/platform/merchants`                               | any    | Paginated cross-tenant list + filters|
| GET    | `/platform/merchants/{merchant_id}`                 | any    | Single merchant detail bundle        |
| POST   | `/platform/merchants/{merchant_id}/suspend`         | any    | Suspend merchant (`reason` required) |
| POST   | `/platform/merchants/{merchant_id}/reactivate`      | any    | Reactivate suspended merchant        |
| POST   | `/platform/merchants/{merchant_id}/notes`           | any    | Append admin note                    |

Filters on list: `?status=active|suspended|kyc_pending`, `?search=`, `?page=`, `?pageSize=`.

### Payments (S5)

| Method | Path                                              | Roles | Description                              |
|--------|---------------------------------------------------|-------|------------------------------------------|
| GET    | `/platform/payments`                              | any   | Cross-tenant payment list + filters      |
| POST   | `/platform/payments/{payment_id}/refund`          | any   | Full or partial refund                   |

### Webhooks (S6)

| Method | Path                                                  | Roles | Description                              |
|--------|-------------------------------------------------------|-------|------------------------------------------|
| GET    | `/platform/webhooks/deliveries`                       | any   | Cross-tenant delivery list + filters     |
| POST   | `/platform/webhooks/deliveries/{delivery_id}/retry`   | any   | Enqueue retry of a delivery              |
| GET    | `/platform/webhooks/health`                           | any   | Aggregate delivery health by endpoint    |

### API Keys (S7)

| Method | Path                                            | Roles | Description                                |
|--------|-------------------------------------------------|-------|--------------------------------------------|
| GET    | `/platform/api-keys`                            | any   | Cross-tenant key inventory (no secrets)    |
| POST   | `/platform/api-keys/{api_key_id}/revoke`        | any   | Revoke an active key                       |

### Support (S8)

| Method | Path                                              | Roles | Description                              |
|--------|---------------------------------------------------|-------|------------------------------------------|
| GET    | `/platform/tickets`                               | any   | Cross-tenant ticket list + filters       |
| GET    | `/platform/tickets/{ticket_id}`                   | any   | Ticket detail + replies                  |
| PATCH  | `/platform/tickets/{ticket_id}`                   | any   | Update status / assignee                 |
| POST   | `/platform/tickets/{ticket_id}/replies`           | any   | Append public/internal reply             |
| GET    | `/platform/kyc/{merchant_id}`                     | any   | KYC bundle (documents + status)          |
| PATCH  | `/platform/kyc/{merchant_id}`                     | any   | Approve / reject KYC review              |

### Team / Admin Management (S9)

| Method | Path                                                | Roles  | Description                            |
|--------|-----------------------------------------------------|--------|----------------------------------------|
| GET    | `/platform/team`                                    | any    | List all platform admins               |
| POST   | `/platform/team/invite`                             | Owner  | Issue invite token                     |
| POST   | `/platform/team/accept-invite`                      | anon   | Redeem invite + set password           |
| GET    | `/platform/team/{admin_id}`                         | any    | Admin detail                           |
| PATCH  | `/platform/team/{admin_id}`                         | Owner  | Update role / display name             |
| POST   | `/platform/team/{admin_id}/suspend`                 | Owner  | Suspend admin (revokes session)        |
| POST   | `/platform/team/{admin_id}/reactivate`              | Owner  | Reactivate suspended admin             |

### Settings (S10)

| Method | Path                  | Roles  | Description                                          |
|--------|-----------------------|--------|------------------------------------------------------|
| GET    | `/platform/settings`  | any    | Singleton platform settings                          |
| PATCH  | `/platform/settings`  | Owner  | Update platform settings (commission, retry policy)  |

### Analytics (S11)

| Method | Path                   | Roles | Description                                                       |
|--------|------------------------|-------|-------------------------------------------------------------------|
| GET    | `/platform/analytics`  | any   | Cached analytics snapshot (`?range=3m|6m|12m`, `?refresh=true`)   |

### Per-merchant Tabs + Config (S13)

Each Merchant Detail tab is now its own paginated endpoint. The Config
resource also accepts a partial PATCH that merges `feature_flags`, `limits`,
and `retry_policy`; PATCH is Owner-only.

| Method | Path                                                       | Roles  | Description                                                           |
|--------|------------------------------------------------------------|--------|-----------------------------------------------------------------------|
| GET    | `/platform/merchants/{merchant_id}/subscriptions`          | any    | Paginated subs + stats + plan-mix (`?page=`, `?pageSize=`, `?status=`)|
| GET    | `/platform/merchants/{merchant_id}/payments`               | any    | Paginated payments scoped to merchant (`?status=`, `?page=`)          |
| GET    | `/platform/merchants/{merchant_id}/webhooks`               | any    | Paginated deliveries scoped to merchant (`?status=`, `?page=`)        |
| GET    | `/platform/merchants/{merchant_id}/audit`                  | any    | Paginated audit log for merchant (`?action=`, `?page=`)               |
| GET    | `/platform/merchants/{merchant_id}/config`                 | any    | Resolved bundle: `featureFlags[]` (catalog merged with overrides), `limits`, `retryPolicy`, `webhookEndpoints` |
| PATCH  | `/platform/merchants/{merchant_id}/config`                 | Owner  | Partial merge of `featureFlags` / `limits` / `retryPolicy`; writes audit row |

The per-tab endpoints replace the bulky `recentPayments` / `recentAudit`
lists that the legacy `/platform/merchants/{id}` detail bundle used to
return. Detail now caps recent payments and audit rows at 5 each for the
Overview cards; full lists live behind the dedicated tab endpoints above.

### Feature flags

Feature flags are server-defined and per-merchant. The catalog lives in
`apps/platform_admin/feature_flags.py`; values are stored on
`MerchantConfig.feature_flags` and resolved with defaults applied:

| Key               | Default | Enforced at                                                                |
|-------------------|---------|----------------------------------------------------------------------------|
| `tokenized_cards` | `true`  | `POST /v1/customers/{id}/payment-methods/portal-session` (attach method)   |
| `manual_refunds`  | `true`  | `POST /v1/payment-attempts/{id}/refund`                                    |
| `promo_codes`     | `false` | Promo create/apply endpoints (gate in place; domain itself out of scope)   |
| `smart_routing`   | `false` | Stamped onto `PaymentAttempt.metadata.routing_policy` as a hint (no behavior change today; reserved for multi-adapter routing) |

When a flag is OFF the merchant endpoint returns `403` with the FE-shape
envelope `{"ok": false, "reason": "Feature '<label>' is disabled for this merchant."}`.

The merchant SPA reads the resolved bundle on bootstrap and hides the
affected controls (cosmetic; the server is always the gate):

```http
GET /api/v1/me/features
```

Response:

```json
{
  "flags": {
    "tokenized_cards": true,
    "manual_refunds": true,
    "promo_codes": false,
    "smart_routing": false
  },
  "catalog": [
    {"key": "tokenized_cards", "label": "Tokenized cards", "description": "...", "default": true},
    {"key": "manual_refunds",  "label": "Manual refunds",  "description": "...", "default": true},
    {"key": "promo_codes",     "label": "Promo codes",     "description": "...", "default": false},
    {"key": "smart_routing",   "label": "Smart adapter routing", "description": "...", "default": false}
  ]
}
```
