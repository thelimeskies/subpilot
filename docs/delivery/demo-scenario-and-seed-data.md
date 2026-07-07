# Demo Scenario and Seed Data

This document defines the exact hackathon demo path and data set. The demo should prove SubPilot is more than a dashboard: it is a subscription operations system using Nomba APIs for payment infrastructure.

## Demo Narrative

Opening line:

"SubPilot helps businesses launch and operate subscriptions without rebuilding recurring billing. Nomba APIs handle checkout, tokenized-card renewals, transfers, and payment webhooks; SubPilot handles plan management, subscription state, invoices, dunning, customer recovery, and developer webhooks."

Core thesis:

- One-time payment is easy.
- Recurring billing is hard because of state, retries, failed payments, proration, customer support, and downstream provisioning.
- SubPilot solves that operational layer.

## Seed Merchant

Merchant:

- Name: Acme Learning Hub
- Industry: online education
- Currency: NGN
- Environment: Test
- Nomba mode: Mock adapter for demo reliability, sandbox adapter configured in settings

Team:

- Owner: Tola Adeyemi
- Billing Admin: Miriam Okoro
- Developer: Femi Johnson
- Finance: Halima Yusuf
- Support: David Eze

## Seed Plans

| Plan | Price | Interval | Trial | Features | Dunning |
|---|---:|---|---:|---|---|
| Starter | NGN 5,000 | Monthly | 7 days | 3 courses, basic support | Default SaaS Recovery |
| Pro | NGN 15,000 | Monthly | 14 days | 10 courses, reports, API access | Default SaaS Recovery |
| Business | NGN 150,000 | Annual | 0 days | Unlimited courses, team seats, priority support | Gentle Enterprise Recovery |

## Seed Dunning Policies

### Default SaaS Recovery

- Retry offsets: day 0, 1, 3, 7, 14
- Grace period: 7 days
- Notifications: email, SMS, webhook
- Final action: pause subscription
- Hard failure behavior: require new payment method

### Gentle Enterprise Recovery

- Retry offsets: day 1, 3, 7, 14, 21
- Grace period: 21 days
- Notifications: email and webhook
- Final action: mark unpaid
- Hard failure behavior: notify billing contact

## Seed Customers

| Customer | Email | Plan | Status | Demo Purpose |
|---|---|---|---|---|
| Ada Okafor | ada@example.com | Pro | Active | Shows healthy subscription |
| Chinedu Bello | chinedu@example.com | Pro | Past due | Main recovery demo |
| Zainab Musa | zainab@example.com | Starter | Trialing | Shows trial lifecycle |
| Tunde Martins | tunde@example.com | Business | Canceling | Shows cancel-at-period-end |
| Kemi Lawal | kemi@example.com | Pro | Active | Shows upcoming renewal |

## Main Demo Flow

### Step 1: Dashboard Overview

Screen:

- Dashboard Overview

Show:

- MRR: NGN 4.8M
- Active subscriptions: 1,284
- Revenue at risk: NGN 312K
- Recovery rate: 68%
- Upcoming renewals
- Recent billing events

Talk track:

"This is the operating console for recurring revenue. The important part is not just revenue; it is the revenue at risk and what the system is doing about it."

### Step 2: Create a Plan

Screen:

- Plan Builder

Action:

- Create or open Pro Monthly.

Show:

- NGN 15,000 monthly
- 14-day trial
- Entitlements
- Dunning policy
- Nomba checkout with card tokenization

Talk track:

"A plan is not only a price. It defines billing cycle, trial behavior, entitlements, dunning, and payment collection."

### Step 3: Developer Creates Subscription

Screen:

- Developer Console

Action:

- Show `POST /api/v1/subscriptions`.
- Show SDK snippet.

Expected system behavior:

- Subscription becomes incomplete.
- Invoice is created.
- Nomba checkout order is created.
- Card tokenization is requested.

Talk track:

"Downstream teams integrate with one subscription API. SubPilot creates the invoice and Nomba checkout session behind the scenes."

### Step 4: Payment Success Activates Subscription

Screen:

- Subscription Detail

Action:

- Simulate Nomba `payment_success` webhook.

Expected system behavior:

- Payment attempt succeeds.
- Invoice becomes paid.
- Subscription becomes active.
- `subscription.activated` webhook is emitted.

Talk track:

"The subscription is activated only after verified payment state changes. The timeline shows every event."

### Step 5: Renewal Fails

Screen:

- Recovery Queue

Action:

- Simulate failed tokenized-card renewal for Chinedu Bello.

Expected system behavior:

- Invoice remains open.
- Payment attempt fails.
- Subscription becomes past_due.
- Dunning run starts.
- Recovery link is created.
- Retry is scheduled.

Talk track:

"This is where subscription systems usually get messy. SubPilot classifies the failure, starts dunning, and gives the billing team an actionable queue."

### Step 6: Customer Self-Service Recovery

Screen:

- Customer Portal

Action:

- Open Chinedu's recovery link.
- Update card through tokenized-card session.
- Retry invoice.

Expected system behavior:

- New token reference is attached.
- Old payment method is no longer default.
- Invoice retry succeeds.
- Subscription returns active.
- Dunning run is marked recovered.

Talk track:

"The customer never gives card details to SubPilot. Nomba handles tokenization; SubPilot stores the token reference and recovers the invoice."

### Step 7: Developer Webhook Replay

Screen:

- Developer Console

Action:

- Show `dunning.recovered` event.
- Replay webhook.

Expected system behavior:

- Delivery attempt is signed.
- Failed deliveries can retry.
- Replay creates a new delivery attempt, not a duplicate event.

Talk track:

"Downstream apps can trust the event stream and dedupe by event ID."

### Step 8: Close with Architecture

Screen/docs:

- Architecture
- ERD
- State Machine Specification

Talk track:

"The UI is only the surface. The core is explicit state machines, idempotency, tenant isolation, and background jobs."

## Demo Reset Requirements

Command:

```bash
python manage.py seed_demo --reset
```

The command should:

- Clear test merchant data.
- Recreate merchant, team, plans, dunning policies, customers, subscriptions, invoices, payment attempts, events.
- Set Chinedu Bello to past_due.
- Set Ada and Kemi to active.
- Set Zainab to trialing.
- Set Tunde to canceling.

## Demo Success Criteria

- Judge understands product in 60 seconds.
- Plan setup is visible.
- Nomba integration point is clear.
- Tokenized-card primitive is explicit.
- Failed renewal and recovery are demonstrated.
- Webhook event delivery is demonstrated.
- Architecture and state-machine docs back up the implementation.
