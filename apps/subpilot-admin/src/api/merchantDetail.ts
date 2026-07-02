/**
 * Hook + types for the platform-admin merchant detail surface (S4).
 * Backed by:
 *   GET    /api/v1/platform/merchants/<id>
 *   POST   /api/v1/platform/merchants/<id>/suspend
 *   POST   /api/v1/platform/merchants/<id>/reactivate
 *   POST   /api/v1/platform/merchants/<id>/notes
 *   POST   /api/v1/platform/merchants/<id>/webhooks/rotate-secret
 *   POST   /api/v1/platform/merchants/<id>/force-close
 *   POST   /api/v1/platform/merchants/<id>/impersonate
 *   POST   /api/v1/platform/payments/<id>/refund        (cross-tenant)
 *   POST   /api/v1/platform/webhooks/deliveries/<id>/retry (cross-tenant)
 *   PATCH  /api/v1/platform/kyc/<id>                    (cross-tenant)
 *   PATCH  /api/v1/platform/merchants/<id>/config       (cross-tenant)
 */
import { useCallback, useEffect, useState } from "react";
import { api, isApiError } from "./client";

export interface MerchantDetailEnvironment {
  id: string;
  mode: "live" | "test" | string;
  label: "Live" | "Test" | string;
}

export interface MerchantDetailPayment {
  id: string;
  amount: string;
  status: "Captured" | "Failed" | "Pending" | "Refunded" | "Recovered" | string;
  method: string;
  customer: string;
  occurredAt: string;
  raw: { amountMinor: number; currency: string };
}

export interface MerchantDetailAuditEntry {
  id: string;
  action: string;
  detail: string;
  actor: string;
  actorRole: string;
  occurredAt: string;
}

export interface MerchantDetailKyc {
  status: string;
  level: string;
  documents: Array<{ kind: string; status: string; uploadedAt: string; fileName?: string; dataUrl?: string; url?: string }>;
  flags: string[];
  notes: string;
  reviewer: string;
  submittedAt: string;
  reviewedAt: string;
}

export interface MerchantDetailNote {
  id: string;
  body: string;
  author: string;
  createdAt: string;
}

export interface MerchantDetailSubscriptionStats {
  active: number;
  trialing: number;
  paused: number;
  pastDue: number;
  canceledMtd: number;
  churnRate: string;
  topPlan: string;
  arpu: string;
}

export interface MerchantDetail {
  id: string;
  name: string;
  slug: string;
  owner: string;
  ownerEmail: string;
  plan: string;
  mrr: string;
  status: "Healthy" | "At risk" | "Suspended" | string;
  rawStatus: string;
  failedInvoices: number;
  recoveryRate: string;
  environment: "Live" | "Test" | string;
  createdAt: string;
  region: string;
  monthlyVolume: string;
  activeSubscriptions: number;
  subscriptionStats: MerchantDetailSubscriptionStats;
  environments: MerchantDetailEnvironment[];
  recentPayments: MerchantDetailPayment[];
  recentAudit: MerchantDetailAuditEntry[];
  kyc: MerchantDetailKyc | null;
  notes: MerchantDetailNote[];
  raw: {
    mrrMinor: number;
    monthlyVolumeMinor: number;
    recoveryRatePct: number;
    currency: string;
    arpuMinor: number;
  };
}

interface DetailResponse {
  ok: boolean;
  merchant: MerchantDetail;
}

export interface UseMerchantDetailResult {
  detail: MerchantDetail | null;
  loading: boolean;
  notFound: boolean;
  error: string | null;
  reload: () => Promise<void>;
  suspend: (input?: { reason?: string; note?: string }) => Promise<void>;
  reactivate: (input?: { note?: string }) => Promise<void>;
  addNote: (input: { body: string; visibility?: string }) => Promise<void>;
  rotateWebhookSecret: (input?: { gracePeriod?: string }) => Promise<{ fingerprint: string; rotatedAt: string; gracePeriod: string }>;
  forceClose: (input?: { note?: string }) => Promise<void>;
  impersonate: () => Promise<{ redirectUrl: string; userId: string; userEmail: string; userName: string; expiresIn: number }>;
  refundPayment: (input: { paymentId: string; reason?: string; note?: string }) => Promise<{ id: string; status: string }>;
  retryWebhook: (input: { deliveryId: string }) => Promise<{ id: string; status: string }>;
  runKycReview: (input?: { level?: string; notes?: string }) => Promise<void>;
  updateConfig: (input: {
    featureFlags?: Record<string, boolean>;
    limits?: Record<string, unknown>;
    retryPolicy?: { attempts?: number; backoff?: string; cooldownHours?: number };
  }) => Promise<void>;
}

export function useMerchantDetail(merchantId: string | undefined): UseMerchantDetailResult {
  const [detail, setDetail] = useState<MerchantDetail | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(merchantId));
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    if (!merchantId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const body = await api.get<DetailResponse>(`/platform/merchants/${merchantId}`);
      if (body.ok) {
        setDetail(body.merchant);
      } else {
        setError("Could not load merchant.");
      }
    } catch (err) {
      if (isApiError(err) && err.status === 404) {
        setNotFound(true);
      } else {
        setError(isApiError(err) ? err.reason : "Could not load merchant.");
      }
    } finally {
      setLoading(false);
    }
  }, [merchantId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const suspend = useCallback(
    async (input?: { reason?: string; note?: string }) => {
      if (!merchantId) return;
      await api.post(`/platform/merchants/${merchantId}/suspend`, input ?? {});
      await reload();
    },
    [merchantId, reload]
  );

  const reactivate = useCallback(
    async (input?: { note?: string }) => {
      if (!merchantId) return;
      await api.post(`/platform/merchants/${merchantId}/reactivate`, input ?? {});
      await reload();
    },
    [merchantId, reload]
  );

  const addNote = useCallback(
    async (input: { body: string; visibility?: string }) => {
      if (!merchantId) return;
      await api.post(`/platform/merchants/${merchantId}/notes`, input);
      await reload();
    },
    [merchantId, reload]
  );

  const rotateWebhookSecret = useCallback(
    async (input?: { gracePeriod?: string }) => {
      if (!merchantId) throw new Error("Missing merchant id.");
      const body = await api.post<{
        ok: boolean;
        fingerprint: string;
        rotatedAt: string;
        gracePeriod: string;
        reason?: string;
      }>(`/platform/merchants/${merchantId}/webhooks/rotate-secret`, {
        grace_period: input?.gracePeriod ?? "24h",
      });
      if (!body.ok) throw new Error(body.reason || "Could not rotate secret.");
      return { fingerprint: body.fingerprint, rotatedAt: body.rotatedAt, gracePeriod: body.gracePeriod };
    },
    [merchantId]
  );

  const forceClose = useCallback(
    async (input?: { note?: string }) => {
      if (!merchantId) return;
      const body = await api.post<{ ok: boolean; reason?: string }>(
        `/platform/merchants/${merchantId}/force-close`,
        { note: input?.note ?? "" },
      );
      if (!body.ok) throw new Error(body.reason || "Could not close merchant.");
      await reload();
    },
    [merchantId, reload]
  );

  const impersonate = useCallback(
    async () => {
      if (!merchantId) throw new Error("Missing merchant id.");
      const body = await api.post<{
        ok: boolean;
        redirectUrl: string;
        userId: string;
        userEmail: string;
        userName: string;
        expiresIn: number;
        reason?: string;
      }>(`/platform/merchants/${merchantId}/impersonate`, {});
      if (!body.ok) throw new Error(body.reason || "Could not start impersonation session.");
      return {
        redirectUrl: body.redirectUrl,
        userId: body.userId,
        userEmail: body.userEmail,
        userName: body.userName,
        expiresIn: body.expiresIn,
      };
    },
    [merchantId]
  );

  const refundPayment = useCallback(
    async (input: { paymentId: string; reason?: string; note?: string }) => {
      const body = await api.post<{
        ok: boolean;
        id: string;
        status: string;
        refundedAt: string | null;
        reason?: string;
      }>(`/platform/payments/${input.paymentId}/refund`, {
        reason: input.reason ?? "",
        note: input.note ?? "",
      });
      if (!body.ok) throw new Error(body.reason || "Refund failed.");
      await reload();
      return { id: body.id, status: body.status };
    },
    [reload]
  );

  const retryWebhook = useCallback(
    async (input: { deliveryId: string }) => {
      const body = await api.post<{
        ok: boolean;
        id: string;
        status: string;
        reason?: string;
      }>(`/platform/webhooks/deliveries/${input.deliveryId}/retry`, {});
      if (!body.ok) throw new Error(body.reason || "Retry failed.");
      return { id: body.id, status: body.status };
    },
    []
  );

  const runKycReview = useCallback(
    async (input?: { level?: string; notes?: string }) => {
      if (!merchantId) return;
      const payload: Record<string, unknown> = { status: "In review" };
      if (input?.level) payload.level = input.level;
      if (input?.notes) payload.notes = input.notes;
      const body = await api.patch<{ ok: boolean; reason?: string }>(
        `/platform/kyc/${merchantId}`,
        payload,
      );
      if (!body.ok) throw new Error(body.reason || "Could not re-run KYC review.");
      await reload();
    },
    [merchantId, reload]
  );

  const updateConfig = useCallback(
    async (input: {
      featureFlags?: Record<string, boolean>;
      limits?: Record<string, unknown>;
      retryPolicy?: { attempts?: number; backoff?: string; cooldownHours?: number };
    }) => {
      if (!merchantId) return;
      const payload: Record<string, unknown> = {};
      if (input.featureFlags) payload.feature_flags = input.featureFlags;
      if (input.limits) payload.limits = input.limits;
      if (input.retryPolicy) payload.retry_policy = input.retryPolicy;
      const body = await api.patch<{ ok: boolean; reason?: string }>(
        `/platform/merchants/${merchantId}/config`,
        payload,
      );
      if (!body.ok) throw new Error(body.reason || "Could not save configuration.");
      await reload();
    },
    [merchantId, reload]
  );

  return {
    detail,
    loading,
    notFound,
    error,
    reload,
    suspend,
    reactivate,
    addNote,
    rotateWebhookSecret,
    forceClose,
    impersonate,
    refundPayment,
    retryWebhook,
    runKycReview,
    updateConfig,
  };
}
