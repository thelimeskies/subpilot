# Delivery Plan

## Hackathon Strategy

The planning goal is to make the product feel complete even if the implementation is an MVP. Build and demo the deepest slice:

1. Create plan.
2. Create subscription with checkout.
3. Simulate successful initial payment.
4. Show subscription activation and outgoing webhook.
5. Simulate renewal failure.
6. Show dunning timeline and recovery queue.
7. Open customer portal and update payment method.
8. Retry payment and recover invoice.
9. Show architecture, ERD, and API docs as evidence of completeness.

## Suggested Tech Stack

Frontend:

- Next.js or React
- Tailwind or CSS modules
- TanStack Query for API state
- Recharts for metrics

Backend:

- Django
- Django REST Framework
- PostgreSQL
- Django ORM
- Celery workers and Celery Beat
- Redis-backed queue/cache
- drf-spectacular for OpenAPI documentation
- HMAC webhook signing

Integrations:

- Nomba Checkout API for initial payment and tokenization
- Nomba tokenized-card payment for renewals
- Nomba webhooks for payment status
- Email/SMS provider can be mocked for hackathon

## Build Phases

### Phase 0: Product Foundations

Deliverables:

- Docs folder
- ERD
- API spec
- Wireframes
- Demo script

Exit criteria:

- Team can explain product in 2 minutes.
- Team knows what to build first.

### Phase 1: Data and Backend Skeleton

Deliverables:

- Django project and app structure
- Database schema via Django migrations
- Seed data
- API auth placeholder
- Plans, customers, subscriptions, invoices endpoints
- Event log

Exit criteria:

- Can create plan and subscription from API.

### Phase 2: Payment Simulation and Nomba Adapter

Deliverables:

- Nomba adapter service interface
- Sandbox mode for checkout order creation
- Mock mode for deterministic demo
- Django REST Framework webhook ingestion endpoint
- Idempotency keys

Exit criteria:

- Can simulate success/failure without live dependency.
- Can point to where real Nomba calls fit.

### Phase 3: Dashboard UX

Deliverables:

- Dashboard
- Plans list and builder
- Subscriptions list and detail
- Recovery queue
- Developer event logs

Exit criteria:

- Judge can click through core merchant journey.

### Phase 4: Dunning and Customer Portal

Deliverables:

- Dunning policy
- Retry schedule
- Recovery link
- Customer portal
- Payment method update simulation

Exit criteria:

- Failed payment can be recovered in demo.

### Phase 5: Polish and Demo

Deliverables:

- Demo data reset script
- Seeded merchants, customers, plans, subscriptions
- Strong empty/error states
- README and architecture slides
- QA pass

Exit criteria:

- Demo works offline or with mocked Nomba if needed.
- Product story is clear and defensible.

## MVP Backlog

### Must Build

- Dashboard overview
- Plan management
- Subscription state machine
- Invoice state machine
- Dunning retry timeline
- Customer portal recovery flow
- Webhook event log
- API examples

### Should Build

- Proration preview
- Webhook replay
- Export CSV
- Customer timeline
- Role-based access display

### Could Build

- Coupons
- Usage metering
- Revenue forecast
- AI retry suggestions
- Embedded plan table

## Demo Data

Merchant:

- Acme Learning Hub

Plans:

- Starter: NGN 5,000 monthly
- Pro: NGN 15,000 monthly, 14-day trial
- Business: NGN 150,000 annual

Customers:

- Ada Okafor: active Pro
- Chinedu Bello: past_due Pro
- Zainab Musa: trialing Starter
- Tunde Martins: canceling Business

Recovery queue:

- Chinedu Bello, NGN 15,000, failed renewal, attempt 2 of 5, next retry tomorrow

## Judging Narrative

Opening:

"SubPilot is an independent subscription management product built on Nomba payment APIs. Nomba handles the payment primitives; SubPilot handles plan management, subscription lifecycle, proration, dunning, customer self-service, and developer webhooks."

Middle:

"The hard part is not charging once. The hard part is state. We model subscriptions, invoices, payment attempts, retries, and webhooks explicitly so merchants and developers can trust the platform."

Close:

"This lets any business using Nomba APIs launch subscriptions without rebuilding recurring billing from scratch. It gives merchants a complete operating console while keeping the integration developer-friendly."

## Testing Plan

Functional:

- Create plan
- Activate plan
- Create subscription
- Process payment success webhook
- Process payment failure webhook
- Retry payment
- Recover subscription
- Cancel subscription
- Replay webhook

Django-specific:

- Model tests for plan, invoice, payment attempt, and subscription state transitions.
- DRF API tests for authenticated merchant endpoints.
- Celery task tests for billing runs, dunning retries, and outbound webhook dispatch.
- Transaction tests for duplicate webhook and duplicate idempotency-key handling.

State machine:

- Invalid transitions are rejected.
- Terminal states cannot become active without explicit resubscribe.
- Duplicate webhooks do not duplicate events.

Security:

- API key required.
- Portal sessions expire.
- Webhook signatures verified.
- Tenant A cannot read Tenant B.

Performance:

- Lists paginate.
- Billing batch locks due rows.
- Queue workers handle retries.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Nomba sandbox unavailable during demo | Demo failure | Mock adapter with same interface |
| Tokenization response fields differ | Integration delay | Keep adapter isolated |
| Webhook delivery is delayed | State confusion | Use pending states and event log |
| Team overbuilds UI | Core incomplete | Build deepest slice first |
| Proration complexity grows | Time loss | Implement preview for fixed-price only |
| Dunning edge cases explode | Time loss | Ship policy templates and clear final action |

## Final Demo Checklist

- [ ] Seed data loads in one command.
- [ ] Dashboard starts on first screen.
- [ ] Plan creation flow works.
- [ ] Subscription activation flow works.
- [ ] Renewal failure flow works.
- [ ] Recovery queue shows failed invoice.
- [ ] Customer portal resolves failed payment.
- [ ] Webhook event log shows emitted events.
- [ ] ERD and architecture docs are ready.
- [ ] Excalidraw wireframe is ready for judge review.
