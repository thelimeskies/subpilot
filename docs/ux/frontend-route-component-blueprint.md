# Frontend Route and Component Blueprint

This document maps the planned UI to frontend routes and reusable components. It assumes a React or Next.js frontend consuming the Django REST API.

## Route Map

| Route | Screen | Priority | Wireframe | Mockup |
|---|---|---|---|---|
| `/dashboard` | Dashboard Overview | P0 | `wireframes/individual/dashboard-overview.excalidraw` | `mockups/dashboard-overview.svg` |
| `/plans` | Plans List | P0 | Combined wireframe | None yet |
| `/plans/new` | Plan Builder | P0 | `wireframes/individual/plan-builder.excalidraw` | `mockups/plan-builder.svg` |
| `/plans/:id` | Plan Detail | P1 | Combined wireframe | None yet |
| `/subscriptions` | Subscriptions List | P0 | Combined wireframe | None yet |
| `/subscriptions/:id` | Subscription Detail | P0 | `wireframes/individual/subscription-detail.excalidraw` | `mockups/subscription-detail.svg` |
| `/recovery` | Recovery Queue | P0 | `wireframes/individual/recovery-queue.excalidraw` | `mockups/recovery-queue.svg` |
| `/customers/:id` | Customer Detail | P1 | Subscription/detail pattern | None yet |
| `/invoices/:id` | Invoice Detail | P1 | `wireframes/individual/invoice-detail.excalidraw` | None yet |
| `/developers` | Developer Console | P0 | `wireframes/individual/developer-console.excalidraw` | `mockups/developer-console.svg` |
| `/settings` | Settings and Policies | P1 | `wireframes/individual/settings-policies.excalidraw` | None yet |
| `/portal/:token` | Customer Portal | P0 | `wireframes/individual/customer-portal.excalidraw` | `mockups/customer-portal.svg` |
| `/portal/:token/mobile` | Mobile Portal Reference | P0 | `wireframes/individual/mobile-customer-portal.excalidraw` | None yet |

## Component Groups

### Layout

- `AppShell`
- `SidebarNav`
- `TopBar`
- `EnvironmentSwitcher`
- `MerchantSwitcher`
- `PageHeader`
- `ActionBar`

### Data Display

- `MetricTile`
- `StatusBadge`
- `Money`
- `DateTime`
- `DataTable`
- `FilterBar`
- `Timeline`
- `EmptyState`
- `ErrorState`
- `SkeletonRows`

### Billing

- `PlanBuilderStepper`
- `PriceInput`
- `BillingCycleSelector`
- `EntitlementEditor`
- `DunningPolicySelector`
- `ProrationPreviewPanel`
- `InvoiceLineItems`
- `PaymentAttemptList`

### Recovery

- `RecoveryQueueTable`
- `FailedInvoicePanel`
- `RetryTimeline`
- `RecoveryLinkStatus`
- `FailureReasonBadge`

### Developer

- `ApiKeyPanel`
- `WebhookEndpointList`
- `EventList`
- `EventPayloadViewer`
- `WebhookDeliveryTimeline`
- `CodeExampleBlock`

### Customer Portal

- `PortalHeader`
- `PortalBillingSummary`
- `PaymentMethodSummary`
- `UpdatePaymentMethodButton`
- `InvoiceReceiptList`
- `PortalExpiredState`

### Modals

- `RetryPaymentDialog`
- `CancelSubscriptionDialog`
- `PauseSubscriptionDialog`
- `ReplayWebhookDialog`
- `ArchivePlanDialog`
- `RevokeApiKeyDialog`

## Brand Implementation Tokens

```ts
export const colors = {
  deepInk: "#0B1720",
  signalTeal: "#14B8A6",
  tealEdge: "#0F766E",
  mintWash: "#ECFDF5",
  canvas: "#F8FAF9",
  surface: "#FFFFFF",
  line: "#D8E7E1",
  mutedText: "#52615D",
  danger: "#B42318",
  warning: "#B7791F",
  success: "#15803D",
  info: "#2563EB",
};
```

## Page-Level API Dependencies

| Page | API Calls |
|---|---|
| Dashboard | `GET /analytics/overview`, `GET /subscriptions?renewing_soon=true`, `GET /events` |
| Plan Builder | `POST /plans`, `POST /plans/{id}/activate`, `GET /dunning-policies` |
| Subscription Detail | `GET /subscriptions/{id}`, `POST /preview-change`, `POST /cancel`, `POST /pause`, `POST /resume` |
| Recovery Queue | `GET /invoices?status=open&past_due=true`, `POST /invoices/{id}/retry`, `POST /payment-method-sessions` |
| Customer Portal | `GET /portal/session`, `POST /portal/payment-method`, `POST /portal/invoices/{id}/pay` |
| Developer Console | `GET /events`, `POST /events/{id}/replay`, `GET/POST /webhook-endpoints` |

## Implementation Priority

P0 frontend order:

1. `AppShell`
2. Dashboard Overview
3. Plan Builder
4. Subscription Detail
5. Recovery Queue
6. Customer Portal
7. Developer Console
8. Critical Modals

P1:

1. Invoice Detail
2. Settings and Policies
3. Customer Detail
4. Mobile portal polish
