# Pitch Deck Outline

This deck should be short, visual, and demo-led. The goal is to prove SubPilot is a complete subscription operations product, not a shallow recurring charge script.

## Slide 1: Title

Title:

- SubPilot

Subtitle:

- Subscription operations, guided from checkout to renewal.

Supporting line:

- An independent subscription billing product using Nomba APIs for checkout, tokenized-card renewals, transfers, and payment webhooks.

Visual:

- Use [Logo Option B](../assets/logo-options/subpilot-option-b-wordmark.svg) or the active horizontal logo.

## Slide 2: Problem

Headline:

- Recurring billing is not just recurring charging.

Points:

- Product teams rebuild plans, invoices, retries, customer portals, and webhooks.
- Failed renewals create support load and revenue leakage.
- Downstream apps need reliable subscription state, not raw payment events.
- Tokenized-card renewals need safe primitives and recovery flows.

Visual:

- Simple flow: plan -> invoice -> charge -> fail -> retry -> recover -> webhook.

## Slide 3: Solution

Headline:

- SubPilot is the subscription operations layer on top of Nomba APIs.

What it handles:

- Plan management
- Billing cycles
- Proration
- Dunning
- Customer self-service
- Tokenized-card primitives
- Webhooks
- Developer SDKs

What Nomba handles:

- Checkout
- Tokenized cards
- Charge API
- Transfers
- Payment webhooks

## Slide 4: Product Surface

Headline:

- One console for recurring revenue operations.

Screens:

- [Dashboard Overview](../ux/mockups/dashboard-overview.svg)
- [Plan Builder](../ux/mockups/plan-builder.svg)
- [Subscription Detail](../ux/mockups/subscription-detail.svg)
- [Recovery Queue](../ux/mockups/recovery-queue.svg)
- [Customer Portal](../ux/mockups/customer-portal.svg)
- [Developer Console](../ux/mockups/developer-console.svg)

Message:

- Owners see revenue.
- Billing teams recover failed invoices.
- Customers self-serve.
- Developers integrate through API/SDK/webhooks.

## Slide 5: Core Demo Flow

Headline:

- From plan creation to recovered revenue.

Steps:

1. Create Pro Monthly plan.
2. Create subscription through API.
3. Nomba checkout tokenizes card.
4. Payment success activates subscription.
5. Renewal fails.
6. Dunning starts.
7. Customer updates card through portal.
8. Retry succeeds.
9. Downstream app receives `dunning.recovered`.

## Slide 6: State Machine Depth

Headline:

- The hard part is state.

Show:

- Subscription state machine.
- Invoice state machine.
- Dunning state machine.
- Webhook delivery state machine.

Reference:

- [State Machine Specification](../technical/state-machines/state-machine-specification.md)

Judging emphasis:

- State-machine completeness.
- Duplicate webhook safety.
- Terminal state rules.
- Idempotency.

## Slide 7: Architecture

Headline:

- Django-first, queue-backed, tenant-safe.

Stack:

- Django
- Django REST Framework
- PostgreSQL
- Celery and Celery Beat
- Redis
- Nomba adapter
- Outbound webhook dispatcher

Reference:

- [Architecture](../technical/architecture.md)
- [Django Model Contracts](../technical/django-model-contracts.md)

## Slide 8: Developer Experience

Headline:

- Downstream teams integrate in minutes.

Show:

- OpenAPI contract.
- Python SDK.
- Django package.
- Node SDK.
- Webhook signature verification.
- Tokenized-card recovery sessions.

Reference:

- [SDK and Packages Plan](../technical/sdk-and-packages.md)
- [OpenAPI Contract](../technical/openapi.yaml)

## Slide 9: Why This Wins

Headline:

- Complete product thinking, not a demo trick.

Points:

- Covers all required track items.
- Makes tokenized cards reusable for downstream teams.
- Handles failed-payment recovery.
- Provides a customer portal.
- Has API, SDK, webhook, ERD, architecture, and state-machine depth.
- Uses Nomba APIs clearly without pretending to be Nomba.

## Slide 10: Close

Headline:

- SubPilot turns Nomba payment primitives into subscription infrastructure.

Final line:

- Launch subscriptions. Recover revenue. Keep downstream systems in sync.

## Speaker Timing

| Section | Time |
|---|---:|
| Problem and solution | 60 seconds |
| Product demo | 3 minutes |
| Architecture and state machines | 90 seconds |
| Developer/API layer | 60 seconds |
| Closing impact | 30 seconds |

Total:

- 7 minutes
