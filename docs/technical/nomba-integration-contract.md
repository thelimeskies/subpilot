# Nomba Integration Contract

This document defines the boundary between SubPilot and Nomba APIs. SubPilot is not a payment processor. It uses Nomba for checkout, tokenized-card charging, transfers/refund extensions, and payment webhooks.

## Integration Goals

- Keep Nomba-specific logic isolated behind a Django service adapter.
- Support mock, sandbox, and live modes with the same interface.
- Never expose Nomba secrets to downstream product teams.
- Never store raw card data.
- Translate Nomba payment events into SubPilot subscription, invoice, payment, and dunning events.

## Adapter Interface

```python
class NombaPaymentAdapter:
    def create_checkout_order(
        self,
        *,
        merchant,
        environment,
        invoice,
        customer,
        success_url: str,
        cancel_url: str,
        tokenize_card: bool,
        idempotency_key: str,
    ) -> CheckoutOrderResult:
        ...

    def create_payment_method_session(
        self,
        *,
        merchant,
        environment,
        customer,
        purpose: str,
        return_url: str,
        idempotency_key: str,
    ) -> PaymentMethodSessionResult:
        ...

    def charge_tokenized_card(
        self,
        *,
        merchant,
        environment,
        invoice,
        payment_method,
        idempotency_key: str,
    ) -> ChargeResult:
        ...

    def verify_webhook_signature(self, *, headers, raw_body: bytes) -> bool:
        ...

    def parse_webhook_event(self, *, payload: dict) -> ParsedNombaEvent:
        ...
```

## Adapter Implementations

| Adapter | Purpose | Use |
|---|---|---|
| `MockNombaAdapter` | Deterministic demo and tests | Default hackathon mode |
| `SandboxNombaAdapter` | Real Nomba sandbox testing | Integration validation |
| `LiveNombaAdapter` | Production payments | Post-hackathon |

## Checkout Order Creation

Used for:

- Initial subscription payment.
- First invoice payment.
- Card tokenization.

Input from SubPilot:

- Customer name/email/phone.
- Invoice number.
- Amount in minor units.
- Currency.
- Success/cancel URLs.
- Metadata: merchant ID, subscription ID, invoice ID, payment attempt ID.
- `tokenize_card=true` when the plan supports renewals.

Expected result:

- Nomba checkout URL.
- Nomba order reference.
- Expiry time if available.

SubPilot effects:

- Store checkout reference on `PaymentAttempt`.
- Return `checkout_url` to downstream app or customer portal.
- Keep subscription `incomplete` until verified payment success.

## Tokenized-Card Charge

Used for:

- Renewal invoices.
- Manual retry.
- Dunning retry.
- Customer portal overdue payment.

Input from SubPilot:

- Nomba token reference from encrypted `PaymentMethod`.
- Invoice amount and currency.
- Customer reference.
- Idempotency key.
- Metadata: invoice ID, subscription ID, attempt number.

Expected result:

- Processor accepted/succeeded/failed/pending response.
- Processor transaction reference.
- Failure code/message when available.

SubPilot effects:

- Store processor reference.
- Keep attempt `pending` until terminal state is confirmed.
- Start dunning on failure.
- Mark invoice paid on success.

## Payment Method Session

Used for:

- Customer replaces expired card.
- Customer updates default card.
- Past-due customer recovers invoice.

Expected behavior:

- Customer completes a Nomba-hosted card/token flow.
- SubPilot receives payment method/token confirmation through webhook or callback.
- SubPilot stores token reference only.

## Webhook Handling

Inbound Nomba events must:

- Verify signature.
- Deduplicate by provider event ID or transaction reference.
- Map to an existing payment attempt where possible.
- Store raw payload summary.
- Apply state transition in a transaction.
- Append SubPilot events after durable mutation.

Handled event categories:

- Payment success.
- Payment failed.
- Payment reversal.
- Token created/updated if provided by Nomba flow.
- Payout/transfer success or failure for future refund/payout extensions.

## Error Mapping

| Nomba/Processor Condition | SubPilot Failure Type | Action |
|---|---|---|
| Insufficient funds | Recoverable | Schedule retry |
| Temporary issuer decline | Recoverable | Schedule retry |
| Network timeout | Processor unavailable | Retry with backoff |
| Expired card/token | Hard failure | Require new payment method |
| Invalid token | Hard failure | Require new payment method |
| Authentication required | Requires action | Send customer action link |
| Duplicate webhook | Duplicate | Acknowledge, no mutation |

## Idempotency

Every Nomba-facing call must use a stable idempotency key:

- Checkout order: `checkout:{invoice_id}:{attempt_id}`
- Tokenized charge: `charge:{invoice_id}:{attempt_number}`
- Manual retry: `retry:{invoice_id}:{attempt_number}:{actor_id}`
- Payment method session: `pms:{customer_id}:{purpose}:{timestamp_or_uuid}`

## Observability

Log fields:

- `merchant_id`
- `environment`
- `invoice_id`
- `payment_attempt_id`
- `nomba_reference`
- `adapter_mode`
- `request_id`
- `failure_code`

Metrics:

- Nomba checkout creation success/failure.
- Tokenized charge success/failure.
- Webhook verification failures.
- Duplicate webhook count.
- Nomba API latency.

## Verified Nomba API Coverage

All authenticated requests use `Authorization: Bearer <access_token>` and the parent business `accountId` header. Endpoints with `{subAccountId}` are scoped through the path parameter, not by replacing the parent `accountId` header.

| Capability | Nomba endpoint | Backend client method |
|---|---|---|
| Issue token | `POST /v1/auth/token/issue` | `issue_token()` |
| Dedicated virtual account | `POST /v1/accounts/virtual/{subAccountId}` | `create_virtual_account(..., sub_account_id=...)` |
| List/filter virtual accounts | `POST /v1/accounts/virtual/list` | `filter_virtual_accounts()` |
| Fetch virtual account | `GET /v1/accounts/virtual/{identifier}` | `fetch_virtual_account()` |
| Expire virtual account | `DELETE /v1/accounts/virtual/{identifier}` | `expire_virtual_account()` |
| Sub-account balance | `GET /v1/accounts/{subAccountId}/balance` | `fetch_sub_account_balance()` |
| Reconcile account transactions | `GET /v1/transactions/accounts/{subAccountId}` | `fetch_account_transactions(sub_account_id=...)` |
| Filter account transactions | `POST /v1/transactions/accounts/{subAccountId}` | `filter_account_transactions(..., sub_account_id=...)` |
| Requery transaction | `GET /v1/transactions/requery/{sessionId}` | `requery_transaction()` |
| Create hosted checkout | `POST /v1/checkout/order` | `create_checkout_order()` |
| Fetch checkout order | `GET /v1/checkout/order/{orderReference}` | `get_checkout_order()` |
| Custom card detail step | `POST /v1/checkout/checkout-card-detail` | `submit_card_details()` |
| Custom card OTP step | `POST /v1/checkout/checkout-card-otp` | `submit_card_otp()` |
| Checkout pay-by-transfer account | `GET /v1/checkout/get-checkout-kta/{orderReference}` | `get_checkout_kta()` |
| Checkout refund | `POST /v1/checkout/refund` | `refund_checkout_transaction()` |
| Charge tokenized card | `POST /v1/checkout/tokenized-card-payment` | `charge_tokenized_card()` |
| List tokenized cards | `GET /v1/checkout/tokenized-card-data` | `list_tokenized_cards()` |
| Create direct-debit mandate | `POST /v1/direct-debits` | `create_direct_debit_mandate()` |
| Debit mandate | `POST /v1/direct-debits/debit-mandate` | `debit_direct_debit_mandate()` |
| Fetch mandate | `GET /v1/direct-debits/{mandateId}` | `get_direct_debit_mandate()` |
| Bank transfer settlement | `POST /v2/transfers/bank/{subAccountId}` | `bank_transfer(..., sub_account_id=...)` |
| Bank account lookup | `POST /v1/transfers/bank/lookup` | `lookup_bank_account()` |
| Bank list | `GET /v1/transfers/banks` | `fetch_banks()` |
| Airtime vending | `POST /v1/bill/topup/{subAccountId}` | `vend_airtime(..., sub_account_id=...)` |
| Data vending | `POST /v1/bill/data/{subAccountId}` | `vend_data(..., sub_account_id=...)` |
| Electricity vending | `POST /v1/bill/electricity/{subAccountId}` | `vend_electricity(..., sub_account_id=...)` |
| Cable TV vending | `POST /v1/bill/cabletv/{subAccountId}` | `vend_cabletv(..., sub_account_id=...)` |
| Global payout exchange rates | `GET /v1/global-payout/exchange-rates` | `global_payout_exchange_rates()` |
| Global payout money conversion | `POST /v1/global-payout/money/convert` | `global_payout_convert_money()` |
| Global payout transfer auth | `POST /v1/global-payout/transfer/authorize` | `global_payout_authorize_transfer()` |
| Wallet transfer | `POST /v2/transfers/wallet/{subAccountId}` | `wallet_transfer(..., sub_account_id=...)` |
| Terminal payment request | `POST /v1/terminals/payment-request/{terminalId}` | `terminal_payment_request()` |

Regression coverage: `backend/apps/payments/tests/test_nomba_client.py::test_endpoint_wrappers_match_official_paths` asserts the exact method, URL, and parent `accountId` header for this matrix.

## Demo Mode Requirements

Mock adapter scenarios:

- `success`: checkout succeeds and token is created.
- `insufficient_funds`: tokenized charge fails recoverably.
- `expired_card`: hard failure requiring new card.
- `processor_timeout`: pending then retry.
- `recovered`: retry succeeds after payment method update.
