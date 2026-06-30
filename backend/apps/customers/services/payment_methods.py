"""Service: attach a payment method to a customer.

The token reference is encrypted at rest (handled by ``PaymentMethod.token``
property). The API layer never returns the token back to clients.
"""
from __future__ import annotations

from django.db import transaction

from apps.audit.services.log_event import log_event
from apps.common.db import atomic_with_retry
from apps.common.exceptions import ServiceError
from apps.events.services.create_event import emit as _emit_event

from ..models import Customer, PaymentMethod


def _pm_payload(pm: PaymentMethod, **extra) -> dict:
    return {
        "payment_method_id": str(pm.id),
        "customer_id": str(pm.customer_id),
        "provider": pm.provider,
        "brand": pm.brand,
        "last4": pm.last4,
        "is_default": pm.is_default,
        "status": pm.status,
        **extra,
    }


@atomic_with_retry
def attach_payment_method(
    *,
    customer: Customer,
    provider: str,
    token: str,
    brand: str = "",
    last4: str = "",
    exp_month: int | None = None,
    exp_year: int | None = None,
    fingerprint: str = "",
    set_default: bool = False,
    metadata: dict | None = None,
    actor_user=None,
    request=None,
) -> PaymentMethod:
    if provider not in dict(PaymentMethod.Provider.choices):
        raise ServiceError("Unsupported provider.")
    if not token:
        raise ServiceError("Token is required.")
    if last4 and (not last4.isdigit() or len(last4) > 4):
        raise ServiceError("last4 must be up to four digits.")

    pm = PaymentMethod(
        merchant=customer.merchant,
        environment=customer.environment,
        customer=customer,
        provider=provider,
        brand=brand,
        last4=last4,
        exp_month=exp_month,
        exp_year=exp_year,
        fingerprint=fingerprint,
        is_default=False,
        status=PaymentMethod.Status.ACTIVE,
        metadata=metadata or {},
    )
    pm.token = token  # property -> encrypted
    pm.save()

    if set_default:
        _set_default(customer=customer, payment_method=pm)
        pm.refresh_from_db()

    log_event(
        action="customers.payment_method_attached",
        actor_user=actor_user,
        merchant=customer.merchant,
        environment=customer.environment,
        target_type="payment_method",
        target_id=str(pm.id),
        metadata={
            "customer_id": str(customer.id),
            "brand": brand,
            "last4": last4,
            "is_default": pm.is_default,
        },
        request=request,
    )
    _emit_event(
        merchant=customer.merchant,
        environment=customer.environment,
        event_type="payment_method.attached",
        aggregate_type="payment_method",
        aggregate_id=str(pm.id),
        payload=_pm_payload(pm),
        actor_user=actor_user,
        request=request,
    )
    return pm


@atomic_with_retry
def set_default_payment_method(
    *, customer: Customer, payment_method: PaymentMethod, actor_user=None, request=None
) -> PaymentMethod:
    if payment_method.customer_id != customer.id:
        raise ServiceError("Payment method does not belong to this customer.")
    if payment_method.status != PaymentMethod.Status.ACTIVE:
        raise ServiceError("Only active payment methods can be set as default.")
    _set_default(customer=customer, payment_method=payment_method)
    payment_method.refresh_from_db()
    log_event(
        action="customers.payment_method_default_set",
        actor_user=actor_user,
        merchant=customer.merchant,
        environment=customer.environment,
        target_type="payment_method",
        target_id=str(payment_method.id),
        request=request,
    )
    _emit_event(
        merchant=customer.merchant,
        environment=customer.environment,
        event_type="payment_method.updated",
        aggregate_type="payment_method",
        aggregate_id=str(payment_method.id),
        payload=_pm_payload(payment_method, change="default_set"),
        actor_user=actor_user,
        request=request,
    )
    return payment_method


def _set_default(*, customer: Customer, payment_method: PaymentMethod) -> None:
    """Atomically flip ``is_default`` so only one row holds it for the customer."""
    PaymentMethod.objects.select_for_update().filter(
        customer=customer, is_default=True
    ).exclude(pk=payment_method.pk).update(is_default=False)
    PaymentMethod.objects.filter(pk=payment_method.pk).update(is_default=True)
