# UI Redlines and Layout Guidelines

These guidelines translate the SubPilot mockups and wireframes into implementation-ready layout rules.

## Global Desktop Shell

| Element | Size |
|---|---:|
| Page canvas | 100vw x 100vh |
| Sidebar width | 240px |
| Sidebar margin | 32px on mockups, 0 or 16px in app shell |
| Top bar height | 64px |
| Content gutter | 24px |
| Card radius | 16-24px |
| Small control radius | 12-14px |
| Table row height | 64-82px |
| Primary button height | 44-56px |

Rules:

- Keep cards at 8-24px radius; do not use overly round pill cards except badges and segmented controls.
- Use white surfaces for main work areas.
- Use Mint Wash only for secondary contextual panels.
- Use Deep Ink for navigation and high-contrast code blocks.

## Typography Redlines

| Use | Size | Weight |
|---|---:|---:|
| App/page title | 30-38px | 850 |
| Section title | 22-26px | 800-850 |
| Card title | 18-22px | 750-850 |
| Table header | 13-14px | 800 |
| Body | 15-17px | 400-600 |
| Button | 15-18px | 800-850 |
| Metadata | 13-15px | 600-750 |

Rules:

- Use tabular numbers for money and metrics.
- Keep letter spacing at 0.
- Avoid huge hero type inside app screens.

## Dashboard Redlines

Layout:

- Sidebar: fixed left.
- Top bar: full width above content.
- Metric tiles: 4 columns on desktop.
- Main content: renewals table plus event panel.

Metric tile:

- Height: 140-150px.
- Label top, value middle, delta bottom.
- Revenue-at-risk uses Mint Wash and Teal Edge only when actionable.

Table:

- Header row: uppercase metadata.
- Row height: 64-72px.
- Status badge at right.

## Plan Builder Redlines

Layout:

- Left step rail: 260-280px.
- Main form: 560-640px.
- Preview panel: 320-360px.

Form controls:

- Input height: 52-56px.
- Vertical spacing between groups: 32-42px.
- Inline validation appears below field, not in toast.

Preview:

- Always visible on desktop.
- Shows final customer-facing summary.
- Shows Nomba checkout/tokenization result clearly.

## Subscription Detail Redlines

Layout:

- Header summary: 120-128px.
- Main timeline: 60-65% width.
- Summary/action panel: 30-35% width.

Timeline:

- Vertical line with event dots.
- Events include timestamp, event type, source, and summary.
- Processor events and outbound webhook events should be visually distinct with labels.

Action panel:

- Shows plan, entitlements, payment method, and proration preview.
- Primary action is only one button at a time.

## Recovery Queue Redlines

Layout:

- Failed invoice table: 60% width.
- Selected invoice/dunning panel: 35% width.

Priority row:

- Selected row uses Mint Wash.
- Urgent row includes explicit next action.
- Hard failures use warning label and "Requires new card" text.

Action panel:

- Retry now and Send portal link are primary actions.
- Mark uncollectible is destructive and must be behind confirmation.

## Customer Portal Redlines

Desktop:

- Centered card max width: 520px.
- Brand header at top.
- Primary CTA spans full width.

Mobile:

- Minimum supported width: 360px.
- Card content should not require horizontal scroll.
- Past-due alert appears above plan details.
- Update payment method CTA remains above secondary actions.

## Developer Console Redlines

Layout:

- API quickstart/code panel left.
- Event stream and payload viewer right.

Code blocks:

- Deep Ink background.
- Monospace font.
- Copy button aligned top right.

Event rows:

- Show event type, status, timestamp, and delivery result.
- Failed delivery must show next retry time.

## Modal Redlines

Modal width:

- 360-520px depending on complexity.

Required content:

- Title.
- Object affected.
- What happens.
- Customer impact.
- Billing/webhook impact.
- Primary action.
- Cancel action.

Button rules:

- Positive action: Signal Teal.
- Destructive action: Danger.
- Cancel action: white surface with Line border.

## Responsive Breakpoints

| Breakpoint | Behavior |
|---|---|
| `>= 1200px` | Full desktop shell with sidebar and multi-column panels |
| `900-1199px` | Sidebar can collapse; panels stack where needed |
| `600-899px` | Tables become card lists; action panels stack |
| `< 600px` | Customer portal mobile layout; dashboard/admin should show compact operational views |

## Accessibility Rules

- All status colors require labels.
- Buttons need visible focus.
- Inputs need labels, not placeholders only.
- Confirmation dialogs trap focus.
- Portal must be keyboard navigable.
- Error messages must be specific and include next action.
