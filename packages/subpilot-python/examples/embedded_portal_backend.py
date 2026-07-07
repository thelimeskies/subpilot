"""Backend helper shape for an embedded portal frontend.

This is framework-agnostic pseudo-handler code. In a Django/FastAPI route,
authenticate your app user, resolve their SubPilot customer ID, then return the
short-lived portal token to the browser.
"""
from __future__ import annotations

import os

from subpilot import SubPilot


client = SubPilot(api_key=os.environ["SUBPILOT_API_KEY"])


def create_billing_portal_payload(subpilot_customer_id: str) -> dict:
    session = client.portal_sessions.create(
        customer_id=subpilot_customer_id,
        allowed_actions=[
            "view_subscriptions",
            "view_invoices",
            "update_payment_method",
            "pay_invoice",
        ],
        ttl_minutes=30,
    )
    publishable = client.publishable_keys.list()["keys"][0]["publishable_key"]
    return {
        "portalToken": session["token"],
        "publishableKey": publishable,
    }
