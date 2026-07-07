# Plan Catalog and Billing Cycles

## Purpose

Let a merchant define what they sell on a recurring basis: products, plans, prices, billing cycles, trials, entitlements, and plan-level billing behavior.

## Users

- Owner: approves packaging and price strategy.
- Billing Admin: creates and manages plans.
- Developer: integrates plan IDs into the merchant product.
- Finance: needs stable price versions for reporting.

## Django Ownership

Primary app: `catalog`

Supporting apps:

- `accounts` for merchant/environment scoping.
- `dunning` for plan-level recovery policy.
- `audit` for plan changes.

## Core Models

### Product

Fields:

- `id`
- `merchant`
- `environment`
- `name`
- `description`
- `status`: active, archived
- `metadata`

Rules:

- Product names can repeat across merchants but not within the same merchant/environment.
- Archived products cannot receive new active plans.

### Plan

Fields:

- `id`
- `merchant`
- `environment`
- `product`
- `name`
- `description`
- `status`: draft, active, archived
- `trial_days`
- `dunning_policy`
- `proration_policy`
- `cancellation_policy`
- `metadata`

Rules:

- A plan can be activated only when it has one current price version.
- Active plans cannot have destructive edits to billing interval or amount.
- Archiving a plan prevents new subscriptions but does not affect existing ones.

### PriceVersion

Fields:

- `id`
- `plan`
- `amount_minor`
- `currency`
- `interval_unit`: day, week, month, year
- `interval_count`
- `setup_fee_minor`
- `active_from`
- `active_to`

Rules:

- Use integer minor units only.
- Only one current price version per plan.
- A price version with subscriptions is immutable.

### PlanFeature

Fields:

- `plan`
- `key`
- `name`
- `limit`
- `included`
- `metadata`

Rules:

- Feature keys should be machine-readable and stable.
- Limits can be numeric or null for unlimited.

## Billing Cycle Rules

Supported MVP intervals:

- Monthly: `interval_unit=month`, `interval_count=1`
- Annual: `interval_unit=year`, `interval_count=1`
- Custom: any valid unit and interval count

Billing anchor:

- If customer subscribes on the 1st-28th, use the same day next period.
- If customer subscribes on the 29th-31st, normalize to the last valid day for short months.
- Store computed `current_period_start` and `current_period_end` on subscription.

Trial behavior:

- Trial can be zero or positive number of days.
- Trial subscription starts as `trialing`.
- At trial end, system attempts first payment using saved payment method or sends checkout link if method is missing.

## API Requirements

Endpoints:

- `POST /api/v1/products`
- `GET /api/v1/products`
- `POST /api/v1/plans`
- `GET /api/v1/plans`
- `GET /api/v1/plans/{id}`
- `POST /api/v1/plans/{id}/activate`
- `POST /api/v1/plans/{id}/archive`
- `POST /api/v1/plans/{id}/clone`

Validation:

- `amount_minor > 0`
- `currency` required
- `interval_count > 0`
- `interval_unit` in supported enum
- `trial_days >= 0`
- `setup_fee_minor >= 0`

## UI Requirements

Screens:

- Plan list
- Plan builder
- Plan detail

Plan builder sections:

- Basics
- Pricing
- Billing cycle
- Trial
- Entitlements
- Dunning policy
- Nomba checkout behavior
- Review

## Edge Cases

- Merchant creates annual plan but labels it monthly.
  - UI should show interval explicitly in preview.
- Merchant edits active price.
  - System creates new price version instead.
- Customer is on archived plan.
  - Existing subscription continues.
- Custom interval is invalid.
  - API returns field-level validation error.

## Acceptance Tests

- Draft plan can be saved without activation.
- Plan cannot activate without price.
- Active plan price mutation creates a new version.
- Existing subscription remains attached to original price version.
- Monthly, annual, and custom intervals compute correct next renewal.

## Demo Moment

Create "Pro Monthly" with:

- NGN 15,000 monthly
- 14-day trial
- 10 seats
- Reports enabled
- API access enabled
- Default SaaS Recovery dunning policy
- Nomba checkout with card tokenization
