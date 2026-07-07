# SubPilot Portal SDK Demo

Sample merchant frontend that embeds `@subpilot/portal-js`.

## Run

```bash
npm run dev:portal-demo
```

Open:

```text
http://localhost:5177/
```

## What It Shows

- Installing `@subpilot/portal-js`.
- Rendering `<SubPilotPortal />`.
- Switching between inline and modal display modes.
- Passing `open`, `onClose`, `showCloseButton`, and `closeLabel`.
- Calling `createSubPilotPortalClient`.
- Using a local Vite proxy for `/api`.

## Local Defaults

The demo defaults to:

- Publishable key: `pk_test_local`
- API base URL: `/api/v1`
- Portal token: the current local sample token in `PortalDemoApp.tsx`

`pk_test_local` is accepted by the local backend for development. Real merchant frontends should use the `pk_test_...` or `pk_live_...` value from the Developers SDK tab.
