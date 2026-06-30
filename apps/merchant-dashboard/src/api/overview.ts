import { useCallback, useEffect, useMemo, useState } from "react";
import { api, isApiError } from "./client";

export interface MerchantOverviewResponse {
  mrr_minor: number;
  active_subscriptions: number;
  trialing_subscriptions: number;
  past_due_subscriptions: number;
  revenue_at_risk_minor: number;
  recovery_rate_pct: number;
  open_invoices_minor: number;
  currency: string;
}

export interface MerchantOverviewStats {
  mrr: string;
  mrrDelta: string;
  activeSubscriptions: string;
  activeSubscriptionsDelta: string;
  revenueAtRisk: string;
  revenueAtRiskDelta: string;
  recovery: string;
  recoveryDelta: string;
  raw: MerchantOverviewResponse;
}

export interface UseMerchantOverviewResult {
  stats: MerchantOverviewStats | null;
  loading: boolean;
  error: string | null;
  reload: (opts?: { force?: boolean }) => Promise<void>;
}

function formatMoney(minor: number, currency: string): string {
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    maximumFractionDigits: 0
  }).format(minor / 100);
}

function formatRecovery(raw: MerchantOverviewResponse): { value: string; delta: string; toneMetric: "rate" | "open" } {
  if (Number.isFinite(raw.recovery_rate_pct) && raw.recovery_rate_pct > 0) {
    return {
      value: `${raw.recovery_rate_pct.toFixed(1)}%`,
      delta: "Failed-payment recovery rate",
      toneMetric: "rate"
    };
  }

  return {
    value: formatMoney(raw.open_invoices_minor, raw.currency),
    delta: "Open invoices",
    toneMetric: "open"
  };
}

function mapOverview(raw: MerchantOverviewResponse): MerchantOverviewStats {
  const activeTotal = raw.active_subscriptions + raw.trialing_subscriptions;
  const recovery = formatRecovery(raw);

  return {
    mrr: formatMoney(raw.mrr_minor, raw.currency),
    mrrDelta: "Backend analytics snapshot",
    activeSubscriptions: String(activeTotal),
    activeSubscriptionsDelta: `${raw.active_subscriptions} active · ${raw.trialing_subscriptions} trialing`,
    revenueAtRisk: formatMoney(raw.revenue_at_risk_minor, raw.currency),
    revenueAtRiskDelta: `${raw.past_due_subscriptions} past due`,
    recovery: recovery.value,
    recoveryDelta: recovery.delta,
    raw
  };
}

export function useMerchantOverview(): UseMerchantOverviewResult {
  const [raw, setRaw] = useState<MerchantOverviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async ({ force }: { force?: boolean } = {}) => {
    setLoading(true);
    setError(null);
    try {
      const path = force ? "/analytics/overview?refresh=true" : "/analytics/overview";
      setRaw(await api.get<MerchantOverviewResponse>(path));
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not load merchant overview.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload({ force: true });
  }, [reload]);

  const stats = useMemo(() => (raw ? mapOverview(raw) : null), [raw]);

  return { stats, loading, error, reload };
}
