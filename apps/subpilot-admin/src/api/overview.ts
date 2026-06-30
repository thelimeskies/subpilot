/**
 * Hook + types for the platform overview snapshot.
 * Backed by GET /api/v1/platform/overview.
 */
import { useCallback, useEffect, useState } from "react";
import { api, isApiError } from "./client";

export interface PlatformStats {
  liveMerchants: number;
  liveMerchantsDelta: string;
  mrr: string;
  mrrDelta: string;
  revenueAtRisk: string;
  revenueAtRiskDelta: string;
  webhookHealth: string;
  webhookHealthDelta: string;
  recoveredThisMonth: string;
  recoveryRate: string;
  raw: {
    liveMerchants: number;
    liveMerchantsDelta: number;
    mrrMinor: number;
    mrrDeltaPct: number;
    revenueAtRiskMinor: number;
    failedInvoiceCount: number;
    webhookHealthPct: number;
    webhookRetriesInFlight: number;
    recoveredThisMonthMinor: number;
    recoveryRatePct: number;
    currency: string;
  };
}

interface OverviewResponse {
  ok: boolean;
  stats: PlatformStats;
}

export interface UseOverviewResult {
  stats: PlatformStats | null;
  loading: boolean;
  error: string | null;
  reload: (opts?: { force?: boolean }) => Promise<void>;
}

export function useOverview(): UseOverviewResult {
  const [stats, setStats] = useState<PlatformStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async ({ force }: { force?: boolean } = {}) => {
    setLoading(true);
    setError(null);
    try {
      const path = force ? "/platform/overview?refresh=true" : "/platform/overview";
      const body = await api.get<OverviewResponse>(path);
      if (body.ok && body.stats) {
        setStats(body.stats);
      } else {
        setError("Could not load overview.");
      }
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not load overview.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { stats, loading, error, reload };
}
