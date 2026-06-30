/**
 * useMerchantConfig — per-merchant operational config (S13).
 *
 * Backed by:
 *   GET   /api/v1/platform/merchants/<id>/config
 *   PATCH /api/v1/platform/merchants/<id>/config   (Owner-only)
 *
 * The PATCH accepts a partial body — only the keys present are merged
 * into the existing JSON columns. Each call returns the full re-resolved
 * bundle so the FE can render the new state without an extra GET.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { api, isApiError } from "./client";

// ---------- Types --------------------------------------------------------

export interface MerchantConfigLimits {
  monthlyVolumeCap: string;
  monthlyVolumeCapMinor: number;
  maxTicketSize: string;
  maxTicketMinor: number;
  highRiskMcc: boolean;
  payoutCadence: string;
  notificationChannel: string;
  notificationChannels: string[];
  currency: string;
}

export interface MerchantConfigRetryPolicy {
  attempts: number;
  backoff: string;
  cooldownHours: number;
}

export interface MerchantConfigFlagRow {
  key: string;
  label: string;
  description: string;
  default: boolean;
  enabled: boolean;
}

export interface MerchantConfigCatalogEntry {
  key: string;
  label: string;
  description: string;
  default: boolean;
}

export interface MerchantConfigWebhookEndpoint {
  id: string;
  url: string;
  events: string[];
  status: string;
  description: string;
}

export interface MerchantConfigBundle {
  merchantId: string;
  limits: MerchantConfigLimits;
  retryPolicy: MerchantConfigRetryPolicy;
  featureFlags: MerchantConfigFlagRow[];
  webhookEndpoints: MerchantConfigWebhookEndpoint[];
  catalog: MerchantConfigCatalogEntry[];
}

interface BundleResponse {
  ok: boolean;
  config: MerchantConfigBundle;
}

interface PatchResponse {
  ok: boolean;
  config: MerchantConfigBundle;
  changed: string[];
}

// Accept both snake_case and camelCase here; the backend tolerates both.
export interface MerchantConfigUpdateInput {
  featureFlags?: Record<string, boolean>;
  feature_flags?: Record<string, boolean>;
  limits?: Partial<{
    monthlyVolumeCapMinor: number;
    maxTicketMinor: number;
    highRiskMcc: boolean;
    payoutCadence: string;
    notificationChannels: string[];
    currency: string;
  }>;
  retryPolicy?: Partial<{
    attempts: number;
    backoff: string;
    cooldownHours: number;
  }>;
  retry_policy?: Partial<{
    attempts: number;
    backoff: string;
    cooldown_hours: number;
  }>;
}

export interface MerchantConfigUpdateResult {
  config: MerchantConfigBundle;
  changed: string[];
}

export interface UseMerchantConfigResult {
  config: MerchantConfigBundle | null;
  loading: boolean;
  notFound: boolean;
  error: string | null;
  saving: boolean;
  saveError: string | null;
  reload: () => Promise<void>;
  update: (input: MerchantConfigUpdateInput) => Promise<MerchantConfigUpdateResult>;
  /**
   * Convenience: flip one flag. Optimistic — local state is updated
   * immediately and rolled back if the PATCH fails.
   */
  setFlag: (key: string, enabled: boolean) => Promise<void>;
}

// ---------- Hook ---------------------------------------------------------

export function useMerchantConfig(merchantId: string | undefined): UseMerchantConfigResult {
  const [config, setConfig] = useState<MerchantConfigBundle | null>(null);
  const [loading, setLoading] = useState<boolean>(Boolean(merchantId));
  const [notFound, setNotFound] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const configRef = useRef<MerchantConfigBundle | null>(null);
  configRef.current = config;

  const reload = useCallback(async () => {
    if (!merchantId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    setNotFound(false);
    try {
      const body = await api.get<BundleResponse>(`/platform/merchants/${merchantId}/config`);
      if (body.ok) {
        setConfig(body.config);
      } else {
        setError("Could not load merchant config.");
      }
    } catch (err) {
      if (isApiError(err) && err.status === 404) setNotFound(true);
      else setError(isApiError(err) ? err.reason : "Could not load merchant config.");
    } finally {
      setLoading(false);
    }
  }, [merchantId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const update = useCallback(
    async (input: MerchantConfigUpdateInput): Promise<MerchantConfigUpdateResult> => {
      if (!merchantId) throw new Error("merchantId is required");
      setSaving(true);
      setSaveError(null);
      try {
        const body = await api.patch<PatchResponse>(
          `/platform/merchants/${merchantId}/config`,
          input
        );
        if (!body.ok) {
          const message = "Could not update merchant config.";
          setSaveError(message);
          throw new Error(message);
        }
        setConfig(body.config);
        return { config: body.config, changed: body.changed ?? [] };
      } catch (err) {
        const reason = isApiError(err) ? err.reason : err instanceof Error ? err.message : "Update failed.";
        setSaveError(reason);
        throw err;
      } finally {
        setSaving(false);
      }
    },
    [merchantId]
  );

  const setFlag = useCallback(
    async (key: string, enabled: boolean) => {
      const snapshot = configRef.current;
      if (snapshot) {
        // Optimistic local update.
        const optimistic: MerchantConfigBundle = {
          ...snapshot,
          featureFlags: snapshot.featureFlags.map((f) =>
            f.key === key ? { ...f, enabled } : f
          ),
        };
        setConfig(optimistic);
      }
      try {
        await update({ featureFlags: { [key]: enabled } });
      } catch (err) {
        // Roll back to last good snapshot.
        if (snapshot) setConfig(snapshot);
        throw err;
      }
    },
    [update]
  );

  return {
    config,
    loading,
    notFound,
    error,
    saving,
    saveError,
    reload,
    update,
    setFlag,
  };
}
