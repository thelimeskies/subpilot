/**
 * Per-tab hooks for the platform-admin Merchant Detail page (S13).
 *
 * Each tab now has its own paginated endpoint instead of being baked into
 * the merchant-detail bundle. These hooks are intentionally narrow and
 * shape-mirror the existing FE seed types so MerchantDetailPage rewiring
 * stays surgical.
 *
 * Backed by:
 *   GET /api/v1/platform/merchants/<id>/subscriptions
 *   GET /api/v1/platform/merchants/<id>/payments
 *   GET /api/v1/platform/merchants/<id>/webhooks
 *   GET /api/v1/platform/merchants/<id>/audit
 */
import { useCallback, useEffect, useState } from "react";
import { api, isApiError } from "./client";
import type { PaymentRow } from "./payments";
import type { DeliveryRow } from "./webhooks";

// ---------- Subscriptions tab --------------------------------------------

export interface MerchantSubscriptionRow {
  id: string;
  rawId: string;
  customer: string;
  plan: string;
  planBucket: string;
  status: string;
  rawStatus: string;
  mrr: string;
  mrrMinor: number;
  currentPeriodEnd: string | null;
  createdAt: string;
}

export interface MerchantSubscriptionStats {
  active: number;
  trialing: number;
  paused: number;
  pastDue: number;
  canceledMtd: number;
  topPlan: string;
  arpu: string;
  arpuMinor: number;
  mrr: string;
  mrrMinor: number;
  currency: string;
}

export interface MerchantPlanMixRow {
  plan: string;
  bucket: string;
  count: number;
  sharePct: number;
}

interface SubscriptionsResponse {
  ok: boolean;
  page: number;
  pageSize: number;
  total: number;
  rows: MerchantSubscriptionRow[];
  stats: MerchantSubscriptionStats;
  planMix: MerchantPlanMixRow[];
}

export interface UseMerchantSubscriptionsParams {
  page?: number;
  pageSize?: number;
  status?: string;
}

export interface UseMerchantSubscriptionsResult {
  rows: MerchantSubscriptionRow[];
  stats: MerchantSubscriptionStats | null;
  planMix: MerchantPlanMixRow[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  notFound: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

function buildSubsQuery(params: UseMerchantSubscriptionsParams): string {
  const usp = new URLSearchParams();
  if (params.page) usp.set("page", String(params.page));
  if (params.pageSize) usp.set("pageSize", String(params.pageSize));
  if (params.status) usp.set("status", params.status);
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function useMerchantSubscriptions(
  merchantId: string | undefined,
  params: UseMerchantSubscriptionsParams = {}
): UseMerchantSubscriptionsResult {
  const [rows, setRows] = useState<MerchantSubscriptionRow[]>([]);
  const [stats, setStats] = useState<MerchantSubscriptionStats | null>(null);
  const [planMix, setPlanMix] = useState<MerchantPlanMixRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(params.page ?? 1);
  const [pageSize, setPageSize] = useState(params.pageSize ?? 25);
  const [loading, setLoading] = useState<boolean>(Boolean(merchantId));
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const key = `${merchantId ?? ""}|${JSON.stringify(params)}`;

  const reload = useCallback(async () => {
    if (!merchantId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const body = await api.get<SubscriptionsResponse>(
        `/platform/merchants/${merchantId}/subscriptions${buildSubsQuery(params)}`
      );
      if (body.ok) {
        setRows(body.rows ?? []);
        setStats(body.stats ?? null);
        setPlanMix(body.planMix ?? []);
        setTotal(body.total ?? 0);
        setPage(body.page ?? 1);
        setPageSize(body.pageSize ?? 25);
      } else {
        setError("Could not load subscriptions.");
      }
    } catch (err) {
      if (isApiError(err) && err.status === 404) setNotFound(true);
      else setError(isApiError(err) ? err.reason : "Could not load subscriptions.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { rows, stats, planMix, total, page, pageSize, loading, notFound, error, reload };
}

// ---------- Payments tab --------------------------------------------------

interface PaymentsResponse {
  ok: boolean;
  page: number;
  pageSize: number;
  total: number;
  rows: PaymentRow[];
}

export interface UseMerchantPaymentsParams {
  page?: number;
  pageSize?: number;
  status?: string;
}

export interface UseMerchantPaymentsResult {
  rows: PaymentRow[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  notFound: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

function buildPaymentsQuery(params: UseMerchantPaymentsParams): string {
  const usp = new URLSearchParams();
  if (params.page) usp.set("page", String(params.page));
  if (params.pageSize) usp.set("pageSize", String(params.pageSize));
  if (params.status) usp.set("status", params.status);
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function useMerchantPayments(
  merchantId: string | undefined,
  params: UseMerchantPaymentsParams = {}
): UseMerchantPaymentsResult {
  const [rows, setRows] = useState<PaymentRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(params.page ?? 1);
  const [pageSize, setPageSize] = useState(params.pageSize ?? 25);
  const [loading, setLoading] = useState<boolean>(Boolean(merchantId));
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const key = `${merchantId ?? ""}|${JSON.stringify(params)}`;

  const reload = useCallback(async () => {
    if (!merchantId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const body = await api.get<PaymentsResponse>(
        `/platform/merchants/${merchantId}/payments${buildPaymentsQuery(params)}`
      );
      if (body.ok) {
        setRows(body.rows ?? []);
        setTotal(body.total ?? 0);
        setPage(body.page ?? 1);
        setPageSize(body.pageSize ?? 25);
      } else {
        setError("Could not load payments.");
      }
    } catch (err) {
      if (isApiError(err) && err.status === 404) setNotFound(true);
      else setError(isApiError(err) ? err.reason : "Could not load payments.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { rows, total, page, pageSize, loading, notFound, error, reload };
}

// ---------- Webhooks tab --------------------------------------------------

interface WebhooksResponse {
  ok: boolean;
  page: number;
  pageSize: number;
  total: number;
  rows: DeliveryRow[];
}

export interface UseMerchantWebhooksParams {
  page?: number;
  pageSize?: number;
  status?: string;
  eventType?: string;
}

export interface UseMerchantWebhooksResult {
  rows: DeliveryRow[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  notFound: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

function buildWebhooksQuery(params: UseMerchantWebhooksParams): string {
  const usp = new URLSearchParams();
  if (params.page) usp.set("page", String(params.page));
  if (params.pageSize) usp.set("pageSize", String(params.pageSize));
  if (params.status) usp.set("status", params.status);
  if (params.eventType) usp.set("eventType", params.eventType);
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function useMerchantWebhooks(
  merchantId: string | undefined,
  params: UseMerchantWebhooksParams = {}
): UseMerchantWebhooksResult {
  const [rows, setRows] = useState<DeliveryRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(params.page ?? 1);
  const [pageSize, setPageSize] = useState(params.pageSize ?? 25);
  const [loading, setLoading] = useState<boolean>(Boolean(merchantId));
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const key = `${merchantId ?? ""}|${JSON.stringify(params)}`;

  const reload = useCallback(async () => {
    if (!merchantId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const body = await api.get<WebhooksResponse>(
        `/platform/merchants/${merchantId}/webhooks${buildWebhooksQuery(params)}`
      );
      if (body.ok) {
        setRows(body.rows ?? []);
        setTotal(body.total ?? 0);
        setPage(body.page ?? 1);
        setPageSize(body.pageSize ?? 25);
      } else {
        setError("Could not load webhook deliveries.");
      }
    } catch (err) {
      if (isApiError(err) && err.status === 404) setNotFound(true);
      else setError(isApiError(err) ? err.reason : "Could not load webhook deliveries.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { rows, total, page, pageSize, loading, notFound, error, reload };
}

// ---------- Audit tab -----------------------------------------------------

export interface MerchantAuditRow {
  id: string;
  rawId: string;
  action: string;
  detail: string;
  actor: string;
  actorRole: string;
  targetType: string;
  targetId: string;
  occurredAt: string;
  metadata: Record<string, unknown>;
}

interface AuditResponse {
  ok: boolean;
  page: number;
  pageSize: number;
  total: number;
  rows: MerchantAuditRow[];
}

export interface UseMerchantAuditParams {
  page?: number;
  pageSize?: number;
  action?: string;
}

export interface UseMerchantAuditResult {
  rows: MerchantAuditRow[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  notFound: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

function buildAuditQuery(params: UseMerchantAuditParams): string {
  const usp = new URLSearchParams();
  if (params.page) usp.set("page", String(params.page));
  if (params.pageSize) usp.set("pageSize", String(params.pageSize));
  if (params.action) usp.set("action", params.action);
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function useMerchantAudit(
  merchantId: string | undefined,
  params: UseMerchantAuditParams = {}
): UseMerchantAuditResult {
  const [rows, setRows] = useState<MerchantAuditRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(params.page ?? 1);
  const [pageSize, setPageSize] = useState(params.pageSize ?? 25);
  const [loading, setLoading] = useState<boolean>(Boolean(merchantId));
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const key = `${merchantId ?? ""}|${JSON.stringify(params)}`;

  const reload = useCallback(async () => {
    if (!merchantId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const body = await api.get<AuditResponse>(
        `/platform/merchants/${merchantId}/audit${buildAuditQuery(params)}`
      );
      if (body.ok) {
        setRows(body.rows ?? []);
        setTotal(body.total ?? 0);
        setPage(body.page ?? 1);
        setPageSize(body.pageSize ?? 25);
      } else {
        setError("Could not load audit log.");
      }
    } catch (err) {
      if (isApiError(err) && err.status === 404) setNotFound(true);
      else setError(isApiError(err) ? err.reason : "Could not load audit log.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { rows, total, page, pageSize, loading, notFound, error, reload };
}
