# Django File-by-File Build Plan

This plan translates the product units into a concrete Django implementation sequence. It is intentionally file-level so the team can divide work during the hackathon without losing the architecture.

## Build Rules

- Build the mock Nomba adapter first so the demo works without network instability.
- Put business mutations in `services/`, not serializers or views.
- Put query composition in `selectors.py`.
- Keep Celery tasks thin; tasks call services.
- Every service that changes billing state must create an event or audit log.
- Every external-facing mutation should accept an idempotency key where duplicate calls are plausible.
- Do not store raw card data, CVV, PAN, processor secrets, or unmasked token values.

## Sprint 0: Project Foundation

### Files to Create

```text
subpilot/
  manage.py
  config/
    settings/base.py
    settings/local.py
    settings/test.py
    settings/production.py
    urls.py
    celery.py
  apps/common/
    models.py
    money.py
    idempotency.py
    crypto.py
    time.py
    tests/
  apps/audit/
    models.py
    services/log_event.py
```

### Tasks

| Task | File | Done when |
|---|---|---|
| Configure settings split | `config/settings/*.py` | Local, test, and production settings import base |
| Add DRF/schema dependencies | `settings/base.py` | DRF and OpenAPI schema route boot |
| Add Celery app | `config/celery.py` | Worker imports Django settings |
| Create base model mixins | `apps/common/models.py` | Timestamp, UUID, merchant, environment mixins exist |
| Create money helpers | `apps/common/money.py` | Minor-unit validation and formatting helpers exist |
| Create idempotency helper | `apps/common/idempotency.py` | Can lock and replay mutation results |
| Create encryption wrapper | `apps/common/crypto.py` | Token references can be encrypted/decrypted through one API |

### Tests

- `apps/common/tests/test_money.py`
- `apps/common/tests/test_idempotency.py`
- `apps/common/tests/test_crypto.py`

## Sprint 1: Tenant, Plans, Customers

### accounts

```text
apps/accounts/
  models.py
  permissions.py
  authentication.py
  selectors.py
  services/api_keys.py
  serializers.py
  views.py
  urls.py
  tests/test_api_keys.py
  tests/test_tenant_isolation.py
```

Implementation order:

1. `Merchant`
2. `Environment`
3. `TeamMember`
4. `ApiKey`
5. API-key authentication
6. Environment selector
7. API key creation/revocation endpoints

Acceptance:

- API keys are hashed.
- Test and live environments are isolated.
- All request-scoped queries require merchant and environment.

### catalog

```text
apps/catalog/
  models.py
  selectors.py
  services/create_product.py
  services/create_plan.py
  services/activate_plan.py
  services/archive_plan.py
  services/clone_plan.py
  services/create_price_version.py
  serializers.py
  views.py
  urls.py
  tests/test_plan_lifecycle.py
  tests/test_price_versions.py
```

Implementation order:

1. `Product`
2. `Plan`
3. `PriceVersion`
4. `PlanFeature`
5. Draft plan creation
6. Price version creation
7. Activation/archive/clone
8. Plan API endpoints

Acceptance:

- Active plan price cannot mutate in place.
- Custom billing interval stores unit and count.
- Plan stores tokenized-card renewal setting.

### customers

```text
apps/customers/
  models.py
  selectors.py
  services/create_customer.py
  services/create_portal_session.py
  services/attach_payment_method.py
  services/set_default_payment_method.py
  serializers.py
  views.py
  urls.py
  tests/test_customers.py
  tests/test_payment_methods.py
  tests/test_portal_sessions.py
```

Implementation order:

1. `Customer`
2. `PaymentMethod`
3. `PortalSession`
4. Customer CRUD service
5. Payment method attach/default services
6. Portal session creation

Acceptance:

- `external_id` unique per merchant/environment.
- Payment method token reference encrypted at rest.
- API response only exposes brand, last4, expiry, and status.

## Sprint 2: Subscription Activation

### subscriptions

```text
apps/subscriptions/
  models.py
  state_machine.py
  selectors.py
  services/create_subscription.py
  services/activate_subscription.py
  services/mark_past_due.py
  services/pause_subscription.py
  services/resume_subscription.py
  services/cancel_subscription.py
  services/preview_change.py
  services/change_plan.py
  serializers.py
  views.py
  urls.py
  tests/test_state_machine.py
  tests/test_create_subscription.py
  tests/test_lifecycle_actions.py
```

Implementation order:

1. `Subscription`
2. `SubscriptionItem`
3. `SubscriptionEvent`
4. State-machine transition table
5. Subscription creation service
6. Activation service
7. Lifecycle action services
8. API viewsets/actions

Acceptance:

- Subscription creation is idempotent.
- Checkout flow starts as `incomplete`.
- Every state transition creates an event.

### invoices

```text
apps/invoices/
  models.py
  selectors.py
  services/create_invoice.py
  services/finalize_invoice.py
  services/create_renewal_invoice.py
  services/mark_paid.py
  services/void_invoice.py
  services/mark_uncollectible.py
  services/export_invoices.py
  serializers.py
  views.py
  urls.py
  tasks.py
  tests/test_invoice_totals.py
  tests/test_renewal_invoice.py
  tests/test_invoice_actions.py
```

Implementation order:

1. `Invoice`
2. `InvoiceLineItem`
3. `CreditNote`
4. Invoice total calculation
5. First invoice creation
6. Renewal invoice creation
7. Finalization and paid/void/uncollectible actions

Acceptance:

- Money stored in minor units.
- Finalized invoice line items are immutable.
- Renewal invoice uniqueness prevents double billing.

### payments

```text
apps/payments/
  models.py
  adapters/base.py
  adapters/mock.py
  adapters/nomba_sandbox.py
  adapters/nomba_live.py
  selectors.py
  services/create_checkout_order.py
  services/charge_invoice.py
  services/process_nomba_webhook.py
  services/classify_failure.py
  services/create_payment_method_session.py
  serializers.py
  views.py
  urls.py
  tasks.py
  tests/test_mock_adapter.py
  tests/test_checkout_flow.py
  tests/test_tokenized_charge.py
  tests/test_webhook_idempotency.py
```

Implementation order:

1. `PaymentAttempt`
2. `ProcessorEvent`
3. Adapter interface
4. Mock adapter
5. Checkout order service
6. Tokenized-card charge service
7. Webhook processing
8. Failure classifier
9. Sandbox/live adapter stubs

Acceptance:

- Mock adapter supports success, insufficient funds, expired card, timeout.
- Processor events are deduplicated.
- Webhook processing is idempotent.
- Tokenized-card failure maps to dunning decision.

## Sprint 3: Recovery and Portal

### dunning

```text
apps/dunning/
  models.py
  selectors.py
  services/create_policy.py
  services/start_dunning.py
  services/schedule_retry.py
  services/process_retry.py
  services/send_recovery_link.py
  services/apply_final_action.py
  serializers.py
  views.py
  urls.py
  tasks.py
  tests/test_policy_builder.py
  tests/test_retry_schedule.py
  tests/test_failed_payment_recovery.py
  tests/test_final_action.py
```

Implementation order:

1. `DunningPolicy`
2. `DunningPolicyStep`
3. `DunningRun`
4. `NotificationLog`
5. Policy builder
6. Start dunning service
7. Retry schedule service
8. Recovery link service
9. Final action service

Acceptance:

- One active dunning run per invoice.
- Hard failures pause retry until payment method replacement.
- Recoverable failures schedule retry using policy offsets.

### customer portal views

```text
apps/portal/
  views.py
  urls.py
  forms.py
  templates/portal/
    base.html
    home.html
    expired.html
    update_payment.html
    invoice.html
    cancel_confirm.html
  tests/test_portal_access.py
  tests/test_portal_recovery_flow.py
```

Implementation order:

1. Portal session resolver
2. Portal home view
3. Update payment method redirect
4. Pay overdue invoice action
5. Receipt view
6. Cancel confirmation

Acceptance:

- Portal session is signed, scoped, and expiring.
- Customer cannot access another customer's portal.
- Past-due state promotes payment-method update.

## Sprint 4: Events, Analytics, Demo

### events

```text
apps/events/
  models.py
  selectors.py
  services/create_event.py
  services/sign_payload.py
  services/dispatch_delivery.py
  services/retry_delivery.py
  services/replay_event.py
  serializers.py
  views.py
  urls.py
  tasks.py
  tests/test_event_store.py
  tests/test_webhook_signatures.py
  tests/test_delivery_retry.py
  tests/test_replay.py
```

Implementation order:

1. `WebhookEndpoint`
2. `WebhookEvent`
3. `WebhookDelivery`
4. Event creation service
5. Signature service
6. Dispatch task
7. Retry task
8. Replay endpoint

Acceptance:

- Events are signed.
- Delivery is at least once.
- Replay creates a new delivery attempt for the same event payload.

### analytics

```text
apps/analytics/
  selectors.py
  services/refresh_metrics.py
  views.py
  urls.py
  tasks.py
  tests/test_dashboard_metrics.py
```

Implementation order:

1. MRR selector
2. Active subscriptions selector
3. Revenue-at-risk selector
4. Recovery-rate selector
5. Dashboard API

Acceptance:

- Metrics are merchant/environment scoped.
- MRR excludes canceled subscriptions.
- Revenue at risk comes from open failed invoices.

### demo

```text
apps/demo/
  management/commands/seed_demo.py
  management/commands/reset_demo.py
  tests/test_demo_seed.py
```

Implementation order:

1. Create merchant and environment.
2. Create team users.
3. Create Pro Monthly plan.
4. Create customers.
5. Create active, trialing, past-due, and recovered subscriptions.
6. Create webhook endpoints and event history.
7. Create recovery queue seed data.

Acceptance:

- One command resets demo to known state.
- Demo data matches `docs/delivery/seed-data.json`.

## Django Template/UI Build Map

| Screen | Templates or components | Backing endpoint/selectors |
|---|---|---|
| Dashboard Overview | `templates/dashboard/overview.html` | `analytics.views.OverviewView` |
| Plan Builder | `templates/catalog/plan_form.html` | `catalog.views.PlanViewSet` |
| Subscription Detail | `templates/subscriptions/detail.html` | `subscriptions.selectors.subscription_detail` |
| Recovery Queue | `templates/dunning/recovery_queue.html` | `dunning.views.RecoveryQueueView` |
| Customer Portal | `templates/portal/home.html` | portal session resolver |
| Developer Console | `templates/developer/events.html` | `events.views.EventListView` |
| Invoice Detail | `templates/invoices/detail.html` | `invoices.selectors.invoice_detail` |
| Settings and Policies | `templates/settings/billing.html` | accounts/catalog/dunning/events settings |

## Minimum Test Command Targets

```bash
pytest apps/accounts apps/catalog apps/customers
pytest apps/subscriptions apps/invoices apps/payments
pytest apps/dunning apps/portal apps/events
pytest apps/analytics apps/demo
```

## First Hackathon Build Order

1. Foundation and tenant scoping.
2. Plan creation.
3. Customer creation.
4. Mock Nomba adapter.
5. Subscription creation with checkout URL.
6. Payment success webhook to active state.
7. Renewal invoice generation.
8. Tokenized-card failure simulation.
9. Dunning/recovery queue.
10. Customer portal update-card flow.
11. Retry succeeds.
12. Outbound webhook delivery and replay.
13. Dashboard metrics and pitch polish.
