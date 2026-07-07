# Screen-by-Screen UI Acceptance

Use this checklist when turning the individual Excalidraw files and SVG mockups into Django templates or frontend components. A screen is not ready for demo until its required states, data, actions, and brand checks pass.

## Global Acceptance

Every screen must satisfy:

- Uses the SubPilot tokens from the design system.
- Uses Deep Ink for navigation, titles, and code-heavy surfaces.
- Uses Signal Teal only for primary actions and active focus.
- Uses white surfaces for work areas and Mint Wash for contextual panels.
- Contains no yellow/gold legacy track styling.
- Does not imply SubPilot is owned by Nomba.
- Shows "Uses Nomba APIs for payments" only as integration copy, not as a logo lockup.
- Handles loading, empty, error, and permission-denied states.
- Avoids raw token, PAN, CVV, secret key, or processor-secret display.

## Dashboard Overview

Wireframe:

- [Dashboard Overview Excalidraw](./wireframes/individual/dashboard-overview.excalidraw)

Mockup:

- [Dashboard Overview SVG](./mockups/dashboard-overview.svg)

Purpose:

- Give owner/admin users an operational summary of subscriptions, revenue at risk, recovery, and upcoming renewals.

Required data:

- MRR
- Active subscriptions
- Revenue at risk
- Recovery rate
- Upcoming renewals
- Recent billing events

Required actions:

- Create subscription
- Open recovery queue
- View API logs
- Filter renewals by plan, status, date, and payment method

States:

| State | Required behavior |
|---|---|
| Loading | Skeleton metric tiles and table rows |
| Empty | "No subscriptions yet" with Create plan/Create subscription actions |
| Healthy | Active metrics, upcoming renewals, recent events |
| At risk | Revenue-at-risk tile highlights failed invoices and links to Recovery Queue |
| Permission denied | Hide finance values for support-only users |

Brand checks:

- Sidebar uses Deep Ink.
- Primary action uses Signal Teal.
- Metric cards are white, not tinted except revenue-at-risk contextual state.

## Plan Builder

Wireframe:

- [Plan Builder Excalidraw](./wireframes/individual/plan-builder.excalidraw)

Mockup:

- [Plan Builder SVG](./mockups/plan-builder.svg)

Purpose:

- Let billing admins create pricing, billing cycles, trials, entitlements, payment options, and dunning policy in one flow.

Required data:

- Product
- Plan name
- Amount in minor units
- Currency
- Interval unit and count
- Trial days
- Setup fee
- Entitlements
- Allowed payment methods
- Tokenize-card-for-renewals flag
- Dunning policy

Required actions:

- Save draft
- Activate plan
- Clone plan
- Preview customer checkout summary

States:

| State | Required behavior |
|---|---|
| Draft | Save enabled, Activate disabled until required fields pass |
| Validation error | Inline errors below fields |
| Active plan | Price fields locked; changes create new price version |
| Archived | Read-only with Clone action |

Brand checks:

- Step rail uses restrained Deep Ink text, not large hero styling.
- Live preview uses white surface and Line borders.
- Tokenization option is explicit and visible.

## Subscription Detail

Wireframe:

- [Subscription Detail Excalidraw](./wireframes/individual/subscription-detail.excalidraw)

Mockup:

- [Subscription Detail SVG](./mockups/subscription-detail.svg)

Purpose:

- Explain a subscription's state, plan, invoices, payment method, processor events, and outbound webhooks.

Required data:

- Customer
- Plan
- Status
- Current period
- Trial/cancel dates
- Default payment method summary
- Invoice list
- Lifecycle timeline
- Webhook deliveries

Required actions:

- Pause
- Resume
- Cancel
- Change plan
- Retry invoice
- Send portal link

States:

| State | Required behavior |
|---|---|
| Incomplete | Show checkout/payment pending explanation |
| Trialing | Show trial end and payment method readiness |
| Active | Show next renewal and default payment method |
| Past due | Promote recovery action and failed invoice |
| Canceling | Show access end date |
| Canceled | Disable renewal and retry actions |

Brand checks:

- Timeline event types use labels, not color alone.
- Danger color is used only for destructive or failed states.
- Processor references are masked where needed.

## Recovery Queue

Wireframe:

- [Recovery Queue Excalidraw](./wireframes/individual/recovery-queue.excalidraw)

Mockup:

- [Recovery Queue SVG](./mockups/recovery-queue.svg)

Purpose:

- Help billing/admin/support users triage failed invoices and recover revenue.

Required data:

- Failed invoice
- Customer
- Amount
- Attempt count
- Failure type
- Last processor reference
- Next action
- Recovery link status
- Dunning step

Required actions:

- Retry now
- Send portal link
- Pause retries
- Mark uncollectible
- Export queue

States:

| State | Required behavior |
|---|---|
| Recoverable | Retry schedule and next attempt shown |
| Hard failure | Requires new card and retry disabled until card update |
| Exhausted | Final action visible |
| Recovered | Row leaves active queue and appears in timeline |
| Bulk selected | Bulk actions appear without hiding row detail |

Brand checks:

- Selected row uses Mint Wash.
- Hard failures use warning label plus text.
- Destructive actions require confirmation modal.

## Customer Portal

Wireframe:

- [Customer Portal Excalidraw](./wireframes/individual/customer-portal.excalidraw)
- [Mobile Customer Portal Excalidraw](./wireframes/individual/mobile-customer-portal.excalidraw)

Mockup:

- [Customer Portal SVG](./mockups/customer-portal.svg)

Purpose:

- Let end customers view subscription status, update payment method, pay overdue invoice, download receipts, and cancel if allowed.

Required data:

- Merchant/product display name
- Current plan
- Renewal date
- Status
- Payment method summary
- Open invoices
- Receipt history
- Cancellation policy

Required actions:

- Update payment method
- Pay overdue invoice
- Download receipt
- Change plan if enabled
- Cancel subscription if enabled

States:

| State | Required behavior |
|---|---|
| Active | Plan and next renewal are prominent |
| Past due | Alert appears above plan details and update-card CTA is primary |
| Missing payment method | Add payment method CTA is primary |
| Expired session | Clear error with request-new-link path |
| Mobile | No horizontal scroll at 360px width |

Brand checks:

- Portal is white centered card on Canvas/Mint context.
- Primary CTA spans full width on mobile.
- Does not ask customer to enter raw card data inside SubPilot.

## Developer Console

Wireframe:

- [Developer Console Excalidraw](./wireframes/individual/developer-console.excalidraw)

Mockup:

- [Developer Console SVG](./mockups/developer-console.svg)

Purpose:

- Help downstream product teams integrate subscriptions, payment-method sessions, tokenized-card recovery, and signed webhooks.

Required data:

- API keys
- Environment
- Quickstart snippets
- Webhook endpoints
- Recent events
- Delivery status
- Payload viewer

Required actions:

- Create API key
- Revoke API key
- Create webhook endpoint
- Replay event
- Copy code
- Copy signing secret once

States:

| State | Required behavior |
|---|---|
| No endpoint | Empty state prompts create endpoint |
| Event success | Shows delivered status and response code |
| Event failed | Shows next retry and response preview |
| Secret created | Secret visible once with copy action |
| Read-only developer | Can view docs but cannot revoke keys without permission |

Brand checks:

- Code panels use Deep Ink.
- Copy buttons are icon-friendly and compact.
- Payload viewer never displays secret keys or token values.

## Invoice Detail

Wireframe:

- [Invoice Detail Excalidraw](./wireframes/individual/invoice-detail.excalidraw)

Purpose:

- Make invoice state, line items, attempts, credits, and receipt actions auditable.

Required data:

- Invoice number
- Customer
- Subscription
- Status
- Period
- Line items
- Credits/proration
- Total
- Payment attempts
- Receipt URL

Required actions:

- Retry payment
- Send payment link
- Void
- Mark uncollectible
- Download receipt

States:

| State | Required behavior |
|---|---|
| Draft | Editable line items |
| Open | Pay/retry actions available |
| Paid | Immutable receipt |
| Void | No payment actions |
| Uncollectible | Finance-only final state |

Brand checks:

- Money uses tabular numbers.
- Finance actions are permission-aware.
- Destructive finance actions use confirmation modal.

## Settings and Policies

Wireframe:

- [Settings and Policies Excalidraw](./wireframes/individual/settings-policies.excalidraw)

Purpose:

- Configure dunning policies, environments, webhook endpoints, API keys, and portal branding.

Required data:

- Dunning retry steps
- Final failure action
- Notification settings
- API keys
- Webhook endpoints
- Portal brand settings

Required actions:

- Create/update dunning policy
- Rotate API key
- Create webhook endpoint
- Test webhook endpoint
- Update portal branding

States:

| State | Required behavior |
|---|---|
| Default policy | Protected from accidental deletion |
| Unsaved changes | Save bar appears |
| Invalid retry schedule | Inline validation |
| Webhook test failed | Shows response code and next step |

Brand checks:

- Settings use dense but calm forms.
- No marketing hero layout inside settings.
- Warning and danger states are explicit.

## Critical Modals

Wireframe:

- [Critical Modals Excalidraw](./wireframes/individual/critical-modals.excalidraw)

Purpose:

- Confirm destructive or financially meaningful changes.

Required modal types:

- Cancel subscription
- Pause access
- Retry invoice
- Mark uncollectible
- Revoke API key
- Delete webhook endpoint

Required content:

- Object affected
- Customer impact
- Billing impact
- Webhook/event impact
- Primary action
- Cancel action

Brand checks:

- Modal width remains between 360px and 520px.
- Danger actions use Danger color, not Signal Teal.
- Cancel action is always available.
