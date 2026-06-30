/**
 * Cross-tenant webhook deliveries hook (S6).
 * Backed by:
 *   GET  /api/v1/platform/webhooks/deliveries
 *   POST /api/v1/platform/webhooks/deliveries/<id>/retry
 *   GET  /api/v1/platform/webhooks/health
 */
import { useCallback, useEffect, useState } from "react";
import { api, isApiError } from "./client";

export interface DeliveryRow {
  id: string;
  rawId: string;
  merchantId: string;
  merchant: string;
  event: string;
  eventId: string;
  endpoint: string;
  endpointId: string;
  status: "Delivered" | "Retrying" | "Failed" | string;
  rawStatus: string;
  attempts: number;
  lastAttempt: string;
  nextAttemptAt: string | null;
  responseCode: number;
  responseBodyExcerpt: string;
}

export interface WebhookHealth {
  windowHours: number;
  delivered: number;
  retrying: number;
  failed: number;
  total: number;
  successRate: number;
}

interface ListResponse {
  ok: boolean;
  page: number;
  pageSize: number;
  total: number;
  results: DeliveryRow[];
}

interface HealthResponse extends WebhookHealth {
  ok: boolean;
}

export interface UseWebhooksParams {
  q?: string;
  status?: string;
  merchantId?: string;
  eventType?: string;
  endpointId?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
}

export interface RetryDeliveryInput {
  rawId: string;
}

export interface RetryDeliveryResult {
  id: string;
  status: string;
  nextAttemptAt: string | null;
  attempts: number;
}

export interface UseWebhooksResult {
  rows: DeliveryRow[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  health: WebhookHealth | null;
  reload: () => Promise<void>;
  retry: (input: RetryDeliveryInput) => Promise<RetryDeliveryResult>;
}

function buildQuery(params: UseWebhooksParams): string {
  const usp = new URLSearchParams();
  if (params.q) usp.set("q", params.q);
  if (params.status) usp.set("status", params.status);
  if (params.merchantId) usp.set("merchant_id", params.merchantId);
  if (params.eventType) usp.set("event_type", params.eventType);
  if (params.endpointId) usp.set("endpoint_id", params.endpointId);
  if (params.dateFrom) usp.set("date_from", params.dateFrom);
  if (params.dateTo) usp.set("date_to", params.dateTo);
  if (params.page) usp.set("page", String(params.page));
  if (params.pageSize) usp.set("page_size", String(params.pageSize));
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function useWebhooks(params: UseWebhooksParams = {}): UseWebhooksResult {
  const [rows, setRows] = useState<DeliveryRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(params.page ?? 1);
  const [pageSize, setPageSize] = useState(params.pageSize ?? 25);
  const [health, setHealth] = useState<WebhookHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const key = JSON.stringify(params);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [listBody, healthBody] = await Promise.all([
        api.get<ListResponse>(`/platform/webhooks/deliveries${buildQuery(params)}`),
        api.get<HealthResponse>(`/platform/webhooks/health`).catch(() => null),
      ]);
      if (listBody.ok) {
        setRows(listBody.results ?? []);
        setTotal(listBody.total ?? 0);
        setPage(listBody.page ?? 1);
        setPageSize(listBody.pageSize ?? 25);
      } else {
        setError("Could not load webhook deliveries.");
      }
      if (healthBody && healthBody.ok) {
        const { ok: _ok, ...rest } = healthBody;
        void _ok;
        setHealth(rest);
      }
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not load webhook deliveries.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const retry = useCallback(async (input: RetryDeliveryInput): Promise<RetryDeliveryResult> => {
    const body = await api.post<{
      ok: boolean;
      id: string;
      status: string;
      nextAttemptAt: string | null;
      attempts: number;
      reason?: string;
    }>(`/platform/webhooks/deliveries/${input.rawId}/retry`, {});
    if (!body.ok) {
      throw new Error(body.reason || "Retry failed.");
    }
    void reload();
    return {
      id: body.id,
      status: body.status,
      nextAttemptAt: body.nextAttemptAt,
      attempts: body.attempts,
    };
  }, [reload]);

  return { rows, total, page, pageSize, loading, error, health, reload, retry };
}
