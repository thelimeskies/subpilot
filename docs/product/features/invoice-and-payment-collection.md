# Invoice and Payment Collection

## Purpose

Create financial records for subscription charges and collect payment through Nomba APIs without storing raw card data.

## Users

- Customer: pays invoices and receives receipts.
- Finance: reconciles charges and exports reports.
- Billing Admin: retries, voids, or marks invoices uncollectible.
- Developer: listens for invoice/payment webhooks.

## Django Ownership

Primary apps:

- `invoices`
- `payments`

Supporting apps:

- `subscriptions`
- `events`
- `audit`

## Core Models

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

Statuses:

- `draft`
- `open`
- `paid`
- `void`
- `uncollectible`
- `refunded`
- `partially_refunded`

### InvoiceLineItem

Types:

- Plan charge
- Setup fee
- Proration charge
- Proration credit
- Manual credit
- Discount
- Tax

Rules:

- Amounts are stored in minor units.
- Line items are immutable after invoice is paid.

### PaymentAttempt

Fields:

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

Statuses:

- `pending`
- `succeeded`
- `failed`
- `requires_action`
- `canceled`

## Nomba Payment Flow

Initial payment:

1. SubPilot creates invoice.
2. SubPilot creates Nomba checkout order.
3. Checkout order requests card tokenization.
4. Customer pays through Nomba checkout.
5. Nomba sends payment webhook.
6. SubPilot marks invoice paid and stores token reference.

Renewal payment:

1. Billing job creates renewal invoice.
2. SubPilot uses tokenized card charge through Nomba.
3. Payment attempt records Nomba reference.
4. Webhook confirms success/failure.
5. Success keeps subscription active; failure starts dunning.

## Django Services

```text
apps/invoices/services/create_invoice.py
apps/invoices/services/finalize_invoice.py
apps/invoices/services/void_invoice.py
apps/payments/services/create_checkout_order.py
apps/payments/services/charge_tokenized_card.py
apps/payments/services/process_nomba_webhook.py
```

## Background Jobs

- `billing.scan_due_subscriptions`
- `billing.generate_renewal_invoice`
- `payments.charge_invoice_with_nomba`
- `payments.reconcile_pending_attempts`

## API Requirements

Endpoints:

- `GET /api/v1/invoices`
- `GET /api/v1/invoices/{id}`
- `POST /api/v1/invoices/{id}/retry`
- `POST /api/v1/invoices/{id}/void`
- `POST /api/v1/invoices/{id}/mark-uncollectible`
- `POST /api/v1/invoices/{id}/payment-link`

## Edge Cases

- Nomba API returns success but webhook is delayed.
  - Keep attempt pending until confirmation or timeout reconciliation.
- Webhook arrives twice.
  - Deduplicate by event/reference.
- Customer pays old invoice link after subscription canceled.
  - Mark invoice paid, but do not reactivate canceled subscription without explicit policy.
- Processor reverses payment.
  - Emit reversal event and reopen or credit invoice according to status.

## Acceptance Tests

- Renewal invoice is generated only once for a billing period.
- Paid invoice cannot be edited.
- Duplicate webhook does not create duplicate payment attempts.
- Failed payment creates `invoice.payment_failed` event.
- Successful payment creates `invoice.payment_succeeded` event and updates subscription.
