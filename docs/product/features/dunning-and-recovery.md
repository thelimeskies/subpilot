# Dunning and Recovery

## Purpose

Recover failed recurring payments with automated retries, customer notifications, self-service recovery links, and clear final actions.

## Users

- Billing Admin: configures policy and monitors failures.
- Customer: updates payment method or pays overdue invoice.
- Support: sees why access changed.
- Developer: receives failed/recovered payment events.

## Django Ownership

Primary app: `dunning`

Supporting apps:

- `payments`
- `invoices`
- `customers`
- `events`
- `audit`

## Core Models

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

Final actions:

- `keep_past_due`
- `pause`
- `cancel`
- `mark_unpaid`

### DunningRun

Fields:

- `invoice`
- `subscription`
- `policy`
- `status`
- `attempt_count`
- `started_at`
- `next_retry_at`
- `exhausted_at`
- `recovered_at`

Statuses:

- `active`
- `paused_for_payment_method`
- `recovered`
- `exhausted`
- `canceled`

### NotificationLog

Fields:

- `dunning_run`
- `channel`
- `recipient`
- `template`
- `status`
- `sent_at`
- `error`

## Failure Classification

Recoverable failures:

- Insufficient funds
- Temporary issuer decline
- Network/processor timeout
- Bank unavailable

Hard failures:

- Card expired
- Card stolen/lost
- Token revoked
- Invalid card
- Authentication required and cannot be completed automatically

Rules:

- Recoverable failure schedules next retry.
- Hard failure sends payment method update link and pauses automatic retries.
- If customer updates payment method, retries resume immediately or on next policy step.

## Recovery Flow

1. Renewal payment fails.
2. Invoice remains open.
3. Subscription moves to `past_due`.
4. Dunning run starts.
5. Recovery link is created.
6. Notification is sent.
7. Retry is scheduled.
8. Customer updates payment method or system retries.
9. Payment succeeds.
10. Invoice becomes paid.
11. Subscription becomes active.
12. `dunning.recovered` and `subscription.activated` events are emitted.

## Background Jobs

- `dunning.start_for_failed_invoice`
- `dunning.schedule_next_retry`
- `dunning.send_recovery_notification`
- `dunning.process_due_retries`
- `dunning.apply_final_action`

## UI Requirements

Screens:

- Recovery queue
- Failed invoice detail
- Dunning policy builder
- Subscription detail timeline
- Customer portal past-due state

Queue sorting:

1. Highest amount due
2. Final action soonest
3. Highest attempt count
4. Oldest failure

## Acceptance Tests

- Failed renewal starts dunning exactly once.
- Recoverable failure schedules retry according to policy.
- Hard failure pauses retries until payment method update.
- Exhausted dunning applies configured final action.
- Successful retry marks dunning run recovered.
- Recovery emits webhook events.

## Demo Moment

Simulate Chinedu Bello's failed Pro renewal:

- Attempt 1 fails for insufficient funds.
- Recovery queue shows NGN 15,000 at risk.
- Customer opens portal and updates card.
- Retry succeeds.
- Dashboard recovery rate improves.
