/**
 * Cross-tenant API keys hook (S7).
 * Backed by:
 *   GET  /api/v1/platform/api-keys
 *   POST /api/v1/platform/api-keys/<id>/revoke
 *
 * The platform admin is read-only + revoke; create/rotate are merchant-only.
 */
import { useCallback, useEffect, useState } from "react";
import { api, isApiError } from "./client";

export interface ApiKeyRow {
  id: string;
  rawId: string;
  label: string;
  prefix: string;
  scope: "Live" | "Test" | string;
  rawScope: string;
  createdBy: string;
  createdAt: string;
  lastUsed: string;
  status: "Active" | "Revoked" | string;
  rawStatus: string;
  merchantId: string;
  merchant: string;
  environmentId: string;
}

interface ListResponse {
  ok: boolean;
  page: number;
  pageSize: number;
  total: number;
  results: ApiKeyRow[];
}

export interface UseApiKeysParams {
  q?: string;
  status?: string;
  scope?: string;
  merchantId?: string;
  environmentId?: string;
  page?: number;
  pageSize?: number;
}

export interface RevokeApiKeyInput {
  rawId: string;
}

export interface RevokeApiKeyResult {
  id: string;
  status: string;
  revokedAt: string | null;
}

export interface UseApiKeysResult {
  rows: ApiKeyRow[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  revoke: (input: RevokeApiKeyInput) => Promise<RevokeApiKeyResult>;
}

function buildQuery(params: UseApiKeysParams): string {
  const usp = new URLSearchParams();
  if (params.q) usp.set("q", params.q);
  if (params.status) usp.set("status", params.status);
  if (params.scope) usp.set("scope", params.scope);
  if (params.merchantId) usp.set("merchant_id", params.merchantId);
  if (params.environmentId) usp.set("environment_id", params.environmentId);
  if (params.page) usp.set("page", String(params.page));
  if (params.pageSize) usp.set("page_size", String(params.pageSize));
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function useApiKeys(params: UseApiKeysParams = {}): UseApiKeysResult {
  const [rows, setRows] = useState<ApiKeyRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(params.page ?? 1);
  const [pageSize, setPageSize] = useState(params.pageSize ?? 25);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const key = JSON.stringify(params);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await api.get<ListResponse>(`/platform/api-keys${buildQuery(params)}`);
      if (body.ok) {
        setRows(body.results ?? []);
        setTotal(body.total ?? 0);
        setPage(body.page ?? 1);
        setPageSize(body.pageSize ?? 25);
      } else {
        setError("Could not load API keys.");
      }
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not load API keys.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const revoke = useCallback(async (input: RevokeApiKeyInput): Promise<RevokeApiKeyResult> => {
    const body = await api.post<{
      ok: boolean;
      id: string;
      status: string;
      revokedAt: string | null;
      reason?: string;
    }>(`/platform/api-keys/${input.rawId}/revoke`, {});
    if (!body.ok) {
      throw new Error(body.reason || "Revoke failed.");
    }
    void reload();
    return {
      id: body.id,
      status: body.status,
      revokedAt: body.revokedAt,
    };
  }, [reload]);

  return { rows, total, page, pageSize, loading, error, reload, revoke };
}
