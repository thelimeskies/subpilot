# Feature Specs

These feature specs expand the build units in [Feature Breakdown and Build Units](../feature-breakdown-and-build-units.md) into implementation-ready product modules.

## Recommended Review Order

1. [Plan Catalog and Billing Cycles](./plan-catalog-and-billing-cycles.md)
2. [Subscription Lifecycle](./subscription-lifecycle.md)
3. [Invoice and Payment Collection](./invoice-and-payment-collection.md)
4. [Dunning and Recovery](./dunning-and-recovery.md)
5. [Tokenized-Card Primitives](./tokenized-card-primitives.md)
6. [Customer Portal](./customer-portal.md)
7. [Developer Webhooks and Events](./developer-webhooks-and-events.md)
8. [Finance, Support, and Operations](./finance-support-operations.md)

## Implementation Principle

Every feature should answer five questions:

- What user problem does this solve?
- Which Django app owns the behavior?
- Which model state changes?
- Which UI screen proves the feature works?
- Which test proves the feature cannot silently break?
