/**
 * Platform-admin analytics hook (S11).
 * Backed by:
 *   GET /api/v1/platform/analytics?range=3m|6m|12m[&refresh=true]
 *
 * Returns a single bundled snapshot mirroring the seven seed-shape sections
 * previously hard-coded in apps/subpilot-admin/src/data/seed.ts.
 */
import { useCallback, useEffect, useState } from "react";
import { api, isApiError } from "./client";

export type AnalyticsRange = "3m" | "6m" | "12m";

export interface RevenuePoint {
  month: string;
  mrr: number;
  newMrr: number;
  churnMrr: number;
  expansionMrr: number;
  gmv: number;
  activeSubs: number;
}

export interface PlanRevenueRow {
  plan: string;
  merchants: number;
  activeSubs: number;
  mrr: string;
  share: number;
  arpu: string;
  churn: string;
}

export interface RegionRevenueRow {
  region: string;
  mrr: string;
  share: number;
  merchants: number;
  growth: string;
  topAdapter: string;
}

export interface CohortRow {
  cohort: string;
  size: number;
  retention: number[];
}

export interface FunnelStep {
  label: string;
  count: number;
  delta?: string;
}

export interface PaymentMethodRow {
  method: string;
  share: number;
  successRate: string;
  avgTicket: string;
}

export interface RecoveryFunnelChannel {
  channel: string;
  count: number;
  share: number;
}

export interface RecoveryFunnel {
  failedThisMonth: number;
  recovered: number;
  pending: number;
  lost: number;
  recoveryRate: string;
  recoveredMrr: string;
  byChannel: RecoveryFunnelChannel[];
}

export interface TopMerchantRow {
  id: string;
  name: string;
  mrr: string;
  growth: string;
  region: string;
}

export interface PlatformAnalytics {
  range: AnalyticsRange;
  revenueSeries: RevenuePoint[];
  planRevenue: PlanRevenueRow[];
  regionRevenue: RegionRevenueRow[];
  retentionCohorts: CohortRow[];
  acquisitionFunnel: FunnelStep[];
  paymentMethodMix: PaymentMethodRow[];
  recoveryFunnel: RecoveryFunnel;
  topMerchantsByRevenue: TopMerchantRow[];
}

interface ReadResponse {
  ok: boolean;
  analytics: PlatformAnalytics;
  reason?: string;
}

export interface UseAnalyticsResult {
  analytics: PlatformAnalytics | null;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  reload: () => Promise<void>;
  refresh: () => Promise<void>;
}

export function useAnalytics(range: AnalyticsRange): UseAnalyticsResult {
  const [analytics, setAnalytics] = useState<PlatformAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchSnapshot = useCallback(
    async (opts: { refresh?: boolean } = {}) => {
      const params = new URLSearchParams({ range });
      if (opts.refresh) params.set("refresh", "true");
      const path = `/platform/analytics?${params.toString()}`;
      const body = await api.get<ReadResponse>(path);
      if (!body.ok) throw new Error(body.reason || "Could not load analytics.");
      return body.analytics;
    },
    [range],
  );

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const snapshot = await fetchSnapshot();
      setAnalytics(snapshot);
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not load analytics.");
    } finally {
      setLoading(false);
    }
  }, [fetchSnapshot]);

  const refresh = useCallback(async () => {
    setRefreshing(true);
    setError(null);
    try {
      const snapshot = await fetchSnapshot({ refresh: true });
      setAnalytics(snapshot);
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not refresh analytics.");
    } finally {
      setRefreshing(false);
    }
  }, [fetchSnapshot]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { analytics, loading, refreshing, error, reload, refresh };
}
