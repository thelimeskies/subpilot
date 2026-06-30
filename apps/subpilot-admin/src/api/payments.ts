/**
 * Cross-tenant payments hook (S5).
 * Backed by GET /api/v1/platform/payments and POST /platform/payments/<id>/refund.
 */
import { useCallback, useEffect, useState } from "react";
import { api, isApiError } from "./client";

export interface PaymentRow {
  id: string;
  rawId: string;
  merchantId: string;
  merchant: string;
  customer: string;
  amount: string;
  status: "Captured" | "Failed" | "Refunded" | "Recovered" | string;
  rawStatus: string;
  method: string;
  reason: string | null;
  occurredAt: string;
  gateway: "Adapter A" | "Adapter B" | string;
  invoiceId: string | null;
  invoiceNumber: string | null;
  raw: {
    amountMinor: number;
    currency: string;
  };
}

interface ListResponse {
  ok: boolean;
  page: number;
  pageSize: number;
  total: number;
  results: PaymentRow[];
}

export interface UsePaymentsParams {
  q?: string;
  status?: string;
  merchantId?: string;
  method?: string;
  gateway?: string;
  dateFrom?: string;
  dateTo?: string;
  page?: number;
  pageSize?: number;
}

export interface RefundPaymentInput {
  rawId: string;
  reason?: string;
  note?: string;
}

export interface RefundPaymentResult {
  id: string;
  status: string;
  refundedAt: string | null;
}

export interface UsePaymentsResult {
  rows: PaymentRow[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  refund: (input: RefundPaymentInput) => Promise<RefundPaymentResult>;
}

function buildQuery(params: UsePaymentsParams): string {
  const usp = new URLSearchParams();
  if (params.q) usp.set("q", params.q);
  if (params.status) usp.set("status", params.status);
  if (params.merchantId) usp.set("merchant_id", params.merchantId);
  if (params.method) usp.set("method", params.method);
  if (params.gateway) usp.set("gateway", params.gateway);
  if (params.dateFrom) usp.set("date_from", params.dateFrom);
  if (params.dateTo) usp.set("date_to", params.dateTo);
  if (params.page) usp.set("page", String(params.page));
  if (params.pageSize) usp.set("page_size", String(params.pageSize));
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function usePayments(params: UsePaymentsParams = {}): UsePaymentsResult {
  const [rows, setRows] = useState<PaymentRow[]>([]);
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
      const body = await api.get<ListResponse>(`/platform/payments${buildQuery(params)}`);
      if (body.ok) {
        setRows(body.results ?? []);
        setTotal(body.total ?? 0);
        setPage(body.page ?? 1);
        setPageSize(body.pageSize ?? 25);
      } else {
        setError("Could not load payments.");
      }
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not load payments.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const refund = useCallback(async (input: RefundPaymentInput): Promise<RefundPaymentResult> => {
    const body = await api.post<{
      ok: boolean;
      id: string;
      status: string;
      refundedAt: string | null;
      reason?: string;
    }>(`/platform/payments/${input.rawId}/refund`, {
      reason: input.reason ?? "",
      note: input.note ?? "",
    });
    if (!body.ok) {
      throw new Error(body.reason || "Refund failed.");
    }
    // Optimistic refresh.
    void reload();
    return { id: body.id, status: body.status, refundedAt: body.refundedAt };
  }, [reload]);

  return { rows, total, page, pageSize, loading, error, reload, refund };
}
