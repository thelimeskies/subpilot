# SubPilot Planning Pack

This folder is the end-to-end planning workspace for **SubPilot**, an independent hackathon product that uses Nomba checkout, tokenized cards, charge APIs, transfers, webhooks, and merchant account primitives as payment infrastructure.

The product goal is to give businesses and product teams a reusable recurring-billing engine instead of forcing every team to rebuild plans, billing cycles, proration, failed-payment recovery, customer self-service, and downstream webhooks from scratch.

## How to Review

Start with these files in order:

1. [Research and Positioning](./product/research-and-positioning.md)
2. [Users and Stories](./product/users-and-stories.md)
3. [Product Requirements](./product/product-requirements.md)
4. [Feature Breakdown and Build Units](./product/feature-breakdown-and-build-units.md)
5. [Build Unit Dependency and Test Contracts](./product/build-unit-dependency-and-test-contracts.md)
6. [Feature to Screen Traceability](./product/feature-to-screen-traceability.md)
7. [RBAC Permissions Matrix](./product/rbac-permissions-matrix.md)
8. [UX Flows and Screens](./ux/ux-flows-and-screens.md)
   - [Screen Specifications](./ux/screen-specifications.md)
   - [Screen State Matrix](./ux/screen-state-matrix.md)
   - [UI Redlines and Layout Guidelines](./ux/ui-redlines-and-layout-guidelines.md)
   - [Screen-by-Screen UI Acceptance](./ux/screen-by-screen-ui-acceptance.md)
   - [Wireframe Brand Compliance Audit](./ux/wireframe-brand-compliance-audit.md)
9. [Design System](./design/design-system.md)
   - [UI Component Inventory](./design/components/ui-component-inventory.md)
10. [Brand Identity](./design/brand-identity.md)
   - [Logo Options](./design/logo-options.md)
   - [Brand Board](./design/brand-board.svg)
11. [Architecture](./technical/architecture.md)
12. [Data Model and ERD](./technical/data-model-erd.md)
13. [State Machine Specification](./technical/state-machines/state-machine-specification.md)
14. [Django Model Contracts](./technical/django-model-contracts.md)
15. [Django Implementation Blueprint](./technical/django-implementation-blueprint.md)
16. [Nomba Integration Contract](./technical/nomba-integration-contract.md)
17. [Celery Job Contracts](./technical/celery-job-contracts.md)
18. [API and Webhooks](./technical/api-and-webhooks.md)
   - [OpenAPI Contract](./technical/openapi.yaml)
19. [Django Implementation Plan](./technical/django-implementation-plan.md)
20. [Django File-by-File Build Plan](./delivery/django-file-by-file-build-plan.md)
21. [Frontend Route and Component Blueprint](./ux/frontend-route-component-blueprint.md)
22. [SDK and Packages Plan](./technical/sdk-and-packages.md)
23. [Customer Portal SDK and Embedded Portal](./technical/customer-portal-sdk.md)
24. [SubPilot Python SDK](./technical/python-sdk.md)
25. [Delivery Plan](./delivery/delivery-plan.md)
26. [Demo Scenario and Seed Data](./delivery/demo-scenario-and-seed-data.md)
   - [Seed Data JSON](./delivery/seed-data.json)
27. [Implementation Backlog](./delivery/implementation-backlog.md)
28. [End-to-End Test Plan](./delivery/end-to-end-test-plan.md)
29. [End-to-End QA Runbook](./delivery/end-to-end-qa-runbook.md)
30. [QA Acceptance Gates](./delivery/qa-acceptance-gates.md)
31. [Pitch Deck Outline](./pitch/pitch-deck-outline.md)
32. [Judging Rubric Response](./pitch/judging-rubric-response.md)
33. [Review and Tweak Guide](./delivery/review-and-tweak-guide.md)
34. [Requirements Coverage and Readiness Audit](./audit/requirements-coverage-and-readiness-audit.md)
35. [Final Planning Review Checklist](./audit/final-planning-review-checklist.md)

Wireframe file:

- [Combined Excalidraw wireframes](./ux/wireframes/subscriptions-engine.excalidraw)
- [Individual screen wireframes](./ux/wireframes/individual/README.md)
- [Screen specifications](./ux/screen-specifications.md)
- [UI redlines and layout guidelines](./ux/ui-redlines-and-layout-guidelines.md)
- [Screen-by-screen UI acceptance](./ux/screen-by-screen-ui-acceptance.md)
- [High-fidelity SVG mockups](./ux/mockups/README.md)

## Folder Structure

```text
docs/
  README.md
  product/      Strategy, users, requirements, feature units
  design/       Brand identity and design system
  ux/           Flows, screen specs, wireframes
  pitch/        Pitch deck outline and judging response
  technical/    Architecture, ERD, APIs, Django plan
  delivery/     Roadmap, demo plan, review guide
  assets/       Logo and brand assets
```

Brand assets:

- [Logo mark](./assets/subpilot-logo-mark.svg)
- [Horizontal logo](./assets/subpilot-logo-horizontal.svg)
- [Horizontal logo on dark](./assets/subpilot-logo-horizontal-dark.svg)
- [Favicon](./assets/subpilot-favicon.svg)

## Product Name Options

- SubPilot
- Recurrly
- BillForge
- LoopBill
- SubStacker

Recommended for hackathon: **SubPilot** because it is short, independent, and clearly points to guided subscription operations. In the pitch, describe it as "using Nomba APIs for payments" rather than implying Nomba owns it.

## Winning Angle

The strongest story is not just "we can charge cards monthly." The strongest story is:

- A clean state machine for every subscription and invoice.
- A developer-first API that downstream teams can integrate in minutes.
- A billing operations console that makes failures, retries, proration, and customer support understandable.
- A customer portal that reduces support load.
- A webhook/event layer that makes this reusable across any business using the platform.
- Multi-tenant controls so the system can serve many merchants and product teams safely.

## Final Brand

**Name:** SubPilot

**Tagline:** Subscription operations, guided from checkout to renewal.

**Positioning:** An independent subscription billing product using Nomba APIs for payment collection, tokenized-card renewals, transfers, and payment webhooks.

## Core Deliverables Covered

- Product strategy and research
- User types and subtypes
- User stories and acceptance criteria
- RBAC permissions matrix
- Full information architecture
- UI screen inventory
- UX flows
- Feature-to-screen traceability
- UI redlines and implementation layout rules
- Screen-by-screen UI acceptance gates
- Wireframe brand compliance audit
- Design system
- Architecture
- ERD and data model
- State-machine specification
- Django model contracts
- Django implementation blueprint
- Frontend route and component blueprint
- Nomba adapter contract
- Celery job contracts
- Public API design
- SDK and package strategy
- Explicit tokenized-card primitives for downstream product teams
- Webhook event design
- Dunning and failed-payment recovery
- Proration model
- Security, compliance, observability, and risk controls
- Hackathon build plan and demo script
- Demo scenario, seed data, and QA gates
- End-to-end test plan
- End-to-end QA runbook
- Django implementation plan
- Django file-by-file build plan
- Feature breakdown, build units, priorities, and acceptance criteria
- Build-unit dependencies, test contracts, and slice gates
- Excalidraw wireframes
- High-fidelity SVG mockups
- Pitch deck outline and judging rubric response
- Product name, logo assets, and brand identity
- Readiness audit
- Final planning review checklist
