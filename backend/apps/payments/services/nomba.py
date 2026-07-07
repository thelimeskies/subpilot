"""SubPilot service layer for Nomba-backed operations."""
from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.utils import timezone

from apps.audit.services.log_event import log_event
from apps.common.exceptions import ServiceError
from apps.customers.models import Customer, PaymentMethod
from apps.invoices.models import Invoice
from apps.payments.integrations.nomba.client import (
    NombaClient,
    NombaError,
    credentials_for_environment,
)
from apps.payments.models import PaymentAttempt

logger = logging.getLogger(__name__)

BANK_ALIASES = {
    "gtbank": "guaranty trust bank",
    "gt bank": "guaranty trust bank",
    "first bank of nigeria": "first bank",
    "uba": "united bank for africa",
}

NIGERIA_BANK_CODE_FALLBACKS = {
    "access bank": ("044", "Access Bank"),
    "ecobank nigeria": ("050", "Ecobank Nigeria"),
    "fidelity bank": ("070", "Fidelity Bank"),
    "first bank": ("011", "First Bank of Nigeria"),
    "guaranty trust bank": ("058", "GTBank"),
    "kuda microfinance bank": ("50211", "Kuda Microfinance Bank"),
    "polaris bank": ("076", "Polaris Bank"),
    "providus bank": ("101", "Providus Bank"),
    "stanbic ibtc": ("221", "Stanbic IBTC"),
    "sterling bank": ("232", "Sterling Bank"),
    "united bank for africa": ("033", "UBA"),
    "union bank": ("032", "Union Bank"),
    "wema bank": ("035", "Wema Bank"),
    "zenith bank": ("057", "Zenith Bank"),
}


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


def _platform_sub_account_id(environment) -> str:
    if environment.nomba_integration_mode == "byok":
        return ""
    if environment.mode == "live":
        return getattr(settings, "NOMBA_PLATFORM_LIVE_SUB_ACCOUNT_ID", "") or ""
    return getattr(settings, "NOMBA_PLATFORM_TEST_SUB_ACCOUNT_ID", "") or ""


def nomba_sub_account_id_for_environment(environment, *, explicit: str | None = None) -> str:
    return explicit or environment.nomba_sub_account_id or _platform_sub_account_id(environment)


def nomba_routing_account_id_for_environment(environment, *, explicit_sub_account_id: str | None = None) -> str:
    return (
        nomba_sub_account_id_for_environment(environment, explicit=explicit_sub_account_id)
        or credentials_for_environment(environment).account_id
    )


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
    return {
        "ok": True,
        "payload": payload,
        "validated_at": environment.nomba_credentials_validated_at,
        "sub_account_id": nomba_sub_account_id_for_environment(environment),
    }


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


def _normalize_bank_name(value: str) -> str:
    normalized = " ".join(value.lower().replace("&", "and").replace(".", " ").split())
    return BANK_ALIASES.get(normalized, normalized)


def _extract_bank_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if not isinstance(payload, dict):
        return []
    candidates = [
        payload.get("data"),
        payload.get("banks"),
        payload.get("result"),
        payload.get("results"),
    ]
    for candidate in candidates:
        if isinstance(candidate, list):
            return [row for row in candidate if isinstance(row, dict)]
        if isinstance(candidate, dict):
            nested = _extract_bank_rows(candidate)
            if nested:
                return nested
    return []


def _bank_label(row: dict[str, Any]) -> str:
    for key in ("name", "bankName", "bank_name", "institutionName", "institution_name"):
        if row.get(key):
            return str(row[key])
    return ""


def _bank_code(row: dict[str, Any]) -> str:
    for key in ("code", "bankCode", "bank_code", "nipCode", "nip_code"):
        if row.get(key):
            return str(row[key])
    return ""


def _resolve_bank_code(client: NombaClient, bank: str) -> tuple[str, str]:
    if bank.strip().isdigit():
        return bank.strip(), bank.strip()
    wanted = _normalize_bank_name(bank)
    try:
        banks_payload = client.fetch_banks()
    except NombaError as exc:
        fallback = NIGERIA_BANK_CODE_FALLBACKS.get(wanted)
        if fallback:
            logger.warning(
                "payments.nomba_bank_list_failed_using_fallback",
                extra={"bank": bank, "reason": str(exc)},
            )
            return fallback
        raise
    else:
        for row in _extract_bank_rows(banks_payload):
            label = _bank_label(row)
            code = _bank_code(row)
            normalized = _normalize_bank_name(label)
            if code and (normalized == wanted or wanted in normalized or normalized in wanted):
                return code, label or bank
    fallback = NIGERIA_BANK_CODE_FALLBACKS.get(wanted)
    if fallback:
        return fallback
    raise ServiceError(f"Nomba does not list '{bank}' as a supported bank.")


def list_nomba_banks(environment) -> dict[str, Any]:
    client = get_nomba_client(environment)
    response = client.fetch_banks()
    banks = []
    for row in _extract_bank_rows(response):
        label = _bank_label(row)
        code = _bank_code(row)
        if label and code:
            banks.append({"name": label, "code": code})
    if not banks:
        raise ServiceError("Nomba did not return any supported banks.")
    banks.sort(key=lambda item: item["name"].lower())
    return {"ok": True, "banks": banks, "raw": response}


def _extract_account_name(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("accountName", "account_name", "name", "account_name_enquiry"):
            if payload.get(key):
                return str(payload[key])
        for key in ("data", "result", "payload"):
            name = _extract_account_name(payload.get(key))
            if name:
                return name
    return ""


def lookup_nomba_bank_account(
    environment,
    *,
    bank: str,
    account_number: str,
    actor_user=None,
    request=None,
) -> dict[str, Any]:
    clean_account_number = "".join(ch for ch in account_number if ch.isdigit())
    if len(clean_account_number) < 10:
        raise ServiceError("Enter a valid 10-digit bank account number.")
    client = get_nomba_client(environment)
    bank_code, bank_name = _resolve_bank_code(client, bank)
    payload = {
        "accountNumber": clean_account_number,
        "bankCode": bank_code,
    }
    response = client.lookup_bank_account(payload)
    account_name = _extract_account_name(response)
    if not account_name:
        raise ServiceError("Nomba did not return an account name for this bank account.")
    log_event(
        action="payments.nomba_bank_account_lookup",
        actor_user=actor_user,
        merchant=environment.merchant,
        environment=environment,
        target_type="environment",
        target_id=str(environment.id),
        metadata={"bank": bank_name, "bank_code": bank_code, "mode": environment.mode},
        request=request,
    )
    return {
        "ok": True,
        "account_name": account_name,
        "bank_name": bank_name,
        "bank_code": bank_code,
        "raw": response,
    }


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
        sub_account_id=nomba_sub_account_id_for_environment(env, explicit=sub_account_id),
    )


def create_nomba_tokenized_checkout(*, invoice: Invoice, idempotency_key: str = "") -> dict[str, Any]:
    """Create the customer-present Nomba checkout that mints a tokenKey.

    This is the CIT leg from the walkthrough: the customer enters card details
    and completes OTP/3DS on Nomba's hosted page. Nomba later sends the tokenKey
    through the payment_success webhook.
    """
    client = get_nomba_client(invoice.environment)
    stable_key = idempotency_key or f"checkout:{invoice.id}"
    order_reference = stable_key.replace(":", "-")
    attempt = _get_or_create_checkout_attempt(
        invoice=invoice,
        idempotency_key=stable_key,
        order_reference=order_reference,
    )
    metadata = {
        "invoice_id": str(invoice.id),
        "customer_id": str(invoice.customer_id),
        "payment_attempt_id": str(attempt.id),
        "subscription_id": str(invoice.subscription_id) if invoice.subscription_id else "",
        "subpilot_idempotency_key": stable_key,
    }
    payload = {
        "order": {
            "orderReference": order_reference,
            "customerId": str(invoice.customer_id),
            "callbackUrl": getattr(settings, "NOMBA_CHECKOUT_CALLBACK_URL", ""),
            "customerEmail": invoice.customer.email,
            "amount": _major_units(invoice.amount_due_minor),
            "currency": invoice.currency,
            "accountId": nomba_routing_account_id_for_environment(invoice.environment),
            "allowedPaymentMethods": ["Card"],
            "orderMetaData": metadata,
        },
        "tokenizeCard": True,
    }
    try:
        response = client.create_checkout_order(payload)
    except NombaError as exc:
        attempt.status = PaymentAttempt.Status.FAILED
        attempt.failure_code = "processor_error"
        attempt.failure_message = str(exc)[:400]
        attempt.save(update_fields=["status", "failure_code", "failure_message", "updated_at"])
        raise
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    checkout_url = str(data.get("checkoutLink") or "")
    nomba_reference = str(data.get("orderReference") or order_reference)
    checkout_id = _checkout_id_from_url(checkout_url)
    if not checkout_url:
        attempt.status = PaymentAttempt.Status.FAILED
        attempt.failure_code = str(response.get("code") or "processor_error")[:64]
        attempt.failure_message = str(
            response.get("description") or data.get("message") or "Nomba did not return a checkout URL."
        )[:400]
        attempt.save(update_fields=["status", "failure_code", "failure_message", "updated_at"])
        return response
    attempt.processor_reference = nomba_reference[:128]
    attempt.metadata = {
        **(attempt.metadata or {}),
        "source": "nomba_hosted_checkout",
        "checkout_url_created": bool(checkout_url),
        "nomba_checkout_id": checkout_id,
        "local_order_reference": order_reference,
        "nomba_order_reference": nomba_reference,
    }
    attempt.save(update_fields=["processor_reference", "metadata", "updated_at"])
    invoice.hosted_payment_url = checkout_url
    invoice.metadata = {
        **(invoice.metadata or {}),
        "nomba_checkout_id": checkout_id,
        "nomba_checkout_order_reference": nomba_reference,
        "nomba_checkout_payment_attempt_id": str(attempt.id),
        "nomba_tokenize_card": True,
        "nomba_checkout_metadata": metadata,
    }
    invoice.save(update_fields=["hosted_payment_url", "metadata", "updated_at"])
    log_event(
        action="payments.nomba_tokenized_checkout_created",
        merchant=invoice.merchant,
        environment=invoice.environment,
        target_type="invoice",
        target_id=str(invoice.id),
        metadata={
            "subscription_id": str(invoice.subscription_id) if invoice.subscription_id else "",
            "order_reference": nomba_reference,
            "checkout_id": checkout_id,
            "has_checkout_url": bool(checkout_url),
        },
    )
    return response


def _get_or_create_checkout_attempt(
    *,
    invoice: Invoice,
    idempotency_key: str,
    order_reference: str,
) -> PaymentAttempt:
    attempt = PaymentAttempt.objects.filter(
        merchant=invoice.merchant,
        environment=invoice.environment,
        idempotency_key=idempotency_key,
    ).first()
    if attempt is not None:
        if attempt.status in {PaymentAttempt.Status.FAILED, PaymentAttempt.Status.ABANDONED}:
            attempt.status = PaymentAttempt.Status.PENDING
            attempt.failure_code = ""
            attempt.failure_message = ""
            attempt.amount_minor = invoice.amount_due_minor
            attempt.currency = invoice.currency
            attempt.processor_reference = order_reference[:128]
            attempt.metadata = {
                **(attempt.metadata or {}),
                "source": "nomba_hosted_checkout",
                "local_order_reference": order_reference,
            }
            attempt.save(
                update_fields=[
                    "status",
                    "failure_code",
                    "failure_message",
                    "amount_minor",
                    "currency",
                    "processor_reference",
                    "metadata",
                    "updated_at",
                ]
            )
        return attempt
    return PaymentAttempt.objects.create(
        merchant=invoice.merchant,
        environment=invoice.environment,
        invoice=invoice,
        payment_method=getattr(invoice.subscription, "default_payment_method", None),
        attempt_number=_next_checkout_attempt_number(invoice),
        status=PaymentAttempt.Status.PENDING,
        amount_minor=invoice.amount_due_minor,
        currency=invoice.currency,
        processor_reference=order_reference[:128],
        idempotency_key=idempotency_key,
        metadata={
            "source": "nomba_hosted_checkout",
            "local_order_reference": order_reference,
        },
    )


def _next_checkout_attempt_number(invoice: Invoice) -> int:
    last = (
        PaymentAttempt.objects.filter(invoice=invoice)
        .order_by("-attempt_number")
        .values_list("attempt_number", flat=True)
        .first()
    )
    return (last or 0) + 1


def _checkout_id_from_url(checkout_url: str) -> str:
    if not checkout_url:
        return ""
    parsed = urlparse(checkout_url)
    parts = [part for part in parsed.path.split("/") if part]
    return parts[-1] if parts else ""


def confirm_nomba_tokenized_checkout(
    *,
    invoice: Invoice,
    order_reference: str,
    request=None,
) -> dict[str, Any]:
    """Poll Nomba for a hosted tokenized checkout and apply it if complete.

    This is a fallback for environments where Nomba webhooks are delayed or not
    yet deliverable. It intentionally reuses ``process_processor_event`` so the
    side effects match the webhook path: attach tokenized card data when
    available, set the customer's default method, activate the subscription, and
    mark the invoice paid.
    """
    response = _get_nomba_checkout_order(invoice=invoice, order_reference=order_reference)
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    tokenized_card = _find_nested_dict(data, "tokenizedCardData") or _find_nested_dict(
        data, "tokenized_card_data"
    )
    status_label, confirmed = _checkout_payment_status(data, tokenized_card=tokenized_card)
    if not confirmed:
        return {
            "confirmed": False,
            "status": status_label or "pending",
            "invoice_paid": invoice.status == Invoice.Status.PAID,
            "payment_method_attached": bool(invoice.customer.payment_methods.filter(provider=PaymentMethod.Provider.NOMBA).exists()),
            "raw": response,
        }

    raw_event = _checkout_order_response_as_webhook_payload(
        invoice=invoice,
        order_reference=order_reference,
        response=response,
        tokenized_card=tokenized_card,
    )
    from apps.payments.adapters import get_adapter

    from .process_processor_event import process_processor_event

    parsed = get_adapter("nomba").parse_webhook(payload=raw_event)
    event = process_processor_event(
        merchant=invoice.merchant,
        environment=invoice.environment,
        parsed=parsed,
        request=request,
    )
    invoice.refresh_from_db()
    return {
        "confirmed": True,
        "status": "payment.succeeded",
        "invoice_paid": invoice.status == Invoice.Status.PAID,
        "payment_method_attached": bool(
            invoice.customer.payment_methods.filter(provider=PaymentMethod.Provider.NOMBA).exists()
        ),
        "event_id": str(event.id),
        "raw": response,
    }


def _get_nomba_checkout_order(*, invoice: Invoice, order_reference: str) -> dict[str, Any]:
    client = get_nomba_client(invoice.environment)
    references = []
    metadata = invoice.metadata if isinstance(invoice.metadata, dict) else {}
    stored_checkout_id = str(metadata.get("nomba_checkout_id") or "")
    hosted_checkout_id = _checkout_id_from_url(invoice.hosted_payment_url or "")
    stored_reference = str(metadata.get("nomba_checkout_order_reference") or "")
    stable_reference = f"checkout-{invoice.id}"
    for candidate in (stored_checkout_id, hosted_checkout_id, stored_reference, order_reference, stable_reference):
        if candidate and candidate not in references:
            references.append(candidate)

    last_error: NombaError | None = None
    last_rejected: str = ""
    for reference in references:
        try:
            response = client.get_checkout_order(reference)
        except NombaError as exc:
            last_error = exc
            continue
        code = str(response.get("code") or "").strip()
        if code and code != "00":
            last_rejected = str(response.get("description") or response.get("message") or code)
            continue
        return response
    if last_error is not None:
        raise last_error
    if last_rejected:
        logger.warning(
            "payments.nomba_checkout_poll_rejected",
            extra={
                "invoice_id": str(invoice.id),
                "references": references,
                "last_rejected": last_rejected,
            },
        )
        return {"code": "pending", "description": last_rejected, "status": False, "data": {}}
    raise ServiceError("No Nomba checkout reference is available for this invoice.")


def _checkout_order_response_as_webhook_payload(
    *,
    invoice: Invoice,
    order_reference: str,
    response: dict[str, Any],
    tokenized_card: dict[str, Any],
) -> dict[str, Any]:
    data = response.get("data") if isinstance(response.get("data"), dict) else {}
    transaction = _find_nested_dict(data, "transaction") or {}
    transaction_id = str(
        transaction.get("transactionId")
        or transaction.get("transaction_id")
        or data.get("transactionId")
        or data.get("transaction_id")
        or data.get("reference")
        or order_reference
    )
    metadata = {
        "invoice_id": str(invoice.id),
        "customer_id": str(invoice.customer_id),
        "subscription_id": str(invoice.subscription_id) if invoice.subscription_id else "",
        "subpilot_idempotency_key": f"checkout:{invoice.id}",
    }
    event_data = {
        **data,
        "currency": data.get("currency") or invoice.currency,
        "amount": data.get("amount") or _major_units(invoice.amount_due_minor or invoice.total_minor),
        "orderReference": data.get("orderReference") or order_reference,
        "orderMetaData": data.get("orderMetaData") if isinstance(data.get("orderMetaData"), dict) else metadata,
        "transaction": {
            **transaction,
            "transactionId": transaction_id,
            "transactionAmount": (
                transaction.get("transactionAmount")
                or data.get("amount")
                or _major_units(invoice.amount_due_minor or invoice.total_minor)
            ),
            "responseCode": transaction.get("responseCode") or "00",
            "responseMessage": transaction.get("responseMessage") or "Payment confirmed by checkout polling",
        },
    }
    if tokenized_card:
        event_data["tokenizedCardData"] = tokenized_card
    return {
        "event_type": "payment_success",
        "requestId": str(data.get("requestId") or data.get("request_id") or f"poll:{order_reference}"),
        "data": event_data,
    }


def _checkout_payment_status(
    data: dict[str, Any],
    *,
    tokenized_card: dict[str, Any],
) -> tuple[str, bool]:
    if tokenized_card.get("tokenKey"):
        return "tokenized", True

    transaction = _find_nested_dict(data, "transaction") or {}
    response_code = str(
        transaction.get("responseCode")
        or transaction.get("response_code")
        or data.get("responseCode")
        or data.get("response_code")
        or ""
    ).strip()
    if response_code == "00":
        return "successful", True

    for value in (
        transaction.get("status"),
        transaction.get("paymentStatus"),
        transaction.get("transactionStatus"),
        data.get("paymentStatus"),
        data.get("payment_status"),
        data.get("transactionStatus"),
        data.get("transaction_status"),
        data.get("orderStatus"),
        data.get("order_status"),
    ):
        label = str(value or "").strip().lower()
        if label in {"success", "successful", "paid", "completed", "complete", "approved"}:
            return label, True
        if label:
            return label, False
    return "", False


def _find_nested_dict(value: Any, key: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    direct = value.get(key)
    if isinstance(direct, dict):
        return direct
    for child in value.values():
        if isinstance(child, dict):
            found = _find_nested_dict(child, key)
            if found:
                return found
        elif isinstance(child, list):
            for item in child:
                found = _find_nested_dict(item, key)
                if found:
                    return found
    return {}


def charge_nomba_tokenized_card(*, invoice: Invoice, payment_method: PaymentMethod, idempotency_key: str) -> dict[str, Any]:
    client = get_nomba_client(invoice.environment)
    order_reference = idempotency_key.replace(":", "-")
    payload = {
        "tokenKey": payment_method.token,
        "order": {
            "orderReference": order_reference,
            "customerId": str(invoice.customer_id),
            "callbackUrl": getattr(settings, "NOMBA_CHECKOUT_CALLBACK_URL", ""),
            "customerEmail": invoice.customer.email,
            "amount": _major_units(invoice.amount_due_minor),
            "currency": invoice.currency,
            "accountId": nomba_routing_account_id_for_environment(invoice.environment),
            "orderMetaData": {
                "invoice_id": str(invoice.id),
                "customer_id": str(invoice.customer_id),
                "subscription_id": str(invoice.subscription_id) if invoice.subscription_id else "",
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
