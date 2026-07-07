# Customer Portal SDK and Embedded Portal

This document describes how merchants integrate the SubPilot customer portal in their own frontend using `@subpilot/portal-js`, and how it relates to the hosted customer portal app.

## Overview

SubPilot supports two customer portal delivery modes:

| Mode | Who hosts it | Use case |
|---|---|---|
| Hosted portal | SubPilot | Merchant sends customers a secure link like `/session/{portal_token}`. Fastest path for billing support and dunning recovery. |
| Embedded portal SDK | Merchant frontend | Merchant wants the portal inside their own app, modal, billing settings page, or account area. |

Both modes use the same package implementation:

- `packages/portal-js`: reusable React component and client helpers.
- `apps/customer-portal`: hosted standalone customer portal app that consumes `@subpilot/portal-js`.
- `apps/portal-demo`: sample merchant frontend that consumes `@subpilot/portal-js`.

## Security Model

The portal uses two separate browser-facing values:

| Value | Example | Safe in browser | Purpose |
|---|---|---:|---|
| Publishable key | `pk_test_...`, `pk_live_...` | Yes | Identifies the merchant environment for frontend usage. |
| Portal token | `portal_...` | Yes, short-lived | Grants scoped customer portal access for one customer/session. |

Secret API keys are never used in frontend code:

| Value | Example | Safe in browser | Purpose |
|---|---|---:|---|
| Secret API key | `nse_test_...` | No | Server-side REST API access, including portal session creation. |

Rules:

- Create portal tokens on the merchant backend with a secret API key.
- Pass only the publishable key and portal token to the frontend.
- Portal tokens are hashed at rest and expire.
- Portal tokens carry `allowed_actions`, so a customer can only perform the actions granted when the session is created.
- SDK requests send `X-SubPilot-Publishable-Key`; if the key is not `pk_test_local`, it must match the portal session environment.

## Merchant Dashboard Setup

In the merchant dashboard:

1. Open `Developers`.
2. Open the `SDK` tab.
3. Choose `Test mode` or `Live mode`.
4. Copy the publishable key.
5. Install and configure `@subpilot/portal-js`.

The same tab includes copyable snippets for:

- Package installation.
- React component usage.
- Server-side portal token creation.

Publishable keys can be rotated from the SDK tab. After rotation, merchant frontends using the old key must be redeployed with the new key.

## Backend Endpoints

### Publishable Keys

Dashboard-authenticated endpoint:

```http
GET /api/v1/api-keys/publishable-key/
```

Response:

```json
{
  "keys": [
    { "mode": "live", "publishable_key": "pk_live_..." },
    { "mode": "test", "publishable_key": "pk_test_..." }
  ]
}
```

Rotate one key:

```http
POST /api/v1/api-keys/publishable-key/
Content-Type: application/json

{ "mode": "test" }
```

Response:

```json
{
  "mode": "test",
  "publishable_key": "pk_test_..."
}
```

### Portal Session Creation

Server-side endpoint. Call this from the merchant backend, not from browser code:

```http
POST /api/v1/customers/{customer_id}/portal-sessions/
Authorization: Bearer nse_test_...
Content-Type: application/json

{
  "allowed_actions": [
    "view_subscriptions",
    "view_invoices",
    "update_payment_method",
    "pay_invoice",
    "cancel_subscription"
  ],
  "ttl_minutes": 60,
  "send_email": false
}
```

The response includes a plaintext `token` exactly once. Send that token to the customer frontend.

### Portal Context

SDK endpoint:

```http
GET /api/v1/portal/context
Authorization: Portal portal_...
X-SubPilot-Publishable-Key: pk_test_...
```

The SDK maps the backend response into frontend-friendly `PortalData`.

## Installing the SDK

```bash
npm install @subpilot/portal-js
```

Import the component and stylesheet:

```tsx
import { SubPilotPortal } from "@subpilot/portal-js";
import "@subpilot/portal-js/styles.css";
```

## Inline Portal Example

```tsx
import { SubPilotPortal } from "@subpilot/portal-js";
import "@subpilot/portal-js/styles.css";

export function BillingSettings({ portalToken }: { portalToken: string }) {
  return (
    <SubPilotPortal
      publishableKey="pk_test_..."
      token={portalToken}
      apiBaseUrl="https://api.subpilot.dev/api/v1"
    />
  );
}
```

Inline mode is the default. It renders the portal directly in the page.

## Modal Portal Example

```tsx
import { useState } from "react";
import { SubPilotPortal } from "@subpilot/portal-js";
import "@subpilot/portal-js/styles.css";

export function BillingPortalModal({ portalToken }: { portalToken: string }) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button type="button" onClick={() => setOpen(true)}>
        Manage billing
      </button>

      <SubPilotPortal
        publishableKey="pk_test_..."
        token={portalToken}
        apiBaseUrl="https://api.subpilot.dev/api/v1"
        displayMode="modal"
        open={open}
        showCloseButton
        closeLabel="Done"
        modalTitle="Manage billing"
        onClose={() => setOpen(false)}
      />
    </>
  );
}
```

Modal mode:

- Renders a full-screen overlay.
- Uses `role="dialog"` and `aria-modal="true"`.
- Closes when the close button is clicked.
- Can close on overlay click when `closeOnOverlayClick` is true.
- Returns `null` when `open={false}`.

## Client Helper Example

Use the client helper when the merchant wants custom UI around SubPilot data:

```ts
import { createSubPilotPortalClient } from "@subpilot/portal-js";

const portal = createSubPilotPortalClient({
  publishableKey: "pk_test_...",
  apiBaseUrl: "https://api.subpilot.dev/api/v1"
});

const data = await portal.loadPortal(portalToken);
```

Available client methods:

| Method | Purpose |
|---|---|
| `loadPortal(token)` | Fetch customer, merchant, subscriptions, invoices, and payment methods. |
| `attachPaymentMethod(token, customerId, input)` | Attach a tokenized/mock payment method from the portal. |
| `payInvoice(token, invoiceId)` | Pay an open invoice. |
| `cancelSubscription(token, subscriptionId)` | Cancel a subscription at period end. |

## Component Props

| Prop | Type | Default | Description |
|---|---|---|---|
| `publishableKey` | `string` | Required | Browser-safe merchant environment key. |
| `token` | `string` | Required | Short-lived portal session token. |
| `apiBaseUrl` | `string` | `"/api/v1"` | API base URL. Use a full URL in production. |
| `displayMode` | `"inline" \| "modal"` | `"inline"` | Render directly in page or inside SDK modal overlay. |
| `open` | `boolean` | `true` | Controlled visibility. Useful for modal mode. |
| `onClose` | `() => void` | `undefined` | Called when the SDK close button or overlay close fires. |
| `showCloseButton` | `boolean` | `displayMode === "modal" || !!onClose` | Whether to show the top close action. |
| `closeLabel` | `string` | `"Close"` | Text for the close button. |
| `modalTitle` | `string` | `"Customer billing portal"` | Accessible label for modal dialog. |
| `closeOnOverlayClick` | `boolean` | `true` | Allows modal overlay click to call `onClose`. |
| `className` | `string` | `undefined` | Extra class added to the portal root. |
| `onLoaded` | `(data: PortalData) => void` | `undefined` | Called after portal context loads. |
| `onError` | `(error: Error) => void` | `undefined` | Called when loading or mutation fails. |

## Data Types

The SDK exports:

- `PortalData`
- `PortalCustomer`
- `PortalMerchant`
- `PortalSubscription`
- `PortalInvoice`
- `PortalPaymentMethod`
- `CardBrand`
- `Currency`
- `SubPilotPortalProps`
- `SubPilotPortalClient`

These types are suitable for merchant TypeScript apps that want to build custom portal surfaces.

## Hosted Portal App

The hosted customer portal app lives in:

```text
apps/customer-portal
```

Run it locally:

```bash
npm run dev:customer-portal
```

Default local URL:

```text
http://localhost:5176/session/{portal_token}
```

The app uses:

```tsx
<SubPilotPortal
  publishableKey={import.meta.env.VITE_SUBPILOT_PUBLISHABLE_KEY ?? "pk_test_local"}
  token={token}
  apiBaseUrl={import.meta.env.VITE_API_BASE ?? "/api/v1"}
/>
```

For local development, Vite proxies `/api` to Django at `http://localhost:8000`.

## Demo App

The SDK demo app lives in:

```text
apps/portal-demo
```

Run it locally:

```bash
npm run dev:portal-demo
```

Default URL:

```text
http://localhost:5177/
```

The demo includes:

- Publishable key input.
- Portal token input.
- API base URL input.
- Inline/modal presentation selector.
- Embedded portal preview.
- Client helper probe.
- Copyable install and usage snippets.

## Local Development

Start the backend:

```bash
cd backend
./.venv/bin/python manage.py runserver 0.0.0.0:8000
```

Start the hosted portal:

```bash
npm run dev:customer-portal
```

Start the SDK demo:

```bash
npm run dev:portal-demo
```

Build and check:

```bash
npm --workspace @subpilot/portal-js run typecheck
npm --workspace @subpilot/portal-js run build
npm --workspace @subpilot/customer-portal-app run typecheck
npm --workspace @subpilot/customer-portal-app run build
npm --workspace @subpilot/portal-demo run typecheck
npm --workspace @subpilot/portal-demo run build
```

## Error Handling

Common errors:

| Error | Likely cause | Fix |
|---|---|---|
| `Portal token expired.` | Session TTL elapsed. | Create a new portal session on the merchant backend. |
| `Invalid portal token.` | Token is missing, malformed, or not found. | Pass the token returned from portal session creation. |
| `Publishable key does not match portal session.` | Wrong environment key or stale rotated key. | Use the publishable key for the same test/live environment as the portal token. |
| Request returns HTML instead of JSON | Frontend dev server is handling `/api` instead of Django. | Configure Vite proxy or use a full `apiBaseUrl`. |
| Portal renders empty billing data | Customer has no invoices/subscriptions/payment methods. | Create or attach billing resources for that customer. |

## Production Checklist

- Use `pk_live_...` only for live customer sessions.
- Keep `nse_live_...` secret API keys on the server only.
- Generate portal sessions server-side after authenticating the customer in the merchant app.
- Use short TTLs for customer portal sessions.
- Restrict `allowed_actions` to the workflow the customer needs.
- Configure CORS for merchant frontend origins if using a full API domain.
- Rotate publishable keys when frontend credentials are exposed in the wrong environment.
- Test both inline and modal rendering on mobile widths.
