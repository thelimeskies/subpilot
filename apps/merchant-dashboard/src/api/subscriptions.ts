import { api } from "./client";

export interface SubscriptionEvent {
  id: string;
  eventType: string;
  fromStatus: string;
  toStatus: string;
  actor: string;
  detail: string;
  occurredAt: string;
}

export interface SubscriptionPlanChangePreview {
  currentPlanId: string;
  newPlanId: string;
  currentPriceVersionId: string;
  newPriceVersionId: string;
  prorationCreditMinor: number;
  prorationChargeMinor: number;
  netMinor: number;
  currency: "NGN" | "USD" | "GBP" | "KES";
  effectiveAt: string;
}

interface BackendSubscriptionEvent {
  id: string;
  event_type?: string | null;
  from_status?: string | null;
  to_status?: string | null;
  actor_label?: string | null;
  metadata?: Record<string, unknown> | null;
  occurred_at?: string | null;
}

interface BackendPlanChangePreview {
  current_plan_id?: string | null;
  new_plan_id?: string | null;
  current_price_version_id?: string | null;
  new_price_version_id?: string | null;
  proration_credit_minor?: number | null;
  proration_charge_minor?: number | null;
  net_minor?: number | null;
  currency?: string | null;
  effective_at?: string | null;
}

function titleize(value: string): string {
  return value
    .replace(/^subscription\./, "")
    .replace(/_/g, " ")
    .split(" ")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function eventDetail(event: BackendSubscriptionEvent): string {
  const metadata = event.metadata ?? {};
  if (typeof metadata.amount_minor === "number") {
    const currency = typeof metadata.currency === "string" ? metadata.currency : "NGN";
    const amount = new Intl.NumberFormat("en-NG", {
      style: "currency",
      currency,
      maximumFractionDigits: 0
    }).format(Math.round(metadata.amount_minor / 100));
    const note = typeof metadata.note === "string" && metadata.note.trim() ? ` · ${metadata.note.trim()}` : "";
    return `${amount} credit applied${note}`;
  }
  if (typeof metadata.note === "string" && metadata.note.trim()) return metadata.note.trim();
  if (typeof metadata.reason === "string" && metadata.reason.trim()) return metadata.reason.trim();
  if (typeof metadata.new_plan_id === "string") return `New plan ${metadata.new_plan_id}`;
  if (typeof metadata.payment_method_id === "string") return `Payment method ${metadata.payment_method_id}`;
  const from = event.from_status;
  const to = event.to_status;
  if (from && to && from !== to) return `${from} -> ${to}`;
  return "Subscription activity recorded by the backend.";
}

export async function loadSubscriptionEvents(subscriptionId: string): Promise<SubscriptionEvent[]> {
  const body = await api.get<BackendSubscriptionEvent[]>(`/subscriptions/${subscriptionId}/events/`);
  return body.map((event) => ({
    id: event.id,
    eventType: titleize(event.event_type ?? "subscription.updated"),
    fromStatus: event.from_status ?? "",
    toStatus: event.to_status ?? "",
    actor: event.actor_label || "System",
    detail: eventDetail(event),
    occurredAt: event.occurred_at ?? new Date().toISOString()
  }));
}

export async function previewSubscriptionPlanChange(
  subscriptionId: string,
  planId: string
): Promise<SubscriptionPlanChangePreview> {
  const body = await api.post<BackendPlanChangePreview>(`/subscriptions/${subscriptionId}/preview-change/`, {
    new_plan_id: planId
  });
  const currency = body.currency === "USD" || body.currency === "GBP" || body.currency === "KES" ? body.currency : "NGN";
  return {
    currentPlanId: body.current_plan_id ?? "",
    newPlanId: body.new_plan_id ?? planId,
    currentPriceVersionId: body.current_price_version_id ?? "",
    newPriceVersionId: body.new_price_version_id ?? "",
    prorationCreditMinor: body.proration_credit_minor ?? 0,
    prorationChargeMinor: body.proration_charge_minor ?? 0,
    netMinor: body.net_minor ?? 0,
    currency,
    effectiveAt: body.effective_at ?? new Date().toISOString()
  };
}

export async function addSubscriptionNote(subscriptionId: string, note: string): Promise<void> {
  await api.post(`/subscriptions/${subscriptionId}/notes/`, { note });
}

export async function applySubscriptionCredit(
  subscriptionId: string,
  amount: number,
  note: string
): Promise<void> {
  await api.post(`/subscriptions/${subscriptionId}/credits/`, {
    amount_minor: Math.round(amount * 100),
    note
  });
}
