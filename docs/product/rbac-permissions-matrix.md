# RBAC Permissions Matrix

SubPilot serves multiple user types and sub-user types. This matrix defines what each role can view and change.

## Roles

| Role | Description |
|---|---|
| Owner | Full merchant workspace control |
| Billing Admin | Manages plans, subscriptions, invoices, dunning |
| Developer | Manages API keys, webhooks, event logs, integration tools |
| Finance | Reviews invoices, exports, reconciliation, refunds/credits if enabled |
| Support | Helps customers with billing state and safe recovery actions |
| Analyst | Read-only reporting access |
| Platform Operator | SubPilot internal support/risk role with audited escalation |

## Permissions

| Capability | Owner | Billing Admin | Developer | Finance | Support | Analyst | Platform Operator |
|---|---:|---:|---:|---:|---:|---:|---:|
| View dashboard | Yes | Yes | Limited | Yes | Limited | Yes | Scoped |
| Create/edit products | Yes | Yes | No | No | No | No | No |
| Create/edit plans | Yes | Yes | No | No | No | No | No |
| Activate/archive plans | Yes | Yes | No | No | No | No | No |
| View customers | Yes | Yes | No | Yes | Yes | Yes | Scoped |
| Create customer | Yes | Yes | API only | No | Yes | No | No |
| Create subscription | Yes | Yes | API only | No | Limited | No | No |
| Pause/resume subscription | Yes | Yes | No | No | Limited | No | Escalated |
| Cancel subscription | Yes | Yes | No | No | Limited | No | Escalated |
| Preview proration | Yes | Yes | No | Yes | Yes | Yes | Scoped |
| Retry invoice | Yes | Yes | No | Yes | Limited | No | Escalated |
| Void invoice | Yes | Yes | No | Yes | No | No | Escalated |
| Mark uncollectible | Yes | Yes | No | Yes | No | No | Escalated |
| View payment methods | Masked | Masked | No | Masked | Masked | No | Masked |
| Create payment method session | Yes | Yes | API only | No | Yes | No | Escalated |
| Manage dunning policies | Yes | Yes | No | No | No | No | No |
| View event logs | Yes | Yes | Yes | Limited | Limited | No | Scoped |
| Replay webhooks | Yes | No | Yes | No | No | No | Escalated |
| Manage webhook endpoints | Yes | No | Yes | No | No | No | No |
| Create/revoke API keys | Yes | No | Yes | No | No | No | No |
| Export invoices | Yes | Yes | No | Yes | No | Yes | Scoped |
| Manage team roles | Yes | No | No | No | No | No | No |
| View audit logs | Yes | Limited | Limited | Limited | Limited | No | Scoped |

## Support-Safe Actions

Support can:

- Resend portal link.
- Add internal note.
- Retry invoice only if policy allows.
- Pause subscription only if granted by owner.
- Explain timeline and failure reason.

Support cannot:

- See token values.
- Create API keys.
- Rotate webhook secrets.
- Edit dunning policy.
- Void invoices.
- Mark invoices uncollectible unless elevated.

## Platform Operator Escalation

Platform operator access must be:

- Time-limited.
- Reason-coded.
- Audit logged.
- Scoped to merchant and environment.
- Read-only by default.

Escalated actions require:

- Ticket/reference.
- Owner or internal approval.
- Audit entry.

## UI Enforcement

The frontend should:

- Hide unavailable actions where appropriate.
- Disable risky actions with explanation when visibility is useful.
- Show role requirement for restricted actions.
- Never reveal sensitive secrets after creation.

The API must:

- Enforce all permissions server-side.
- Return 403 for unauthorized action.
- Avoid leaking whether cross-tenant objects exist.
