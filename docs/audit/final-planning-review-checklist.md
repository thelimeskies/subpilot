# Final Planning Review Checklist

This checklist is for the last review pass before implementation or pitch-deck production. It maps directly to the original planning request and should be used to decide what to tweak next.

## Review Status Legend

- **Ready**: enough detail exists to build or present.
- **Review**: covered, but requires human taste/product decision.
- **Improve**: known gap before implementation.

## Original Request Coverage

| Original ask | Status | Evidence | Review action |
|---|---|---|---|
| Create `docs/` folder | Ready | `docs/README.md` | None |
| Comprehensive research | Ready | `product/research-and-positioning.md` | Confirm target merchant examples fit hackathon pitch |
| UI/UX | Ready | `ux/ux-flows-and-screens.md`, `ux/screen-specifications.md` | Review main flows in order |
| Design system | Ready | `design/design-system.md` | Confirm colors still feel right |
| Architecture | Ready | `technical/architecture.md` | Confirm team can build selected MVP slice |
| User flows | Ready | `ux/ux-flows-and-screens.md` | Validate demo flow timing |
| User stories | Ready | `product/users-and-stories.md` | Confirm no key persona is missing |
| Excalidraw wireframes | Ready | `ux/wireframes/` | Open individual files and review screen by screen |
| User types/subtypes | Ready | `product/users-and-stories.md`, `product/rbac-permissions-matrix.md` | Confirm roles match implementation auth |
| ERD | Ready | `technical/data-model-erd.md` | Confirm Django models match ERD before coding |
| Detailed product plan | Ready | `product/product-requirements.md`, `delivery/delivery-plan.md` | Use review guide |
| Product design/mockups | Ready | `ux/mockups/`, `design/brand-board.svg` | Review visual direction |
| Feature breakdown | Ready | `product/feature-breakdown-and-build-units.md` | Use build-unit contracts |
| Units and dependencies | Ready | `product/build-unit-dependency-and-test-contracts.md` | Build by slice order |
| Django implementation | Ready | `technical/django-implementation-blueprint.md`, `delivery/django-file-by-file-build-plan.md` | Start with mock adapter |
| SDK/packages | Ready | `technical/sdk-and-packages.md` | Decide if Node SDK is P1 or skipped |
| Tokenized-card primitives | Ready | `product/features/tokenized-card-primitives.md` | Keep prominent in pitch |
| Product name | Review | `design/brand-identity.md` | Keep SubPilot or rename before coding |
| Logo | Review | `assets/`, `design/logo-options.md` | User should approve active mark |
| Brand color | Ready | `design/brand-identity.md`, `design/design-system.md` | Confirm no legacy yellow style remains |

## Hackathon Winning Criteria

| Criterion | Strong evidence | Why it matters |
|---|---|---|
| State-machine completeness | `technical/state-machines/state-machine-specification.md` | Judges can see subscription states are not hand-waved |
| Dunning sophistication | `product/features/dunning-and-recovery.md`, `delivery/django-file-by-file-build-plan.md` | Recovery flow is more than retry button |
| Multi-tenant cleanliness | `product/rbac-permissions-matrix.md`, `technical/django-model-contracts.md` | Shows infrastructure quality |
| API ergonomics | `technical/openapi.yaml`, `technical/sdk-and-packages.md` | Proves downstream teams can integrate |
| Tokenized-card use | `product/features/tokenized-card-primitives.md`, `technical/nomba-integration-contract.md` | Directly addresses the track primitive |
| Customer self-service | `product/features/customer-portal.md`, `ux/screen-by-screen-ui-acceptance.md` | Shows end-to-end recovery |
| Demo clarity | `delivery/demo-scenario-and-seed-data.md`, `pitch/pitch-deck-outline.md` | Helps judges understand quickly |

## Must-Show Demo Path

1. Dashboard shows MRR, active subscriptions, revenue at risk, and recovered revenue.
2. Plan Builder shows Pro Monthly with card tokenization for renewals.
3. Developer Console creates subscription through API quickstart.
4. Nomba mock checkout returns success and token reference.
5. Subscription Detail moves from incomplete to active.
6. Outbound webhook delivers `subscription.activated`.
7. Renewal invoice is generated.
8. Tokenized-card charge fails.
9. Recovery Queue classifies failure and schedules dunning.
10. Customer Portal updates payment method through Nomba token flow.
11. Retry succeeds and invoice becomes paid.
12. Webhook replay shows downstream event ergonomics.

## Visual QA Checklist

| Check | Pass condition |
|---|---|
| Logo | Active mark is simple, readable at favicon size, and not Nomba-branded |
| Palette | Uses Deep Ink, Signal Teal, Mint Wash, white surfaces, and no legacy yellow |
| Dashboard | Operational dashboard, not a landing page |
| Plan Builder | Tokenization and dunning settings visible |
| Subscription Detail | Timeline explains processor, invoice, state, and webhook events |
| Recovery Queue | Hard failure versus recoverable failure is visually obvious |
| Customer Portal | Past-due recovery CTA is obvious on desktop and mobile |
| Developer Console | Code snippets, event payload, and replay actions are clear |
| Modals | Financial/destructive actions explain billing and customer impact |

## Technical QA Checklist

| Check | Pass condition |
|---|---|
| Tenant scoping | Every business model includes merchant/environment scope |
| Money | All monetary amounts use minor units |
| Idempotency | Subscription creation, webhook processing, and invoice retry are safe to replay |
| Processor boundary | Nomba secrets never reach downstream teams or frontend |
| Token storage | Token references encrypted; raw card data never stored |
| Events | Subscription, invoice, payment, dunning, and webhook events are append-only |
| Celery | Renewal scan, retries, webhook dispatch, and cleanup jobs are defined |
| SDKs | Python and Django package paths support the demo integration |
| Demo data | Seed data can reproduce active, past-due, recovered, and failed states |

## Decisions Before Coding

1. Confirm product name: SubPilot or rename.
2. Confirm active logo mark or choose one alternative.
3. Confirm MVP scope: P0 only or include proration preview.
4. Decide UI implementation style: Django templates, React frontend, or hybrid.
5. Decide demo adapter mode: mock-only for hackathon or sandbox plus mock fallback.
6. Decide SDK scope: Python/Django only for demo or include TypeScript skeleton.

## Current Recommendation

Build the P0 demo with:

- Django + DRF backend.
- Django templates or simple React screens for the six demo surfaces.
- Mock Nomba adapter with sandbox-shaped responses.
- Python SDK and `subpilot-django` package examples.
- Active SubPilot S signal logo.
- Signal Teal/Deep Ink brand direction.

This gives the strongest chance of finishing the core story: plan, subscribe, tokenize card, renew, fail, recover, and notify downstream systems.
