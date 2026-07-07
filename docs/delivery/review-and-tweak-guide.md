# Review and Tweak Guide

## What to Review First

1. Product scope: [Product Requirements](../product/product-requirements.md)
2. User coverage: [Users and Stories](../product/users-and-stories.md)
3. Feature units: [Feature Breakdown and Build Units](../product/feature-breakdown-and-build-units.md)
4. Unit dependencies and tests: [Build Unit Dependency and Test Contracts](../product/build-unit-dependency-and-test-contracts.md)
5. RBAC: [RBAC Permissions Matrix](../product/rbac-permissions-matrix.md)
6. UI coverage: [UX Flows and Screens](../ux/ux-flows-and-screens.md)
7. Technical depth: [Architecture](../technical/architecture.md) and [Data Model and ERD](../technical/data-model-erd.md)
8. State machines: [State Machine Specification](../technical/state-machines/state-machine-specification.md)
9. Django model contracts: [Django Model Contracts](../technical/django-model-contracts.md)
10. Django implementation blueprint: [Django Implementation Blueprint](../technical/django-implementation-blueprint.md)
11. Nomba integration: [Nomba Integration Contract](../technical/nomba-integration-contract.md)
12. Celery jobs: [Celery Job Contracts](../technical/celery-job-contracts.md)
13. API ergonomics: [API and Webhooks](../technical/api-and-webhooks.md)
14. OpenAPI contract: [OpenAPI YAML](../technical/openapi.yaml)
15. Django build plan: [Django Implementation Plan](../technical/django-implementation-plan.md)
16. Django file-by-file execution: [Django File-by-File Build Plan](./django-file-by-file-build-plan.md)
17. Frontend blueprint: [Frontend Route and Component Blueprint](../ux/frontend-route-component-blueprint.md)
18. SDK/package strategy: [SDK and Packages Plan](../technical/sdk-and-packages.md)
19. Tokenized-card primitives: [Tokenized-Card Primitives](../product/features/tokenized-card-primitives.md)
20. Feature-to-screen coverage: [Feature to Screen Traceability](../product/feature-to-screen-traceability.md)
21. Visual direction: [Design System](../design/design-system.md)
22. UI components: [UI Component Inventory](../design/components/ui-component-inventory.md)
23. Brand: [Brand Identity](../design/brand-identity.md)
24. Logo options: [Logo Options](../design/logo-options.md)
25. Brand board: [Brand Board](../design/brand-board.svg)
26. Demo scenario: [Demo Scenario and Seed Data](./demo-scenario-and-seed-data.md)
27. Seed data: [Seed Data JSON](./seed-data.json)
28. Implementation backlog: [Implementation Backlog](./implementation-backlog.md)
29. E2E test plan: [End-to-End Test Plan](./end-to-end-test-plan.md)
30. QA gates: [QA Acceptance Gates](./qa-acceptance-gates.md)
31. Pitch deck: [Pitch Deck Outline](../pitch/pitch-deck-outline.md)
32. Judging response: [Judging Rubric Response](../pitch/judging-rubric-response.md)
33. Screen specs: [Screen Specifications](../ux/screen-specifications.md)
34. Screen states: [Screen State Matrix](../ux/screen-state-matrix.md)
35. UI redlines: [UI Redlines and Layout Guidelines](../ux/ui-redlines-and-layout-guidelines.md)
36. Screen-by-screen UI acceptance: [Screen-by-Screen UI Acceptance](../ux/screen-by-screen-ui-acceptance.md)
37. Wireframe brand audit: [Wireframe Brand Compliance Audit](../ux/wireframe-brand-compliance-audit.md)
38. Wireframes: [Combined Excalidraw wireframes](../ux/wireframes/subscriptions-engine.excalidraw) and [Individual wireframes](../ux/wireframes/individual/README.md)
39. High-fidelity mockups: [SVG Mockups](../ux/mockups/README.md)
40. Readiness audit: [Requirements Coverage and Readiness Audit](../audit/requirements-coverage-and-readiness-audit.md)
41. Final planning checklist: [Final Planning Review Checklist](../audit/final-planning-review-checklist.md)

## Decisions to Make

### Product Name

Recommended: SubPilot.

Alternatives:

- SubPilot
- Recurrly
- BillForge
- LoopBill
- SubStacker

Recommended working choice: **SubPilot**. Position it as an independent product using Nomba APIs, not as a product owned by Nomba.

### Logo

Recommended:

- Use the clean S monogram logo mark in the app.
- Use the horizontal wordmark in the pitch deck and README.
- Keep the phrase "Uses Nomba APIs for payments" as a small integration note, not part of the core logo.

### MVP Depth

Recommended:

- Build plan management, subscription activation, renewal failure, dunning recovery, customer portal, and webhook event log.

Avoid:

- Usage metering, coupons, and tax in the first build unless the team already has the core flow working.

### Demo Mode

Recommended:

- Use a Nomba adapter with two modes:
  - `sandbox`: calls real Nomba sandbox where stable.
  - `mock`: deterministic payment success/failure for demo.

### UI Theme

Recommended:

- Operational fintech dashboard with Signal Teal for primary actions.
- Avoid a marketing landing page as the main experience.

## Review Questions

- Does every required track item appear in product, UX, architecture, and data model?
- Can a judge understand the state machine without reading code?
- Can a developer integrate from the API docs?
- Can a billing admin resolve a failed payment from the UI?
- Can an end customer self-serve from the portal?
- Does the ERD prove this is multi-tenant and audit-ready?
- Does the demo show why this product is stronger because it uses Nomba APIs for payments instead of trying to become a payment processor?

## Suggested Next Artifacts

The planning pack already includes OpenAPI, seed data, state-machine specs, wireframes, mockups, and pitch structure. The next best artifacts are implementation-facing deliverables:

- Clickable prototype or implemented Django templates matching the SVG mockups.
- State-machine test suite in Django.
- Contract tests for Nomba adapter mock and sandbox modes.
- Demo script as speaker notes tied to seed data.
- Final pitch deck built from the outline.

## Change Log Template

Use this when tweaking scope:

```md
## Change

Decision:

Why:

Files updated:

Impact on MVP:

Impact on demo:
```
