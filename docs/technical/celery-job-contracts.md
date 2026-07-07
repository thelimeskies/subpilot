# Celery Job Contracts

SubPilot needs background jobs for billing cycles, payment retries, dunning notifications, and webhook delivery. This document defines each job's ownership, inputs, idempotency, locking, and failure behavior.

## Global Job Rules

- Jobs must be idempotent.
- Jobs must log `job_id`, `merchant_id`, `environment`, and affected object IDs.
- Jobs that mutate billing state use `transaction.atomic()`.
- Jobs that process due records use `select_for_update(skip_locked=True)`.
- Jobs should emit structured events after durable state changes.
- Jobs should fail loudly for programmer errors but retry for external dependency errors.

## Queue Names

| Queue | Jobs |
|---|---|
| `billing` | Renewal scanning and invoice generation |
| `payments` | Nomba checkout/charge/reconciliation |
| `dunning` | Failed-payment recovery |
| `webhooks` | Outbound event delivery |
| `notifications` | Email/SMS recovery messages |
| `analytics` | Dashboard metric refresh |

## Job: `billing.scan_due_subscriptions`

Purpose:

- Find subscriptions due for renewal.

Schedule:

- Every 15 minutes in demo/test.
- Hourly or more frequently in production based on scale.

Inputs:

- `merchant_id`
- `environment`
- optional `as_of`

Behavior:

- Select active subscriptions where `current_period_end <= as_of`.
- Enqueue `billing.process_subscription_renewal` per subscription.

Idempotency:

- Enqueue key: `renewal:{subscription_id}:{current_period_end}`.

## Job: `billing.process_subscription_renewal`

Purpose:

- Generate renewal invoice and begin payment collection.

Inputs:

- `subscription_id`
- `period_end`

Behavior:

1. Lock subscription.
2. Verify still due and active.
3. Create invoice if not already created for period.
4. Create payment attempt.
5. Enqueue `payments.charge_invoice_with_nomba`.

Failure behavior:

- If subscription no longer active, exit cleanly.
- If invoice exists, reuse it.
- If database conflict, retry.

## Job: `payments.charge_invoice_with_nomba`

Purpose:

- Charge an invoice using the default tokenized payment method.

Inputs:

- `invoice_id`
- `payment_attempt_id`

Behavior:

1. Lock invoice and payment attempt.
2. Validate invoice is open.
3. Validate payment method is active.
4. Call Nomba adapter.
5. Store processor reference.
6. If synchronous failure, classify and enqueue dunning.
7. If pending, wait for webhook or reconciliation.

Retries:

- Retry external network failures with exponential backoff.
- Do not retry hard card failures automatically.

## Job: `payments.process_nomba_webhook`

Purpose:

- Apply verified Nomba webhook events.

Inputs:

- `processor_event_id`

Behavior:

1. Load stored processor event.
2. Deduplicate.
3. Lock payment attempt.
4. Apply terminal state.
5. Update invoice and subscription.
6. Emit SubPilot event.

Idempotency:

- Unique provider event ID.
- Terminal payment attempts cannot be re-terminalized.

## Job: `dunning.start_for_failed_invoice`

Purpose:

- Create dunning run for failed invoice.

Inputs:

- `invoice_id`
- `failure_type`

Behavior:

- Create one active dunning run per invoice.
- Schedule retry if recoverable.
- Create payment recovery portal session.
- Enqueue notification.
- Emit `dunning.started`.

## Job: `dunning.process_due_retries`

Purpose:

- Retry due failed invoices.

Schedule:

- Every 15 minutes.

Behavior:

- Select active dunning runs where `next_retry_at <= now`.
- Enqueue `payments.charge_invoice_with_nomba`.
- Increment attempt count after attempt is created.

## Job: `dunning.apply_final_action`

Purpose:

- Apply dunning policy final action after attempts are exhausted.

Actions:

- Keep past_due.
- Pause subscription.
- Cancel subscription.
- Mark unpaid.

Effects:

- Emit `dunning.exhausted`.
- Emit subscription state event if state changes.

## Job: `events.dispatch_outbound_webhook`

Purpose:

- Deliver a SubPilot event to merchant webhook endpoint.

Inputs:

- `webhook_delivery_id`

Behavior:

1. Load event and endpoint.
2. Sign payload.
3. Send HTTP POST.
4. Store status code and response preview.
5. Mark delivered on 2xx.
6. Schedule retry on failure.

Retry policy:

- 1 min, 5 min, 30 min, 2 hours, 12 hours, 24 hours.
- Exhaust after max attempts.

## Job: `analytics.refresh_dashboard_metrics`

Purpose:

- Precompute dashboard metrics.

Metrics:

- MRR.
- ARR.
- Active subscriptions.
- Trialing subscriptions.
- Past due subscriptions.
- Revenue at risk.
- Recovery rate.
- Churn.

Schedule:

- Every 15 minutes for demo.
- Hourly or event-driven in production.

## Job Test Matrix

| Job | Critical Test |
|---|---|
| `billing.scan_due_subscriptions` | Does not enqueue duplicate renewal jobs |
| `billing.process_subscription_renewal` | Creates one invoice per period |
| `payments.charge_invoice_with_nomba` | Hard failure does not auto-retry |
| `payments.process_nomba_webhook` | Duplicate webhook is no-op |
| `dunning.start_for_failed_invoice` | One active run per invoice |
| `dunning.process_due_retries` | Only due runs are retried |
| `dunning.apply_final_action` | Applies correct policy action |
| `events.dispatch_outbound_webhook` | Failed delivery schedules retry |
| `analytics.refresh_dashboard_metrics` | Metrics match seed data |
