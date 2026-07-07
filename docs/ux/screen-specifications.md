# Screen Specifications

These screen specs pair with the individual Excalidraw files in `docs/ux/wireframes/individual/`. Each screen should use the SubPilot brand tokens from `docs/design/design-system.md`: Deep Ink, Signal Teal, Mint Wash, white surfaces, and status colors with labels.

## Screen Map

| Screen | Wireframe | Primary Users | Priority |
|---|---|---|---|
| Dashboard Overview | `individual/dashboard-overview.excalidraw` | Owner, Billing Admin, Finance | P0 |
| Plan Builder | `individual/plan-builder.excalidraw` | Owner, Billing Admin | P0 |
| Subscription Detail | `individual/subscription-detail.excalidraw` | Billing Admin, Support | P0 |
| Recovery Queue | `individual/recovery-queue.excalidraw` | Billing Admin, Support | P0 |
| Customer Portal | `individual/customer-portal.excalidraw` | End Customer | P0 |
| Developer Console | `individual/developer-console.excalidraw` | Developer | P0 |
| Invoice Detail | `individual/invoice-detail.excalidraw` | Finance, Billing Admin, Support | P1 |
| Settings and Policies | `individual/settings-policies.excalidraw` | Owner, Developer, Billing Admin | P1 |

## Global Layout Rules

- Desktop app shell uses a 240px left sidebar, 64px top bar, and 24px content gutters.
- Primary buttons use Signal Teal with Deep Ink or white text depending on contrast.
- Destructive actions use Danger and require a confirmation dialog.
- Status badges always include text, not color alone.
- Tables must support search, filters, pagination, column visibility, and row-level actions.
- Detail screens use a main timeline/content area plus a right-side summary/action panel.
- Customer portal uses a single-column responsive layout and merchant branding.

## Dashboard Overview

Purpose:

- Give the merchant a fast operating view of recurring revenue, active subscriptions, failed payments, and upcoming renewals.

Data:

- MRR
- ARR
- Active subscriptions
- Trialing subscriptions
- Past due subscriptions
- Revenue at risk
- Recovery rate
- Upcoming renewals
- Recent billing events

Primary actions:

- Create plan
- Create subscription
- Open recovery queue
- View API logs

States:

- Empty: show "Create your first recurring plan" and link to Plan Builder.
- Loading: skeleton metric tiles and table rows.
- Error: show retry action and request id.

Acceptance:

- A judge can understand the product's business value from this first screen.
- Revenue-at-risk tile links directly to the recovery queue.

## Plan Builder

Purpose:

- Let a billing admin create and activate a sellable recurring plan.

Sections:

- Basics: product, plan name, description.
- Pricing: amount, currency, setup fee.
- Billing cycle: monthly, annual, custom interval.
- Trial: trial days and trial end behavior.
- Entitlements: feature keys and limits.
- Payment: Nomba checkout methods, card tokenization.
- Dunning: policy selection.
- Review: preview checkout-facing plan summary.

Primary actions:

- Save draft
- Activate plan
- Clone existing plan

Validation:

- Amount must be greater than zero.
- Custom interval requires `interval_count` and `interval_unit`.
- Active price versions cannot be edited.

Acceptance:

- Plan can be created with monthly, annual, or custom billing.
- The UI clearly shows that Nomba is used for payment collection, not product ownership.

## Subscription Detail

Purpose:

- Give support and billing teams a complete view of one customer's subscription state.

Data:

- Customer identity
- Subscription status
- Current period
- Renewal date
- Current plan and quantity
- Default payment method summary
- Latest invoice
- Payment attempts
- Subscription events
- Outbound webhooks

Primary actions:

- Retry payment
- Send portal link
- Change plan
- Pause
- Resume
- Cancel

States:

- Active
- Trialing
- Past due
- Paused
- Canceling
- Canceled

Acceptance:

- Timeline explains how the subscription reached its current state.
- Unsafe actions require confirmation and show customer impact.

## Recovery Queue

Purpose:

- Help billing admins recover failed recurring revenue.

Data:

- Failed invoices
- Failure reason
- Attempt count
- Next retry
- Recovery link status
- Revenue at risk
- Customer notification state

Primary actions:

- Retry now
- Resend recovery link
- Pause retries
- Mark uncollectible
- Open customer portal preview

Filters:

- Plan
- Failure reason
- Attempt count
- Next retry date
- Amount
- Customer segment

Acceptance:

- The queue prioritizes high-value failed invoices and urgent next actions.
- A failed invoice can be recovered through the customer portal flow.

## Customer Portal

Purpose:

- Let subscribers manage billing without contacting support.

Data:

- Merchant brand
- Customer name/email
- Current plan
- Renewal date
- Subscription status
- Payment method summary
- Invoice history

Primary actions:

- Update payment method
- Pay overdue invoice
- Download receipt
- Change plan if allowed
- Cancel if allowed

States:

- Active
- Trialing
- Past due
- Canceled
- Portal session expired

Acceptance:

- Past due state makes the recovery action prominent.
- Portal actions are constrained by merchant policy.

## Developer Console

Purpose:

- Help developers integrate, debug, and trust SubPilot.

Data:

- Test/live API keys
- Webhook endpoint list
- Recent events
- Delivery attempts
- Signature status
- Sample payloads

Primary actions:

- Create API key
- Add webhook endpoint
- Replay event
- Copy payload
- Rotate webhook secret

Acceptance:

- A developer can see the event lifecycle from subscription creation to webhook delivery.
- Failed webhook delivery shows HTTP status, response body preview, attempt count, and next retry.

## Invoice Detail

Purpose:

- Provide a finance-grade view of an invoice, line items, and payment history.

Data:

- Invoice number and status
- Customer
- Subscription
- Line items
- Amounts in minor units and display units
- Payment attempts
- Processor references
- Webhook events

Primary actions:

- Retry payment
- Void
- Mark uncollectible
- Send payment link
- Download receipt
- Export

Acceptance:

- Paid invoices are immutable except for credit/refund records.
- Payment attempts explain processor status and failure reason.

## Settings and Policies

Purpose:

- Centralize billing behavior, Nomba credentials, environments, webhooks, and team roles.

Sections:

- Workspace
- Environments
- Nomba API connection
- API keys
- Webhook endpoints
- Dunning policies
- Portal branding
- Team roles

Acceptance:

- Test and live settings are visibly separated.
- Sensitive credentials are never displayed after creation.
