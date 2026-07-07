# Feature to Screen Traceability

This maps planned product features to the screens and wireframes that prove they are covered.

## Traceability Matrix

| Feature | Priority | Primary Screen | Wireframe | Supporting Docs |
|---|---|---|---|---|
| Merchant dashboard metrics | P0 | Dashboard Overview | `../ux/wireframes/individual/dashboard-overview.excalidraw` | [Analytics unit](./feature-breakdown-and-build-units.md) |
| Plan management | P0 | Plan Builder | `../ux/wireframes/individual/plan-builder.excalidraw` | [Plan catalog spec](./features/plan-catalog-and-billing-cycles.md) |
| Billing cycles | P0 | Plan Builder | `../ux/wireframes/individual/plan-builder.excalidraw` | [Plan catalog spec](./features/plan-catalog-and-billing-cycles.md) |
| Trial setup | P0 | Plan Builder | `../ux/wireframes/individual/plan-builder.excalidraw` | [Plan catalog spec](./features/plan-catalog-and-billing-cycles.md) |
| Subscription lifecycle | P0 | Subscription Detail | `../ux/wireframes/individual/subscription-detail.excalidraw` | [Subscription lifecycle spec](./features/subscription-lifecycle.md) |
| Invoice generation | P0 | Invoice Detail | `../ux/wireframes/individual/invoice-detail.excalidraw` | [Invoice/payment spec](./features/invoice-and-payment-collection.md) |
| Tokenized-card primitives | P0 | Developer Console, Customer Portal | `../ux/wireframes/individual/developer-console.excalidraw`, `../ux/wireframes/individual/customer-portal.excalidraw` | [Tokenized-card primitives](./features/tokenized-card-primitives.md) |
| Nomba checkout integration | P0 | Plan Builder, Developer Console | `../ux/wireframes/individual/plan-builder.excalidraw`, `../ux/wireframes/individual/developer-console.excalidraw` | [SDK/packages](../technical/sdk-and-packages.md) |
| Dunning policy | P0 | Settings and Policies, Recovery Queue | `../ux/wireframes/individual/settings-policies.excalidraw`, `../ux/wireframes/individual/recovery-queue.excalidraw` | [Dunning spec](./features/dunning-and-recovery.md) |
| Failed payment recovery | P0 | Recovery Queue, Customer Portal | `../ux/wireframes/individual/recovery-queue.excalidraw`, `../ux/wireframes/individual/customer-portal.excalidraw` | [Dunning spec](./features/dunning-and-recovery.md) |
| Mobile failed-payment recovery | P0 | Mobile Customer Portal | `../ux/wireframes/individual/mobile-customer-portal.excalidraw` | [Customer portal spec](./features/customer-portal.md) |
| Customer self-service portal | P0 | Customer Portal | `../ux/wireframes/individual/customer-portal.excalidraw` | [Customer portal spec](./features/customer-portal.md) |
| Developer webhooks | P0 | Developer Console | `../ux/wireframes/individual/developer-console.excalidraw` | [Webhooks/events spec](./features/developer-webhooks-and-events.md) |
| Webhook replay confirmation | P0 | Critical Modals | `../ux/wireframes/individual/critical-modals.excalidraw` | [Webhooks/events spec](./features/developer-webhooks-and-events.md) |
| SDKs and packages | P0/P1 | Developer Console | `../ux/wireframes/individual/developer-console.excalidraw` | [SDK/packages plan](../technical/sdk-and-packages.md) |
| Proration preview | P1 | Subscription Detail | `../ux/wireframes/individual/subscription-detail.excalidraw` | [Feature breakdown](./feature-breakdown-and-build-units.md) |
| Retry payment confirmation | P0 | Critical Modals | `../ux/wireframes/individual/critical-modals.excalidraw` | [Invoice/payment spec](./features/invoice-and-payment-collection.md) |
| Cancel subscription confirmation | P0 | Critical Modals | `../ux/wireframes/individual/critical-modals.excalidraw` | [Subscription lifecycle spec](./features/subscription-lifecycle.md) |
| Finance reconciliation | P1 | Invoice Detail | `../ux/wireframes/individual/invoice-detail.excalidraw` | [Finance/support spec](./features/finance-support-operations.md) |
| Support timeline | P1 | Subscription Detail | `../ux/wireframes/individual/subscription-detail.excalidraw` | [Finance/support spec](./features/finance-support-operations.md) |
| Workspace/settings | P1 | Settings and Policies | `../ux/wireframes/individual/settings-policies.excalidraw` | [Django plan](../technical/django-implementation-plan.md) |

## Coverage Gaps to Add Later

- Mobile customer portal wireframe.
- API-key creation modal.
- Webhook replay confirmation modal.
- Plan archive confirmation modal.
- Empty states for no plans, no subscriptions, no failed payments.
- Error state for Nomba API outage.
