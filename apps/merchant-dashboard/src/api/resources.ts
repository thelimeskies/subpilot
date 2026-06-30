import { api } from "./client";
import { mapApiKey } from "./apiKeys";
import { mapTeamMember } from "./team";
import { loadWorkspaceSettings } from "./settings";
import type {
  ApiKey,
  AuditEvent,
  Customer,
  Invoice,
  InvoiceStatus,
  MerchantOrg,
  PaymentChannel,
  PaymentMethod,
  PaymentRecord,
  PaymentRecordStatus,
  Plan,
  PlanInterval,
  PlanStatus,
  RecoveryItem,
  RecoveryReason,
  RecoveryStage,
  Subscription,
  SubscriptionStatus,
  TeamMember,
  MerchantSettings,
  WebhookEndpoint,
  WebhookEvent,
  WebhookEventRecord
} from "../data/seed";
import { defaultSettings, org as seedOrg } from "../data/seed";

type ListResponse<T> = T[] | { results?: T[] };

interface BackendPlan {
  id: string;
  product_id?: string;
  product_name?: string;
  name: string;
  description?: string | null;
  status?: string;
  trial_days?: number | null;
  metadata?: Record<string, unknown> | null;
  features?: unknown;
  active_price?: {
    amount_minor?: number | null;
    currency?: string | null;
    interval_unit?: string | null;
    interval_count?: number | null;
  } | null;
  created_at?: string | null;
}

interface BackendCustomer {
  id: string;
  external_id?: string | null;
  email: string;
  name?: string | null;
  phone?: string | null;
  status?: string | null;
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
}

interface BackendSubscriptionItem {
  amount_minor?: number | null;
  currency?: string | null;
  interval_unit?: string | null;
  interval_count?: number | null;
  quantity?: number | null;
  status?: string | null;
}

interface BackendSubscription {
  id: string;
  customer_id: string;
  plan_id: string;
  plan_name?: string | null;
  default_payment_method_id?: string | null;
  status?: string | null;
  current_period_start?: string | null;
  current_period_end?: string | null;
  trial_end?: string | null;
  cancel_at_period_end?: boolean | null;
  canceled_at?: string | null;
  items?: BackendSubscriptionItem[];
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
}

interface BackendInvoiceLineItem {
  description?: string | null;
  quantity?: number | null;
  amount_minor?: number | null;
  unit_amount_minor?: number | null;
}

interface BackendInvoice {
  id: string;
  number?: string | null;
  customer_id: string;
  subscription_id?: string | null;
  status?: string | null;
  subtotal_minor?: number | null;
  tax_minor?: number | null;
  total_minor?: number | null;
  amount_due_minor?: number | null;
  currency?: string | null;
  due_at?: string | null;
  paid_at?: string | null;
  hosted_payment_url?: string | null;
  line_items?: BackendInvoiceLineItem[];
  metadata?: Record<string, unknown> | null;
  created_at?: string | null;
}

interface BackendPaymentAttempt {
  id: string;
  invoice: string | null;
  payment_method?: string | null;
  attempt_number?: number | null;
  status?: string | null;
  amount_minor?: number | null;
  currency?: string | null;
  failure_code?: string | null;
  failure_message?: string | null;
  failure_category?: string | null;
  refunded_at?: string | null;
  refunded_amount_minor?: number | null;
  refund_reason?: string | null;
  next_retry_at?: string | null;
  created_at?: string | null;
}

interface BackendDunningRun {
  id: string;
  invoice: string;
  subscription?: string | null;
  status?: string | null;
  attempt_count?: number | null;
  started_at?: string | null;
  next_retry_at?: string | null;
  updated_at?: string | null;
}

interface BackendPaymentMethod {
  id: string;
  customer: string;
  brand?: string | null;
  last4?: string | null;
  exp_month?: number | null;
  exp_year?: number | null;
  is_default?: boolean | null;
}

interface BackendWebhookEndpoint {
  id: string;
  url: string;
  enabled?: boolean | null;
  event_filters?: string[] | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface BackendEvent {
  id: string;
  event_type?: string | null;
  payload?: Record<string, unknown> | null;
  occurred_at?: string | null;
  created_at?: string | null;
}

interface BackendApiKey {
  id: string;
  name: string;
  prefix: string;
  environment?: string | null;
  scopes?: string[] | null;
  status?: string | null;
  last_used_at?: string | null;
  created_at?: string | null;
}

interface BackendTeamMember {
  id: string;
  name: string;
  email: string;
  role: string;
  mfa_enabled?: boolean | null;
  status?: string | null;
  last_seen_at?: string | null;
}

interface BackendAuditLog {
  id: string;
  actor_label?: string | null;
  actor_role?: string | null;
  action?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  metadata?: Record<string, unknown> | null;
  ip_address?: string | null;
  occurred_at?: string | null;
}

export interface MerchantResources {
  org: MerchantOrg;
  settings: MerchantSettings;
  plans: Plan[];
  customers: Customer[];
  subscriptions: Subscription[];
  invoices: Invoice[];
  payments: PaymentRecord[];
  recoveryItems: RecoveryItem[];
  webhookEndpoints: WebhookEndpoint[];
  webhookEvents: WebhookEventRecord[];
  apiKeys: ApiKey[];
  teamMembers: TeamMember[];
  auditEvents: AuditEvent[];
}

export type MerchantResourcePatch = Partial<MerchantResources>;

type ResourceKind =
  | "settings"
  | "plans"
  | "customers"
  | "subscriptions"
  | "invoices"
  | "paymentAttempts"
  | "dunningRuns"
  | "paymentMethods"
  | "webhookEndpoints"
  | "webhookEvents"
  | "apiKeys"
  | "teamMembers"
  | "auditLogs";

function asList<T>(body: ListResponse<T>): T[] {
  return Array.isArray(body) ? body : body.results ?? [];
}

async function readList<T>(path: string): Promise<T[]> {
  try {
    return asList(await api.get<ListResponse<T>>(path));
  } catch (err) {
    console.warn(`Could not load ${path}`, err);
    return [];
  }
}

function money(minor: number | null | undefined): number {
  return Math.round((minor ?? 0) / 100);
}

function currency(value: string | null | undefined): MerchantOrg["currency"] {
  const normalized = (value ?? "NGN").toUpperCase();
  return normalized === "USD" || normalized === "GBP" || normalized === "KES" ? normalized : "NGN";
}

function isoDate(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : new Date().toISOString().slice(0, 10);
}

function interval(value: string | null | undefined): PlanInterval {
  if (value === "year" || value === "yearly") return "yearly";
  if (value === "week" || value === "weekly") return "weekly";
  return "monthly";
}

function planStatus(value: string | null | undefined): PlanStatus {
  if (value === "active" || value === "draft" || value === "archived") return value;
  if (value === "inactive") return "archived";
  return "draft";
}

function subscriptionStatus(value: string | null | undefined): SubscriptionStatus {
  if (
    value === "active" ||
    value === "trialing" ||
    value === "past_due" ||
    value === "paused" ||
    value === "cancelled" ||
    value === "incomplete"
  ) {
    return value;
  }
  if (value === "canceled") return "cancelled";
  return "active";
}

function invoiceStatus(value: string | null | undefined): InvoiceStatus {
  if (
    value === "draft" ||
    value === "open" ||
    value === "paid" ||
    value === "past_due" ||
    value === "void" ||
    value === "uncollectible"
  ) {
    return value;
  }
  if (value === "voided") return "void";
  return "open";
}

function customerStatus(value: string | null | undefined): Customer["status"] {
  if (value === "active" || value === "delinquent" || value === "churned" || value === "blocked") return value;
  if (value === "archived") return "blocked";
  if (value === "inactive") return "churned";
  return "active";
}

function paymentMethodBrand(value: string | null | undefined): PaymentMethod["brand"] {
  if (value === "Mastercard" || value === "Verve" || value === "Amex") return value;
  return "Visa";
}

function paymentStatus(value: string | null | undefined): PaymentRecordStatus {
  if (value === "succeeded" || value === "captured" || value === "paid") return "captured";
  if (value === "recovered") return "recovered";
  if (value === "refunded") return "refunded";
  if (value === "failed") return "failed";
  return "pending";
}

function reason(value: string | null | undefined): RecoveryReason {
  const normalized = (value ?? "").toLowerCase();
  if (normalized.includes("fund")) return "insufficient_funds";
  if (normalized.includes("token")) return "token_expired";
  if (normalized.includes("auth")) return "authentication_failed";
  if (normalized.includes("honor")) return "do_not_honor";
  return "card_declined";
}

function codeForPlan(plan: BackendPlan): string {
  const code = plan.metadata?.code;
  if (typeof code === "string" && code.trim()) return code.trim().toUpperCase();
  const slug = plan.name
    .toUpperCase()
    .replace(/[^A-Z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 18);
  return slug || `PLAN-${plan.id.slice(0, 6).toUpperCase()}`;
}

function mapWebhookEvent(value: string | null | undefined): WebhookEvent {
  if (value === "invoice.paid" || value === "invoice.payment_succeeded") return "invoice.paid";
  if (value === "invoice.payment_failed") return "invoice.payment_failed";
  if (value === "invoice.voided" || value === "invoice.void") return "invoice.voided";
  if (value === "subscription.created") return "subscription.created";
  if (value === "subscription.updated") return "subscription.updated";
  if (value === "subscription.cancelled" || value === "subscription.canceled") return "subscription.cancelled";
  if (value === "payment.captured" || value === "payment.succeeded") return "payment.captured";
  if (value === "payment.refunded") return "payment.refunded";
  if (value === "customer.created") return "customer.created";
  return "customer.updated";
}

function expandWebhookFilters(filters: string[] | null | undefined): WebhookEvent[] {
  const events = new Set<WebhookEvent>();
  for (const filter of filters ?? []) {
    if (filter === "invoice.*") {
      events.add("invoice.paid").add("invoice.payment_failed").add("invoice.voided");
    } else if (filter === "subscription.*") {
      events.add("subscription.created").add("subscription.updated").add("subscription.cancelled");
    } else if (filter === "payment.*") {
      events.add("payment.captured").add("payment.refunded");
    } else if (filter === "customer.*") {
      events.add("customer.created").add("customer.updated");
    } else {
      events.add(mapWebhookEvent(filter));
    }
  }
  return [...events];
}

function byCount<T extends string>(items: readonly T[]): Map<T, number> {
  const counts = new Map<T, number>();
  for (const item of items) counts.set(item, (counts.get(item) ?? 0) + 1);
  return counts;
}

function latestPaidInvoiceDate(invoices: readonly Invoice[], customerId: string): string {
  const paid = invoices
    .filter((invoice) => invoice.customerId === customerId && invoice.paidAt)
    .sort((a, b) => (a.paidAt! < b.paidAt! ? 1 : -1));
  return paid[0]?.paidAt ?? "—";
}

function customerMrr(subscriptions: readonly Subscription[], customerId: string): number {
  return subscriptions.reduce((sum, subscription) => {
    if (subscription.customerId !== customerId) return sum;
    if (subscription.status !== "active" && subscription.status !== "trialing") return sum;
    const divisor = subscription.interval === "yearly" ? 12 : subscription.interval === "weekly" ? 12 / 52 : 1;
    return sum + Math.round(subscription.amount / divisor);
  }, 0);
}

function mapPlans(plans: BackendPlan[], subscriptions: BackendSubscription[]): Plan[] {
  const planCounts = byCount(subscriptions.map((subscription) => subscription.plan_id));
  return plans.map((plan) => ({
    id: plan.id,
    name: plan.name,
    code: codeForPlan(plan),
    amount: money(plan.active_price?.amount_minor),
    currency: currency(plan.active_price?.currency),
    interval: interval(plan.active_price?.interval_unit),
    trialDays: plan.trial_days ?? 0,
    description: plan.description ?? plan.product_name ?? "Recurring subscription plan",
    status: planStatus(plan.status),
    subscribers: planCounts.get(plan.id) ?? 0,
    createdAt: isoDate(plan.created_at)
  }));
}

function mapSubscriptions(subscriptions: BackendSubscription[]): Subscription[] {
  return subscriptions.map((subscription) => {
    const item = subscription.items?.find((candidate) => candidate.status === "active") ?? subscription.items?.[0];
    const quantity = item?.quantity ?? 1;
    const notes = typeof subscription.metadata?.notes === "string" ? subscription.metadata.notes : "";
    const resumeAt = typeof subscription.metadata?.resume_at === "string" ? subscription.metadata.resume_at : "";
    return {
      id: subscription.id,
      customerId: subscription.customer_id,
      planId: subscription.plan_id,
      status: subscriptionStatus(subscription.status),
      startedAt: isoDate(subscription.created_at),
      currentPeriodStart: isoDate(subscription.current_period_start ?? subscription.created_at),
      currentPeriodEnd: isoDate(subscription.current_period_end ?? subscription.created_at),
      cancelAt: subscription.canceled_at ?? (subscription.cancel_at_period_end ? subscription.current_period_end ?? null : null),
      trialEnd: subscription.trial_end ?? null,
      amount: money(item?.amount_minor) * quantity,
      interval: interval(item?.interval_unit),
      paymentMethodId: subscription.default_payment_method_id ?? null,
      notes: [notes, resumeAt ? `Resume target: ${resumeAt}` : ""].filter(Boolean).join("\n")
    };
  });
}

function mapInvoices(invoices: BackendInvoice[], attempts: BackendPaymentAttempt[]): Invoice[] {
  const attemptsByInvoice = byCount(attempts.map((attempt) => attempt.invoice).filter((id): id is string => Boolean(id)));
  return invoices.map((invoice) => {
    const total = money(invoice.total_minor ?? invoice.amount_due_minor ?? invoice.subtotal_minor);
    const outstanding = money(invoice.amount_due_minor);
    return {
      id: invoice.id,
      number: invoice.number ?? invoice.id.slice(0, 12).toUpperCase(),
      customerId: invoice.customer_id,
      subscriptionId: invoice.subscription_id ?? null,
      status: invoiceStatus(invoice.status),
      subtotal: money(invoice.subtotal_minor),
      tax: money(invoice.tax_minor),
      total,
      amountDue: total,
      amountPaid: Math.max(0, total - outstanding),
      currency: currency(invoice.currency),
      issuedAt: isoDate(invoice.created_at),
      dueAt: isoDate(invoice.due_at ?? invoice.created_at),
      paidAt: invoice.paid_at ?? null,
      lineItems: (invoice.line_items ?? []).map((item) => ({
        description: item.description ?? "Subscription charge",
        quantity: item.quantity ?? 1,
        unitAmount: money(item.unit_amount_minor ?? item.amount_minor)
      })),
      attempts: attemptsByInvoice.get(invoice.id) ?? 0,
      notes: invoiceNotes(invoice)
    };
  });
}

function invoiceNotes(invoice: BackendInvoice): string {
  const notes: string[] = [];
  const metadataNote = invoice.metadata?.notes;
  if (typeof metadataNote === "string" && metadataNote.trim()) notes.push(metadataNote.trim());
  const creditNote = invoice.metadata?.last_credit_note_note;
  if (typeof creditNote === "string" && creditNote.trim()) {
    notes.push(`Credit applied: ${creditNote.trim()}`);
  }
  if (invoice.hosted_payment_url) notes.push(`Payment link: ${invoice.hosted_payment_url}`);
  return notes.join("\n");
}

function mapCustomers(
  customers: BackendCustomer[],
  subscriptions: readonly Subscription[],
  invoices: readonly Invoice[],
  paymentMethods: readonly BackendPaymentMethod[]
): Customer[] {
  const methodsByCustomer = paymentMethods.reduce<Map<string, PaymentMethod[]>>((acc, method) => {
    const year = method.exp_year ? String(method.exp_year).slice(-2).padStart(2, "0") : "29";
    const month = method.exp_month ? String(method.exp_month).padStart(2, "0") : "12";
    const mapped: PaymentMethod = {
      id: method.id,
      brand: paymentMethodBrand(method.brand),
      last4: method.last4 || "0000",
      expiry: `${month}/${year}`,
      isDefault: Boolean(method.is_default)
    };
    const existing = acc.get(method.customer) ?? [];
    existing.push(mapped);
    acc.set(method.customer, existing);
    return acc;
  }, new Map());

  return customers.map((customer) => ({
    id: customer.id,
    name: customer.name ?? customer.email,
    email: customer.email,
    phone: customer.phone ?? "—",
    country: typeof customer.metadata?.country === "string" ? customer.metadata.country : "Nigeria",
    status: customerStatus(customer.status),
    mrr: customerMrr(subscriptions, customer.id),
    defaultMethodId: (methodsByCustomer.get(customer.id) ?? []).find((m) => m.isDefault)?.id ?? null,
    paymentMethods: methodsByCustomer.get(customer.id) ?? [],
    createdAt: isoDate(customer.created_at),
    lastPaymentAt: latestPaidInvoiceDate(invoices, customer.id),
    notes: typeof customer.metadata?.notes === "string" ? customer.metadata.notes : ""
  }));
}

function mapPayments(
  attempts: BackendPaymentAttempt[],
  invoices: readonly Invoice[],
  paymentMethods: readonly BackendPaymentMethod[]
): PaymentRecord[] {
  const invoicesById = new Map(invoices.map((invoice) => [invoice.id, invoice]));
  const paymentMethodsById = new Map(paymentMethods.map((method) => [method.id, method]));
  return attempts.map((attempt) => {
    const invoice = attempt.invoice ? invoicesById.get(attempt.invoice) : null;
    const paymentMethod = attempt.payment_method ? paymentMethodsById.get(attempt.payment_method) : null;
    const refundedAmount = attempt.refunded_amount_minor ?? 0;
    const status = refundedAmount > 0 || attempt.refunded_at ? "refunded" : paymentStatus(attempt.status);
    return {
      id: attempt.id,
      invoiceId: attempt.invoice,
      customerId: invoice?.customerId ?? "unknown",
      amount: status === "refunded"
        ? -money(refundedAmount || attempt.amount_minor)
        : status === "failed" || status === "pending"
          ? 0
          : money(attempt.amount_minor),
      currency: currency(attempt.currency ?? invoice?.currency),
      channel: "card" satisfies PaymentChannel,
      status,
      cardBrand: paymentMethod ? paymentMethodBrand(paymentMethod.brand) : undefined,
      last4: paymentMethod?.last4 || undefined,
      failureReason: attempt.refund_reason ?? attempt.failure_message ?? attempt.failure_code ?? undefined,
      occurredAt: attempt.refunded_at ?? attempt.created_at ?? new Date().toISOString(),
      gateway: "primary"
    };
  });
}

function mapRecoveryItems(
  invoices: readonly Invoice[],
  attempts: readonly BackendPaymentAttempt[],
  runs: readonly BackendDunningRun[]
): RecoveryItem[] {
  const attemptsByInvoice = new Map<string, BackendPaymentAttempt[]>();
  for (const attempt of attempts) {
    if (!attempt.invoice) continue;
    const list = attemptsByInvoice.get(attempt.invoice) ?? [];
    list.push(attempt);
    attemptsByInvoice.set(attempt.invoice, list);
  }

  const invoicesById = new Map(invoices.map((invoice) => [invoice.id, invoice]));
  const mappedRunInvoiceIds = new Set<string>();
  const fromRuns = runs
    .filter((run) => run.status === "active" || run.status === "suspended")
    .map((run) => {
      const invoice = invoicesById.get(run.invoice);
      if (!invoice) return null;
      mappedRunInvoiceIds.add(invoice.id);
      const invoiceAttempts = (attemptsByInvoice.get(invoice.id) ?? []).sort((a, b) =>
        (a.created_at ?? "") < (b.created_at ?? "") ? 1 : -1
      );
      const latest = invoiceAttempts[0];
      const attemptCount = Math.max(invoice.attempts, run.attempt_count ?? 0, latest?.attempt_number ?? 0);
      return {
        id: run.id,
        invoiceId: invoice.id,
        customerId: invoice.customerId,
        amount: Math.max(0, invoice.amountDue - invoice.amountPaid),
        attempts: attemptCount,
        reason: reason(latest?.failure_category ?? latest?.failure_code ?? latest?.failure_message),
        stage: run.status === "suspended" ? "paused" : attemptCount >= 4 ? "manual_review" : "retry_queue",
        nextRetryAt: run.next_retry_at ?? latest?.next_retry_at ?? null,
        lastAttemptAt: latest?.created_at ?? run.updated_at ?? run.started_at ?? invoice.dueAt
      } satisfies RecoveryItem;
    })
    .filter((item): item is RecoveryItem => item !== null);

  const fallback = invoices
    .filter((invoice) => invoice.status === "past_due" || invoice.status === "uncollectible" || invoice.amountPaid < invoice.amountDue)
    .filter((invoice) => !mappedRunInvoiceIds.has(invoice.id))
    .slice(0, 20)
    .map((invoice) => {
      const invoiceAttempts = (attemptsByInvoice.get(invoice.id) ?? []).sort((a, b) =>
        (a.created_at ?? "") < (b.created_at ?? "") ? 1 : -1
      );
      const latest = invoiceAttempts[0];
      const attemptCount = Math.max(invoice.attempts, latest?.attempt_number ?? 0);
      const stage: RecoveryStage = attemptCount >= 4 ? "manual_review" : "retry_queue";
      return {
        id: `rec_${invoice.id}`,
        invoiceId: invoice.id,
        customerId: invoice.customerId,
        amount: Math.max(0, invoice.amountDue - invoice.amountPaid),
        attempts: attemptCount,
        reason: reason(latest?.failure_category ?? latest?.failure_code ?? latest?.failure_message),
        stage,
        nextRetryAt: latest?.next_retry_at ?? null,
        lastAttemptAt: latest?.created_at ?? invoice.dueAt
      };
    });

  return [...fromRuns, ...fallback].slice(0, 20);
}

function mapWebhookEndpoints(endpoints: BackendWebhookEndpoint[]): WebhookEndpoint[] {
  return endpoints.map((endpoint) => ({
    id: endpoint.id,
    url: endpoint.url,
    events: expandWebhookFilters(endpoint.event_filters),
    status: endpoint.enabled === false ? "disabled" : "active",
    signingVersion: "v2",
    createdAt: isoDate(endpoint.created_at),
    lastDeliveryAt: endpoint.updated_at ?? endpoint.created_at ?? "—",
    successRate: endpoint.enabled === false ? 0 : 1
  }));
}

function mapWebhookEvents(events: BackendEvent[], endpoints: readonly WebhookEndpoint[]): WebhookEventRecord[] {
  const fallbackEndpointId = endpoints[0]?.id ?? "backend";
  return events.map((event) => ({
    id: event.id,
    endpointId: typeof event.payload?.endpoint_id === "string" ? event.payload.endpoint_id : fallbackEndpointId,
    event: mapWebhookEvent(event.event_type),
    status: "delivered",
    attempts: 1,
    occurredAt: event.occurred_at ?? event.created_at ?? new Date().toISOString(),
    payloadPreview: JSON.stringify({
      type: event.event_type,
      data: event.payload ?? {}
    }).slice(0, 180)
  }));
}

function sentenceCase(value: string): string {
  const spaced = value
    .replace(/^[a-z_]+\./, "")
    .replace(/_/g, " ")
    .trim();
  return spaced ? spaced.charAt(0).toUpperCase() + spaced.slice(1) : "Recorded action";
}

function auditTarget(log: BackendAuditLog): string {
  const metadata = log.metadata ?? {};
  const candidates = [
    metadata.email,
    metadata.name,
    metadata.export_id,
    metadata.new_owner_email,
    metadata.delivery_email
  ];
  const metadataTarget = candidates.find((value): value is string => typeof value === "string" && value.trim().length > 0);
  if (metadataTarget) return metadataTarget;

  const targetType = log.target_type?.trim();
  const targetId = log.target_id?.trim();
  if (targetType && targetId) return `${targetType}:${targetId}`;
  if (targetId) return targetId;
  return "Workspace";
}

function mapAuditLogs(logs: BackendAuditLog[]): AuditEvent[] {
  return logs.map((log) => ({
    id: log.id,
    actor: log.actor_label || "System",
    action: sentenceCase(log.action ?? ""),
    target: auditTarget(log),
    occurredAt: log.occurred_at ?? new Date().toISOString(),
    ipAddress: log.ip_address ?? "—"
  }));
}

function allResourceKinds(): ResourceKind[] {
  return [
    "settings",
    "plans",
    "customers",
    "subscriptions",
    "invoices",
    "paymentAttempts",
    "dunningRuns",
    "paymentMethods",
    "webhookEndpoints",
    "webhookEvents",
    "apiKeys",
    "teamMembers",
    "auditLogs"
  ];
}

function resourceKindsForPath(pathname: string): ResourceKind[] {
  const segment = pathname.split("/").filter(Boolean)[0] ?? "";
  if (
    segment === "sign-in" ||
    segment === "sign-up" ||
    segment === "verify-email" ||
    segment === "forgot" ||
    segment === "reset" ||
    segment === "mfa-challenge" ||
    segment === "onboarding"
  ) {
    return [];
  }

  switch (segment) {
    case "":
      return ["settings", "customers", "invoices", "paymentAttempts", "dunningRuns", "webhookEndpoints", "auditLogs"];
    case "plans":
      return ["plans", "subscriptions", "invoices", "customers"];
    case "subscriptions":
      return ["subscriptions", "plans", "customers", "invoices"];
    case "invoices":
      return ["invoices", "customers", "paymentAttempts", "paymentMethods"];
    case "payments":
      return ["paymentAttempts", "invoices", "customers", "paymentMethods"];
    case "customers":
      return ["customers", "subscriptions", "plans", "invoices", "paymentMethods", "paymentAttempts"];
    case "recovery":
      return ["invoices", "paymentAttempts", "dunningRuns", "customers"];
    case "developers":
      return ["webhookEndpoints", "webhookEvents", "apiKeys"];
    case "team":
      return ["teamMembers"];
    case "settings":
      return ["settings", "teamMembers", "auditLogs"];
    case "portal-preview":
      return ["settings", "customers", "subscriptions", "plans", "invoices"];
    default:
      return ["settings"];
  }
}

async function loadMerchantResourceKinds(kinds: readonly ResourceKind[]): Promise<MerchantResourcePatch> {
  const requested = new Set(kinds);
  if (requested.size === 0) return {};

  const [
    backendPlans,
    backendCustomers,
    backendSubscriptions,
    backendInvoices,
    backendAttempts,
    backendDunningRuns,
    backendPaymentMethods,
    backendEndpoints,
    backendEvents,
    backendApiKeys,
    backendTeamMembers,
    backendAuditLogs,
    workspaceSettings
  ] = await Promise.all([
    requested.has("plans") ? readList<BackendPlan>("/catalog/plans/") : Promise.resolve([]),
    requested.has("customers") ? readList<BackendCustomer>("/customers/") : Promise.resolve([]),
    requested.has("subscriptions") ? readList<BackendSubscription>("/subscriptions/") : Promise.resolve([]),
    requested.has("invoices") ? readList<BackendInvoice>("/invoices/") : Promise.resolve([]),
    requested.has("paymentAttempts") ? readList<BackendPaymentAttempt>("/payment-attempts/") : Promise.resolve([]),
    requested.has("dunningRuns") ? readList<BackendDunningRun>("/dunning-runs/") : Promise.resolve([]),
    requested.has("paymentMethods") ? readList<BackendPaymentMethod>("/payment-methods/") : Promise.resolve([]),
    requested.has("webhookEndpoints") ? readList<BackendWebhookEndpoint>("/webhook-endpoints/") : Promise.resolve([]),
    requested.has("webhookEvents") ? readList<BackendEvent>("/events/") : Promise.resolve([]),
    requested.has("apiKeys") ? readList<BackendApiKey>("/api-keys/") : Promise.resolve([]),
    requested.has("teamMembers") ? readList<BackendTeamMember>("/team-members/") : Promise.resolve([]),
    requested.has("auditLogs") ? readList<BackendAuditLog>("/audit-logs/") : Promise.resolve([]),
    requested.has("settings")
      ? loadWorkspaceSettings().catch((err) => {
          console.warn("Could not load /workspace-settings/", err);
          return { org: seedOrg, settings: defaultSettings };
        })
      : Promise.resolve(null)
  ]);

  const patch: MerchantResourcePatch = {};
  const subscriptions = requested.has("subscriptions") ? mapSubscriptions(backendSubscriptions) : [];
  const invoices = requested.has("invoices") ? mapInvoices(backendInvoices, backendAttempts) : [];
  const webhookEndpoints = requested.has("webhookEndpoints") ? mapWebhookEndpoints(backendEndpoints) : [];

  if (workspaceSettings) {
    patch.org = workspaceSettings.org;
    patch.settings = workspaceSettings.settings;
  }
  if (requested.has("subscriptions")) patch.subscriptions = subscriptions;
  if (requested.has("plans")) patch.plans = mapPlans(backendPlans, backendSubscriptions);
  if (requested.has("invoices")) patch.invoices = invoices;
  if (requested.has("customers")) patch.customers = mapCustomers(backendCustomers, subscriptions, invoices, backendPaymentMethods);
  if (requested.has("paymentAttempts")) patch.payments = mapPayments(backendAttempts, invoices, backendPaymentMethods);
  if (requested.has("dunningRuns") || requested.has("paymentAttempts")) {
    patch.recoveryItems = mapRecoveryItems(invoices, backendAttempts, backendDunningRuns);
  }
  if (requested.has("webhookEndpoints")) patch.webhookEndpoints = webhookEndpoints;
  if (requested.has("webhookEvents")) patch.webhookEvents = mapWebhookEvents(backendEvents, webhookEndpoints);
  if (requested.has("apiKeys")) patch.apiKeys = backendApiKeys.map(mapApiKey);
  if (requested.has("teamMembers")) patch.teamMembers = backendTeamMembers.map(mapTeamMember);
  if (requested.has("auditLogs")) patch.auditEvents = mapAuditLogs(backendAuditLogs);

  return patch;
}

export async function loadMerchantResourcesForPath(pathname: string): Promise<MerchantResourcePatch> {
  return loadMerchantResourceKinds(resourceKindsForPath(pathname));
}

export async function loadMerchantResources(): Promise<MerchantResources> {
  const resources = await loadMerchantResourceKinds(allResourceKinds());
  return {
    org: resources.org ?? seedOrg,
    settings: resources.settings ?? defaultSettings,
    plans: resources.plans ?? [],
    customers: resources.customers ?? [],
    subscriptions: resources.subscriptions ?? [],
    invoices: resources.invoices ?? [],
    payments: resources.payments ?? [],
    recoveryItems: resources.recoveryItems ?? [],
    webhookEndpoints: resources.webhookEndpoints ?? [],
    webhookEvents: resources.webhookEvents ?? [],
    apiKeys: resources.apiKeys ?? [],
    teamMembers: resources.teamMembers ?? [],
    auditEvents: resources.auditEvents ?? []
  };
}
