# @subpilot/portal-js

React package for embedding the SubPilot customer billing portal in merchant frontends.

## Install

```bash
npm install @subpilot/portal-js
```

## Inline Usage

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

## Modal Usage

```tsx
import { useState } from "react";
import { SubPilotPortal } from "@subpilot/portal-js";
import "@subpilot/portal-js/styles.css";

export function BillingModal({ portalToken }: { portalToken: string }) {
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
        onClose={() => setOpen(false)}
      />
    </>
  );
}
```

## Client Helper

```ts
import { createSubPilotPortalClient } from "@subpilot/portal-js";

const portal = createSubPilotPortalClient({
  publishableKey: "pk_test_...",
  apiBaseUrl: "https://api.subpilot.dev/api/v1"
});

const data = await portal.loadPortal(portalToken);
```

## Props

| Prop | Type | Default |
|---|---|---|
| `publishableKey` | `string` | Required |
| `token` | `string` | Required |
| `apiBaseUrl` | `string` | `"/api/v1"` |
| `displayMode` | `"inline" \| "modal"` | `"inline"` |
| `open` | `boolean` | `true` |
| `onClose` | `() => void` | `undefined` |
| `showCloseButton` | `boolean` | Modal or `onClose` |
| `closeLabel` | `string` | `"Close"` |
| `modalTitle` | `string` | `"Customer billing portal"` |
| `closeOnOverlayClick` | `boolean` | `true` |
| `className` | `string` | `undefined` |
| `onLoaded` | `(data) => void` | `undefined` |
| `onError` | `(error) => void` | `undefined` |

## Security

Use publishable keys in browser code. Create portal session tokens on your backend with a secret API key, then pass only the short-lived `portal_...` token to the frontend.

Full integration docs: [`docs/technical/customer-portal-sdk.md`](../../docs/technical/customer-portal-sdk.md).
