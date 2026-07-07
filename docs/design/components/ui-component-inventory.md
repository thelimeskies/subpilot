# UI Component Inventory

This document defines the reusable UI components needed to implement the wireframes while staying aligned with the SubPilot design system.

## Foundation Components

### App Shell

Used in:

- Dashboard
- Plans
- Subscriptions
- Recovery
- Developer Console
- Settings

Requirements:

- 240px sidebar.
- 64px top bar.
- Environment switcher.
- Merchant/workspace switcher.
- Search field.
- Uses Deep Ink sidebar and white content surfaces.

### Status Badge

Statuses:

- Subscription: draft, incomplete, trialing, active, past_due, paused, unpaid, canceling, canceled, expired.
- Invoice: draft, open, paid, void, uncollectible, refunded, partially_refunded.
- Payment: pending, succeeded, failed, requires_action, canceled.
- Webhook: pending, delivered, retry_scheduled, exhausted.

Rules:

- Must include text label.
- Use color only as support, never as the sole signal.

### Metric Tile

Used in:

- Dashboard Overview

Variants:

- Revenue
- Count
- Rate
- Warning

Required elements:

- Label
- Value
- Delta
- Optional hint
- Click target

### Data Table

Used in:

- Subscriptions list
- Invoices list
- Recovery queue
- Event logs
- Customers list

Required controls:

- Search
- Filter chips
- Column visibility
- Pagination
- Row actions
- Empty state

### Timeline

Used in:

- Subscription detail
- Customer detail
- Invoice detail
- Webhook event detail

Required elements:

- Timestamp
- Event name
- Actor/source
- Human summary
- Raw payload link where relevant

## Billing Components

### Plan Builder Stepper

Steps:

- Basics
- Pricing
- Billing cycle
- Trial
- Entitlements
- Dunning
- Nomba checkout
- Review

Rules:

- Saved draft persists incomplete forms.
- Active plan price changes create a new version.

### Proration Preview Panel

Shows:

- Current plan credit
- New plan charge
- Net due today
- Effective date
- Renewal date
- Customer impact

Actions:

- Confirm immediate change
- Schedule for renewal
- Cancel

### Dunning Policy Builder

Controls:

- Retry offsets
- Grace period
- Final action
- Notification channels
- Hard failure behavior

Preview:

- Timeline of retry attempts.
- Final action date.

### Recovery Action Panel

Used in:

- Recovery Queue
- Invoice Detail
- Subscription Detail

Actions:

- Retry now
- Resend recovery link
- Pause retries
- Mark uncollectible
- Open customer portal

## Developer Components

### API Key Panel

Requirements:

- Show prefix only after creation.
- Copy button only at creation time for full key.
- Revoke action requires confirmation.

### Webhook Event Viewer

Shows:

- Event type
- Event ID
- Payload
- Delivery attempts
- Status code
- Response body preview
- Replay action

### Code Example Block

Languages:

- Python
- Django
- TypeScript
- curl

Requirements:

- Copy button.
- Environment-specific key placeholders.
- Idempotency-key examples.

## Customer Portal Components

### Portal Header

Shows:

- Merchant brand
- Customer email/name
- Secure session indicator

### Billing Summary

Shows:

- Current plan
- Status
- Renewal date
- Amount
- Payment method summary

### Payment Method Update CTA

States:

- Normal
- Past due urgent
- Processing
- Success
- Failure

Rules:

- Never show raw card details.
- Route through Nomba tokenized flow.

## Confirmation Dialogs

Required dialogs:

- Cancel subscription
- Pause subscription
- Retry payment
- Mark invoice uncollectible
- Void invoice
- Replay webhook
- Revoke API key
- Archive plan

Each dialog must include:

- What will happen.
- Customer impact.
- Billing impact.
- Webhook impact.
- Confirmation action.
