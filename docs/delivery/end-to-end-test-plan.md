# End-to-End Test Plan

This test plan verifies the demo path and the highest-risk billing behavior.

## Test Environment

- Django app in test mode.
- PostgreSQL test database.
- Redis test broker or eager Celery mode.
- `MockNombaAdapter`.
- Seed data from [seed-data.json](./seed-data.json).

## Test Command Targets

Expected commands:

```bash
python manage.py seed_demo --reset
pytest tests/e2e/test_demo_recovery_flow.py
pytest tests/state_machines/
pytest tests/api/
```

## E2E-01 Create Plan and Activate

Steps:

1. Create product.
2. Create Pro Monthly plan.
3. Attach Default SaaS Recovery.
4. Activate plan.

Expected:

- Plan status is active.
- Price version exists.
- Plan has dunning policy.
- Audit log records activation.

## E2E-02 Create Subscription Through Checkout

Steps:

1. Create customer Ada.
2. Create subscription for Pro Monthly.
3. Mock Nomba checkout success.
4. Process webhook.

Expected:

- Subscription moves `incomplete -> active`.
- First invoice is paid.
- Payment method token is stored encrypted.
- `subscription.activated` event is emitted.

## E2E-03 Renewal Failure Starts Dunning

Steps:

1. Set Chinedu subscription to due.
2. Run billing renewal job.
3. Mock tokenized-card insufficient funds.

Expected:

- Renewal invoice is open.
- Payment attempt failed.
- Subscription is past_due.
- Dunning run is active.
- Recovery link exists.
- `invoice.payment_failed` and `dunning.started` events are emitted.

## E2E-04 Customer Portal Recovery

Steps:

1. Open Chinedu recovery portal session.
2. Mock card update success.
3. Retry invoice.
4. Mock charge success.

Expected:

- New payment method is default.
- Invoice becomes paid.
- Dunning run becomes recovered.
- Subscription becomes active.
- `dunning.recovered` event is emitted.

## E2E-05 Webhook Replay

Steps:

1. Create webhook endpoint.
2. Fail delivery for `dunning.recovered`.
3. Replay event.

Expected:

- Original event ID stays the same.
- New delivery attempt is created.
- Payload is signed.
- Delivery history shows replay.

## E2E-06 Proration Preview

Steps:

1. Active Pro subscription.
2. Preview upgrade to Business.

Expected:

- Preview shows unused credit.
- Preview shows new charge.
- Net due is calculated.
- No subscription mutation occurs before confirm.

## E2E-07 Tenant Isolation

Steps:

1. Create second merchant.
2. Attempt to fetch Acme customer with second merchant API key.

Expected:

- API returns 404 or permission error.
- No cross-tenant data leaks.

## E2E-08 Hard Failure Requires New Card

Steps:

1. Mock tokenized-card expired failure.
2. Process failed renewal.

Expected:

- Dunning pauses for payment method.
- Automatic retry is not scheduled until card update.
- Customer portal link asks for new card.

## Demo Readiness Exit Criteria

- All E2E tests pass in mock mode.
- Demo seed command is deterministic.
- Failed renewal recovery can be run twice after reset.
- Webhook replay can be shown without external dependency.
- Dashboard metrics match seeded data.
