// Seed data for the SubPilot merchant dashboard. Represents one merchant
// workspace ("Acme Learning Hub") and everything it operates on.
//
// All values are demo-only — no real customer or payment data.

export interface MerchantOrg {
  id: string;
  legalName: string;
  tradingName: string;
  country: string;
  timezone: string;
  currency: "NGN" | "USD" | "GBP" | "KES";
  brandColor: string;
  portalSubdomain: string;
  taxId: string;
  statementDescriptor: string;
  payoutBank: string;
  payoutAccount: string;
  settlementFrequency: "daily" | "weekly" | "monthly";
  createdAt: string;
}

export const org: MerchantOrg = {
  id: "org_acme",
  legalName: "Acme Learning Hub Ltd",
  tradingName: "Acme Learning Hub",
  country: "Nigeria",
  timezone: "Africa/Lagos",
  currency: "NGN",
  brandColor: "#056058",
  portalSubdomain: "acme",
  taxId: "TIN-9876123",
  statementDescriptor: "ACMELEARN",
  payoutBank: "GTBank",
  payoutAccount: "0123456789",
  settlementFrequency: "daily",
  createdAt: "2025-04-12"
};

export type PlanInterval = "monthly" | "yearly" | "weekly";
export type PlanStatus = "active" | "draft" | "archived";

export interface Plan {
  id: string;
  name: string;
  code: string;
  amount: number;
  currency: MerchantOrg["currency"];
  interval: PlanInterval;
  trialDays: number;
  description: string;
  status: PlanStatus;
  subscribers: number;
  createdAt: string;
}

export const plans: Plan[] = [
  {
    id: "plan_starter",
    name: "Starter",
    code: "STARTER-M",
    amount: 9500,
    currency: "NGN",
    interval: "monthly",
    trialDays: 14,
    description: "5 seats · email support · basic analytics",
    status: "active",
    subscribers: 184,
    createdAt: "2025-04-15"
  },
  {
    id: "plan_growth",
    name: "Growth",
    code: "GROWTH-M",
    amount: 28500,
    currency: "NGN",
    interval: "monthly",
    trialDays: 14,
    description: "25 seats · priority support · API access",
    status: "active",
    subscribers: 612,
    createdAt: "2025-04-15"
  },
  {
    id: "plan_scale",
    name: "Scale",
    code: "SCALE-M",
    amount: 89000,
    currency: "NGN",
    interval: "monthly",
    trialDays: 7,
    description: "Unlimited seats · SSO · custom dunning rules",
    status: "active",
    subscribers: 274,
    createdAt: "2025-04-15"
  },
  {
    id: "plan_scale_annual",
    name: "Scale (Annual)",
    code: "SCALE-Y",
    amount: 890000,
    currency: "NGN",
    interval: "yearly",
    trialDays: 0,
    description: "Two months free · annual billing · dedicated CSM",
    status: "active",
    subscribers: 96,
    createdAt: "2025-08-02"
  },
  {
    id: "plan_archive",
    name: "Legacy Pro",
    code: "PRO-LEGACY",
    amount: 19500,
    currency: "NGN",
    interval: "monthly",
    trialDays: 0,
    description: "Grandfathered plan — closed to new signups.",
    status: "archived",
    subscribers: 38,
    createdAt: "2024-11-01"
  }
];

export type CustomerStatus = "active" | "delinquent" | "churned" | "blocked";

export interface PaymentMethod {
  id: string;
  brand: "Visa" | "Mastercard" | "Verve" | "Amex";
  last4: string;
  expiry: string;
  isDefault: boolean;
}

export interface Customer {
  id: string;
  name: string;
  email: string;
  phone: string;
  country: string;
  status: CustomerStatus;
  mrr: number;
  defaultMethodId: string | null;
  paymentMethods: PaymentMethod[];
  createdAt: string;
  lastPaymentAt: string;
  notes: string;
}

const FIRST_NAMES = [
  "Ada", "Tunde", "Imani", "Kemi", "Zainab", "Chinedu", "Ifeoma", "Ola",
  "Ngozi", "Kola", "Sade", "Bayo", "Hauwa", "Femi", "Yemi", "Tobi",
  "Amaka", "Bisi", "Dapo", "Funmi", "Gbenga", "Halima", "Idris", "Jude",
  "Lola", "Musa"
];
const LAST_NAMES = [
  "Okafor", "Martins", "Bello", "Lawal", "Musa", "Adesanya", "Eze",
  "Olawale", "Bakare", "Idowu", "Akinwale", "Onuoha", "Akande", "Adeyemi",
  "Williams", "Obi", "Adebayo", "Salami", "Adeleke", "Etim", "Okeke",
  "Ojo", "Anyanwu", "Yusuf", "Oluwole", "Ojediran"
];
const STATUSES: CustomerStatus[] = ["active", "active", "active", "active", "delinquent", "active", "churned", "active", "blocked"];
const COUNTRIES = ["Nigeria", "Ghana", "Kenya", "South Africa"];
const CARD_BRANDS: PaymentMethod["brand"][] = ["Visa", "Mastercard", "Verve", "Mastercard", "Visa", "Amex"];

function pad(n: number) {
  return n < 10 ? `0${n}` : `${n}`;
}

function deterministicLast4(seed: number) {
  return ((seed * 9301 + 49297) % 10000).toString().padStart(4, "0");
}

function generateCustomers(): Customer[] {
  const out: Customer[] = [];
  for (let i = 0; i < 28; i += 1) {
    const first = FIRST_NAMES[i % FIRST_NAMES.length];
    const last = LAST_NAMES[(i * 3) % LAST_NAMES.length];
    const status = STATUSES[i % STATUSES.length];
    const id = `cus_${(0x10000 + i).toString(16).slice(-4)}`;
    const country = COUNTRIES[i % COUNTRIES.length];
    const monthOfPayment = ((i * 7) % 11) + 1;
    const dayOfPayment = ((i * 13) % 27) + 1;
    const baseMrr = status === "churned" ? 0 : status === "blocked" ? 0 : [9500, 28500, 28500, 89000][i % 4];
    const methods: PaymentMethod[] =
      status === "churned"
        ? []
        : [
            {
              id: `pm_${id}_a`,
              brand: CARD_BRANDS[i % CARD_BRANDS.length],
              last4: deterministicLast4(i + 11),
              expiry: `${pad(((i * 5) % 12) + 1)}/2${(7 + (i % 3))}`,
              isDefault: true
            },
            ...(i % 4 === 0
              ? [
                  {
                    id: `pm_${id}_b`,
                    brand: CARD_BRANDS[(i + 2) % CARD_BRANDS.length],
                    last4: deterministicLast4(i + 47),
                    expiry: `${pad(((i * 3) % 12) + 1)}/2${(8 + (i % 2))}`,
                    isDefault: false
                  } as PaymentMethod
                ]
              : [])
          ];
    out.push({
      id,
      name: `${first} ${last}`,
      email: `${first.toLowerCase()}.${last.toLowerCase()}@example.${country === "Nigeria" ? "ng" : "co"}`,
      phone: `+234 80${pad((i * 17) % 100)} ${pad((i * 31) % 100)}${pad((i * 13) % 100)}`,
      country,
      status,
      mrr: baseMrr,
      defaultMethodId: methods.find((m) => m.isDefault)?.id ?? null,
      paymentMethods: methods,
      createdAt: `2026-${pad(monthOfPayment)}-${pad(dayOfPayment)}`,
      lastPaymentAt: `2026-09-${pad(((i * 7) % 27) + 1)}T${pad((i * 3) % 24)}:${pad((i * 11) % 60)}:00Z`,
      notes:
        i % 5 === 0
          ? "VIP — always reach out before retrying failed cards."
          : i % 7 === 0
          ? "Requested annual billing — quote when up for renewal."
          : ""
    });
  }
  return out;
}

export const customers: Customer[] = generateCustomers();

export type SubscriptionStatus =
  | "active"
  | "trialing"
  | "past_due"
  | "paused"
  | "cancelled"
  | "incomplete";

export interface Subscription {
  id: string;
  customerId: string;
  planId: string;
  status: SubscriptionStatus;
  startedAt: string;
  currentPeriodStart: string;
  currentPeriodEnd: string;
  cancelAt: string | null;
  trialEnd: string | null;
  amount: number;
  interval: PlanInterval;
  paymentMethodId: string | null;
  notes: string;
}

const SUB_STATUSES: SubscriptionStatus[] = [
  "active", "active", "active", "active", "active", "active",
  "trialing", "trialing", "past_due", "past_due", "paused",
  "cancelled", "active", "active", "incomplete"
];

function generateSubscriptions(): Subscription[] {
  const out: Subscription[] = [];
  for (let i = 0; i < 34; i += 1) {
    const customer = customers[i % customers.length];
    if (customer.status === "blocked") continue;
    const plan = plans[i % 4]; // skip the archived plan for new subs
    const status = customer.status === "churned" ? "cancelled" : SUB_STATUSES[i % SUB_STATUSES.length];
    const startMonth = ((i * 5) % 11) + 1;
    const startDay = ((i * 11) % 27) + 1;
    out.push({
      id: `sub_${(0x20000 + i).toString(16).slice(-4)}`,
      customerId: customer.id,
      planId: plan.id,
      status,
      startedAt: `2026-${pad(startMonth)}-${pad(startDay)}`,
      currentPeriodStart: `2026-09-${pad(((i * 3) % 27) + 1)}`,
      currentPeriodEnd: `2026-10-${pad(((i * 3) % 27) + 1)}`,
      cancelAt: status === "cancelled" ? `2026-10-${pad(((i * 3) % 27) + 1)}` : null,
      trialEnd: status === "trialing" ? `2026-10-${pad(((i * 7) % 14) + 7)}` : null,
      amount: plan.amount,
      interval: plan.interval,
      paymentMethodId: customer.defaultMethodId,
      notes: i % 9 === 0 ? "Switched from Growth → Scale on prorated upgrade." : ""
    });
  }
  return out;
}

export const subscriptions: Subscription[] = generateSubscriptions();

export type InvoiceStatus = "draft" | "open" | "paid" | "past_due" | "void" | "uncollectible";

export interface InvoiceLineItem {
  description: string;
  quantity: number;
  unitAmount: number;
}

export interface Invoice {
  id: string;
  number: string;
  customerId: string;
  subscriptionId: string | null;
  status: InvoiceStatus;
  subtotal?: number;
  tax?: number;
  total?: number;
  amountDue: number;
  amountPaid: number;
  currency: MerchantOrg["currency"];
  issuedAt: string;
  dueAt: string;
  paidAt: string | null;
  lineItems: InvoiceLineItem[];
  attempts: number;
  notes: string;
}

const INVOICE_STATUSES: InvoiceStatus[] = [
  "paid", "paid", "paid", "paid", "open", "open", "past_due",
  "past_due", "draft", "void", "paid", "paid", "uncollectible", "paid"
];

function generateInvoices(): Invoice[] {
  const out: Invoice[] = [];
  for (let i = 0; i < 38; i += 1) {
    const sub = subscriptions[i % subscriptions.length];
    const customer = customers.find((c) => c.id === sub.customerId);
    if (!customer) continue;
    const status = INVOICE_STATUSES[i % INVOICE_STATUSES.length];
    const month = ((i * 3) % 9) + 1;
    const day = ((i * 7) % 27) + 1;
    out.push({
      id: `in_${(0x30000 + i).toString(16).slice(-4)}`,
      number: `INV-2026-${pad(((i * 17) % 9000) + 1000)}`,
      customerId: customer.id,
      subscriptionId: sub.id,
      status,
      amountDue: sub.amount,
      amountPaid: status === "paid" ? sub.amount : status === "past_due" ? Math.floor(sub.amount / 2) : 0,
      currency: "NGN",
      issuedAt: `2026-${pad(month)}-${pad(day)}`,
      dueAt: `2026-${pad(month)}-${pad(Math.min(day + 14, 28))}`,
      paidAt: status === "paid" ? `2026-${pad(month)}-${pad(Math.min(day + 1, 28))}` : null,
      lineItems: [
        {
          description: `${plans.find((p) => p.id === sub.planId)?.name ?? "Plan"} — period charge`,
          quantity: 1,
          unitAmount: sub.amount
        }
      ],
      attempts: status === "past_due" ? ((i % 3) + 1) : status === "uncollectible" ? 4 : 1,
      notes: status === "uncollectible" ? "Marked uncollectible — refer to recovery dashboard." : ""
    });
  }
  return out;
}

export const invoices: Invoice[] = generateInvoices();

export type PaymentChannel = "card" | "bank_transfer" | "ussd" | "wallet";
export type PaymentRecordStatus = "captured" | "failed" | "refunded" | "recovered" | "pending";

export interface PaymentRecord {
  id: string;
  invoiceId: string | null;
  customerId: string;
  amount: number;
  currency: MerchantOrg["currency"];
  channel: PaymentChannel;
  status: PaymentRecordStatus;
  cardBrand?: PaymentMethod["brand"];
  last4?: string;
  failureReason?: string;
  occurredAt: string;
  gateway: "primary" | "fallback";
}

const PAY_STATUSES: PaymentRecordStatus[] = [
  "captured", "captured", "captured", "captured", "failed", "failed",
  "refunded", "recovered", "captured", "pending"
];
const CHANNELS: PaymentChannel[] = ["card", "card", "card", "bank_transfer", "ussd", "card", "wallet"];
const FAIL_REASONS = [
  "Insufficient funds",
  "Card declined by issuer",
  "Token expired",
  "Authentication failed",
  "Do not honor"
];

function generatePayments(): PaymentRecord[] {
  const out: PaymentRecord[] = [];
  for (let i = 0; i < 42; i += 1) {
    const invoice = invoices[i % invoices.length];
    const status = PAY_STATUSES[i % PAY_STATUSES.length];
    const channel = CHANNELS[i % CHANNELS.length];
    const customer = customers.find((c) => c.id === invoice.customerId);
    out.push({
      id: `py_${(0x40000 + i).toString(16).slice(-4)}`,
      invoiceId: invoice.id,
      customerId: invoice.customerId,
      amount:
        status === "refunded"
          ? -Math.floor(invoice.amountDue / 2)
          : status === "failed" || status === "pending"
          ? 0
          : invoice.amountDue,
      currency: "NGN",
      channel,
      status,
      cardBrand: channel === "card" ? customer?.paymentMethods[0]?.brand : undefined,
      last4: channel === "card" ? customer?.paymentMethods[0]?.last4 : undefined,
      failureReason: status === "failed" ? FAIL_REASONS[i % FAIL_REASONS.length] : undefined,
      occurredAt: `2026-${pad(((i * 5) % 9) + 1)}-${pad(((i * 11) % 27) + 1)}T${pad((i * 7) % 24)}:${pad((i * 13) % 60)}:${pad((i * 17) % 60)}Z`,
      gateway: i % 5 === 0 ? "fallback" : "primary"
    });
  }
  return out;
}

export const payments: PaymentRecord[] = generatePayments();

export type RecoveryReason =
  | "insufficient_funds"
  | "card_declined"
  | "token_expired"
  | "authentication_failed"
  | "do_not_honor";

export type RecoveryStage = "retry_queue" | "manual_review" | "paused";

export interface RecoveryItem {
  id: string;
  invoiceId: string;
  customerId: string;
  amount: number;
  attempts: number;
  reason: RecoveryReason;
  stage: RecoveryStage;
  nextRetryAt: string | null;
  lastAttemptAt: string;
}

function generateRecoveryItems(): RecoveryItem[] {
  const overdue = invoices.filter((inv) => inv.status === "past_due" || inv.status === "uncollectible");
  return overdue.slice(0, 14).map((inv, i) => ({
    id: `rec_${(0x50000 + i).toString(16).slice(-4)}`,
    invoiceId: inv.id,
    customerId: inv.customerId,
    amount: inv.amountDue - inv.amountPaid,
    attempts: inv.attempts,
    reason: (["insufficient_funds", "card_declined", "token_expired", "authentication_failed", "do_not_honor"] as RecoveryReason[])[i % 5],
    stage: i % 6 === 5 ? "paused" : i % 4 === 3 ? "manual_review" : "retry_queue",
    nextRetryAt:
      i % 6 === 5
        ? null
        : `2026-09-${pad(((i * 3) % 27) + 5)}T${pad((i * 5) % 24)}:00:00Z`,
    lastAttemptAt: `2026-09-${pad(((i * 5) % 27) + 1)}T${pad((i * 7) % 24)}:00:00Z`
  }));
}

export const recoveryItems: RecoveryItem[] = generateRecoveryItems();

// ----- Developer surface -----
export type WebhookEvent =
  | "subscription.created"
  | "subscription.updated"
  | "subscription.cancelled"
  | "invoice.paid"
  | "invoice.payment_failed"
  | "invoice.voided"
  | "payment.captured"
  | "payment.refunded"
  | "customer.created"
  | "customer.updated";

export const ALL_WEBHOOK_EVENTS: WebhookEvent[] = [
  "subscription.created",
  "subscription.updated",
  "subscription.cancelled",
  "invoice.paid",
  "invoice.payment_failed",
  "invoice.voided",
  "payment.captured",
  "payment.refunded",
  "customer.created",
  "customer.updated"
];

export interface WebhookEndpoint {
  id: string;
  url: string;
  events: WebhookEvent[];
  status: "active" | "disabled" | "failing";
  signingVersion: "v1" | "v2";
  createdAt: string;
  lastDeliveryAt: string;
  successRate: number;
}

export const webhookEndpoints: WebhookEndpoint[] = [
  {
    id: "we_billing_prod",
    url: "https://api.acmelearning.co/billing/webhooks",
    events: ["invoice.paid", "invoice.payment_failed", "subscription.updated", "subscription.cancelled"],
    status: "active",
    signingVersion: "v2",
    createdAt: "2025-04-22",
    lastDeliveryAt: "2026-09-12T09:42:11Z",
    successRate: 0.998
  },
  {
    id: "we_crm_sync",
    url: "https://acme.activepieces.io/hooks/customer-sync",
    events: ["customer.created", "customer.updated", "subscription.created"],
    status: "active",
    signingVersion: "v2",
    createdAt: "2025-09-04",
    lastDeliveryAt: "2026-09-12T08:18:42Z",
    successRate: 0.965
  },
  {
    id: "we_finance_legacy",
    url: "https://internal.acmelearning.co/legacy-billing",
    events: ["invoice.paid", "payment.captured"],
    status: "failing",
    signingVersion: "v1",
    createdAt: "2024-11-19",
    lastDeliveryAt: "2026-09-11T22:01:09Z",
    successRate: 0.612
  }
];

export type WebhookDeliveryStatus = "delivered" | "failed" | "pending";

export interface WebhookEventRecord {
  id: string;
  endpointId: string;
  event: WebhookEvent;
  status: WebhookDeliveryStatus;
  attempts: number;
  occurredAt: string;
  payloadPreview: string;
}

function generateWebhookEvents(): WebhookEventRecord[] {
  const out: WebhookEventRecord[] = [];
  for (let i = 0; i < 30; i += 1) {
    const endpoint = webhookEndpoints[i % webhookEndpoints.length];
    const event = endpoint.events[i % endpoint.events.length];
    const status: WebhookDeliveryStatus =
      i % 11 === 0 ? "failed" : i % 9 === 0 ? "pending" : "delivered";
    out.push({
      id: `evt_${(0x60000 + i).toString(16).slice(-4)}`,
      endpointId: endpoint.id,
      event,
      status,
      attempts: status === "failed" ? 4 : 1,
      occurredAt: `2026-09-${pad(((i * 5) % 12) + 1)}T${pad((i * 7) % 24)}:${pad((i * 11) % 60)}:00Z`,
      payloadPreview: `{ "type": "${event}", "data": { ... } }`
    });
  }
  return out;
}

export const webhookEvents: WebhookEventRecord[] = generateWebhookEvents();

export interface ApiKey {
  id: string;
  name: string;
  prefix: string;
  scopes: Array<"read" | "write" | "admin">;
  status: "active" | "revoked";
  createdAt: string;
  lastUsedAt: string;
}

export const apiKeys: ApiKey[] = [
  {
    id: "ak_live_acme",
    name: "Production server",
    prefix: "nse_live_4pq",
    scopes: ["read", "write"],
    status: "active",
    createdAt: "2025-04-22",
    lastUsedAt: "2026-09-12T09:42:11Z"
  },
  {
    id: "ak_live_billing",
    name: "Billing worker",
    prefix: "nse_live_9wk",
    scopes: ["read", "write", "admin"],
    status: "active",
    createdAt: "2025-08-03",
    lastUsedAt: "2026-09-12T08:51:19Z"
  },
  {
    id: "ak_test_dev",
    name: "Local development",
    prefix: "nse_test_2eb",
    scopes: ["read", "write"],
    status: "active",
    createdAt: "2025-04-22",
    lastUsedAt: "2026-09-10T14:11:09Z"
  }
];

export interface TeamMember {
  id: string;
  name: string;
  email: string;
  role: "Owner" | "Admin" | "Finance" | "Support" | "Read-only";
  mfaEnabled: boolean;
  status: "active" | "invited" | "disabled";
  lastSeenAt: string;
}

export const teamMembers: TeamMember[] = [
  {
    id: "tm_owner",
    name: "Ada Okafor",
    email: "owner@acme.test",
    role: "Owner",
    mfaEnabled: true,
    status: "active",
    lastSeenAt: "2026-09-12T09:42:11Z"
  },
  {
    id: "tm_finance",
    name: "Kemi Lawal",
    email: "finance@acme.test",
    role: "Finance",
    mfaEnabled: true,
    status: "active",
    lastSeenAt: "2026-09-12T08:11:54Z"
  },
  {
    id: "tm_support",
    name: "Zainab Musa",
    email: "support@acme.test",
    role: "Support",
    mfaEnabled: false,
    status: "active",
    lastSeenAt: "2026-09-11T22:01:09Z"
  },
  {
    id: "tm_dev",
    name: "Chinedu Bello",
    email: "dev@acme.test",
    role: "Admin",
    mfaEnabled: true,
    status: "active",
    lastSeenAt: "2026-09-10T17:42:00Z"
  },
  {
    id: "tm_invite",
    name: "Tunde Martins",
    email: "tunde@acme.test",
    role: "Read-only",
    mfaEnabled: false,
    status: "invited",
    lastSeenAt: "—"
  }
];

export interface AuditEvent {
  id: string;
  actor: string;
  action: string;
  target: string;
  occurredAt: string;
  ipAddress: string;
}

const AUDIT_TEMPLATES: Array<Pick<AuditEvent, "actor" | "action" | "target">> = [
  { actor: "Ada Okafor", action: "Updated dunning schedule", target: "Settings → Dunning rules" },
  { actor: "Kemi Lawal", action: "Marked invoice paid", target: "INV-2026-1042" },
  { actor: "Zainab Musa", action: "Sent portal link", target: "amaka.eze@example.ng" },
  { actor: "Ada Okafor", action: "Rotated webhook secret", target: "we_billing_prod" },
  { actor: "Chinedu Bello", action: "Generated API key", target: "Billing worker" },
  { actor: "Ada Okafor", action: "Invited teammate", target: "tunde@acme.test" },
  { actor: "Kemi Lawal", action: "Refunded payment", target: "py_40012" },
  { actor: "Ada Okafor", action: "Archived plan", target: "Legacy Pro" },
  { actor: "Zainab Musa", action: "Added customer note", target: "imani.bello@example.ng" },
  { actor: "Ada Okafor", action: "Updated branding", target: "Settings → Branding" }
];

function generateAuditEvents(): AuditEvent[] {
  const out: AuditEvent[] = [];
  for (let i = 0; i < 24; i += 1) {
    const tpl = AUDIT_TEMPLATES[i % AUDIT_TEMPLATES.length];
    out.push({
      id: `aud_${(0x70000 + i).toString(16).slice(-4)}`,
      actor: tpl.actor,
      action: tpl.action,
      target: tpl.target,
      occurredAt: `2026-09-${pad(((i * 3) % 12) + 1)}T${pad((i * 7) % 24)}:${pad((i * 11) % 60)}:00Z`,
      ipAddress: `102.${(i * 17) % 256}.${(i * 31) % 256}.${(i * 13) % 256}`
    });
  }
  return out;
}

export const auditEvents: AuditEvent[] = generateAuditEvents();

// ----- Settings shape (persisted via store) -----
export interface MerchantSettings {
  branding: {
    primaryColor: string;
    logoUrl: string | null;
    portalSubdomain: string;
  };
  payouts: {
    bank: string;
    accountNumber: string;
    settlementFrequency: MerchantOrg["settlementFrequency"];
    descriptor: string;
    paused: boolean;
  };
  planDefaults: {
    trialDays: number;
    proration: "create_proration" | "none";
    currency: MerchantOrg["currency"];
    taxBehavior: "exclusive" | "inclusive";
  };
  dunning: {
    schedule: number[]; // hours between retries
    maxAttempts: number;
    graceDays: number;
    finalAction: "cancel" | "uncollectible";
  };
  dunningTemplates: DunningTemplate[];
  notifications: Record<string, Record<string, boolean>>;
  security: {
    requireMfa: boolean;
    ipAllowlist: string[];
    sessionTimeoutMinutes: number;
  };
  portal: {
    allowCancel: boolean;
    allowPause: boolean;
    allowChangePlan: boolean;
    successUrl: string;
    cancelUrl: string;
  };
}

export interface DunningTemplate {
  id: string;
  label: string;
  body: string;
}

export const defaultDunningTemplates: DunningTemplate[] = [
  { id: "first", label: "First reminder (12h)", body: "Hi {{name}}, your last payment didn't go through. Update your card to keep service active." },
  { id: "second", label: "Second reminder (24h)", body: "Hi {{name}}, second attempt failed. Visit your portal to retry payment." },
  { id: "final", label: "Final notice (72h)", body: "Hi {{name}}, this is the final attempt. Service will pause if payment isn't completed today." }
];

export const defaultSettings: MerchantSettings = {
  branding: {
    primaryColor: org.brandColor,
    logoUrl: null,
    portalSubdomain: org.portalSubdomain
  },
  payouts: {
    bank: org.payoutBank,
    accountNumber: org.payoutAccount,
    settlementFrequency: org.settlementFrequency,
    descriptor: org.statementDescriptor,
    paused: false
  },
  planDefaults: {
    trialDays: 14,
    proration: "create_proration",
    currency: org.currency,
    taxBehavior: "exclusive"
  },
  dunning: {
    schedule: [12, 24, 72],
    maxAttempts: 4,
    graceDays: 3,
    finalAction: "uncollectible"
  },
  dunningTemplates: defaultDunningTemplates,
  notifications: {
    invoice: { email: true, sms: false, slack: true },
    failure: { email: true, sms: true, slack: true },
    cancellation: { email: true, sms: false, slack: false }
  },
  security: {
    requireMfa: true,
    ipAllowlist: [],
    sessionTimeoutMinutes: 60
  },
  portal: {
    allowCancel: true,
    allowPause: true,
    allowChangePlan: true,
    successUrl: "https://acmelearning.co/billing/success",
    cancelUrl: "https://acmelearning.co/billing/cancel"
  }
};
