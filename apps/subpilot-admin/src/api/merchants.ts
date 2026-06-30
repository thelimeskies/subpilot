/**
 * Hook + types for the cross-tenant merchants list.
 * Backed by GET /api/v1/platform/merchants.
 */
import { useCallback, useEffect, useState } from "react";
import { api, isApiError } from "./client";

export interface MerchantRow {
  id: string;
  name: string;
  owner: string;
  ownerEmail: string;
  plan: "Starter" | "Growth" | "Enterprise" | "Internal" | string;
  mrr: string;
  status: "Healthy" | "At risk" | "Suspended" | string;
  failedInvoices: number;
  recoveryRate: string;
  environment: "Live" | "Test" | string;
  createdAt: string;
  region: string;
  monthlyVolume: string;
  activeSubscriptions: number;
  raw: {
    mrrMinor: number;
    monthlyVolumeMinor: number;
    recoveryRatePct: number;
    currency: string;
  };
}

interface ListResponse {
  ok: boolean;
  page: number;
  pageSize: number;
  total: number;
  results: MerchantRow[];
}

export interface UseMerchantsParams {
  q?: string;
  status?: string;
  plan?: string;
  region?: string;
  environment?: string;
  page?: number;
  pageSize?: number;
}

export interface UseMerchantsResult {
  rows: MerchantRow[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

function buildQuery(params: UseMerchantsParams): string {
  const usp = new URLSearchParams();
  if (params.q) usp.set("q", params.q);
  if (params.status) usp.set("status", params.status);
  if (params.plan) usp.set("plan", params.plan);
  if (params.region) usp.set("region", params.region);
  if (params.environment) usp.set("environment", params.environment);
  if (params.page) usp.set("page", String(params.page));
  if (params.pageSize) usp.set("page_size", String(params.pageSize));
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function useMerchants(params: UseMerchantsParams = {}): UseMerchantsResult {
  const [rows, setRows] = useState<MerchantRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(params.page ?? 1);
  const [pageSize, setPageSize] = useState(params.pageSize ?? 25);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Stable serialised key to drive the effect.
  const key = JSON.stringify(params);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await api.get<ListResponse>(`/platform/merchants${buildQuery(params)}`);
      if (body.ok) {
        setRows(body.results ?? []);
        setTotal(body.total ?? 0);
        setPage(body.page ?? 1);
        setPageSize(body.pageSize ?? 25);
      } else {
        setError("Could not load merchants.");
      }
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not load merchants.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { rows, total, page, pageSize, loading, error, reload };
}
