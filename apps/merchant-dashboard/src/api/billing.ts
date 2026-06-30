import { api } from "./client";
import { isApiError } from "./client";
import type { Customer, Invoice, InvoiceStatus, PaymentChannel, PaymentMethod, PaymentRecordStatus, Subscription } from "../data/seed";

const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "/api/v1";
const CUSTOMER_PORTAL_BASE =
  (import.meta.env.VITE_CUSTOMER_PORTAL_URL as string | undefined)?.replace(/\/$/, "") ??
  (typeof window !== "undefined" ? window.location.origin : "");

type CustomerInput = Omit<
  Customer,
  "id" | "paymentMethods" | "defaultMethodId" | "mrr" | "createdAt" | "lastPaymentAt"
> &
  Partial<Pick<Customer, "paymentMethods" | "mrr" | "notes">>;

export interface ArchivedCustomerResult {
  pausedSubscriptions: number;
  emailSent: boolean;
}

export async function createBillingCustomer(input: CustomerInput): Promise<string> {
  const customer = await api.post<{ id: string }>("/customers/", {
    email: input.email,
    name: input.name,
    phone: input.phone,
    metadata: {
      country: input.country,
      notes: input.notes ?? ""
    }
  });
  return customer.id;
}

export async function updateBillingCustomer(id: string, patch: Partial<Customer>): Promise<void> {
  const metadata: Record<string, unknown> = {};
  if (patch.country !== undefined) metadata.country = patch.country;
  if (patch.notes !== undefined) metadata.notes = patch.notes;

  await api.patch(`/customers/${id}/`, {
    email: patch.email,
    name: patch.name,
    phone: patch.phone,
    metadata: Object.keys(metadata).length ? metadata : undefined
  });
}

export async function archiveBillingCustomer(id: string): Promise<ArchivedCustomerResult> {
  const body = await api.post<{ paused_subscriptions?: number; email_sent?: boolean }>(`/customers/${id}/archive/`, {});
  return {
    pausedSubscriptions: body.paused_subscriptions ?? 0,
    emailSent: body.email_sent ?? false
  };
}

export async function mergeBillingCustomer(sourceId: string, targetId: string): Promise<void> {
  await api.post(`/customers/${sourceId}/merge/`, {
    target_customer_id: targetId
  });
}

export async function reactivateBillingCustomer(id: string): Promise<void> {
  await api.post(`/customers/${id}/reactivate/`, {});
}

export async function attachBillingPaymentMethod(
  customerId: string,
  input: Pick<PaymentMethod, "brand" | "last4" | "expiry"> & { setDefault?: boolean }
): Promise<void> {
  const [expMonthRaw, expYearRaw] = input.expiry.split("/");
  const expMonth = Number(expMonthRaw);
  const expYear = Number(expYearRaw?.length === 2 ? `20${expYearRaw}` : expYearRaw);
  await api.post(`/customers/${customerId}/payment-methods/`, {
    provider: "mock",
    token: `tok_mock_${customerId}_${input.last4}_${Date.now()}`,
    brand: input.brand,
    last4: input.last4,
    exp_month: Number.isFinite(expMonth) ? expMonth : null,
    exp_year: Number.isFinite(expYear) ? expYear : null,
    set_default: input.setDefault ?? false,
    metadata: {
      source: "merchant_dashboard"
    }
  });
}

export async function setDefaultBillingPaymentMethod(id: string): Promise<void> {
  await api.post(`/payment-methods/${id}/set-default/`, {});
}

export async function createPortalSession(
  customerId: string,
  options: { subscriptionId?: string | null; invoiceId?: string | null; sendEmail?: boolean } = {}
): Promise<{ token: string; url: string; emailQueued: boolean }> {
  const body = await api.post<{ token: string; url?: string; email_queued?: boolean }>(`/customers/${customerId}/portal-sessions/`, {
    allowed_actions: [
      "view_subscriptions",
      "view_invoices",
      "update_payment_method",
      "pay_invoice",
      "cancel_subscription"
    ],
    subscription_id: options.subscriptionId ?? null,
    invoice_id: options.invoiceId ?? null,
    send_email: options.sendEmail ?? false,
    return_url: typeof window !== "undefined" ? window.location.origin : "",
    ttl_minutes: 24 * 60
  });
  return {
    token: body.token,
    url: body.url ?? `${CUSTOMER_PORTAL_BASE}/session/${body.token}`,
    emailQueued: body.email_queued ?? false
  };
}

export async function createBillingSubscription(input: Omit<Subscription, "id">): Promise<string> {
  const subscription = await api.post<{ id: string }>("/subscriptions/", {
    customer_id: input.customerId,
    plan_id: input.planId,
    quantity: 1,
    default_payment_method_id: input.paymentMethodId || null,
    metadata: {
      notes: input.notes,
      requested_start_date: input.startedAt,
      requested_trial_end: input.trialEnd
    }
  });

  await api.post(`/subscriptions/${subscription.id}/activate/`, {
    with_trial: input.status === "trialing"
  });

  return subscription.id;
}

export async function cancelBillingSubscription(
  id: string,
  mode: "immediate" | "end_of_period",
  reason = ""
): Promise<void> {
  await api.post(`/subscriptions/${id}/cancel/`, {
    at_period_end: mode === "end_of_period",
    reason
  });
}

export async function pauseBillingSubscription(
  id: string,
  reason = "Customer requested pause",
  resumeAt?: string | null
): Promise<void> {
  await api.post(`/subscriptions/${id}/pause/`, {
    reason,
    resume_at: resumeAt || null
  });
}

export async function resumeBillingSubscription(id: string): Promise<void> {
  await api.post(`/subscriptions/${id}/resume/`);
}

export async function changeBillingSubscriptionPlan(id: string, planId: string): Promise<void> {
  await api.post(`/subscriptions/${id}/change-plan/`, {
    new_plan_id: planId
  });
}

export async function updateBillingSubscriptionPaymentMethod(
  id: string,
  paymentMethodId: string
): Promise<void> {
  await api.post(`/subscriptions/${id}/payment-method/`, {
    payment_method_id: paymentMethodId
  });
}

export async function createBillingInvoice(input: Omit<Invoice, "id">): Promise<string> {
  const invoice = await api.post<{ id: string }>("/invoices/", {
    customer_id: input.customerId,
    subscription_id: input.subscriptionId,
    currency: input.currency,
    due_at: input.dueAt ? new Date(input.dueAt).toISOString() : null,
    line_items: input.lineItems.map((line) => ({
      type: "one_time",
      description: line.description,
      amount_minor: Math.round(line.unitAmount * 100),
      quantity: line.quantity,
      currency: input.currency
    })),
    metadata: {
      notes: input.notes
    }
  });

  await retryTransient(() => api.post(`/invoices/${invoice.id}/finalize/`, {}));
  return invoice.id;
}

export async function voidBillingInvoice(id: string, reason = "Voided from merchant dashboard"): Promise<void> {
  await api.post(`/invoices/${id}/void/`, { reason });
}

export async function markBillingInvoicePaid(id: string, amount: number): Promise<void> {
  await api.post(`/invoices/${id}/pay/`, {
    paid_amount_minor: Math.round(amount * 100),
    paid_at: new Date().toISOString()
  });
}

export async function applyBillingInvoiceCredit(
  id: string,
  amount: number,
  note = "",
  reason = "other"
): Promise<void> {
  await api.post(`/invoices/${id}/apply-credit/`, {
    amount_minor: Math.round(amount * 100),
    reason,
    note
  });
}

export async function sendBillingInvoiceReminder(
  id: string,
  channel: "email" | "sms",
  message: string
): Promise<void> {
  await api.post(`/invoices/${id}/send-reminder/`, { channel, message });
}

export async function downloadBillingInvoicePdf(id: string, invoiceNumber: string): Promise<void> {
  const response = await fetch(`${API_BASE}/invoices/${id}/pdf/`, {
    credentials: "include"
  });
  if (!response.ok) {
    throw new Error(`PDF download failed (${response.status})`);
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

export async function exportBillingInvoicesCsv(filters: { status?: InvoiceStatus | "all"; q?: string } = {}): Promise<void> {
  const params = new URLSearchParams();
  if (filters.status && filters.status !== "all") params.set("status", filters.status);
  if (filters.q?.trim()) params.set("q", filters.q.trim());
  const suffix = params.toString() ? `?${params.toString()}` : "";
  await downloadBackendFile(`/invoices/export/${suffix}`, "subpilot-invoices.csv", "Invoice export failed");
}

export async function refundBillingPayment(
  id: string,
  amount: number,
  full: boolean,
  reason = ""
): Promise<void> {
  await api.post(`/payment-attempts/${id}/refund/`, {
    amount_minor: Math.round(amount * 100),
    full,
    reason
  });
}

export async function downloadPaymentReceiptPdf(id: string): Promise<void> {
  const response = await fetch(`${API_BASE}/payment-attempts/${id}/receipt/`, {
    credentials: "include"
  });
  if (!response.ok) {
    throw new Error(`Receipt download failed (${response.status})`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = `receipt-${id}.pdf`;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

export async function exportPaymentAttemptsCsv(
  filters: { status?: PaymentRecordStatus | "all"; channel?: PaymentChannel | "all"; q?: string } = {}
): Promise<void> {
  const params = new URLSearchParams();
  if (filters.status && filters.status !== "all") params.set("status", filters.status);
  if (filters.channel && filters.channel !== "all") params.set("channel", filters.channel);
  if (filters.q?.trim()) params.set("q", filters.q.trim());
  const suffix = params.toString() ? `?${params.toString()}` : "";
  await downloadBackendFile(`/payment-attempts/export/${suffix}`, "subpilot-payments.csv", "Payment export failed");
}

async function downloadBackendFile(path: string, filename: string, errorPrefix: string): Promise<void> {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include"
  });
  if (!response.ok) {
    throw new Error(`${errorPrefix} (${response.status})`);
  }
  const blob = await response.blob();
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
}

async function retryTransient<T>(operation: () => Promise<T>): Promise<T> {
  let lastError: unknown;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      return await operation();
    } catch (err) {
      lastError = err;
      if (!isApiError(err) || err.status < 500 || attempt === 2) break;
      await new Promise((resolve) => setTimeout(resolve, 250 * (attempt + 1)));
    }
  }
  throw lastError;
}
