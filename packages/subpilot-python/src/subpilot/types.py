from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, TypedDict


JsonObject = Dict[str, Any]
PortalAction = Literal[
    "view_subscriptions",
    "view_invoices",
    "update_payment_method",
    "pay_invoice",
    "cancel_subscription",
]


class Customer(TypedDict, total=False):
    id: str
    external_id: str
    email: str
    name: str
    phone: str
    status: str
    metadata: JsonObject
    created_at: str
    updated_at: str


class PaymentMethod(TypedDict, total=False):
    id: str
    customer: str
    provider: str
    brand: str
    last4: str
    exp_month: Optional[int]
    exp_year: Optional[int]
    status: str
    is_default: bool
    fingerprint: str
    metadata: JsonObject


class PortalSession(TypedDict, total=False):
    id: str
    customer: str
    subscription: Optional[str]
    invoice: Optional[str]
    allowed_actions: List[PortalAction]
    return_url: str
    expires_at: str
    used_at: Optional[str]
    created_at: str


class PortalSessionCreateResponse(TypedDict, total=False):
    session: PortalSession
    token: str
    url: str
    email_queued: bool
