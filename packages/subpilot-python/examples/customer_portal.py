"""Create a customer portal session.

Run:

    SUBPILOT_API_KEY=nse_test_... python examples/customer_portal.py
"""
from __future__ import annotations

import os

from subpilot import SubPilot


def main() -> None:
    client = SubPilot(
        api_key=os.environ["SUBPILOT_API_KEY"],
        base_url=os.environ.get("SUBPILOT_BASE_URL", "http://localhost:8000/api/v1"),
    )

    customer = client.customers.create(
        email="ada@example.com",
        name="Ada Okafor",
        external_id="demo_user_123",
        metadata={"source": "python_example"},
        idempotency_key="demo-customer-ada",
    )

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
        idempotency_key=f"demo-portal-{customer['id']}",
    )

    print("Customer:", customer["id"])
    print("Portal URL:", session["url"])
    print("Portal token:", session["token"])


if __name__ == "__main__":
    main()
