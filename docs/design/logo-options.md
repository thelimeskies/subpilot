# Logo Options

The previous mark was too busy. These options are intentionally simpler and easier to use in the dashboard, favicon, pitch deck, and docs.

## Recommendation

Use **Option B: Wordmark** as the main brand lockup and use its square icon in the app sidebar and favicon.

Why:

- It is the cleanest and most product-ready.
- It avoids overexplaining billing with a complex symbol.
- It scales down better than the ledger/route mark.
- It keeps SubPilot independent from Nomba while still feeling like fintech infrastructure.

## Options

### Option A: Flow

Asset:

- [Option A SVG](../assets/logo-options/subpilot-option-a-flow.svg)

Best for:

- Pitch slides
- Architecture diagrams
- When you want the mark to suggest lifecycle flow

Concern:

- More conceptual than instantly readable.

### Option B: Wordmark

Asset:

- [Option B SVG](../assets/logo-options/subpilot-option-b-wordmark.svg)

Best for:

- Primary product identity
- Dashboard header
- Website/app documentation
- Pitch deck cover

Concern:

- Less symbolic, but that is acceptable because the product UI and tagline carry the meaning.

### Option C: SP Monogram

Asset:

- [Option C SVG](../assets/logo-options/subpilot-option-c-sp-monogram.svg)

Best for:

- Dark pitch slides
- App icon variations
- Social/avatar use

Concern:

- SP initials may be less memorable than the full SubPilot name.

## Logo Decision Criteria

Choose the logo that passes these tests:

- Works at 32px favicon size.
- Looks professional in a fintech dashboard.
- Does not look like Nomba's own brand.
- Does not imply SubPilot is a bank or card network.
- Does not overuse decoration.
- Can be recreated easily in CSS/SVG if needed.

## Implementation Decision

Current active assets in `docs/assets/` use a simplified S signal mark with no embedded tagline or integration badge. If the team prefers Option A, B, or C, copy that SVG into the active asset slots:

- `subpilot-logo-mark.svg`
- `subpilot-logo-horizontal.svg`
- `subpilot-logo-horizontal-dark.svg`
- `subpilot-favicon.svg`
