# Django Implementation Plan

## Goal

Build SubPilot as a Django-first subscription operations product. Django should own the domain model, API, admin/back-office workflows, scheduled billing jobs, Nomba integration, and webhook delivery.

## Recommended Project Layout

```text
subpilot/
  manage.py
  config/
    settings/
      base.py
      local.py
      production.py
    urls.py
    celery.py
  apps/
    accounts/
    catalog/
    customers/
    subscriptions/
    invoices/
    payments/
    dunning/
    events/
    audit/
    analytics/
  tests/
```

## Core Django Apps

| App | Responsibility |
|---|---|
| `accounts` | Merchants, environments, API keys, team members, RBAC |
| `catalog` | Products, plans, price versions, entitlements |
| `customers` | Customers, payment method token references, portal sessions |
| `subscriptions` | Subscription records, items, lifecycle transitions |
| `invoices` | Invoices, line items, credits, receipts |
| `payments` | Nomba checkout, tokenized-card charges, payment attempts, inbound webhooks |
| `dunning` | Retry policies, failed-payment workflows, recovery links |
| `events` | Internal events, outbound webhook endpoints, delivery attempts |
| `audit` | Immutable audit logs |
| `analytics` | Dashboard metrics, exports, reporting queries |

## Domain Services

Keep business logic out of serializers and views. Use service modules:

```text
apps/subscriptions/services/create_subscription.py
apps/subscriptions/services/change_plan.py
apps/subscriptions/services/cancel_subscription.py
apps/invoices/services/generate_invoice.py
apps/payments/services/nomba_adapter.py
apps/payments/services/process_processor_webhook.py
apps/dunning/services/schedule_retry.py
apps/events/services/dispatch_webhook.py
```

## API Layer

Use Django REST Framework.

Recommended route groups:

- `/api/v1/products`
- `/api/v1/plans`
- `/api/v1/customers`
- `/api/v1/subscriptions`
- `/api/v1/invoices`
- `/api/v1/dunning-policies`
- `/api/v1/webhook-endpoints`
- `/api/v1/events`
- `/api/v1/portal/sessions`
- `/api/v1/nomba/webhooks`

## Background Jobs

Use Celery and Celery Beat.

Tasks:

- `billing.scan_due_subscriptions`
- `billing.process_subscription_renewal`
- `payments.charge_invoice_with_nomba`
- `payments.process_nomba_webhook`
- `dunning.schedule_next_retry`
- `dunning.send_recovery_notification`
- `events.dispatch_outbound_webhook`
- `events.retry_failed_webhooks`
- `analytics.refresh_dashboard_metrics`

## Nomba Adapter

Create a single adapter interface:

```python
class NombaPaymentAdapter:
    def create_checkout_order(self, *, invoice, customer, tokenize_card):
        ...

    def charge_tokenized_card(self, *, invoice, payment_method, idempotency_key):
        ...

    def verify_webhook_signature(self, *, headers, raw_body):
        ...

    def parse_webhook_event(self, *, payload):
        ...
```

Implement modes:

- `MockNombaAdapter` for demo reliability
- `SandboxNombaAdapter` for real sandbox testing
- `LiveNombaAdapter` for production

## Data Integrity

Use:

- `transaction.atomic()` around invoice creation, subscription changes, and payment attempt updates.
- `select_for_update()` when billing due subscriptions or retrying failed invoices.
- Unique constraints for idempotency keys, invoice numbers, event ids, and Nomba processor references.
- Append-only event and audit tables.

## Testing Priorities

1. Subscription state transitions.
2. Invoice generation and renewal dates.
3. Duplicate payment webhook handling.
4. Dunning retry scheduling.
5. Proration preview for upgrades and downgrades.
6. Outbound webhook signing and retry.
7. Tenant isolation in every query.

## Hackathon Build Order

1. Models and migrations for merchant, plan, customer, subscription, invoice, payment attempt, dunning policy, event.
2. DRF endpoints for plans, customers, subscriptions, invoices.
3. Mock Nomba adapter and webhook simulator.
4. Celery task for renewal failure and recovery retry.
5. Dashboard screens wired to seeded data.
6. Customer portal recovery link.
7. Webhook event log and replay.
