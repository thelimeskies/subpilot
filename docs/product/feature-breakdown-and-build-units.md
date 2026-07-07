# Feature Breakdown and Build Units

This document breaks SubPilot into concrete build units for a Django implementation. Each unit includes purpose, users, Django ownership, data objects, API surface, background jobs, UI screens, acceptance criteria, and demo value.

## Priority Legend

- **P0**: Required for the hackathon demo and core product story.
- **P1**: Strong differentiator; build after P0 flow works.
- **P2**: Useful polish or post-hackathon scope.

## Effort Units

Use these units for planning:

- **S**: 0.5-1 day
- **M**: 1-2 days
- **L**: 3-5 days
- **XL**: 1+ week

## Product Modules

| Module | Priority | Django Apps | Primary Users | Demo Value |
|---|---|---|---|---|
| Merchant workspace and RBAC | P0 | `accounts`, `audit` | Owner, Admin, Developer | Shows multi-tenant seriousness |
| Product and plan catalog | P0 | `catalog` | Owner, Billing Admin | Satisfies plan management |
| Subscription lifecycle | P0 | `subscriptions`, `events` | Billing Admin, Developer | Shows state-machine depth |
| Checkout and payment methods | P0 | `payments`, `customers` | Customer, Developer | Shows Nomba API usage |
| Invoice generation | P0 | `invoices`, `subscriptions` | Finance, Billing Admin | Makes recurring billing real |
| Dunning and recovery | P0 | `dunning`, `payments`, `events` | Billing Admin, Customer | Strongest judged differentiator |
| Customer portal | P0 | `customers`, `subscriptions`, `invoices` | End Customer | Reduces support and completes UX |
| Webhooks and event delivery | P0 | `events` | Developer | Proves downstream ergonomics |
| Proration | P1 | `subscriptions`, `invoices` | Billing Admin, Customer | Shows billing maturity |
| Analytics and exports | P1 | `analytics`, `invoices` | Owner, Finance | Supports business review |
| Support timeline | P1 | `audit`, `events` | Support Agent | Improves operational completeness |
| Coupons and credits | P2 | `invoices`, `catalog` | Billing Admin | Useful, not required for demo |
| Usage-based billing | P2 | `metering`, `invoices` | SaaS Teams | Future expansion |

## Build Unit Matrix

### U01 Merchant Workspace

| Area | Detail |
|---|---|
| Priority | P0 |
| Effort | M |
| Users | Owner, Developer, Billing Admin, Finance, Support |
| Django apps | `accounts`, `audit` |
| Models | `Merchant`, `Environment`, `TeamMember`, `Role`, `ApiKey`, `AuditLog` |
| APIs | `GET /me`, `GET /merchants/current`, `GET /environments`, `POST /api-keys`, `DELETE /api-keys/{id}` |
| UI | Workspace switcher, environment switcher, API key panel |
| Jobs | None for MVP |
| Acceptance | Every record created by API is scoped by `merchant_id` and `environment`. Test and live keys cannot access each other's data. |
| Demo proof | Toggle Test/Live and show different webhook/API keys. |

### U02 Product Catalog

| Area | Detail |
|---|---|
| Priority | P0 |
| Effort | M |
| Users | Owner, Billing Admin |
| Django apps | `catalog` |
| Models | `Product`, `Plan`, `PriceVersion`, `PlanFeature` |
| APIs | `POST /products`, `POST /plans`, `POST /plans/{id}/activate`, `POST /plans/{id}/archive`, `POST /plans/{id}/clone` |
| UI | Plan list, plan builder, plan detail |
| Jobs | None |
| Acceptance | Plans support monthly, annual, and custom intervals. Active plan prices are immutable; changes create a new price version. |
| Demo proof | Create Pro Monthly plan with trial, entitlements, Nomba checkout options, and dunning policy. |

### U03 Customer Records

| Area | Detail |
|---|---|
| Priority | P0 |
| Effort | S |
| Users | Billing Admin, Support, Developer |
| Django apps | `customers` |
| Models | `Customer`, `PaymentMethod`, `PortalSession` |
| APIs | `POST /customers`, `GET /customers`, `GET /customers/{id}`, `GET /customers/{id}/timeline` |
| UI | Customers list, customer detail, timeline |
| Jobs | Payment method expiry scan later |
| Acceptance | Customer `external_id` is unique per merchant. Payment methods store token references only, never raw card data. |
| Demo proof | Open customer profile and show subscription/payment timeline. |

### U04 Subscription Creation

| Area | Detail |
|---|---|
| Priority | P0 |
| Effort | L |
| Users | Developer, Customer, Billing Admin |
| Django apps | `subscriptions`, `invoices`, `payments`, `events` |
| Models | `Subscription`, `SubscriptionItem`, `Invoice`, `InvoiceLineItem`, `PaymentAttempt`, `SubscriptionEvent` |
| APIs | `POST /subscriptions`, `GET /subscriptions/{id}` |
| UI | Create subscription, subscription detail |
| Jobs | Create checkout session if async |
| Acceptance | Creating a checkout subscription creates an incomplete subscription, first open invoice, payment attempt, and Nomba checkout order with card tokenization enabled. |
| Demo proof | Customer starts Pro plan and receives checkout URL. |

### U05 Subscription State Machine

| Area | Detail |
|---|---|
| Priority | P0 |
| Effort | L |
| Users | Billing Admin, Developer, Support |
| Django apps | `subscriptions`, `events`, `audit` |
| Models | `Subscription`, `SubscriptionEvent`, `AuditLog` |
| APIs | `POST /subscriptions/{id}/pause`, `POST /subscriptions/{id}/resume`, `POST /subscriptions/{id}/cancel` |
| UI | Subscription detail, action confirmation dialogs |
| Jobs | State transition cleanup jobs |
| Acceptance | Invalid transitions are rejected. Terminal states require explicit resubscribe. Every transition appends an event. |
| Demo proof | Show state machine docs and a subscription timeline changing from incomplete to active to past_due to recovered. |

### U06 Invoice Generation

| Area | Detail |
|---|---|
| Priority | P0 |
| Effort | L |
| Users | Finance, Billing Admin, Customer |
| Django apps | `invoices`, `subscriptions` |
| Models | `Invoice`, `InvoiceLineItem`, `CreditNote` |
| APIs | `GET /invoices`, `GET /invoices/{id}`, `POST /invoices/{id}/void`, `POST /invoices/{id}/mark-uncollectible` |
| UI | Invoice list, invoice detail, receipt view |
| Jobs | `billing.scan_due_subscriptions`, `billing.generate_renewal_invoice` |
| Acceptance | Renewal invoices are generated once per billing period and include plan, quantity, proration, credits, and total in minor units. |
| Demo proof | Show invoice detail with line items and payment attempts. |

### U07 Nomba Payment Adapter

| Area | Detail |
|---|---|
| Priority | P0 |
| Effort | M |
| Users | Developer, Customer |
| Django apps | `payments` |
| Models | `PaymentAttempt`, `ProcessorEvent`, `PaymentMethod` |
| APIs | Internal service plus `POST /nomba/webhooks` |
| UI | Payment attempt logs, developer diagnostics |
| Jobs | `payments.charge_invoice_with_nomba`, `payments.process_nomba_webhook` |
| Acceptance | Adapter supports mock, sandbox, and live modes. Webhook processing verifies signature, deduplicates events, and updates payment attempts idempotently. |
| Demo proof | Toggle mock success/failure and show the same subscription flow without breaking demo. |

### U08 Dunning Policy Builder

| Area | Detail |
|---|---|
| Priority | P0 |
| Effort | M |
| Users | Billing Admin, Owner |
| Django apps | `dunning` |
| Models | `DunningPolicy`, `DunningRun`, `NotificationLog` |
| APIs | `POST /dunning-policies`, `GET /dunning-policies`, `PATCH /dunning-policies/{id}` |
| UI | Policy builder, retry timeline preview |
| Jobs | None directly; policies are consumed by retry jobs |
| Acceptance | Policy supports retry offsets, grace period, notification channels, hard-failure behavior, and final action. |
| Demo proof | Show Default SaaS Recovery policy with retry day 0, 1, 3, 7, 14 and final action pause. |

### U09 Failed Payment Recovery

| Area | Detail |
|---|---|
| Priority | P0 |
| Effort | L |
| Users | Billing Admin, Customer, Support |
| Django apps | `dunning`, `payments`, `invoices`, `events` |
| Models | `PaymentAttempt`, `DunningRun`, `PortalSession`, `WebhookEvent` |
| APIs | `POST /invoices/{id}/retry`, `POST /invoices/{id}/payment-link` |
| UI | Recovery queue, failed invoice detail, customer portal payment update |
| Jobs | `dunning.schedule_next_retry`, `dunning.send_recovery_notification`, `payments.retry_failed_invoice` |
| Acceptance | Recoverable failures schedule retries. Hard failures pause retries until a new payment method is added. Successful recovery marks invoice paid and subscription active. |
| Demo proof | Simulate failed renewal, open recovery queue, send portal link, update card, recover invoice. |

### U10 Customer Portal

| Area | Detail |
|---|---|
| Priority | P0 |
| Effort | M |
| Users | End Customer |
| Django apps | `customers`, `subscriptions`, `invoices`, `payments` |
| Models | `PortalSession`, `Customer`, `Subscription`, `Invoice` |
| APIs | `POST /portal/sessions`, `GET /portal/session`, `POST /portal/payment-method`, `POST /portal/invoices/{id}/pay` |
| UI | Portal home, update payment, invoice receipts, cancel confirmation |
| Jobs | Portal session expiry cleanup |
| Acceptance | Portal sessions are signed, scoped, and expiring. Customer can update payment method, pay overdue invoice, view receipts, and cancel if policy allows. |
| Demo proof | Open branded customer portal from recovery queue. |

### U11 Outbound Webhooks

| Area | Detail |
|---|---|
| Priority | P0 |
| Effort | M |
| Users | Developer |
| Django apps | `events` |
| Models | `WebhookEndpoint`, `WebhookEvent`, `WebhookDelivery` |
| APIs | `POST /webhook-endpoints`, `GET /events`, `POST /events/{id}/replay` |
| UI | Developer console, event log, delivery detail |
| Jobs | `events.dispatch_outbound_webhook`, `events.retry_failed_webhooks` |
| Acceptance | Events are signed, delivered at least once, retried with backoff, and replayable. Failed deliveries show status code and response body preview. |
| Demo proof | Show `subscription.activated` delivery and replay button. |

### U12 Proration Preview

| Area | Detail |
|---|---|
| Priority | P1 |
| Effort | M |
| Users | Billing Admin, Customer |
| Django apps | `subscriptions`, `invoices` |
| Models | `SubscriptionChangePreview`, or computed service object |
| APIs | `POST /subscriptions/{id}/preview-change`, `POST /subscriptions/{id}/change` |
| UI | Change plan drawer, proration preview |
| Jobs | Apply scheduled changes at cycle end |
| Acceptance | Preview shows unused credit, new plan charge, net due, effective date, renewal date, and invoice impact before mutation. |
| Demo proof | Upgrade Pro to Business mid-cycle and show net due before confirmation. |

### U13 Analytics and Exports

| Area | Detail |
|---|---|
| Priority | P1 |
| Effort | M |
| Users | Owner, Finance |
| Django apps | `analytics`, `invoices` |
| Models | `MetricSnapshot`, exports can be generated files |
| APIs | `GET /analytics/overview`, `GET /exports/invoices.csv`, `GET /exports/subscriptions.csv` |
| UI | Dashboard metrics, export buttons |
| Jobs | `analytics.refresh_dashboard_metrics` |
| Acceptance | Dashboard shows MRR, active subscriptions, revenue at risk, recovery rate, churn, and upcoming renewals. |
| Demo proof | Start demo on dashboard with live-looking metrics. |

### U14 Support Timeline

| Area | Detail |
|---|---|
| Priority | P1 |
| Effort | S |
| Users | Support Agent, Billing Admin |
| Django apps | `events`, `audit`, `customers` |
| Models | `AuditLog`, `WebhookEvent`, `SubscriptionEvent`, `NotificationLog` |
| APIs | `GET /customers/{id}/timeline`, `GET /subscriptions/{id}/timeline` |
| UI | Customer detail timeline, subscription timeline |
| Jobs | None |
| Acceptance | Timeline combines plan changes, invoice generation, payment attempts, recovery notifications, portal actions, and webhook delivery events. |
| Demo proof | Support can explain exactly why a customer is past_due. |

## MVP Delivery Slices

### Slice 1: Sellable Plan

Units:

- U01 Merchant Workspace
- U02 Product Catalog
- U08 Dunning Policy Builder

Exit:

- Merchant can create and activate a plan with billing cycle, trial, dunning policy, and Nomba checkout settings.

### Slice 2: Subscribe and Activate

Units:

- U03 Customer Records
- U04 Subscription Creation
- U05 Subscription State Machine
- U07 Nomba Payment Adapter
- U11 Outbound Webhooks

Exit:

- API creates an incomplete subscription, checkout payment succeeds, subscription becomes active, webhook is emitted.

### Slice 3: Renew and Recover

Units:

- U06 Invoice Generation
- U09 Failed Payment Recovery
- U10 Customer Portal

Exit:

- Renewal fails, dunning starts, customer updates payment through portal, retry succeeds, subscription returns active.

### Slice 4: Operational Confidence

Units:

- U12 Proration Preview
- U13 Analytics and Exports
- U14 Support Timeline

Exit:

- Billing admin can explain plan changes, failed payments, customer history, and revenue metrics.

## Demo-Critical Acceptance Checklist

- [ ] Create plan with monthly, annual, or custom cycle.
- [ ] Attach dunning policy to plan.
- [ ] Create customer and subscription.
- [ ] Generate first invoice.
- [ ] Create Nomba checkout order with tokenization.
- [ ] Process payment success webhook.
- [ ] Activate subscription.
- [ ] Emit signed outbound webhook.
- [ ] Generate renewal invoice.
- [ ] Simulate failed tokenized-card charge.
- [ ] Move subscription to past_due.
- [ ] Schedule retry and send recovery link.
- [ ] Customer opens portal and updates payment method.
- [ ] Retry succeeds and invoice becomes paid.
- [ ] Subscription returns active.
- [ ] Developer console shows event delivery and replay.
- [ ] Dashboard shows recovered revenue.
