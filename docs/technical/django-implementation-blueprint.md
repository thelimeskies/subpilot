# Django Implementation Blueprint

This is the implementation blueprint for converting the planning package into a Django product. It defines app boundaries, modules, serializers, views, permissions, services, Celery tasks, and test files.

## Project Shape

```text
subpilot/
  manage.py
  config/
    settings/
      base.py
      local.py
      test.py
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
```

## Shared App Conventions

Each app should use this structure where relevant:

```text
apps/<app>/
  admin.py
  apps.py
  models.py
  serializers.py
  permissions.py
  selectors.py
  services/
  tasks.py
  urls.py
  views.py
  tests/
```

Rules:

- `models.py` defines storage only.
- `selectors.py` owns query composition.
- `services/` owns business mutations.
- `views.py` stays thin.
- `tasks.py` calls services, not raw model mutation.
- Tests target services and API behavior directly.

## accounts

Purpose:

- Merchant tenancy, environments, team roles, API keys.

Key files:

- `models.py`: `Merchant`, `Environment`, `TeamMember`, `Role`, `ApiKey`
- `permissions.py`: role and scope checks
- `services/api_keys.py`: create, hash, revoke keys
- `selectors.py`: current merchant/environment lookup

API views:

- `CurrentMerchantView`
- `EnvironmentListView`
- `ApiKeyViewSet`

Tests:

- API key cannot access another merchant.
- Revoked key is rejected.
- Test/live environments are isolated.

## catalog

Purpose:

- Products, plans, price versions, entitlements.

Key files:

- `models.py`: `Product`, `Plan`, `PriceVersion`, `PlanFeature`
- `services/create_plan.py`
- `services/activate_plan.py`
- `services/archive_plan.py`
- `services/clone_plan.py`
- `services/create_price_version.py`

API views:

- `ProductViewSet`
- `PlanViewSet`
- `ActivatePlanView`
- `ArchivePlanView`
- `ClonePlanView`

Tests:

- Active prices are immutable.
- Activating a plan requires a price.
- Monthly, annual, and custom cycles validate.

## customers

Purpose:

- Customer records, payment method display records, portal sessions.

Key files:

- `models.py`: `Customer`, `PaymentMethod`, `PortalSession`
- `services/create_customer.py`
- `services/create_portal_session.py`
- `services/attach_payment_method.py`
- `services/set_default_payment_method.py`

API views:

- `CustomerViewSet`
- `CustomerTimelineView`
- `PaymentMethodListView`
- `PaymentMethodSessionCreateView`

Tests:

- Customer external IDs are unique per merchant.
- Portal sessions expire.
- Payment method token is never returned in API response.

## subscriptions

Purpose:

- Subscription state machine and lifecycle actions.

Key files:

- `models.py`: `Subscription`, `SubscriptionItem`, `SubscriptionEvent`
- `state_machine.py`
- `services/create_subscription.py`
- `services/activate_subscription.py`
- `services/pause_subscription.py`
- `services/resume_subscription.py`
- `services/cancel_subscription.py`
- `services/preview_change.py`
- `services/change_plan.py`

API views:

- `SubscriptionViewSet`
- `PauseSubscriptionView`
- `ResumeSubscriptionView`
- `CancelSubscriptionView`
- `PreviewSubscriptionChangeView`
- `ChangeSubscriptionView`

Tests:

- Invalid transitions are rejected.
- Duplicate activation webhook is idempotent.
- Cancel-at-period-end keeps access until period end.
- Proration preview does not mutate subscription.

## invoices

Purpose:

- Invoice creation, line items, totals, receipts, finance actions.

Key files:

- `models.py`: `Invoice`, `InvoiceLineItem`, `CreditNote`
- `services/create_invoice.py`
- `services/finalize_invoice.py`
- `services/mark_paid.py`
- `services/void_invoice.py`
- `services/mark_uncollectible.py`
- `services/export_invoices.py`

API views:

- `InvoiceViewSet`
- `RetryInvoiceView`
- `VoidInvoiceView`
- `MarkUncollectibleView`
- `PaymentLinkView`

Tests:

- Paid invoice cannot be edited.
- Renewal invoice is created once per period.
- Invoice totals use minor units.

## payments

Purpose:

- Nomba adapter, payment attempts, processor events, tokenized-card charge.

Key files:

- `models.py`: `PaymentAttempt`, `ProcessorEvent`
- `adapters/base.py`
- `adapters/mock.py`
- `adapters/nomba_sandbox.py`
- `adapters/nomba_live.py`
- `services/create_checkout_order.py`
- `services/charge_invoice.py`
- `services/process_nomba_webhook.py`
- `services/classify_failure.py`
- `tasks.py`

API views:

- `NombaWebhookView`
- internal service views only where needed

Tests:

- Processor event deduplication.
- Recoverable failures start dunning.
- Hard failures require card update.
- Mock adapter can run full demo without network.

## dunning

Purpose:

- Failed-payment recovery policies and retry orchestration.

Key files:

- `models.py`: `DunningPolicy`, `DunningRun`, `NotificationLog`
- `services/start_dunning.py`
- `services/schedule_retry.py`
- `services/process_retry.py`
- `services/apply_final_action.py`
- `services/send_recovery_link.py`
- `tasks.py`

API views:

- `DunningPolicyViewSet`
- `RecoveryQueueView`

Tests:

- One active dunning run per invoice.
- Retry offsets are honored.
- Final action is applied exactly once.

## events

Purpose:

- Event store, webhook endpoints, delivery attempts, replay.

Key files:

- `models.py`: `WebhookEndpoint`, `WebhookEvent`, `WebhookDelivery`
- `services/create_event.py`
- `services/sign_payload.py`
- `services/dispatch_delivery.py`
- `services/replay_event.py`
- `tasks.py`

API views:

- `WebhookEndpointViewSet`
- `EventListView`
- `EventDetailView`
- `ReplayEventView`

Tests:

- Payload signatures verify.
- Failed delivery schedules retry.
- Replay creates delivery attempt but not source event.

## analytics

Purpose:

- Dashboard metrics and exports.

Key files:

- `models.py`: `MetricSnapshot`
- `selectors.py`: live dashboard queries
- `services/refresh_metrics.py`
- `tasks.py`

API views:

- `DashboardMetricsView`
- `InvoiceExportView`
- `SubscriptionExportView`

Tests:

- Metrics match seed data.
- Exports respect tenant scoping.

## Milestone Build Order

1. `accounts`, tenancy, API auth.
2. `catalog`, plans, price versions.
3. `customers`, payment method display records.
4. `subscriptions`, state machine.
5. `invoices`, invoice generation.
6. `payments`, mock Nomba adapter.
7. `dunning`, retry/recovery.
8. `events`, webhook delivery.
9. `analytics`, dashboard metrics.
10. SDK/package layer.
