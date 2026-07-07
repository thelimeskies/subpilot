# Developer Webhooks and Events

## Purpose

Give downstream applications reliable events so they can provision access, revoke access, sync invoices, and react to payment failures.

## Users

- Developer
- Developer Relations
- Platform Operator

## Django Ownership

Primary app: `events`

Supporting apps:

- `subscriptions`
- `invoices`
- `payments`
- `dunning`

## Event Store

Events are append-only.

Fields:

- `id`
- `merchant`
- `environment`
- `event_type`
- `aggregate_type`
- `aggregate_id`
- `payload`
- `occurred_at`
- `created_at`

## Webhook Endpoint

Fields:

- `merchant`
- `environment`
- `url`
- `description`
- `enabled`
- `secret`
- `event_filters`

Rules:

- Secrets are shown only once.
- Disabled endpoints receive no new deliveries.
- Test and live endpoints are separate.

## Delivery Attempt

Fields:

- `event`
- `endpoint`
- `status`
- `attempt_count`
- `last_status_code`
- `last_response_body`
- `next_attempt_at`
- `delivered_at`

## Delivery Rules

- At least once delivery.
- HMAC signed.
- Exponential backoff.
- Replayable from dashboard.
- Merchants dedupe by `event_id`.

## Required Events

Subscription:

- `subscription.created`
- `subscription.activated`
- `subscription.changed`
- `subscription.past_due`
- `subscription.paused`
- `subscription.resumed`
- `subscription.canceled`

Invoice:

- `invoice.created`
- `invoice.payment_succeeded`
- `invoice.payment_failed`
- `invoice.marked_uncollectible`

Dunning:

- `dunning.started`
- `dunning.retry_scheduled`
- `dunning.recovered`
- `dunning.exhausted`

Payment method:

- `payment_method.updated`

## Developer Console UX

Must show:

- API keys
- Environment toggle
- Webhook endpoints
- Recent events
- Delivery detail
- Payload viewer
- Replay action
- Signature verification guide

## Acceptance Tests

- Event is created after durable state mutation.
- Delivery payload is signed.
- Failed delivery retries.
- Replay creates a new delivery attempt without duplicating the source event.
- Event filters are respected.

## Demo Moment

Show `subscription.activated`, open payload, replay event, and show delivery attempt result.
