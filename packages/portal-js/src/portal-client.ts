export type CardBrand = "Visa" | "Mastercard" | "Verve" | "Amex";
export type Currency = "NGN" | "USD" | "GBP" | "KES";

export interface SubPilotPortalOptions {
  publishableKey: string;
  apiBaseUrl?: string;
}

export interface PortalPaymentMethod {
  id: string;
  brand: CardBrand;
  last4: string;
  expiry: string;
  isDefault: boolean;
}

export interface PortalInvoice {
  id: string;
  number: string;
  status: "draft" | "open" | "paid" | "past_due" | "void" | "uncollectible";
  amountDue: number;
  amountPaid: number;
  currency: Currency;
  issuedAt: string;
  dueAt: string;
  paidAt: string | null;
}

export interface PortalSubscription {
  id: string;
  planId: string;
  planName: string;
  status: "active" | "trialing" | "past_due" | "paused" | "cancelled" | "incomplete";
  currentPeriodEnd: string;
  cancelAt: string | null;
  amount: number;
  currency: Currency;
  interval: "monthly" | "weekly" | "yearly";
}

export interface PortalPlanFeature {
  label: string;
  detail: string;
}

export interface PortalPlan {
  id: string;
  name: string;
  description: string;
  productName: string;
  trialDays: number;
  amountMinor: number;
  amount: number;
  currency: Currency;
  intervalUnit: string;
  intervalCount: number;
  features: PortalPlanFeature[];
}

export interface PortalPlansResponse {
  currentPlanId: string | null;
  plans: PortalPlan[];
}

export interface PortalChangePreview {
  currentPlanId: string;
  newPlanId: string;
  prorationCreditMinor: number;
  prorationChargeMinor: number;
  prorationCredit: number;
  prorationCharge: number;
  netMinor: number;
  net: number;
  currency: Currency;
  effectiveAt: string;
}

export interface PortalCustomer {
  id: string;
  name: string;
  email: string;
  defaultMethodId: string | null;
}

export interface PortalMerchant {
  name: string;
  legalName: string;
  brandColor: string;
  logoUrl: string | null;
  portalSubdomain: string;
  allowCancel: boolean;
  allowPause: boolean;
  allowChangePlan: boolean;
  allowSubscribe: boolean;
  successUrl: string;
  cancelUrl: string;
}

export interface PortalData {
  customer: PortalCustomer;
  merchant: PortalMerchant;
  subscriptions: PortalSubscription[];
  invoices: PortalInvoice[];
  paymentMethods: PortalPaymentMethod[];
  allowedActions: string[];
}

export interface PortalPaymentMethodCheckout {
  checkoutUrl: string;
  invoiceId: string;
  orderReference: string;
  processor: "nomba";
}

export interface PortalPaymentMethodCheckoutConfirmation {
  confirmed: boolean;
  status: string;
  invoiceId: string;
  invoicePaid: boolean;
  paymentMethodAttached: boolean;
  eventId: string;
}

interface BackendContext {
  customer: {
    id: string;
    email: string;
    name?: string | null;
  };
  subscriptions: Array<{
    id: string;
    plan_id?: string | null;
    plan_name?: string | null;
    status?: string | null;
    current_period_end?: string | null;
    cancel_at_period_end?: boolean | null;
    canceled_at?: string | null;
    items?: Array<{
      amount_minor?: number | null;
      currency?: string | null;
      interval_unit?: string | null;
      quantity?: number | null;
    }>;
  }>;
  invoices: Array<{
    id: string;
    number?: string | null;
    status?: string | null;
    total_minor?: number | null;
    amount_due_minor?: number | null;
    subtotal_minor?: number | null;
    currency?: string | null;
    due_at?: string | null;
    paid_at?: string | null;
    created_at?: string | null;
  }>;
  payment_methods?: Array<{
    id: string;
    brand?: string | null;
    last4?: string | null;
    exp_month?: number | null;
    exp_year?: number | null;
    is_default?: boolean | null;
  }>;
  merchant?: {
    name?: string | null;
    legal_name?: string | null;
    brand_color?: string | null;
    logo_url?: string | null;
    portal_subdomain?: string | null;
    allow_cancel?: boolean | null;
    allow_pause?: boolean | null;
    allow_change_plan?: boolean | null;
    allow_subscribe?: boolean | null;
    success_url?: string | null;
    cancel_url?: string | null;
  } | null;
  allowed_actions?: string[] | null;
}

export interface SubPilotPortalClient {
  loadPortal(token: string): Promise<PortalData>;
  createPaymentMethodCheckout(token: string, invoiceId?: string): Promise<PortalPaymentMethodCheckout>;
  confirmPaymentMethodCheckout(token: string, payload: { orderReference?: string; orderId?: string; invoiceId?: string }): Promise<PortalPaymentMethodCheckoutConfirmation>;
  setDefaultPaymentMethod(token: string, methodId: string): Promise<void>;
  payInvoice(token: string, invoiceId: string): Promise<void>;
  cancelSubscription(token: string, subscriptionId: string): Promise<void>;
  listPlans(token: string): Promise<PortalPlansResponse>;
  previewChangePlan(token: string, subscriptionId: string, newPlanId: string): Promise<PortalChangePreview>;
  changePlan(token: string, subscriptionId: string, newPlanId: string): Promise<{ subscription: PortalSubscription; preview: PortalChangePreview }>;
  subscribe(token: string, planId: string): Promise<{
    subscription: PortalSubscription;
    invoiceId: string;
    checkoutUrl: string;
    orderReference: string;
    processor: "nomba";
  }>;
}

export function createSubPilotPortalClient(options: SubPilotPortalOptions): SubPilotPortalClient {
  const apiBaseUrl = (options.apiBaseUrl ?? "/api/v1").replace(/\/$/, "");

  async function portalRequest<T>(token: string, path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
    const { json, headers: rawHeaders, method = "GET", ...rest } = init;
    const headers = new Headers(rawHeaders ?? {});
    headers.set("Accept", "application/json");
    headers.set("Authorization", `Portal ${token}`);
    headers.set("X-SubPilot-Publishable-Key", options.publishableKey);

    let body = init.body;
    if (json !== undefined) {
      headers.set("Content-Type", "application/json");
      body = JSON.stringify(json);
    }

    const response = await fetch(`${apiBaseUrl}${path.startsWith("/") ? path : `/${path}`}`, {
      method,
      headers,
      body,
      ...rest
    });
    const text = await response.text();
    const payload = text ? tryJson(text) : null;
    if (!response.ok) {
      throw new Error(reasonFromPayload(payload, `Portal request failed (${response.status})`));
    }
    return payload as T;
  }

  return {
    async loadPortal(token) {
      const context = await portalRequest<BackendContext>(token, "/portal/context");
      return mapPortalContext(context);
    },
    async createPaymentMethodCheckout(token, invoiceId) {
      const body = await portalRequest<{
        checkout_url: string;
        invoice_id: string;
        order_reference?: string;
        processor: "nomba";
      }>(token, "/portal/payment-methods/checkout", {
        method: "POST",
        json: invoiceId ? { invoice_id: invoiceId } : {}
      });
      return {
        checkoutUrl: body.checkout_url,
        invoiceId: body.invoice_id,
        orderReference: body.order_reference ?? "",
        processor: body.processor
      };
    },
    async confirmPaymentMethodCheckout(token, payload) {
      const body = await portalRequest<{
        confirmed: boolean;
        status: string;
        invoice_id: string;
        invoice_paid: boolean;
        payment_method_attached: boolean;
        event_id: string;
      }>(token, "/portal/payment-methods/checkout/confirm", {
        method: "POST",
        json: {
          order_reference: payload.orderReference,
          order_id: payload.orderId,
          invoice_id: payload.invoiceId
        }
      });
      return {
        confirmed: body.confirmed,
        status: body.status,
        invoiceId: body.invoice_id,
        invoicePaid: body.invoice_paid,
        paymentMethodAttached: body.payment_method_attached,
        eventId: body.event_id
      };
    },
    async setDefaultPaymentMethod(token, methodId) {
      await portalRequest(token, `/portal/payment-methods/${methodId}/set-default`, {
        method: "POST"
      });
    },
    async payInvoice(token, invoiceId) {
      await portalRequest(token, `/portal/invoices/${invoiceId}/pay`, { method: "POST" });
    },
    async cancelSubscription(token, subscriptionId) {
      await portalRequest(token, `/portal/subscriptions/${subscriptionId}/cancel`, {
        method: "POST",
        json: { at_period_end: true, reason: "Cancelled from customer portal" }
      });
    },
    async listPlans(token) {
      const body = await portalRequest<{
        current_plan_id: string | null;
        plans: Array<{
          id: string;
          name: string;
          description: string;
          product_name: string;
          trial_days: number;
          amount_minor: number;
          currency: string;
          interval_unit: string;
          interval_count: number;
          features: Array<{ label: string; detail: string }>;
        }>;
      }>(token, "/portal/plans");
      return {
        currentPlanId: body.current_plan_id ?? null,
        plans: body.plans.map((p) => ({
          id: p.id,
          name: p.name,
          description: p.description ?? "",
          productName: p.product_name ?? "",
          trialDays: p.trial_days ?? 0,
          amountMinor: p.amount_minor ?? 0,
          amount: money(p.amount_minor),
          currency: currency(p.currency),
          intervalUnit: p.interval_unit ?? "month",
          intervalCount: p.interval_count ?? 1,
          features: (p.features ?? []).map((f) => ({ label: f.label, detail: f.detail ?? "" }))
        }))
      };
    },
    async previewChangePlan(token, subscriptionId, newPlanId) {
      const body = await portalRequest<{
        current_plan_id: string;
        new_plan_id: string;
        proration_credit_minor: number;
        proration_charge_minor: number;
        net_minor: number;
        currency: string;
        effective_at: string;
      }>(token, `/portal/subscriptions/${subscriptionId}/preview-change`, {
        method: "POST",
        json: { new_plan_id: newPlanId }
      });
      return mapChangePreview(body);
    },
    async changePlan(token, subscriptionId, newPlanId) {
      const body = await portalRequest<{
        subscription: BackendContext["subscriptions"][number];
        preview: {
          current_plan_id: string;
          new_plan_id: string;
          proration_credit_minor: number;
          proration_charge_minor: number;
          net_minor: number;
          currency: string;
          effective_at: string;
        };
      }>(token, `/portal/subscriptions/${subscriptionId}/change-plan`, {
        method: "POST",
        json: { new_plan_id: newPlanId }
      });
      return {
        subscription: mapSubscription(body.subscription),
        preview: mapChangePreview(body.preview)
      };
    },
    async subscribe(token, planId) {
      const body = await portalRequest<{
        subscription: BackendContext["subscriptions"][number];
        invoice_id: string;
        checkout_url: string;
        order_reference?: string;
        processor: "nomba";
      }>(token, "/portal/subscribe", {
        method: "POST",
        json: { plan_id: planId }
      });
      return {
        subscription: mapSubscription(body.subscription),
        invoiceId: body.invoice_id,
        checkoutUrl: body.checkout_url,
        orderReference: body.order_reference ?? "",
        processor: body.processor
      };
    }
  };
}

function mapChangePreview(p: {
  current_plan_id: string;
  new_plan_id: string;
  proration_credit_minor: number;
  proration_charge_minor: number;
  net_minor: number;
  currency: string;
  effective_at: string;
}): PortalChangePreview {
  return {
    currentPlanId: p.current_plan_id,
    newPlanId: p.new_plan_id,
    prorationCreditMinor: p.proration_credit_minor ?? 0,
    prorationChargeMinor: p.proration_charge_minor ?? 0,
    prorationCredit: money(p.proration_credit_minor),
    prorationCharge: money(p.proration_charge_minor),
    netMinor: p.net_minor ?? 0,
    net: money(p.net_minor),
    currency: currency(p.currency),
    effectiveAt: p.effective_at
  };
}

function mapSubscription(subscription: BackendContext["subscriptions"][number]): PortalSubscription {
  const item = subscription.items?.[0];
  const quantity = item?.quantity ?? 1;
  return {
    id: subscription.id,
    planId: subscription.plan_id ?? "",
    planName: subscription.plan_name || "Subscription plan",
    status: subscriptionStatus(subscription.status),
    currentPeriodEnd: isoDate(subscription.current_period_end),
    cancelAt: subscription.canceled_at ?? (subscription.cancel_at_period_end ? subscription.current_period_end ?? null : null),
    amount: money(item?.amount_minor) * quantity,
    currency: currency(item?.currency),
    interval: interval(item?.interval_unit)
  };
}

function mapPortalContext(context: BackendContext): PortalData {
  const methods = (context.payment_methods ?? []).map((method) => {
    const month = String(method.exp_month ?? 12).padStart(2, "0");
    const year = String(method.exp_year ?? 2029).slice(-2).padStart(2, "0");
    return {
      id: method.id,
      brand: brand(method.brand),
      last4: method.last4 || "0000",
      expiry: `${month}/${year}`,
      isDefault: Boolean(method.is_default)
    };
  });

  return {
    customer: {
      id: context.customer.id,
      name: context.customer.name || context.customer.email,
      email: context.customer.email,
      defaultMethodId: methods.find((method) => method.isDefault)?.id ?? null
    },
    merchant: {
      name: context.merchant?.name || "Merchant",
      legalName: context.merchant?.legal_name || context.merchant?.name || "Merchant",
      brandColor: context.merchant?.brand_color || "#056058",
      logoUrl: context.merchant?.logo_url || null,
      portalSubdomain: context.merchant?.portal_subdomain || "portal",
      allowCancel: context.merchant?.allow_cancel ?? true,
      allowPause: context.merchant?.allow_pause ?? true,
      allowChangePlan: context.merchant?.allow_change_plan ?? true,
      allowSubscribe: context.merchant?.allow_subscribe ?? true,
      successUrl: context.merchant?.success_url || "",
      cancelUrl: context.merchant?.cancel_url || ""
    },
    subscriptions: context.subscriptions.map((subscription) => mapSubscription(subscription)),
    invoices: context.invoices.map((invoice) => {
      const total = money(invoice.total_minor ?? invoice.amount_due_minor ?? invoice.subtotal_minor);
      const outstanding = money(invoice.amount_due_minor);
      return {
        id: invoice.id,
        number: invoice.number || invoice.id.slice(0, 12).toUpperCase(),
        status: invoiceStatus(invoice.status),
        amountDue: total,
        amountPaid: Math.max(0, total - outstanding),
        currency: currency(invoice.currency),
        issuedAt: isoDate(invoice.created_at),
        dueAt: isoDate(invoice.due_at ?? invoice.created_at),
        paidAt: invoice.paid_at ?? null
      };
    }),
    paymentMethods: methods,
    allowedActions: context.allowed_actions ?? []
  };
}

function tryJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

function reasonFromPayload(payload: unknown, fallback: string): string {
  if (typeof payload === "object" && payload && "reason" in payload) return String((payload as { reason: unknown }).reason);
  if (typeof payload === "object" && payload && "detail" in payload) return String((payload as { detail: unknown }).detail);
  return fallback;
}

function money(minor: number | null | undefined): number {
  return Math.round((minor ?? 0) / 100);
}

function currency(value: string | null | undefined): Currency {
  const normalized = (value ?? "NGN").toUpperCase();
  return normalized === "USD" || normalized === "GBP" || normalized === "KES" ? normalized : "NGN";
}

function isoDate(value: string | null | undefined): string {
  return value ? value.slice(0, 10) : new Date().toISOString().slice(0, 10);
}

function brand(value: string | null | undefined): CardBrand {
  if (value === "Mastercard" || value === "Verve" || value === "Amex") return value;
  return "Visa";
}

function interval(value: string | null | undefined): PortalSubscription["interval"] {
  if (value === "year" || value === "yearly") return "yearly";
  if (value === "week" || value === "weekly") return "weekly";
  return "monthly";
}

function subscriptionStatus(value: string | null | undefined): PortalSubscription["status"] {
  if (value === "trialing" || value === "past_due" || value === "paused" || value === "cancelled" || value === "incomplete") return value;
  if (value === "canceled") return "cancelled";
  return "active";
}

function invoiceStatus(value: string | null | undefined): PortalInvoice["status"] {
  if (value === "draft" || value === "paid" || value === "past_due" || value === "void" || value === "uncollectible") return value;
  if (value === "voided") return "void";
  return "open";
}

export function formatCurrency(amount: number, code: Currency): string {
  return new Intl.NumberFormat("en-NG", { style: "currency", currency: code, maximumFractionDigits: 0 }).format(amount);
}

export function prettyStatus(status: string): string {
  return status.split("_").map((part) => part.charAt(0).toUpperCase() + part.slice(1)).join(" ");
}
