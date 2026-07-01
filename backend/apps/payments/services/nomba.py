"""SubPilot service layer for Nomba-backed operations."""
from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.exceptions import ServiceError
from apps.customers.models import Customer, PaymentMethod
from apps.invoices.models import Invoice
from apps.payments.integrations.nomba.client import (
    NombaError,
    credentials_for_environment,
    NombaClient,
)
from apps.payments.models import PaymentAttempt


def _major_units(amount_minor: int) -> str:
    return f"{Decimal(amount_minor) / Decimal(100):.2f}"


def _configured_or_raise(environment) -> None:
    creds = credentials_for_environment(environment)
    missing = [
        name
        for name, value in {
            "account_id": creds.account_id,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
        }.items()
        if not value
    ]
    if missing:
        raise ServiceError(f"Nomba credentials are missing: {', '.join(missing)}.")


def get_nomba_client(environment) -> NombaClient:
    _configured_or_raise(environment)
    return NombaClient(environment=environment, credentials=credentials_for_environment(environment))


def validate_nomba_credentials(environment, *, actor_user=None, request=None) -> dict[str, Any]:
    _configured_or_raise(environment)
    client = NombaClient(
        environment=environment,
        credentials=credentials_for_environment(environment),
    )
    try:
        payload = client.issue_token()
        ok = True
        reason = ""
    except NombaError as exc:
        payload = {"error": str(exc)}
        ok = False
        reason = str(exc)

    environment.nomba_credentials_validated_at = timezone.now() if ok else None
    environment.nomba_last_validation = {
        "ok": ok,
        "reason": reason,
        "validated_at": timezone.now().isoformat(),
        "mode": environment.mode,
    }
    environment.save(
        update_fields=[
            "nomba_credentials_validated_at",
            "nomba_last_validation",
            "updated_at",
        ]
    )
    log_event(
        action="payments.nomba_credentials_validated",
        actor_user=actor_user,
        merchant=environment.merchant,
        environment=environment,
        target_type="environment",
        target_id=str(environment.id),
        metadata={"ok": ok, "mode": environment.mode, "reason": reason[:200]},
        request=request,
    )
    if not ok:
        raise ServiceError(reason)
    return {"ok": True, "payload": payload, "validated_at": environment.nomba_credentials_validated_at}


def activate_nomba_environment(environment, *, mode: str, actor_user=None, request=None) -> dict[str, Any]:
    if environment.mode != mode:
        raise ServiceError("Cannot activate a different environment mode.")
    validate_nomba_credentials(environment, actor_user=actor_user, request=request)
    if environment.mode == "live":
        environment.nomba_live_active = True
        environment.save(update_fields=["nomba_live_active", "updated_at"])
    log_event(
        action="payments.nomba_environment_activated",
        actor_user=actor_user,
        merchant=environment.merchant,
        environment=environment,
        target_type="environment",
        target_id=str(environment.id),
        metadata={"mode": environment.mode, "live_active": environment.nomba_live_active},
        request=request,
    )
    return {"ok": True, "mode": environment.mode, "live_active": environment.nomba_live_active}


def sync_nomba_accounts(environment, *, actor_user=None, request=None) -> dict[str, Any]:
    client = get_nomba_client(environment)
    payload = client.list_accounts()
    log_event(
        action="payments.nomba_accounts_synced",
        actor_user=actor_user,
        merchant=environment.merchant,
        environment=environment,
        target_type="environment",
        target_id=str(environment.id),
        metadata={"mode": environment.mode},
        request=request,
    )
    return payload


def map_nomba_sub_account(environment, *, sub_account_id: str, actor_user=None, request=None) -> dict[str, Any]:
    environment.nomba_sub_account_id = sub_account_id
    environment.save(update_fields=["nomba_sub_account_id", "updated_at"])
    log_event(
        action="payments.nomba_sub_account_mapped",
        actor_user=actor_user,
        merchant=environment.merchant,
        environment=environment,
        target_type="environment",
        target_id=str(environment.id),
        metadata={"sub_account_id": sub_account_id},
        request=request,
    )
    return {"ok": True, "sub_account_id": sub_account_id}


def create_nomba_virtual_account(
    *,
    customer: Customer,
    environment=None,
    sub_account_id: str | None = None,
    expected_amount_minor: int | None = None,
    expiry_date: str = "",
) -> dict[str, Any]:
    env = environment or customer.environment
    client = get_nomba_client(env)
    account_ref = f"subpilot-{customer.id}".replace("-", "")[:64]
    payload: dict[str, Any] = {
        "accountRef": account_ref,
        "accountName": (customer.name or customer.email)[:64],
    }
    if expected_amount_minor is not None:
        payload["expectedAmount"] = _major_units(expected_amount_minor)
    if expiry_date:
        payload["expiryDate"] = expiry_date
    return client.create_virtual_account(
        payload,
        sub_account_id=sub_account_id or env.nomba_sub_account_id,
    )


def charge_nomba_tokenized_card(*, invoice: Invoice, payment_method: PaymentMethod, idempotency_key: str) -> dict[str, Any]:
    client = get_nomba_client(invoice.environment)
    order_reference = idempotency_key.replace(":", "-")
    payload = {
        "tokenKey": payment_method.token,
        "order": {
            "orderReference": order_reference,
            "customerId": str(invoice.customer_id),
            "callbackUrl": "",
            "customerEmail": invoice.customer.email,
            "amount": _major_units(invoice.amount_due_minor),
            "currency": invoice.currency,
            "accountId": invoice.environment.nomba_sub_account_id or invoice.environment.nomba_account_id,
            "orderMetaData": {
                "invoice_id": str(invoice.id),
                "customer_id": str(invoice.customer_id),
                "subpilot_idempotency_key": idempotency_key,
            },
        },
    }
    return client.charge_tokenized_card(payload)


def refund_nomba_payment(*, payment_attempt: PaymentAttempt, amount_minor: int, reason: str = "") -> dict[str, Any]:
    if not payment_attempt.processor_reference:
        raise ServiceError("Cannot refund a Nomba payment without a processor reference.")
    client = get_nomba_client(payment_attempt.environment)
    payload: dict[str, Any] = {
        "transactionId": payment_attempt.processor_reference,
        "amount": _major_units(amount_minor),
    }
    payout = payment_attempt.invoice.metadata.get("refund_destination") if isinstance(payment_attempt.invoice.metadata, dict) else None
    if isinstance(payout, dict):
        if payout.get("accountNumber"):
            payload["accountNumber"] = payout["accountNumber"]
        if payout.get("bankCode"):
            payload["bankCode"] = payout["bankCode"]
    response = client.refund_checkout_transaction(payload)
    log_event(
        action="payments.nomba_refund_requested",
        merchant=payment_attempt.merchant,
        environment=payment_attempt.environment,
        target_type="payment_attempt",
        target_id=str(payment_attempt.id),
        metadata={"amount_minor": amount_minor, "reason": reason, "reference": payment_attempt.processor_reference},
    )
    return response


def verify_nomba_transaction(environment, *, reference: str) -> dict[str, Any]:
    client = get_nomba_client(environment)
    try:
        return client.fetch_checkout_transaction(transactionId=reference)
    except NombaError:
        return client.requery_transaction(reference)
