// Memoized selectors / aggregate computations over the seed (or store) data.
//
// The store passes the live entity arrays into these helpers (rather than
// reading directly from `seed.ts`) so that mutations performed via
// `<DataProvider/>` are reflected. Callers who only need raw seed reads can
// also import the generic helpers and pass the seed exports directly.

import type {
  AuditEvent,
  Customer,
  Invoice,
  PaymentRecord,
  Plan,
  RecoveryItem,
  Subscription,
  TeamMember,
  WebhookEndpoint,
  WebhookEventRecord
} from "./seed";

// ---------- Generic memo helper ----------

/**
 * Build an O(1) id → entity lookup over an array. Re-creates the index when
 * the source array reference changes (which is what happens whenever the
 * `<DataProvider/>` `useState` setter swaps in a new array).
 */
export function createIndex<T, K extends string | number>(
  items: readonly T[],
  keyFn: (item: T) => K
): Map<K, T> {
  const map = new Map<K, T>();
  for (const item of items) {
    map.set(keyFn(item), item);
  }
  return map;
}

// ---------- Single-entity lookups ----------

export function findCustomerById(customers: readonly Customer[], id: string | undefined | null) {
  if (!id) return null;
  return customers.find((c) => c.id === id) ?? null;
}

export function findPlanById(plans: readonly Plan[], id: string | undefined | null) {
  if (!id) return null;
  return plans.find((p) => p.id === id) ?? null;
}

export function findSubscriptionById(subs: readonly Subscription[], id: string | undefined | null) {
  if (!id) return null;
  return subs.find((s) => s.id === id) ?? null;
}

export function findInvoiceById(invoices: readonly Invoice[], id: string | undefined | null) {
  if (!id) return null;
  return invoices.find((i) => i.id === id) ?? null;
}

export function findTeamMemberByEmail(team: readonly TeamMember[], email: string) {
  const lower = email.toLowerCase();
  return team.find((m) => m.email.toLowerCase() === lower) ?? null;
}

// ---------- Customer-scoped lookups ----------

export function findSubscriptionsByCustomer(subs: readonly Subscription[], customerId: string) {
  return subs.filter((s) => s.customerId === customerId);
}

export function findInvoicesByCustomer(invoices: readonly Invoice[], customerId: string) {
  return invoices.filter((i) => i.customerId === customerId);
}

export function findPaymentsByCustomer(payments: readonly PaymentRecord[], customerId: string) {
  return payments.filter((p) => p.customerId === customerId);
}

// ---------- Plan-scoped lookups ----------

export function findSubscriptionsByPlan(subs: readonly Subscription[], planId: string) {
  return subs.filter((s) => s.planId === planId);
}

// ---------- KPI computations ----------

const MRR_BY_INTERVAL: Record<Subscription["interval"], number> = {
  monthly: 1,
  yearly: 1 / 12,
  weekly: 52 / 12
};

/**
 * Sum of normalized monthly recurring revenue over active + trialing subs.
 * Returns the integer NGN amount.
 */
export function computeMrr(subs: readonly Subscription[]): number {
  return subs.reduce((sum, sub) => {
    if (sub.status !== "active" && sub.status !== "trialing") return sum;
    const factor = MRR_BY_INTERVAL[sub.interval] ?? 1;
    return sum + Math.round(sub.amount * factor);
  }, 0);
}

export function computeActiveSubsCount(subs: readonly Subscription[]): number {
  return subs.filter((s) => s.status === "active" || s.status === "trialing").length;
}

/**
 * Outstanding NGN sitting in past-due / uncollectible invoices that haven't
 * been fully paid yet.
 */
export function computeRevenueAtRisk(invoices: readonly Invoice[]): number {
  return invoices.reduce((sum, inv) => {
    if (inv.status !== "past_due" && inv.status !== "uncollectible") return sum;
    return sum + Math.max(0, inv.amountDue - inv.amountPaid);
  }, 0);
}

/**
 * Total NGN recovered in the current month — sum of `recovered` payments
 * occurring this month relative to the most recent payment in the seed.
 */
export function computeRecoveredMtd(payments: readonly PaymentRecord[]): number {
  if (payments.length === 0) return 0;
  // Anchor "this month" to the latest payment in the dataset so the demo is
  // never empty regardless of when it's viewed.
  const sorted = [...payments].sort((a, b) => (a.occurredAt < b.occurredAt ? 1 : -1));
  const anchor = new Date(sorted[0].occurredAt);
  const yearMonth = `${anchor.getUTCFullYear()}-${String(anchor.getUTCMonth() + 1).padStart(2, "0")}`;
  return payments.reduce((sum, p) => {
    if (p.status !== "recovered") return sum;
    if (!p.occurredAt.startsWith(yearMonth)) return sum;
    return sum + Math.max(0, p.amount);
  }, 0);
}

// ---------- Activity feeds ----------

export function recentAuditEvents(events: readonly AuditEvent[], limit = 6) {
  return [...events]
    .sort((a, b) => (a.occurredAt < b.occurredAt ? 1 : -1))
    .slice(0, limit);
}

export function recentRecoveryItems(items: readonly RecoveryItem[], limit = 5) {
  return [...items]
    .sort((a, b) => {
      const aNext = a.nextRetryAt ?? "";
      const bNext = b.nextRetryAt ?? "";
      return aNext < bNext ? -1 : aNext > bNext ? 1 : 0;
    })
    .slice(0, limit);
}

export function recentWebhookEvents(events: readonly WebhookEventRecord[], limit = 6) {
  return [...events]
    .sort((a, b) => (a.occurredAt < b.occurredAt ? 1 : -1))
    .slice(0, limit);
}

export function failingEndpoints(endpoints: readonly WebhookEndpoint[]) {
  return endpoints.filter((e) => e.status === "failing" || e.successRate < 0.9);
}

// ---------- Formatting helpers (used by Overview, also useful elsewhere) ----------

export function formatCurrency(amount: number, currency: "NGN" | "USD" | "GBP" | "KES" = "NGN") {
  const sign = amount < 0 ? "-" : "";
  const abs = Math.abs(amount);
  const symbol = currency === "NGN" ? "₦" : currency === "USD" ? "$" : currency === "GBP" ? "£" : "KSh ";
  if (abs >= 1_000_000) return `${sign}${symbol}${(abs / 1_000_000).toFixed(2)}M`;
  if (abs >= 1_000) return `${sign}${symbol}${(abs / 1_000).toFixed(1)}K`;
  return `${sign}${symbol}${abs.toLocaleString("en-NG")}`;
}

export function formatRelative(iso: string): string {
  if (!iso || iso === "—") return "—";
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return iso;
  const now = Date.now();
  const diffMs = now - t;
  const minutes = Math.round(diffMs / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  const months = Math.round(days / 30);
  return `${months}mo ago`;
}
