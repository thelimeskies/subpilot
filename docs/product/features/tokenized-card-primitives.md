# Tokenized-Card Primitives

## Purpose

Expose safe, reusable card-token primitives for downstream product teams so they can create subscriptions, update payment methods, retry invoices, and recover failed payments without storing or handling raw card data.

SubPilot uses Nomba tokenized-card capabilities as the payment infrastructure layer, then wraps them in subscription-aware APIs, SDKs, events, and operational tooling.

## Users

- Developer integrating SubPilot into a SaaS, membership, marketplace, education, or creator product.
- Billing Admin who needs customer payment methods updated safely.
- Customer who updates card details through the portal.
- Support Agent who can resend secure payment-method update links.

## What SubPilot Owns

SubPilot owns:

- Customer-to-token mapping.
- Default payment method selection.
- Renewal charge orchestration.
- Failed payment classification.
- Payment method update sessions.
- Token lifecycle status.
- Subscription/invoice state updates after tokenized charges.
- Events and webhooks for downstream systems.

SubPilot does not own:

- Raw card capture.
- Raw PAN, CVV, or card storage.
- Nomba's underlying token vault.
- Issuer authentication outside the supported Nomba flow.

## Django Ownership

Primary app: `payments`

Supporting apps:

- `customers`
- `subscriptions`
- `invoices`
- `dunning`
- `events`
- `audit`

## Core Models

### PaymentMethod

Fields:

- `id`
- `merchant`
- `environment`
- `customer`
- `nomba_token_key`
- `provider`: `nomba`
- `brand`
- `last4`
- `exp_month`
- `exp_year`
- `status`: active, expired, revoked, failed_verification
- `is_default`
- `fingerprint`
- `metadata`
- `created_at`
- `updated_at`

Rules:

- Never store raw card data.
- Token references must be encrypted at rest.
- Only one default active payment method per customer per merchant/environment.
- Expired/revoked methods cannot be used for renewal attempts.

### PaymentMethodSession

Purpose:

- Creates a secure flow for adding or updating a payment method.

Fields:

- `customer`
- `subscription`
- `invoice`
- `purpose`: initial_subscription, update_card, recover_invoice, replace_expired_card
- `status`: pending, completed, expired, failed
- `checkout_reference`
- `return_url`
- `expires_at`

## Primitive Operations

### Create Initial Token

Used when:

- Customer starts subscription through checkout.

Flow:

1. Downstream app calls `POST /api/v1/subscriptions`.
2. SubPilot creates incomplete subscription and first invoice.
3. SubPilot creates Nomba checkout order with card tokenization enabled.
4. Customer pays through Nomba checkout.
5. Nomba webhook confirms payment and returns token reference.
6. SubPilot stores token reference as `PaymentMethod`.
7. SubPilot activates subscription.
8. SubPilot emits `payment_method.attached` and `subscription.activated`.

### Attach Replacement Token

Used when:

- Card expired.
- Card revoked.
- Customer wants to change default card.
- Dunning hard failure requires a new card.

Flow:

1. Dashboard or API creates payment method session.
2. Customer receives secure portal link.
3. Customer completes Nomba checkout/token update flow.
4. Nomba webhook confirms token.
5. SubPilot marks old method non-default.
6. SubPilot marks new method default.
7. If linked invoice is overdue, retry invoice.

### Charge Tokenized Card

Used when:

- Renewal invoice is due.
- Admin retries invoice.
- Customer pays overdue invoice.

Flow:

1. SubPilot locks invoice and subscription.
2. SubPilot creates `PaymentAttempt`.
3. SubPilot calls Nomba tokenized-card charge API.
4. SubPilot records processor reference.
5. Webhook confirms success or failure.
6. Success marks invoice paid.
7. Failure starts or advances dunning.

### Revoke Token

Used when:

- Customer removes payment method.
- Token becomes invalid.
- Merchant support revokes method after customer request.

Rules:

- Cannot revoke the only default payment method for an active subscription without collecting replacement or warning user.
- Revocation creates `payment_method.revoked` event.

## API Requirements

Endpoints:

```http
GET /api/v1/customers/{customer_id}/payment-methods
POST /api/v1/customers/{customer_id}/payment-method-sessions
POST /api/v1/payment-methods/{payment_method_id}/set-default
DELETE /api/v1/payment-methods/{payment_method_id}
POST /api/v1/invoices/{invoice_id}/retry
```

Create payment method session:

```json
{
  "purpose": "recover_invoice",
  "invoice_id": "inv_123",
  "subscription_id": "sub_123",
  "return_url": "https://merchant.app/billing"
}
```

Response:

```json
{
  "id": "pms_123",
  "status": "pending",
  "checkout_url": "https://checkout.nomba.com/...",
  "expires_at": "2026-07-05T12:00:00Z"
}
```

## SDK Requirements

SDKs should expose:

```python
client.payment_methods.list(customer_id)
client.payment_methods.create_session(customer_id, purpose="recover_invoice", invoice_id="inv_123")
client.payment_methods.set_default(payment_method_id)
client.invoices.retry(invoice_id)
```

JavaScript equivalent:

```ts
await subpilot.paymentMethods.createSession({
  customerId: "cus_123",
  purpose: "recover_invoice",
  invoiceId: "inv_123",
});
```

## Events

Required events:

- `payment_method.attached`
- `payment_method.updated`
- `payment_method.revoked`
- `payment_method.expired`
- `invoice.payment_succeeded`
- `invoice.payment_failed`
- `dunning.recovered`

## UI Requirements

Merchant dashboard:

- Customer detail shows payment methods as brand/last4/expiry only.
- Subscription detail shows default payment method.
- Recovery queue shows "requires new card" for hard failures.

Customer portal:

- Update card action.
- Pay overdue invoice after update.
- Clear success/failure messaging.

Developer console:

- Tokenized-card flow guide.
- Sample API calls.
- Event payload examples.

## Security Requirements

- Do not log token values in plaintext.
- Encrypt token references at rest.
- Mask all card display data.
- Use signed, expiring sessions for customer token updates.
- Audit default payment method changes.
- Treat Nomba webhook as untrusted until signature verification succeeds.

## Acceptance Tests

- Initial checkout token creates default payment method.
- Renewal charge uses default active token.
- Revoked token cannot be charged.
- Expired token produces hard-failure recovery flow.
- Duplicate token webhook does not attach duplicate payment method.
- Customer cannot update another customer's card.
- Retry after card update marks invoice paid and dunning recovered.

## Demo Moment

Show the failed renewal flow:

1. Nomba tokenized-card charge fails.
2. Recovery queue marks invoice as requiring action.
3. Customer opens portal and updates card through tokenized flow.
4. SubPilot stores only token reference.
5. Retry succeeds.
6. Downstream merchant app receives `dunning.recovered`.
