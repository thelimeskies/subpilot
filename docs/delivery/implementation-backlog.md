# Implementation Backlog

This backlog converts the feature specs into buildable Django tickets.

## Sprint 0: Foundation

| ID | Task | Unit | Owner | Estimate | Done When |
|---|---|---|---|---:|---|
| FND-01 | Create Django project structure | U01 | Backend | M | `config`, `apps`, settings, URLs, Celery app exist |
| FND-02 | Configure PostgreSQL and Redis | U01 | Backend | S | Local settings connect and tests run |
| FND-03 | Add DRF, django-filter, drf-spectacular | U01 | Backend | S | API schema endpoint works |
| FND-04 | Add base model mixins | U01 | Backend | S | Timestamp, merchant, environment mixins exist |
| FND-05 | Seed demo merchant and users | U01 | Backend | S | Demo data loads in one command |

## Sprint 1: Plans and Customers

| ID | Task | Unit | Owner | Estimate | Done When |
|---|---|---|---|---:|---|
| CAT-01 | Product and plan models | U02 | Backend | M | Migrations and tests pass |
| CAT-02 | Price version immutability | U02 | Backend | M | Active plan price edits create versions |
| CAT-03 | Plan builder API | U02 | Backend | M | CRUD and activate/archive endpoints work |
| CAT-04 | Plan builder UI | U02 | Frontend | L | Creates Pro Monthly demo plan |
| CUS-01 | Customer model and API | U03 | Backend | S | Customer CRUD works |
| CUS-02 | Customer detail UI | U03 | Frontend | M | Shows profile and timeline shell |

## Sprint 2: Subscribe and Activate

| ID | Task | Unit | Owner | Estimate | Done When |
|---|---|---|---|---:|---|
| SUB-01 | Subscription models | U04 | Backend | M | Models and migrations pass |
| SUB-02 | State machine service | U05 | Backend | L | Valid and invalid transitions tested |
| INV-01 | Invoice and line item models | U06 | Backend | M | Invoice totals use minor units |
| PAY-01 | Nomba adapter interface | U07 | Backend | M | Mock and sandbox classes share interface |
| PAY-02 | Create checkout order flow | U07 | Backend | M | Subscription returns checkout URL |
| EVT-01 | Event store model | U11 | Backend | M | Events append after state changes |
| UI-01 | Subscription detail UI | U05 | Frontend | L | Timeline and actions visible |

## Sprint 3: Dunning and Recovery

| ID | Task | Unit | Owner | Estimate | Done When |
|---|---|---|---|---:|---|
| DUN-01 | Dunning policy model | U08 | Backend | M | Retry offsets and final action saved |
| DUN-02 | Failed payment classifier | U09 | Backend | M | Recoverable vs hard failures tested |
| DUN-03 | Retry scheduler Celery task | U09 | Backend | L | Next retry computed and queued |
| DUN-04 | Recovery queue UI | U09 | Frontend | L | Shows failed invoice priorities |
| POR-01 | Portal session model | U10 | Backend | M | Signed expiring sessions work |
| POR-02 | Customer portal UI | U10 | Frontend | L | Past-due recovery flow works |

## Sprint 4: Developer and Demo Polish

| ID | Task | Unit | Owner | Estimate | Done When |
|---|---|---|---|---:|---|
| WH-01 | Webhook endpoint model/API | U11 | Backend | M | Endpoint CRUD works |
| WH-02 | Signed delivery worker | U11 | Backend | L | HMAC delivery and retry tested |
| WH-03 | Developer console UI | U11 | Frontend | M | Event log and replay visible |
| ANA-01 | Dashboard metrics | U13 | Backend | M | MRR, active, past_due, recovery rate available |
| ANA-02 | Dashboard UI | U13 | Frontend | M | Demo starts with metrics |
| QA-01 | Demo reset command | All | Backend | S | One command resets demo data |
| QA-02 | End-to-end demo script | All | Product | S | Script matches product story |

## Sprint 5: SDK and Package Layer

| ID | Task | Unit | Owner | Estimate | Done When |
|---|---|---|---|---:|---|
| SDK-01 | Python SDK HTTP client | SDK | Backend | M | Auth, idempotency, retries, typed errors work |
| SDK-02 | Python SDK resources | SDK | Backend | M | Plans, customers, subscriptions, invoices, payment methods, events supported |
| SDK-03 | Django package webhook view | SDK | Backend | M | Merchant Django app can verify SubPilot webhook |
| SDK-04 | Django package billing helpers | SDK | Backend | M | Merchant app can create subscription and portal session |
| SDK-05 | Tokenized-card session helper | SDK | Backend | S | SDK can create recover-invoice payment method session |
| SDK-06 | Node SDK skeleton | SDK | Backend | L | TypeScript client supports core resources |
| SDK-07 | SDK docs and examples | SDK | Product | M | Examples cover create subscription, update card, retry invoice, webhooks |
