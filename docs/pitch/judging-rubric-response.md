# Judging Rubric Response

This document maps SubPilot directly to the infrastructure-track judging criteria from the prompt.

## Track Requirement Coverage

| Required Area | SubPilot Coverage | Evidence |
|---|---|---|
| Plan management | Products, plans, price versions, entitlements, plan builder | `product/features/plan-catalog-and-billing-cycles.md` |
| Billing cycles | Monthly, annual, custom interval, billing anchor rules | `product/features/plan-catalog-and-billing-cycles.md` |
| Proration | Preview service, upgrade/downgrade drawer, invoice line items | `product/feature-breakdown-and-build-units.md` |
| Dunning | Retry policies, hard failure handling, recovery queue, final actions | `product/features/dunning-and-recovery.md` |
| Failed-payment recovery | Recovery queue, portal links, payment method sessions, retry jobs | `delivery/demo-scenario-and-seed-data.md` |
| Customer self-service portal | Portal sessions, update card, pay invoice, receipts, cancel policy | `product/features/customer-portal.md` |
| Webhooks | Event store, signed delivery, retry, replay, SDK verification | `product/features/developer-webhooks-and-events.md` |
| Tokenized-card primitives | Payment method sessions, default tokens, renewal charges, SDK helpers | `product/features/tokenized-card-primitives.md` |

## Judging Criteria

### State-Machine Completeness

SubPilot defines state machines for:

- Subscriptions
- Invoices
- Payment attempts
- Dunning runs
- Webhook delivery

Evidence:

- [State Machine Specification](../technical/state-machines/state-machine-specification.md)

### Dunning Sophistication

SubPilot includes:

- Retry offsets by policy.
- Grace periods.
- Recoverable vs hard failure classification.
- Customer notification channels.
- Final actions: pause, cancel, mark unpaid, keep past_due.
- Recovery portal links.
- Dunning events.

Evidence:

- [Dunning and Recovery](../product/features/dunning-and-recovery.md)

### Multi-Tenant Cleanliness

SubPilot includes:

- Merchant and environment scoping on all tenant models.
- Test/live separation.
- Merchant-scoped API keys.
- Tenant-scoped webhook endpoints.
- Audit logs for sensitive operations.

Evidence:

- [Django Model Contracts](../technical/django-model-contracts.md)
- [Architecture](../technical/architecture.md)

### API Ergonomics

SubPilot includes:

- OpenAPI contract.
- Idempotency keys.
- Python SDK.
- Django package.
- Node SDK plan.
- Webhook verification helpers.
- Tokenized-card recovery sessions.

Evidence:

- [OpenAPI Contract](../technical/openapi.yaml)
- [SDK and Packages Plan](../technical/sdk-and-packages.md)

## Strongest Demo Proof

The most important demo is:

1. Show dashboard revenue at risk.
2. Open Chinedu Bello failed invoice.
3. Explain recoverable tokenized-card failure.
4. Open customer portal.
5. Update payment method.
6. Retry invoice.
7. Show subscription active again.
8. Show `dunning.recovered` webhook.

This proves plan management, tokenized-card primitives, failed-payment recovery, customer self-service, and downstream webhooks in one coherent flow.
