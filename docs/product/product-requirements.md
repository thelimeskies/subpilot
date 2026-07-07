# Product Requirements

## Product Summary

SubPilot is an independent recurring billing platform with a merchant dashboard, customer self-service portal, and developer API. It handles plan management, subscription lifecycle, invoice generation, card token charging through Nomba APIs, dunning, proration, event delivery, and auditability.

## In Scope for Hackathon MVP

- Merchant dashboard
- Plan CRUD with versions
- Customer records
- Subscription create, cancel, pause, resume, upgrade, downgrade
- Monthly, annual, and custom intervals
- Trial support
- Invoice generation
- Tokenized-card payment orchestration through Nomba
- Manual and automatic retry policies
- Payment recovery links
- Customer portal
- Webhook endpoints for downstream systems
- Event log and webhook replay
- ERD and architecture diagrams
- Excalidraw UI wireframes

## Stretch Scope

- Usage-based metering
- Coupons and promotions
- Tax calculations
- Team-based approvals for refunds and credits
- Revenue recognition exports
- Multi-currency billing
- Direct debit mandates
- AI-assisted retry timing
- Embedded no-code checkout widget

## Explicit Non-Goals for MVP

- Raw card storage
- Replacing Nomba's checkout or charge APIs
- Full accounting system
- Full CRM
- Native mobile app
- Marketplace payout automation beyond design-level support

## Core Objects

- Merchant
- Environment
- Product
- Plan
- Price version
- Feature entitlement
- Customer
- Payment method token
- Subscription
- Subscription item
- Invoice
- Invoice line item
- Payment attempt
- Dunning policy
- Notification
- Portal session
- Webhook endpoint
- Webhook event
- Webhook delivery
- Audit log

## Functional Requirements

### Plan Management

- Create products and plans.
- Support fixed amount, currency, billing interval, trial period, setup fee, metadata, and features.
- Version prices so existing subscribers remain stable.
- Archive plans without deleting history.
- Allow plan templates: Basic, Pro, Business, Enterprise.

### Subscription Management

- Create subscription from API, dashboard, or checkout link.
- Support states: draft, incomplete, trialing, active, past_due, paused, canceled, unpaid, expired.
- Support immediate and end-of-cycle cancellation.
- Support pause with or without billing pause.
- Support resume with payment validation.
- Support change plan with proration preview.
- Support subscription quantity changes.
- Store every lifecycle transition as an event.

### Billing Cycles

- Monthly and annual cycles are first-class.
- Custom cycles support interval_count and interval_unit.
- Billing anchor controls renewal date.
- Grace periods are configurable.
- Trial end can trigger invoice generation and collection.

### Invoicing

- Generate invoices for each cycle.
- Generate line items for plan charge, setup fee, proration, credits, discounts, and manual adjustments.
- Track invoice states: draft, open, paid, void, uncollectible, refunded, partially_refunded.
- Support hosted invoice payment link.
- Allow receipt download.

### Payment Orchestration

- Initial payment can use Nomba Checkout with tokenization enabled.
- Renewal payment uses stored token key through Nomba tokenized-card charge.
- Each payment attempt has idempotency key, amount, currency, token reference, status, processor reference, and raw response summary.
- Webhook confirmation is authoritative when processor state changes.
- Reversals and refunds update invoice and subscription state.

### Dunning

- Create dunning policies per merchant or per plan.
- Configure retry cadence: for example day 0, day 1, day 3, day 7, day 14.
- Configure notification channels: email, SMS, webhook.
- Configure grace period and final action: keep past_due, pause, cancel, or mark unpaid.
- Stop retries on hard failure until customer updates payment method.
- Generate secure recovery links.

### Customer Portal

- Secure, time-limited portal sessions.
- View current plan, billing cycle, renewal date, invoice history, payment method summary, and subscription status.
- Update card through Nomba checkout or token update flow.
- Pay overdue invoice.
- Upgrade, downgrade, cancel, pause, or resume if allowed by merchant policy.
- Portal is merchant-branded.

### Webhooks

- Emit signed events for subscription, invoice, payment, customer, and portal changes.
- Retry failed webhook deliveries with exponential backoff.
- Allow replay from event log.
- Provide dashboard inspector with request, response, status code, and attempts.

### Admin and Support

- Search customers, subscriptions, invoices, and payment references.
- Customer timeline.
- Safe support actions with audit logs.
- Export subscriptions and invoices.
- Dashboard metrics.

## Non-Functional Requirements

### Security

- Never store raw card data.
- Encrypt API keys, webhook secrets, and processor tokens where appropriate.
- Scope all records by merchant_id and environment.
- Use RBAC for dashboard actions.
- Use signed webhooks and idempotency keys.

### Reliability

- Payment jobs are retried with backoff.
- Webhook ingestion is idempotent.
- Billing runs are resumable.
- Duplicate processor events do not double-charge or double-provision.
- Out-of-order events are handled by state transitions and timestamps.

### Observability

- Every subscription has a timeline.
- Every invoice has payment attempts.
- Every webhook delivery has request/response logs.
- Background jobs have run ids and metrics.
- Alerts exist for failed billing batches, webhook spike failures, and processor outage.

### Performance

- Dashboard lists should paginate and filter server-side.
- Billing batch should process tenants independently.
- API reads should support cursor pagination.
- Webhook event delivery should be asynchronous.

## Event Taxonomy

| Event | When Emitted |
|---|---|
| `customer.created` | Customer is created |
| `plan.created` | Plan is created |
| `plan.activated` | Plan is made sellable |
| `subscription.created` | Subscription record is created |
| `subscription.trialing` | Trial begins |
| `subscription.activated` | Subscription becomes active |
| `subscription.changed` | Plan, quantity, billing anchor, or metadata changes |
| `subscription.past_due` | Invoice payment fails and grace starts |
| `subscription.paused` | Access or billing pauses |
| `subscription.resumed` | Subscription resumes |
| `subscription.canceled` | Subscription reaches canceled state |
| `invoice.created` | Invoice generated |
| `invoice.payment_succeeded` | Payment confirmed |
| `invoice.payment_failed` | Payment attempt failed |
| `payment_method.updated` | Customer updates payment method |
| `dunning.retry_scheduled` | Retry is scheduled |
| `dunning.exhausted` | Recovery policy reaches final action |
| `webhook.delivery_failed` | Downstream endpoint fails |

## Success Criteria for Demo

- A judge can create a plan, subscribe a customer, simulate payment success, see activation, simulate renewal failure, inspect dunning, update payment through customer portal, and see recovery.
- A developer can read API docs and understand exactly how to integrate.
- The ERD, architecture, and wireframes prove this is more than a UI shell.
