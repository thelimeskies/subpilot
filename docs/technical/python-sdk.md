# SubPilot Python SDK

The Python package lives in `packages/subpilot-python` and is intended for merchant backends that create customers, subscriptions, invoices, and customer portal sessions.

## Install

Local development:

```bash
pip install -e packages/subpilot-python
```

Package usage:

```bash
pip install subpilot
```

## Quickstart

```python
from subpilot import SubPilot

client = SubPilot(api_key="nse_test_...")

customer = client.customers.create(
    email="ada@example.com",
    name="Ada Okafor",
    external_id="user_123",
    idempotency_key="customer-user-123",
)

session = client.portal_sessions.create(
    customer_id=customer["id"],
    allowed_actions=[
        "view_subscriptions",
        "view_invoices",
        "update_payment_method",
        "pay_invoice",
    ],
    ttl_minutes=60,
    idempotency_key=f"portal-{customer['id']}",
)

print(session["url"])
```

## Client

```python
client = SubPilot(
    api_key="nse_test_...",
    base_url="https://api.subpilot.dev/api/v1",
    timeout=20.0,
)
```

Arguments:

| Argument | Required | Default | Description |
|---|---:|---|---|
| `api_key` | Yes | None | Secret API key. Use only on the backend. |
| `base_url` | No | `https://api.subpilot.dev/api/v1` | API base URL. Use `http://localhost:8000/api/v1` locally. |
| `timeout` | No | `20.0` | Request timeout in seconds. |

## Resources

| Resource | Methods |
|---|---|
| `client.customers` | `list`, `retrieve`, `create`, `update`, `archive`, `reactivate`, `merge` |
| `client.payment_methods` | `list`, `attach`, `set_default` |
| `client.portal_sessions` | `list`, `create` |
| `client.portal` | `context`, `pay_invoice` |
| `client.subscriptions` | `list`, `create` |
| `client.invoices` | `list`, `retry` |
| `client.publishable_keys` | `list`, `rotate` |

## Customer API

```python
customer = client.customers.create(
    email="ada@example.com",
    name="Ada Okafor",
    phone="+2348000000000",
    external_id="user_123",
    metadata={"plan_source": "web_app"},
    idempotency_key="customer-user-123",
)

client.customers.update(customer["id"], name="Ada O.", idempotency_key="customer-user-123-update")
```

## Payment Methods

SubPilot never accepts raw card data. Attach provider token references only:

```python
method = client.payment_methods.attach(
    customer["id"],
    provider="mock",
    token="tok_provider_4242",
    brand="Visa",
    last4="4242",
    exp_month=4,
    exp_year=2028,
    set_default=True,
    idempotency_key=f"pm-{customer['id']}-4242",
)
```

## Portal Sessions

```python
session = client.portal_sessions.create(
    customer_id=customer["id"],
    allowed_actions=[
        "view_subscriptions",
        "view_invoices",
        "update_payment_method",
        "pay_invoice",
        "cancel_subscription",
    ],
    ttl_minutes=60,
)
```

The response includes:

- `session`: stored portal session metadata.
- `token`: plaintext `portal_...` token returned once.
- `url`: hosted portal URL.
- `email_queued`: whether SubPilot queued a portal email.

## Embedded Portal Backend

Merchant frontend should never create portal sessions directly. The backend should return the portal token:

```python
def billing_portal_payload(current_user):
    customer_id = current_user.subpilot_customer_id
    session = client.portal_sessions.create(
        customer_id=customer_id,
        allowed_actions=["view_subscriptions", "view_invoices", "update_payment_method"],
        ttl_minutes=30,
    )
    return {"portalToken": session["token"]}
```

Then the frontend can render `@subpilot/portal-js` with its publishable key.

## Errors

The package raises:

| Error | Meaning |
|---|---|
| `SubPilotAPIError` | API returned a non-2xx response. Includes `status_code` and `payload`. |
| `SubPilotConnectionError` | Network or DNS failure. |
| `SubPilotError` | Base class for package exceptions. |

Example:

```python
from subpilot import SubPilot, SubPilotAPIError

try:
    client.customers.retrieve("bad-id")
except SubPilotAPIError as exc:
    print(exc.status_code)
    print(exc.payload)
```

## Examples

Runnable examples:

```text
packages/subpilot-python/examples/customer_portal.py
packages/subpilot-python/examples/embedded_portal_backend.py
```

Run locally:

```bash
SUBPILOT_API_KEY=nse_test_... \
SUBPILOT_BASE_URL=http://localhost:8000/api/v1 \
python packages/subpilot-python/examples/customer_portal.py
```

## Security Notes

- Keep `nse_test_...` and `nse_live_...` keys on the server only.
- Send only `portal_...` tokens and `pk_test_...` or `pk_live_...` keys to browser code.
- Use idempotency keys for every retryable mutation.
- Use short portal session TTLs.
- Limit `allowed_actions` to what the customer needs for the current workflow.
