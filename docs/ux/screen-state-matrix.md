# Screen State Matrix

This document expands the screen specs beyond happy paths. Each major UI surface should account for loading, empty, error, and edge states before implementation.

## State Categories

| State | Meaning | UI Requirement |
|---|---|---|
| Loading | Data request is in flight | Skeletons, not spinners alone |
| Empty | No records exist yet | Clear explanation and primary next action |
| Ready | Normal populated state | Data, actions, filters, pagination |
| Warning | User attention needed | Status label plus explanation |
| Error | Request or system failed | Actionable message, retry, request ID |
| Restricted | User lacks permission | Explain required role without exposing sensitive data |

## Dashboard Overview

| State | Trigger | UI Behavior |
|---|---|---|
| Loading | Metrics and tables loading | Skeleton metric tiles and table rows |
| Empty first run | No plans or subscriptions | "Create your first recurring plan" CTA |
| Ready | Metrics available | MRR, active subs, revenue at risk, recovery rate, upcoming renewals |
| Warning | Revenue at risk > threshold | Highlight revenue-at-risk tile and link to Recovery Queue |
| Error | Analytics request failed | Show retry and request ID |

## Plan Builder

| State | Trigger | UI Behavior |
|---|---|---|
| Draft | Plan incomplete | Save draft allowed, activate disabled |
| Validation error | Missing price or invalid interval | Inline field errors |
| Active immutable price | Editing active price | Explain price versioning and create new version |
| Ready to activate | Required fields complete | Activate plan CTA enabled |
| Archived | Plan archived | Read-only with clone action |

## Subscription Detail

| State | Trigger | UI Behavior |
|---|---|---|
| Active | Paid current period | Actions: change plan, pause, cancel, send portal |
| Trialing | Trial active | Show trial end and payment method readiness |
| Past due | Renewal failed | Show dunning state, recovery link, retry action |
| Paused | Admin/customer paused | Show pause reason and resume requirements |
| Canceling | Cancel at period end | Show access end date and undo option if policy allows |
| Canceled | Terminal | Disable lifecycle actions except resubscribe |
| Error | Timeline failed | Show retry without hiding summary panel |

## Recovery Queue

| State | Trigger | UI Behavior |
|---|---|---|
| Empty | No failed invoices | "No failed payments need attention" plus recently recovered invoices |
| Ready | Failed invoices exist | Prioritized table and selected invoice panel |
| Hard failure | Token expired/revoked | Show "requires new card" and portal link CTA |
| Retry due | `next_retry_at <= now` | Highlight row and enable retry now |
| Processor outage | Nomba unavailable | Pause retries and show incident banner |
| Exhausted | Attempts exhausted | Show final action and audit trail |

## Customer Portal

| State | Trigger | UI Behavior |
|---|---|---|
| Active | Subscription active | Plan, renewal, payment method, receipts |
| Past due | Open failed invoice | Prominent update card/pay invoice CTA |
| Trialing | Trial active | Trial end and payment method readiness |
| Canceled | Subscription ended | Receipt history and resubscribe if allowed |
| Expired session | Portal token expired | Ask customer to request a new secure link |
| Payment update failed | Nomba token update failed | Explain failure and retry |

## Developer Console

| State | Trigger | UI Behavior |
|---|---|---|
| No API keys | First run | Create test key CTA |
| No webhooks | No endpoints | Add endpoint CTA and docs link |
| Events ready | Events exist | Event list, payload viewer, delivery status |
| Delivery failed | HTTP failure | Show status code, response body, retry time |
| Secret rotated | Webhook secret rotated | Show only once, audit action |

## Invoice Detail

| State | Trigger | UI Behavior |
|---|---|---|
| Draft | Invoice not finalized | Editable line items |
| Open | Payment due | Retry, send payment link, void |
| Paid | Payment succeeded | Immutable invoice, receipt download |
| Uncollectible | Dunning exhausted | Show final action and late payment policy |
| Refunded | Refund exists | Show credit/refund records |

## Settings and Policies

| State | Trigger | UI Behavior |
|---|---|---|
| Test configured | Sandbox credentials set | Show connected status |
| Live incomplete | Live credentials missing | Checklist and disabled live mode |
| Secret created | API/webhook secret generated | Show secret once |
| Permission denied | Non-owner role | Read-only with role explanation |
