# Subscription Lifecycle

## Purpose

Track a customer's recurring agreement from creation through trial, activation, renewal, failed payment, recovery, pause, cancellation, and terminal states.

## Users

- Customer: subscribes, pauses, cancels, resumes.
- Billing Admin: manages lifecycle actions.
- Developer: provisions access based on webhook events.
- Support: explains current status.

## Django Ownership

Primary app: `subscriptions`

Supporting apps:

- `invoices` for financial documents.
- `payments` for collection state.
- `events` for outbound webhooks.
- `audit` for actor history.

## Core Statuses

| Status | Meaning | Customer Access |
|---|---|---|
| `draft` | Created internally, not started | No |
| `incomplete` | Checkout/payment pending | No or provisional |
| `trialing` | Trial active | Yes |
| `active` | Paid and current | Yes |
| `past_due` | Payment failed, still recoverable | Merchant policy |
| `paused` | Subscription paused | No or limited |
| `unpaid` | Dunning exhausted but not canceled | No |
| `canceling` | Cancels at period end | Yes until period end |
| `canceled` | Ended | No |
| `expired` | Checkout/trial expired before activation | No |

## State Transition Rules

Allowed transitions:

- `draft -> incomplete`
- `incomplete -> active`
- `incomplete -> trialing`
- `incomplete -> expired`
- `trialing -> active`
- `trialing -> past_due`
- `active -> past_due`
- `active -> paused`
- `active -> canceling`
- `active -> canceled`
- `canceling -> canceled`
- `past_due -> active`
- `past_due -> paused`
- `past_due -> unpaid`
- `past_due -> canceled`
- `paused -> active`
- `unpaid -> active`
- `unpaid -> canceled`

Rejected transitions:

- `canceled -> active`
- `expired -> active`
- `draft -> active`
- `unpaid -> trialing`

## Lifecycle Actions

### Create Subscription

Input:

- Customer or customer data
- Plan ID
- Quantity
- Collection method
- Success/cancel URLs
- Metadata

Effects:

- Create customer if needed.
- Create subscription in `incomplete` or `trialing`.
- Create first invoice if payment is due now.
- Create Nomba checkout order for initial payment.
- Append `subscription.created`.

### Activate Subscription

Trigger:

- Nomba payment success webhook.
- Manual admin activation only in test/demo mode.

Effects:

- Mark invoice paid.
- Set `current_period_start`.
- Set `current_period_end`.
- Set status `active`.
- Emit `subscription.activated`.

### Pause Subscription

Modes:

- Pause access only.
- Pause billing and access.

Effects:

- Set status `paused`.
- Store pause reason and actor.
- Emit `subscription.paused`.

### Resume Subscription

Requirements:

- Payment method present.
- No blocking unpaid invoice unless paid or explicitly waived.

Effects:

- Set status `active`.
- Recalculate renewal if billing was paused.
- Emit `subscription.resumed`.

### Cancel Subscription

Modes:

- Immediate cancellation.
- Cancel at period end.

Effects:

- Immediate: set `canceled_at`, status `canceled`.
- Period end: status `canceling`, `cancel_at_period_end=true`.
- Emit `subscription.canceling` or `subscription.canceled`.

## Django Service Pattern

Use services instead of view-level business logic:

```text
apps/subscriptions/services/create_subscription.py
apps/subscriptions/services/activate_subscription.py
apps/subscriptions/services/pause_subscription.py
apps/subscriptions/services/resume_subscription.py
apps/subscriptions/services/cancel_subscription.py
apps/subscriptions/services/change_plan.py
```

Each service should:

- Use `transaction.atomic()`.
- Lock subscription row with `select_for_update()` where needed.
- Validate transition before mutation.
- Append subscription event.
- Create outbound webhook event after durable state change.

## API Requirements

Endpoints:

- `POST /api/v1/subscriptions`
- `GET /api/v1/subscriptions`
- `GET /api/v1/subscriptions/{id}`
- `POST /api/v1/subscriptions/{id}/pause`
- `POST /api/v1/subscriptions/{id}/resume`
- `POST /api/v1/subscriptions/{id}/cancel`
- `POST /api/v1/subscriptions/{id}/preview-change`
- `POST /api/v1/subscriptions/{id}/change`

## UI Requirements

Screens:

- Subscriptions list
- Subscription detail
- Change plan drawer
- Cancel confirmation
- Pause/resume confirmation

Detail screen must show:

- Current status
- Customer
- Plan and quantity
- Renewal date
- Latest invoice
- Payment method summary
- Timeline
- Webhook delivery state
- Action buttons based on status

## Acceptance Tests

- Duplicate activation webhook does not activate twice.
- Invalid transitions return a clear error.
- Cancel-at-period-end keeps access until period end.
- Past-due recovery returns subscription to active.
- Every transition creates an event and audit entry.

## Demo Moment

Show one subscription moving through:

`incomplete -> active -> past_due -> active`

The timeline should make the product feel trustworthy.
