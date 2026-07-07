# SDK and Packages Plan

SubPilot should feel like infrastructure, not just a dashboard. Downstream product teams need SDKs and packages that make subscription creation, portal sessions, tokenized-card recovery, and webhook verification easy.

## Package Strategy

| Package | Language | Audience | Priority |
|---|---|---|---|
| `subpilot-python` | Python | Django/FastAPI/Flask teams | P0 |
| `subpilot-django` | Python/Django | Django teams | P0 |
| `@subpilot/node` | TypeScript/JavaScript | Node/Next.js teams | P1 |
| `@subpilot/react` | TypeScript/React | Frontend app teams | P1 |
| `subpilot-cli` | Python or Node | Developers and demo ops | P1 |

Current implemented frontend package:

| Package | Location | Purpose |
|---|---|---|
| `@subpilot/portal-js` | `packages/portal-js` | React customer portal component and browser client helpers for merchant frontends. |
| `subpilot` | `packages/subpilot-python` | Python backend client for customer, portal-session, invoice, subscription, and publishable-key APIs. |

See [Customer Portal SDK and Embedded Portal](./customer-portal-sdk.md) for the implementation guide, props, security model, hosted portal app, and demo app.
See [SubPilot Python SDK](./python-sdk.md) for backend package usage and examples.

## Package Responsibilities

### `subpilot-python`

Core API client.

Features:

- API key authentication.
- Idempotency-key helper.
- Customers, plans, subscriptions, invoices, payment methods, portal sessions, and webhooks resources.
- Retry-safe HTTP client.
- Typed errors.
- Webhook signature verification.

Example:

```python
from subpilot import SubPilot

client = SubPilot(api_key="sp_test_xxx")

subscription = client.subscriptions.create(
    customer={
        "email": "ada@example.com",
        "name": "Ada Okafor",
        "external_id": "user_123",
    },
    items=[{"plan_id": "plan_pro_monthly", "quantity": 1}],
    success_url="https://app.example.com/billing/success",
    cancel_url="https://app.example.com/billing/cancel",
    idempotency_key="sub-create-user-123-pro",
)

print(subscription.checkout_url)
```

### `subpilot-django`

Django integration package for downstream merchant apps.

Features:

- Django settings integration.
- Webhook view helper.
- Signature verification decorator.
- Models for mapping local users/workspaces to SubPilot customers/subscriptions.
- Management command to test webhook delivery.
- Helper for creating billing portal sessions.

Example:

```python
# settings.py
SUBPILOT_API_KEY = "sp_test_xxx"
SUBPILOT_WEBHOOK_SECRET = "whsec_xxx"
```

```python
# urls.py
from django.urls import path
from subpilot_django.views import SubPilotWebhookView

urlpatterns = [
    path("billing/webhooks/subpilot/", SubPilotWebhookView.as_view()),
]
```

```python
from subpilot_django.client import subpilot

def start_subscription(request):
    subscription = subpilot.subscriptions.create(
        customer={
            "email": request.user.email,
            "external_id": str(request.user.id),
        },
        items=[{"plan_id": "plan_pro_monthly"}],
        success_url="https://merchant.app/billing/success",
        cancel_url="https://merchant.app/billing/cancel",
    )
    return redirect(subscription.checkout_url)
```

### `@subpilot/node`

Node/TypeScript API client.

Features:

- Typed resources.
- Webhook signature verification.
- Idempotency helpers.
- ESM and CommonJS support.

Example:

```ts
import { SubPilot } from "@subpilot/node";

const subpilot = new SubPilot({ apiKey: process.env.SUBPILOT_API_KEY! });

const session = await subpilot.paymentMethods.createSession({
  customerId: "cus_123",
  purpose: "recover_invoice",
  invoiceId: "inv_123",
});
```

### `@subpilot/react`

Frontend helpers. This should not expose secret keys.

Features:

- Portal redirect button.
- Subscription status badge component.
- Invoice payment call-to-action component.
- Hooks that call the merchant backend, not SubPilot directly with secret keys.

Example:

```tsx
<BillingPortalButton customerId={user.subpilotCustomerId}>
  Manage billing
</BillingPortalButton>
```

### `subpilot-cli`

Developer and demo helper.

Commands:

```bash
subpilot login
subpilot plans list
subpilot subscriptions create --customer ada@example.com --plan plan_pro_monthly
subpilot events listen
subpilot events replay evt_123
subpilot demo reset
```

## SDK Resource Map

| SDK Resource | API Endpoints |
|---|---|
| `client.products` | `/products` |
| `client.plans` | `/plans` |
| `client.customers` | `/customers` |
| `client.subscriptions` | `/subscriptions` |
| `client.invoices` | `/invoices` |
| `client.payment_methods` | `/customers/{id}/payment-methods`, `/payment-method-sessions` |
| `client.dunning_policies` | `/dunning-policies` |
| `client.webhook_endpoints` | `/webhook-endpoints` |
| `client.events` | `/events` |

## Webhook Verification API

Python:

```python
event = client.webhooks.construct_event(
    payload=request.body,
    signature=request.headers["SubPilot-Signature"],
    timestamp=request.headers["SubPilot-Timestamp"],
    secret=settings.SUBPILOT_WEBHOOK_SECRET,
)
```

Node:

```ts
const event = subpilot.webhooks.constructEvent({
  payload: rawBody,
  signature: req.headers["subpilot-signature"],
  timestamp: req.headers["subpilot-timestamp"],
  secret: process.env.SUBPILOT_WEBHOOK_SECRET!,
});
```

## Error Handling

SDK errors:

- `AuthenticationError`
- `PermissionError`
- `ValidationError`
- `IdempotencyConflictError`
- `RateLimitError`
- `ApiConnectionError`
- `ProcessorUnavailableError`

Each error should expose:

- `code`
- `message`
- `request_id`
- `status_code`
- `details`

## Versioning

- API version header: `SubPilot-Version: 2026-07-05`
- SDK semantic versioning.
- Breaking API changes require a new API version.
- Webhook payload versions are explicit.

## Package Build Units

| ID | Package | Task | Priority | Estimate |
|---|---|---|---|---:|
| SDK-01 | `subpilot-python` | Core HTTP client and auth | P0 | M |
| SDK-02 | `subpilot-python` | Resource clients | P0 | M |
| SDK-03 | `subpilot-python` | Webhook verification | P0 | S |
| SDK-04 | `subpilot-django` | Settings and client helper | P0 | S |
| SDK-05 | `subpilot-django` | Webhook view/decorator | P0 | M |
| SDK-06 | `subpilot-django` | Local mapping models | P1 | M |
| SDK-07 | `@subpilot/node` | TypeScript client | P1 | L |
| SDK-08 | `@subpilot/react` | Portal button and billing UI helpers | P1 | M |
| SDK-09 | `subpilot-cli` | Event listen/replay and demo reset | P1 | M |

## Acceptance Criteria

- Django merchant app can create a subscription in under 10 lines of code.
- Django merchant app can verify webhooks with one class-based view or decorator.
- SDK supports tokenized-card recovery session creation.
- SDK never exposes Nomba secrets or raw card data.
- SDK examples cover subscription create, portal session, invoice retry, and webhook handling.
