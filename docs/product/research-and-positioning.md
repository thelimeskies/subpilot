# Research and Positioning

## Source Context

The prompt screenshot defines an infrastructure-track focus called **Subscriptions Engine** with these must-haves:

- Plan management
- Billing cycles: monthly, annual, custom
- Proration
- Dunning and failed-payment recovery
- Customer self-service portal
- Webhooks for downstream systems

It lists relevant Nomba APIs as Checkout API, tokenized cards, Charge API, and Transfers. The judging criteria are state-machine completeness, dunning sophistication, multi-tenant cleanliness, and API ergonomics for downstream developers.

## Nomba Platform Findings

Nomba's developer docs currently expose payment and finance primitives that can support a managed subscription layer:

- Accept payments using checkout or charge APIs. Source: [Nomba welcome docs](https://developer.nomba.com/docs/introduction/welcome-to-nomba)
- Create checkout orders with callback URLs, customer metadata, allowed payment methods, and optional card tokenization. Source: [Create online checkout order](https://developer.nomba.com/nomba-api-reference/online-checkout/create-an-online-checkout-order)
- Charge a customer using tokenized card data. Source: [Tokenized card payment](https://developer.nomba.com/nomba-api-reference/online-checkout/charge-a-customer-using-tokenized-card-data)
- List, update, and delete tokenized cards. Source: [Nomba API reference](https://developer.nomba.com/nomba-api-reference/introduction)
- Execute transfers, account lookup, and wallet movements. Source: [Nomba transfers API reference](https://developer.nomba.com/nomba-api-reference/introduction)
- Receive webhook notifications for payment success, payment failed, payment reversal, payout success, payout failed, and payout refund. Source: [Nomba webhooks](https://developer.nomba.com/docs/api-basics/webhook)
- Authenticate with OAuth2 client credentials, refresh tokens before expiry, and secure credentials server-side. Source: [Nomba authentication](https://developer.nomba.com/docs/getting-started/authentication)
- Test Transfer, Virtual Account, and Checkout in sandbox mode. Source: [Nomba Try the API](https://developer.nomba.com/docs/guides/try-the-api)

## Comparable Billing System Patterns

Stripe Billing is a useful benchmark for subscription lifecycle design:

- Subscriptions move through explicit states such as trialing, active, incomplete, past_due, unpaid, canceled, and paused. Source: [Stripe subscription lifecycle](https://docs.stripe.com/billing/subscriptions/overview)
- Subscription systems should use webhooks to provision access and react to payment changes. Source: [Stripe subscription lifecycle](https://docs.stripe.com/billing/subscriptions/overview)
- Dunning should track attempt counts, next retry times, hard declines, and final outcomes. Source: [Stripe Smart Retries](https://docs.stripe.com/billing/revenue-recovery/smart-retries)
- Proration is needed when customers upgrade, downgrade, change quantity, or switch plans mid-cycle. Source: [Stripe prorations](https://docs.stripe.com/billing/subscriptions/prorations)

## Product Positioning

**SubPilot** is an independent managed recurring-billing product for Nigerian and African businesses that want subscription billing while using Nomba APIs for payment collection, tokenized-card renewals, transfers, and payment webhooks.

The product is both:

- A merchant-facing operations console for plans, subscribers, invoices, payment failures, and analytics.
- A developer platform with APIs, webhooks, sandbox logs, idempotent billing commands, and embeddable customer portal links.

## Target Customer Segments

1. SaaS companies
   - Need recurring card billing, trial periods, upgrades, downgrades, annual plans, and invoices.
2. Membership businesses
   - Need simple monthly recurring plans and recovery when cards fail.
3. Marketplaces and platforms
   - Need multi-tenant billing for many merchants or sub-accounts.
4. Education and creator platforms
   - Need student/customer portals, self-service cancellation, and renewal reminders.
5. API-first product teams
   - Need a reusable layer to avoid rebuilding subscriptions in every product surface while keeping control of their own customer experience.

## Product Hypothesis

If SubPilot provides a reusable subscription engine on top of Nomba checkout, tokenized cards, charge APIs, transfers, and webhooks, product teams can ship paid recurring products faster while merchants get a clear billing console and customers get self-service controls.

## Differentiation for Hackathon Judging

Most hackathon teams will likely implement a narrow recurring charge demo. This plan should win by showing:

- Formal subscription and invoice state machines
- Dunning policy builder
- Retry timeline and customer recovery links
- Multi-tenant merchant/account boundary design
- Developer API and webhook ergonomics
- Customer portal UX
- Demo-ready operational dashboards
- Clear audit logs and idempotency

## Assumptions

- Nomba card tokenization can be requested from checkout and reused for future charges.
- Nomba webhooks can confirm success, failure, and reversal events.
- Subscription Engine stores its own subscription, invoice, entitlement, and retry state.
- Payment orchestration calls Nomba APIs but never stores raw card data.
- Transfers are optional for refund, settlement, partner payout, or revenue-split extensions.

## Key Product Constraints

- Payment success can be delayed, duplicated, or delivered out of order through webhooks.
- Tokenized card charges can fail for recoverable and non-recoverable reasons.
- A merchant may have multiple product teams, environments, sub-accounts, and webhook endpoints.
- Customers need to update payment methods without support tickets.
- Dunning should avoid aggressive retries that damage trust or increase issuer declines.

## North Star

**Successful recurring revenue processed with minimal manual intervention.**

Supporting metrics:

- Activation: first live subscription created per merchant.
- Recovery: percentage of failed invoices recovered.
- Developer adoption: API keys with at least one successful subscription creation.
- Operations quality: average time to resolve failed subscription issues.
- Customer experience: percentage of payment method updates completed through self-service.
