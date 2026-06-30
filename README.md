# SubPilot

SubPilot is a subscription billing and recovery workspace for merchants building on Nomba payment rails.

This repository is organized as a monorepo for the hackathon product:

```text
apps/
  subpilot-admin/        Platform admin console
  merchant-dashboard/    Merchant billing workspace
  customer-portal/       Hosted customer self-service portal
  portal-demo/           Example merchant integration
  landing-page/          Public product site
packages/
  ui/                    Shared React UI package
  portal-js/             Embeddable customer portal package
  subpilot-python/       Python SDK package
backend/
  apps/                  Django domain apps
  config/                Django project configuration
  scripts/               Smoke and demo scripts
```

## Local Setup

```bash
npm install
```

Frontend commands:

```bash
npm run dev:admin
npm run dev:merchant
npm run dev:customer-portal
npm run dev:portal-demo
npm run dev:landing
npm run typecheck
npm run build
```

Backend setup will use the files under `backend/` as the Django service is filled in.

## Planned Product Areas

- Merchant subscription plans, invoices, payments, and customer records.
- Failed-payment recovery and customer self-service payment updates.
- Nomba payment adapter, webhook processing, and reconciliation flow.
- Platform admin tools for support, merchant oversight, and integration health.
- Public landing page and developer-facing integration surfaces.
