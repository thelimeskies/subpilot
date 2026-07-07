# UX Flows and Screens

## Information Architecture

```mermaid
flowchart TD
  Home[Dashboard Home]
  Plans[Plans]
  Subs[Subscriptions]
  Customers[Customers]
  Invoices[Invoices]
  Recovery[Recovery Queue]
  Developers[Developers]
  Settings[Settings]
  Portal[Customer Portal]

  Home --> Plans
  Home --> Subs
  Home --> Invoices
  Home --> Recovery
  Plans --> PlanCreate[Create/Edit Plan]
  Plans --> PlanDetail[Plan Detail]
  Subs --> SubDetail[Subscription Detail]
  Customers --> CustomerDetail[Customer Timeline]
  Invoices --> InvoiceDetail[Invoice Detail]
  Recovery --> FailedInvoice[Failed Invoice Detail]
  Developers --> ApiKeys[API Keys]
  Developers --> Webhooks[Webhook Endpoints]
  Developers --> EventLogs[Event Logs]
  Settings --> Branding[Portal Branding]
  Settings --> Team[Team and Roles]
  Settings --> BillingPolicy[Billing Policies]
  Portal --> PortalPlan[Plan and Renewal]
  Portal --> PortalPayment[Payment Method]
  Portal --> PortalReceipts[Receipts]
```

## Screen Inventory

### Merchant Dashboard

Purpose: executive and operations overview.

Must show:

- Monthly recurring revenue
- Active subscriptions
- Trialing subscriptions
- Past due subscriptions
- Failed revenue at risk
- Recovery rate
- Recent billing events
- Upcoming renewals
- Quick actions: create plan, create subscription, open recovery queue

### Plans List

Purpose: manage sellable recurring packages.

Must show:

- Product and plan name
- Active/draft/archived state
- Price and interval
- Subscribers count
- Trial days
- Dunning policy
- Last updated
- Actions: edit, clone, archive, view

### Plan Builder

Purpose: create or edit a plan.

Sections:

- Basics: product, plan name, description
- Pricing: amount, currency, interval, custom interval count
- Trial and setup: trial days, setup fee
- Entitlements: feature list, limits
- Billing behavior: proration policy, cancellation policy, dunning policy
- Checkout: allowed payment methods, card tokenization, redirect URLs
- Review and activate

### Subscriptions List

Purpose: operational view of all subscriber contracts.

Must show:

- Customer
- Plan
- Status
- Current period
- Renewal date
- Latest invoice status
- Payment method summary
- MRR/ARR contribution
- Filters: status, plan, date, failed payment, trial ending

### Subscription Detail

Purpose: support, billing, and lifecycle control.

Sections:

- Status header and key dates
- Customer and payment method
- Current plan and price
- Timeline
- Invoices
- Payment attempts
- Entitlements
- Actions: retry payment, change plan, pause, resume, cancel, send recovery link

### Recovery Queue

Purpose: central dunning operations.

Must show:

- Failed invoices ordered by revenue at risk and next action
- Failure reason
- Attempt count
- Next retry
- Customer notification state
- Recovery link status
- Bulk actions: resend links, pause retries, export

### Developer Console

Purpose: API adoption.

Must show:

- Environment switcher: test/live
- API keys
- Webhook endpoints
- Recent events
- Webhook delivery attempts
- Event replay
- Sample payloads
- Idempotency guide

### Customer Portal

Purpose: reduce merchant support load.

Must show:

- Brand header
- Current plan and renewal date
- Payment method summary
- Overdue invoice warning
- Update payment method
- Pay invoice
- Change plan if allowed
- Cancel or pause if allowed
- Invoice receipts

## Merchant First-Run Flow

```mermaid
sequenceDiagram
  participant Owner as Merchant Owner
  participant UI as Merchant Dashboard
  participant Engine as Subscriptions Engine
  participant Nomba as Nomba APIs
  participant App as Merchant App

  Owner->>UI: Create plan
  UI->>Engine: Save draft plan
  Owner->>UI: Activate plan
  UI->>Engine: Activate plan version
  Owner->>UI: Copy checkout link or API sample
  App->>Engine: Create subscription
  Engine->>Nomba: Create checkout order with tokenizeCard=true
  Nomba-->>Engine: checkoutLink and orderReference
  Engine-->>App: checkout_url
```

## Customer Activation Flow

```mermaid
sequenceDiagram
  participant Customer
  participant Checkout as Nomba Checkout
  participant Engine as Subscription Engine
  participant Merchant as Merchant App

  Customer->>Checkout: Pay first invoice
  Checkout-->>Engine: payment_success webhook
  Engine->>Engine: Verify signature and idempotency
  Engine->>Engine: Mark invoice paid
  Engine->>Engine: Activate subscription
  Engine-->>Merchant: subscription.activated webhook
  Merchant-->>Customer: Provision product access
```

## Renewal and Dunning Flow

```mermaid
flowchart TD
  A[Billing cycle due] --> B[Generate invoice]
  B --> C[Attempt tokenized card charge]
  C -->|Success| D[Mark invoice paid]
  D --> E[Keep subscription active]
  E --> F[Emit invoice.payment_succeeded]
  C -->|Recoverable failure| G[Mark invoice open]
  G --> H[Set subscription past_due]
  H --> I[Schedule retry and notify customer]
  I --> J{Retry succeeds?}
  J -->|Yes| D
  J -->|No, attempts remain| I
  J -->|No, exhausted| K[Apply final action]
  K --> L[Pause, cancel, unpaid, or keep past_due]
  C -->|Hard failure| M[Require new payment method]
  M --> N[Send recovery link]
```

## Proration Change Flow

```mermaid
flowchart LR
  A[Billing admin selects new plan] --> B[Engine calculates unused credit]
  B --> C[Engine calculates new charge]
  C --> D[Preview net due]
  D --> E{Admin confirms?}
  E -->|No| F[Discard preview]
  E -->|Yes immediate| G[Create proration invoice]
  G --> H[Attempt charge or apply credit]
  H --> I[Update subscription item]
  E -->|Yes end of cycle| J[Schedule plan change]
```

## Subscription State Machine

```mermaid
stateDiagram-v2
  [*] --> draft
  draft --> incomplete: checkout_started
  incomplete --> active: initial_payment_succeeded
  incomplete --> expired: initial_payment_timeout
  incomplete --> trialing: trial_started
  trialing --> active: trial_payment_succeeded
  trialing --> past_due: trial_payment_failed
  active --> past_due: renewal_failed
  active --> paused: pause_requested
  active --> canceled: cancel_immediate
  active --> canceling: cancel_at_period_end
  canceling --> canceled: period_ended
  paused --> active: resume_success
  past_due --> active: recovery_payment_succeeded
  past_due --> unpaid: dunning_mark_unpaid
  past_due --> paused: dunning_pause
  past_due --> canceled: dunning_cancel
  unpaid --> active: overdue_invoice_paid
  unpaid --> canceled: cancel
  canceled --> [*]
  expired --> [*]
```

## Design Intent

The UI should feel like a serious finance operations product:

- Dense but readable information.
- Tables, filters, status badges, timelines, and focused action panels.
- Minimal decoration.
- Calm neutral base with Signal Teal as a purposeful action color.
- Clear separation between safe actions, destructive actions, and irreversible billing changes.
