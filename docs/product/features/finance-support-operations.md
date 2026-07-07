# Finance, Support, and Operations

## Purpose

Give non-developer teams confidence that billing is explainable, searchable, auditable, and exportable.

## Users

- Finance Operator
- Billing Admin
- Support Agent
- Owner
- Platform Operator

## Django Ownership

Primary apps:

- `analytics`
- `audit`
- `invoices`

Supporting apps:

- `events`
- `customers`
- `subscriptions`

## Finance Features

### Invoice Export

Columns:

- Invoice number
- Customer
- Subscription
- Plan
- Status
- Currency
- Subtotal
- Tax
- Discount
- Total
- Amount due
- Paid at
- Processor reference
- Created at

### Revenue Dashboard

Metrics:

- MRR
- ARR
- Active subscriptions
- Trialing subscriptions
- Past due subscriptions
- Revenue at risk
- Recovery rate
- Churned subscriptions

### Reconciliation View

Shows:

- Invoice
- Payment attempt
- Nomba reference
- Webhook confirmation
- Settlement/export status

## Support Features

### Customer Timeline

Timeline combines:

- Subscription changes
- Invoice creation
- Payment attempts
- Failed payment reasons
- Recovery notifications
- Portal actions
- Webhook deliveries
- Admin actions

### Safe Support Actions

Allowed:

- Resend portal link
- Retry invoice if policy allows
- Pause subscription
- Add internal note

Restricted:

- Refunds
- Credits
- API key management
- Team role changes

## Audit Requirements

Every sensitive action records:

- Actor
- Role
- Merchant
- Environment
- Action
- Target object
- Before/after summary
- IP address where available
- User agent where available
- Timestamp

## Acceptance Tests

- Finance export respects merchant/environment scope.
- Support cannot access API keys.
- Audit entry is created for pause, cancel, retry, and policy edits.
- Customer timeline shows events in chronological order.

## Demo Moment

Open a past-due customer timeline and explain the full story in under 30 seconds: invoice generated, Nomba charge failed, recovery link sent, portal opened, card updated, retry succeeded.
