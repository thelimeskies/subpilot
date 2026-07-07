# Wireframe Brand Compliance Audit

This audit checks whether the individual wireframes match the SubPilot brand guide and product requirements.

## Brand Tokens Checked

| Token | Hex | Required Use |
|---|---|---|
| Deep Ink | `#0B1720` | Navigation, text, high-contrast surfaces |
| Signal Teal | `#14B8A6` | Primary actions and selected states |
| Teal Edge | `#0F766E` | Primary borders and emphasis |
| Mint Wash | `#ECFDF5` | Soft panels and secondary surfaces |
| Canvas | `#F8FAF9` | Page background |
| Surface | `#FFFFFF` | Main cards, tables, detail panels |
| Line | `#D8E7E1` | Dividers and borders |
| Muted Text | `#52615D` | Secondary text |

## Screen Audit

| Screen | File | Brand Match | Notes |
|---|---|---|---|
| Dashboard Overview | `individual/dashboard-overview.excalidraw` | Pass | Uses Deep Ink shell, white cards, Signal Teal CTA, Mint event panel |
| Plan Builder | `individual/plan-builder.excalidraw` | Pass | Uses Deep Ink step rail, white form, Mint preview |
| Subscription Detail | `individual/subscription-detail.excalidraw` | Pass | Uses white timeline and Mint summary/action panel |
| Recovery Queue | `individual/recovery-queue.excalidraw` | Pass | Uses white table and Mint selected-invoice policy panel |
| Customer Portal | `individual/customer-portal.excalidraw` | Pass | Uses centered white portal card, Mint brand block, Signal Teal CTA |
| Mobile Customer Portal | `individual/mobile-customer-portal.excalidraw` | Pass | Uses mobile frame, Deep Ink header, warning state, Signal Teal CTA |
| Developer Console | `individual/developer-console.excalidraw` | Pass | Uses white API panel and Mint event/debug panel |
| Invoice Detail | `individual/invoice-detail.excalidraw` | Pass | Uses white finance panel and Mint action panel |
| Settings and Policies | `individual/settings-policies.excalidraw` | Pass | Uses Deep Ink settings rail and white policy workspace |
| Critical Modals | `individual/critical-modals.excalidraw` | Pass | Uses white modal cards, Signal Teal positive actions, Danger destructive action |

## UI Quality Checklist

- [x] Individual wireframes exist for all P0 screens.
- [x] P1 finance/settings screens are represented.
- [x] Primary actions use Signal Teal.
- [x] Navigation uses Deep Ink.
- [x] Secondary panels use Mint Wash.
- [x] Tables and detail panels use white surfaces.
- [x] Wireframes avoid the old yellow palette.
- [x] Wireframes are split for individual review.
- [x] Mobile portal recovery wireframe exists.
- [x] Critical confirmation modal wireframe exists.
- [x] Screen specs define users, data, actions, states, and acceptance criteria.

## Remaining Visual Improvements Before Implementation

- Replace text-only table rows with higher-fidelity component drawings in Figma or React.
- Add mobile customer portal variant.
- Add modal wireframes for cancel, retry payment, and plan-change confirmation.
- Add empty-state wireframes for first-run dashboard and no failed payments.
- Add redline spacing annotations if converting to Figma.
