import type {
  Customer,
  Invoice,
  InvoiceStatus,
  MerchantOrg,
  PaymentMethod,
  PlanInterval,
  Subscription,
  SubscriptionStatus
} from "../data/seed";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "/api/v1";

export interface PortalApiError extends Error {
  status: number;
  reason: string;
  payload: unknown;
}

interface BackendCustomer {
  id: string;
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
  quantity?: number | null;
}

interface BackendSubscription {
  id: string;
  customer_id: string;
  plan_id: string;
  plan_name?: string | null;
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
  total_minor?: number | null;
  amount_due_minor?: number | null;
  subtotal_minor?: number | null;
  currency?: string | null;
  due_at?: string | null;
  paid_at?: string | null;
  line_items?: BackendInvoiceLineItem[];
  created_at?: string | null;
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

interface PortalContextResponse {
  customer: BackendCustomer;
  subscriptions: BackendSubscription[];
  invoices: BackendInvoice[];
  payment_methods?: BackendPaymentMethod[];
  merchant?: BackendPortalMerchant | null;
  allowed_actions: string[];
}

interface BackendPortalMerchant {
  name?: string | null;
  legal_name?: string | null;
  brand_color?: string | null;
  logo_url?: string | null;
  portal_subdomain?: string | null;
  allow_cancel?: boolean | null;
  allow_pause?: boolean | null;
  allow_change_plan?: boolean | null;
  success_url?: string | null;
  cancel_url?: string | null;
}

export type PortalSubscription = Subscription & { planName: string; currency: MerchantOrg["currency"] };

export interface PortalPreviewData {
  customer: Customer;
  subscriptions: PortalSubscription[];
  invoices: Invoice[];
  paymentMethods: PaymentMethod[];
  merchant: PortalMerchantBranding;
  allowedActions: string[];
}

export interface PortalMerchantBranding {
  name: string;
  legalName: string;
  brandColor: string;
  logoUrl: string | null;
  portalSubdomain: string;
  allowCancel: boolean;
  allowPause: boolean;
  allowChangePlan: boolean;
  successUrl: string;
  cancelUrl: string;
}

export interface PortalAttachPaymentMethodInput {
  brand: PaymentMethod["brand"];
  last4: string;
  expiry: string;
}

async function portalRequest<T>(
  token: string,
  path: string,
  init: RequestInit & { json?: unknown } = {}
): Promise<T> {
  const { json, headers: rawHeaders, method = "GET", ...rest } = init;
  const headers = new Headers(rawHeaders ?? {});
  headers.set("Accept", "application/json");
  headers.set("Authorization", `Portal ${token}`);

  let body = init.body;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }

  const response = await fetch(`${API_BASE}${path.startsWith("/") ? path : `/${path}`}`, {
    method,
    headers,
    body,
    ...rest
  });

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    const error = new Error(reasonFromPayload(payload, `Portal request failed (${response.status})`)) as PortalApiError;
    error.status = response.status;
    error.reason = error.message;
    error.payload = payload;
    throw error;
  }

  return payload as T;
}

function reasonFromPayload(payload: unknown, fallback: string): string {
  if (typeof payload === "object" && payload && "reason" in payload) {
    return String((payload as { reason: unknown }).reason);
  }
  if (typeof payload === "object" && payload && "detail" in payload) {
    return String((payload as { detail: unknown }).detail);
  }
  return fallback;
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

function paymentMethodBrand(value: string | null | undefined): PaymentMethod["brand"] {
  if (value === "Mastercard" || value === "Verve" || value === "Amex") return value;
  return "Visa";
}

function mapPaymentMethods(methods: BackendPaymentMethod[]): PaymentMethod[] {
  return methods.map((method) => {
    const year = method.exp_year ? String(method.exp_year).slice(-2).padStart(2, "0") : "29";
    const month = method.exp_month ? String(method.exp_month).padStart(2, "0") : "12";
    return {
      id: method.id,
      brand: paymentMethodBrand(method.brand),
      last4: method.last4 || "0000",
      expiry: `${month}/${year}`,
      isDefault: Boolean(method.is_default)
    };
  });
}

function mapSubscriptions(subscriptions: BackendSubscription[]): PortalSubscription[] {
  return subscriptions.map((subscription) => {
    const item = subscription.items?.[0];
    const quantity = item?.quantity ?? 1;
    return {
      id: subscription.id,
      customerId: subscription.customer_id,
      planId: subscription.plan_id,
      planName: subscription.plan_name ?? "Subscription plan",
      status: subscriptionStatus(subscription.status),
      startedAt: isoDate(subscription.created_at),
      currentPeriodStart: isoDate(subscription.current_period_start ?? subscription.created_at),
      currentPeriodEnd: isoDate(subscription.current_period_end ?? subscription.created_at),
      cancelAt: subscription.canceled_at ?? (subscription.cancel_at_period_end ? subscription.current_period_end ?? null : null),
      trialEnd: subscription.trial_end ?? null,
      amount: money(item?.amount_minor) * quantity,
      currency: currency(item?.currency),
      interval: interval(item?.interval_unit),
      paymentMethodId: null,
      notes: subscription.cancel_at_period_end ? "Cancellation scheduled at period end" : ""
    };
  });
}

function mapInvoices(invoices: BackendInvoice[]): Invoice[] {
  return invoices.map((invoice) => {
    const total = money(invoice.total_minor ?? invoice.amount_due_minor ?? invoice.subtotal_minor);
    const outstanding = money(invoice.amount_due_minor);
    return {
      id: invoice.id,
      number: invoice.number ?? invoice.id.slice(0, 12).toUpperCase(),
      customerId: invoice.customer_id,
      subscriptionId: invoice.subscription_id ?? null,
      status: invoiceStatus(invoice.status),
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
      attempts: 0,
      notes: ""
    };
  });
}

function mapCustomer(customer: BackendCustomer, methods: PaymentMethod[]): Customer {
  return {
    id: customer.id,
    name: customer.name ?? customer.email,
    email: customer.email,
    phone: customer.phone ?? "—",
    country: typeof customer.metadata?.country === "string" ? customer.metadata.country : "Nigeria",
    status: customer.status === "archived" ? "blocked" : customer.status === "inactive" ? "churned" : "active",
    mrr: 0,
    defaultMethodId: methods.find((method) => method.isDefault)?.id ?? null,
    paymentMethods: methods,
    createdAt: isoDate(customer.created_at),
    lastPaymentAt: "—",
    notes: typeof customer.metadata?.notes === "string" ? customer.metadata.notes : ""
  };
}

function mapMerchant(merchant: BackendPortalMerchant | null | undefined): PortalMerchantBranding {
  return {
    name: merchant?.name || "Merchant",
    legalName: merchant?.legal_name || merchant?.name || "Merchant",
    brandColor: merchant?.brand_color || "#056058",
    logoUrl: merchant?.logo_url || null,
    portalSubdomain: merchant?.portal_subdomain || "portal",
    allowCancel: merchant?.allow_cancel ?? true,
    allowPause: merchant?.allow_pause ?? true,
    allowChangePlan: merchant?.allow_change_plan ?? true,
    successUrl: merchant?.success_url || "",
    cancelUrl: merchant?.cancel_url || ""
  };
}

export async function loadPortalPreview(token: string): Promise<PortalPreviewData> {
  const context = await portalRequest<PortalContextResponse>(token, "/portal/context");
  const paymentMethods = mapPaymentMethods(context.payment_methods ?? []);
  return {
    customer: mapCustomer(context.customer, paymentMethods),
    subscriptions: mapSubscriptions(context.subscriptions),
    invoices: mapInvoices(context.invoices),
    paymentMethods,
    merchant: mapMerchant(context.merchant),
    allowedActions: context.allowed_actions ?? []
  };
}

export async function attachPortalPaymentMethod(
  token: string,
  customerId: string,
  input: PortalAttachPaymentMethodInput
): Promise<void> {
  const [expMonthRaw, expYearRaw] = input.expiry.split("/");
  const expMonth = Number(expMonthRaw);
  const expYear = Number(expYearRaw?.length === 2 ? `20${expYearRaw}` : expYearRaw);
  await portalRequest(token, "/portal/payment-methods", {
    method: "POST",
    json: {
      provider: "mock",
      token: `tok_portal_${customerId}_${input.last4}_${Date.now()}`,
      brand: input.brand,
      last4: input.last4,
      exp_month: Number.isFinite(expMonth) ? expMonth : null,
      exp_year: Number.isFinite(expYear) ? expYear : null,
      set_default: true,
      metadata: {
        source: "customer_portal_preview"
      }
    }
  });
}

export async function payPortalInvoice(token: string, invoiceId: string): Promise<void> {
  await portalRequest(token, `/portal/invoices/${invoiceId}/pay`, { method: "POST" });
}

export async function downloadPortalInvoicePdf(token: string, invoiceId: string, invoiceNumber: string): Promise<void> {
  const response = await fetch(`${API_BASE}/portal/invoices/${invoiceId}/pdf`, {
    headers: {
      Accept: "application/pdf",
      Authorization: `Portal ${token}`
    }
  });

  if (!response.ok) {
    let payload: unknown = null;
    const text = await response.text();
    if (text) {
      try {
        payload = JSON.parse(text);
      } catch {
        payload = text;
      }
    }
    const error = new Error(reasonFromPayload(payload, `Invoice PDF download failed (${response.status})`)) as PortalApiError;
    error.status = response.status;
    error.reason = error.message;
    error.payload = payload;
    throw error;
  }

  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `${invoiceNumber}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function cancelPortalSubscription(token: string, subscriptionId: string): Promise<void> {
  await portalRequest(token, `/portal/subscriptions/${subscriptionId}/cancel`, {
    method: "POST",
    json: {
      at_period_end: true,
      reason: "Cancelled from customer portal"
    }
  });
}
