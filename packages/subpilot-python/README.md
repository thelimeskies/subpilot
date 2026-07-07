# subpilot

Python client for the SubPilot recurring billing API.

## Install

```bash
pip install subpilot
```

For local development in this repository:

```bash
pip install -e packages/subpilot-python
```

## Quickstart

```python
from subpilot import SubPilot

client = SubPilot(api_key="nse_test_...")

customer = client.customers.create(
    email="ada@example.com",
    name="Ada Okafor",
    external_id="user_123",
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
)

print(session["url"])
print(session["token"])
```

## Resources

- `client.customers`
- `client.payment_methods`
- `client.portal_sessions`
- `client.portal`
- `client.subscriptions`
- `client.invoices`
- `client.publishable_keys`

## Security

Use secret API keys only on your backend. Publishable keys are for browser SDKs. Portal tokens are short-lived and scoped to one customer session.

## Examples

See `examples/customer_portal.py`.
