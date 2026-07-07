# Design System

## Design Principles

1. **Operational clarity over decoration**
   - Billing users need to understand money movement, risk, and status quickly.

2. **State is the UI**
   - Subscription, invoice, payment, retry, and webhook states must be visible everywhere they matter.

3. **Preview before mutation**
   - Plan changes, cancellations, proration, retries, and refunds should show impact before confirmation.

4. **Developer trust**
   - API payloads, event logs, signatures, and idempotency should be inspectable.

5. **Customer self-service**
   - Past due and active customers should resolve common billing issues without contacting support.

## Visual Direction

Recommended style: modern fintech operations console for the **SubPilot** brand.

- Background: light neutral
- Primary action: Signal Teal, a confident operational accent
- Data and nav: deep ink, white, soft mint, neutral gray
- Status colors: green success, amber warning, red failure, blue information, gray paused
- Layout: left navigation, top environment switcher, dense tables, detail drawers, timelines

## Design Tokens

```css
:root {
  --color-bg: #f8faf9;
  --color-surface: #ffffff;
  --color-surface-muted: #ecfdf5;
  --color-border: #d8e7e1;
  --color-text: #0b1720;
  --color-text-muted: #52615d;
  --color-primary: #14b8a6;
  --color-primary-strong: #0f766e;
  --color-accent: #f97316;
  --color-success: #15803d;
  --color-warning: #b7791f;
  --color-danger: #b42318;
  --color-info: #2563eb;
  --color-paused: #64748b;
  --radius-sm: 4px;
  --radius-md: 8px;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-5: 24px;
  --space-6: 32px;
  --font-sans: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}
```

## Typography

| Use | Size | Weight |
|---|---:|---:|
| Page title | 28 | 700 |
| Section title | 20 | 650 |
| Card title | 16 | 650 |
| Body | 14 | 400 |
| Table cell | 13 | 400 |
| Metadata | 12 | 500 |
| Badge | 12 | 650 |

Rules:

- No negative letter spacing.
- Avoid oversized headings inside dashboards.
- Use tabular numbers for money, dates, and metrics.

## Components

### Navigation

- Left sidebar for main product areas.
- SubPilot logo mark at the top of the sidebar.
- Environment switcher in top bar: Test and Live.
- Merchant/account selector for multi-tenant operators.

### Status Badge

Subscription statuses:

- Draft: gray
- Incomplete: blue
- Trialing: blue
- Active: green
- Past due: amber
- Paused: gray-blue
- Unpaid: red
- Canceling: amber
- Canceled: gray
- Expired: gray

Invoice statuses:

- Draft
- Open
- Paid
- Void
- Uncollectible
- Refunded
- Partially refunded

### Metric Tile

Used for MRR, ARR, active subscribers, trials, failures, recovery rate.

Must include:

- Label
- Value
- Delta
- Optional sparkline
- Click-through target

### Timeline

Used on subscription, customer, invoice, and webhook details.

Events should include:

- Timestamp
- Actor
- Event type
- Human readable summary
- Raw payload link when relevant

### Policy Builder

Used for dunning, cancellation, and proration settings.

Controls:

- Segmented control for default policy templates
- Numeric steppers for days and attempts
- Toggles for notification channels
- Select menus for final action
- Preview panel for sample timeline

### Data Table

Expected features:

- Server-side pagination
- Search
- Filter chips
- Column visibility
- Export
- Bulk actions where safe
- Empty state with primary action

### Confirmation Dialog

Use for:

- Cancel subscription
- Mark invoice uncollectible
- Archive plan
- Replay webhook
- Force retry payment

Must include:

- What will happen
- Customer impact
- Money impact
- Webhook impact
- Confirm action

## Page Layout Standards

Dashboard:

- 240px sidebar
- 64px top bar
- 24px page gutters
- Metric grid first
- Operational tables below

Detail page:

- Header with status, key metadata, and primary actions
- Two-column layout: main timeline/invoices plus right-side summary panel
- Sticky action area on desktop

Customer portal:

- Single-column centered layout
- Merchant brand header
- Strong overdue state when applicable
- Payment update action must be prominent

## Empty States

Plans empty:

- Message: "Create your first recurring plan."
- Action: Create plan

Subscriptions empty:

- Message: "Subscriptions appear here after customers start a plan."
- Actions: Create subscription, view API quickstart

Recovery empty:

- Message: "No failed payments need attention."
- Secondary: Show recently recovered invoices

Webhooks empty:

- Message: "Add an endpoint to receive billing events."
- Action: Add endpoint

## Error States

Payment failed:

- Show reason, retry schedule, and recovery link.
- Avoid vague "Something went wrong."

Webhook failed:

- Show status code, response body preview, attempt count, next retry.

Proration blocked:

- Show exact reason: unpaid invoice, missing payment method, canceled plan, or invalid effective date.

## Accessibility

- Text contrast should meet WCAG AA.
- All status colors require text labels.
- Forms need labels and inline validation.
- Keyboard navigation for tables, tabs, dialogs, and portal flows.
- Destructive buttons require clear labels and confirmation.
