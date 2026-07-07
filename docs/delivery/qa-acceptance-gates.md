# QA Acceptance Gates

These gates define what "ready for hackathon demo" means for SubPilot.

## Product Gates

- [ ] Every must-have track requirement is mapped to a feature spec.
- [ ] Every P0 feature maps to at least one screen.
- [ ] Every P0 feature maps to at least one Django app.
- [ ] Every payment-related feature states how Nomba APIs are used.
- [ ] Tokenized-card primitives are described for downstream teams.
- [ ] Dunning policy and recovery flow are demo-ready.

## API Gates

- [ ] OpenAPI file validates with an OpenAPI parser.
- [ ] Mutation endpoints require `Idempotency-Key`.
- [ ] API error shape includes type, code, message, request ID, and details.
- [ ] Pagination is consistent across list endpoints.
- [ ] Payment-method APIs never expose raw token values.
- [ ] Webhook replay endpoint does not create duplicate source events.

## Django Gates

- [ ] Models include merchant and environment scoping.
- [ ] Money fields use integer minor units.
- [ ] Renewal billing uses `transaction.atomic()`.
- [ ] Due subscriptions are locked with `select_for_update()`.
- [ ] Duplicate Nomba webhook processing is idempotent.
- [ ] Celery tasks exist for billing, dunning, payment retry, and webhook delivery.
- [ ] Demo seed command resets deterministic data.

## UI Gates

- [ ] Dashboard has MRR, active subscriptions, revenue at risk, recovery rate.
- [ ] Plan Builder supports monthly, annual, custom cycles, trial, entitlements, dunning, Nomba checkout.
- [ ] Subscription Detail shows state, plan, payment method, invoices, events, and actions.
- [ ] Recovery Queue prioritizes failed invoices and shows next action.
- [ ] Customer Portal supports update card, pay overdue invoice, receipts, cancel policy.
- [ ] Developer Console shows API keys, events, webhooks, replay, payloads.
- [ ] Individual wireframes match brand tokens.
- [ ] Empty states and error states are defined before implementation.

## State Machine Gates

- [ ] Invalid subscription transitions are rejected.
- [ ] Paid invoices are immutable.
- [ ] Recoverable failures schedule retries.
- [ ] Hard failures require payment method update.
- [ ] Dunning final action is applied after attempts are exhausted.
- [ ] Webhook delivery retries and replay are separate.

## Security Gates

- [ ] Raw card data is never stored.
- [ ] Token references are encrypted at rest.
- [ ] API keys are hashed.
- [ ] Webhook secrets are encrypted.
- [ ] Portal sessions are signed and expiring.
- [ ] Sensitive actions are audit logged.
- [ ] Test and live environments are isolated.

## Demo Gates

- [ ] Demo reset command works.
- [ ] Demo works in mock Nomba mode.
- [ ] Demo does not depend on external network success.
- [ ] Judge can see Nomba integration points.
- [ ] Judge can see state-machine completeness.
- [ ] Judge can see dunning sophistication.
- [ ] Judge can see multi-tenant cleanliness.
- [ ] Judge can see downstream API/SDK ergonomics.
