# Customer Portal

## Purpose

Give subscribers a secure, merchant-branded place to manage billing without support intervention.

## Users

- Active subscriber
- Trial subscriber
- Past-due subscriber
- Canceled subscriber
- Enterprise account buyer

## Django Ownership

Primary app: `customers`

Supporting apps:

- `subscriptions`
- `invoices`
- `payments`
- `dunning`
- `audit`

## Portal Session

Portal sessions must be:

- Signed
- Time-limited
- Scoped to merchant and customer
- Restricted by allowed actions
- Single-use for sensitive actions if needed

Fields:

- `customer`
- `merchant`
- `environment`
- `token_hash`
- `allowed_actions`
- `return_url`
- `expires_at`
- `used_at`

## Portal Screens

### Portal Home

Shows:

- Merchant brand
- Customer identity
- Current plan
- Subscription status
- Renewal date
- Payment method summary
- Invoice history

### Update Payment Method

Shows:

- Reason for update
- Current payment summary
- Nomba checkout/update flow
- Success/failure result

### Pay Invoice

Shows:

- Invoice number
- Amount due
- Due date
- Failed reason if past due
- Pay button

### Cancel Subscription

Shows:

- Current plan
- Cancellation effect
- Access end date
- Confirmation checkbox

## Policy Controls

Merchant can configure:

- Allow customer cancellation
- Allow pause/resume
- Allow plan changes
- Require cancellation reason
- End access immediately or at period end

## Past-Due UX

Past-due portal state must prioritize:

- Amount due
- Why payment failed
- What happens if unpaid
- Update payment method action
- Support contact fallback

## Acceptance Tests

- Expired portal session cannot be used.
- Customer cannot access another customer's portal.
- Updating payment method stores token reference only.
- Paying overdue invoice recovers subscription if policy allows.
- Cancel action follows merchant cancellation policy.

## Demo Moment

Open recovery link from the queue, show customer-facing past-due state, update card, then return to merchant dashboard showing recovered invoice.
