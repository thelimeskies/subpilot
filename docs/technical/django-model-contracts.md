# Django Model Contracts

This document defines implementation-level model contracts for the Django build. It complements the ERD by specifying fields, constraints, indexes, and service ownership.

## Global Model Conventions

All tenant-scoped models include:

- `id = UUIDField(primary_key=True)`
- `merchant = ForeignKey(Merchant)`
- `environment = CharField(choices=["test", "live"])`
- `created_at`
- `updated_at`

Rules:

- Use integer minor units for all money fields.
- Use `models.JSONField(default=dict, blank=True)` for metadata.
- Use database-level unique constraints for references and idempotency.
- Use `select_for_update()` when processing subscriptions, invoices, payment attempts, and dunning runs.

## accounts

### Merchant

Fields:

- `name`
- `slug`
- `status`: active, suspended
- `default_currency`
- `nomba_account_id`

Constraints:

- Unique `slug`.

Indexes:

- `status`

### Environment

Fields:

- `merchant`
- `mode`: test, live
- `nomba_account_id`
- `nomba_client_id`
- `nomba_client_secret_encrypted`
- `webhook_secret_encrypted`

Constraints:

- Unique `(merchant, mode)`.

### ApiKey

Fields:

- `merchant`
- `environment`
- `name`
- `key_prefix`
- `key_hash`
- `scopes`
- `last_used_at`
- `revoked_at`

Constraints:

- Unique `key_hash`.

## catalog

### Product

Fields:

- `merchant`
- `environment`
- `name`
- `description`
- `status`
- `metadata`

Constraints:

- Unique `(merchant, environment, name)`.

### Plan

Fields:

- `merchant`
- `environment`
- `product`
- `name`
- `description`
- `status`
- `trial_days`
- `dunning_policy`
- `proration_policy`
- `cancellation_policy`
- `metadata`

Constraints:

- Unique `(merchant, environment, product, name)`.

Indexes:

- `(merchant, environment, status)`

### PriceVersion

Fields:

- `plan`
- `amount_minor`
- `currency`
- `interval_unit`
- `interval_count`
- `setup_fee_minor`
- `active_from`
- `active_to`

Constraints:

- At most one active price version per plan.
- `amount_minor > 0`.
- `interval_count > 0`.

## customers

### Customer

Fields:

- `merchant`
- `environment`
- `external_id`
- `email`
- `name`
- `phone`
- `metadata`

Constraints:

- Unique `(merchant, environment, external_id)` when external id is not null.

Indexes:

- `(merchant, environment, email)`

### PaymentMethod

Fields:

- `merchant`
- `environment`
- `customer`
- `provider`: nomba
- `token_encrypted`
- `brand`
- `last4`
- `exp_month`
- `exp_year`
- `status`
- `is_default`
- `fingerprint`
- `metadata`

Constraints:

- One default active payment method per customer.
- Token reference must be encrypted.

Indexes:

- `(merchant, environment, customer, status)`

### PortalSession

Fields:

- `merchant`
- `environment`
- `customer`
- `subscription`
- `invoice`
- `token_hash`
- `allowed_actions`
- `return_url`
- `expires_at`
- `used_at`

Indexes:

- `token_hash`
- `expires_at`

## subscriptions

### Subscription

Fields:

- `merchant`
- `environment`
- `customer`
- `status`
- `billing_anchor`
- `current_period_start`
- `current_period_end`
- `trial_end`
- `cancel_at_period_end`
- `canceled_at`
- `default_payment_method`
- `dunning_policy`
- `metadata`

Indexes:

- `(merchant, environment, status, current_period_end)`
- `(merchant, environment, customer)`

### SubscriptionItem

Fields:

- `subscription`
- `price_version`
- `quantity`
- `status`

Constraints:

- `quantity > 0`.

## invoices

### Invoice

Fields:

- `merchant`
- `environment`
- `customer`
- `subscription`
- `number`
- `status`
- `subtotal_minor`
- `discount_minor`
- `tax_minor`
- `total_minor`
- `amount_due_minor`
- `currency`
- `due_at`
- `paid_at`
- `hosted_payment_url`

Constraints:

- Unique `(merchant, environment, number)`.
- Amount fields cannot be negative except credit line items.

Indexes:

- `(merchant, environment, status, due_at)`
- `(merchant, environment, subscription)`

### InvoiceLineItem

Fields:

- `invoice`
- `type`
- `description`
- `amount_minor`
- `quantity`
- `currency`
- `metadata`

## payments

### PaymentAttempt

Fields:

- `merchant`
- `environment`
- `invoice`
- `payment_method`
- `attempt_number`
- `status`
- `amount_minor`
- `currency`
- `failure_code`
- `failure_message`
- `processor_reference`
- `idempotency_key`
- `next_retry_at`

Constraints:

- Unique `(invoice, attempt_number)`.
- Unique `(merchant, environment, idempotency_key)`.

Indexes:

- `(merchant, environment, status, next_retry_at)`

### ProcessorEvent

Fields:

- `merchant`
- `environment`
- `provider`: nomba
- `provider_event_id`
- `processor_reference`
- `event_type`
- `payload`
- `received_at`
- `processed_at`

Constraints:

- Unique `(provider, provider_event_id)`.

## dunning

### DunningPolicy

Fields:

- `merchant`
- `environment`
- `name`
- `retry_offsets_days`
- `grace_period_days`
- `final_action`
- `notify_email`
- `notify_sms`
- `notify_webhook`
- `hard_failure_behavior`

### DunningRun

Fields:

- `merchant`
- `environment`
- `invoice`
- `subscription`
- `policy`
- `status`
- `attempt_count`
- `started_at`
- `next_retry_at`
- `recovered_at`
- `exhausted_at`

Constraints:

- One active dunning run per invoice.

Indexes:

- `(merchant, environment, status, next_retry_at)`

## events

### WebhookEndpoint

Fields:

- `merchant`
- `environment`
- `url`
- `description`
- `enabled`
- `secret_encrypted`
- `event_filters`

### WebhookEvent

Fields:

- `merchant`
- `environment`
- `event_type`
- `aggregate_type`
- `aggregate_id`
- `payload`
- `occurred_at`

Indexes:

- `(merchant, environment, event_type, occurred_at)`

### WebhookDelivery

Fields:

- `webhook_event`
- `endpoint`
- `status`
- `attempt_count`
- `last_status_code`
- `last_response_body`
- `next_attempt_at`
- `delivered_at`

Indexes:

- `(status, next_attempt_at)`

## Service Ownership

| Service | App | Owns |
|---|---|---|
| `CreatePlanService` | `catalog` | Plan validation and price version creation |
| `CreateSubscriptionService` | `subscriptions` | Customer, subscription, first invoice, checkout session |
| `ActivateSubscriptionService` | `subscriptions` | Activation from paid invoice |
| `GenerateInvoiceService` | `invoices` | Billing period invoice creation |
| `ChargeInvoiceService` | `payments` | Nomba tokenized-card charge |
| `ProcessNombaWebhookService` | `payments` | Processor event validation and state update |
| `StartDunningService` | `dunning` | Failed invoice recovery workflow |
| `DispatchWebhookService` | `events` | Outbound event delivery |
