/**
 * Platform-admin settings hook (S10).
 * Backed by:
 *   GET   /api/v1/platform/settings
 *   PATCH /api/v1/platform/settings   (Owner-only)
 */
import { useCallback, useEffect, useState } from "react";
import { api, isApiError } from "./client";

export interface PlatformPolicy {
  defaultRetryAttempts: number;
  defaultBackoff: string;
  defaultCooldownHours: number;
  webhookSignatureHeader: string;
  webhookSignatureKeyAge: string;
  passwordMinLength: number;
  sessionLifetimeHours: number;
  ipAllowlistEnabled: boolean;
  enforcedMfa: boolean;
  dataRetentionDays: number;
  readOnlyMode: boolean;
  blockNewSignups: boolean;
  webhookDeliveriesEnabled: boolean;
  cardTokenizationEnabled: boolean;
  bankTransferRecoveryEnabled: boolean;
  // Security tab extras
  ssoGoogleEnabled: boolean;
  sessionTimeoutEnabled: boolean;
  blockNewCountriesEnabled: boolean;
  passwordRotationDays: number;
  passwordHistoryCount: number;
  passwordLockoutThreshold: number;
  verifyHmacOnReceipts: boolean;
  enforceTls13: boolean;
  requireIdempotencyKey: boolean;
  allowSelfSignedDevEndpoints: boolean;
  // Data tab extras
  webhookDeliveryRetentionDays: number;
  tokenizedCardRetentionDays: number;
  customerProfileRetention: string;
  // Branding tab
  brandDisplayName: string;
  brandSupportEmail: string;
  brandPrimaryColor: string;
  brandAccentColor: string;
  // Adapters tab routing
  routingStrategy: string;
  autoFailoverOn5xx: boolean;
  retryOnDifferentAdapter: boolean;
  forceFailoverOverride: boolean;
  // Webhooks tab signing + delivery defaults
  webhookSignatureAlgorithm: string;
  webhookTimestampToleranceSeconds: number;
  webhookReplayWindowMinutes: number;
  webhookTimeoutSeconds: number;
  webhookConcurrencyPerMerchant: number;
  subscribedEventTypes: string[];
  // Dunning cadence
  dunningEmailD1: boolean;
  dunningEmailSmsD3: boolean;
  dunningFinalNoticeD7: boolean;
  dunningAutoPauseD10: boolean;
  // Loose typing — backend stores any JSON object so unknown extra keys are tolerated.
  [k: string]: unknown;
}

export interface NombaModeConfig {
  baseUrl: string;
  accountId: string;
  subAccountId: string;
  clientId: string;
  hasClientSecret: boolean;
  hasWebhookSecret: boolean;
}

export interface NombaLiveModeConfig extends NombaModeConfig {
  liveActive: boolean;
}

export interface NombaPlatformConfig {
  activeMode: "test" | "live";
  test: NombaModeConfig;
  live: NombaLiveModeConfig;
}

export interface AdapterRow {
  name: string;
  role: string;
  uptime: string;
  latencyP95: string;
  failoverTrigger: string;
  region: string;
  status: string;
}

export interface PlatformSettings {
  id: string;
  key: string;
  policy: PlatformPolicy;
  nombaPlatform: NombaPlatformConfig;
  adapterStatus: AdapterRow[];
  updatedAt: string;
}

interface ReadResponse {
  ok: boolean;
  settings: PlatformSettings;
  reason?: string;
}

export interface UpdateSettingsInput {
  policy?: Partial<PlatformPolicy>;
  nombaPlatform?: {
    activeMode?: "test" | "live";
    liveActive?: boolean;
    test?: Partial<NombaModeConfig> & { clientSecret?: string; webhookSecret?: string };
    live?: Partial<NombaModeConfig> & { clientSecret?: string; webhookSecret?: string };
  };
  adapterStatus?: AdapterRow[];
}

export interface UseSettingsResult {
  settings: PlatformSettings | null;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  update: (input: UpdateSettingsInput) => Promise<PlatformSettings>;
}

export function useSettings(): UseSettingsResult {
  const [settings, setSettings] = useState<PlatformSettings | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await api.get<ReadResponse>("/platform/settings");
      if (body.ok) {
        setSettings(body.settings);
      } else {
        setError(body.reason || "Could not load settings.");
      }
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not load settings.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void reload();
  }, [reload]);

  const update = useCallback(
    async (input: UpdateSettingsInput): Promise<PlatformSettings> => {
      const payload: Record<string, unknown> = {};
      if (input.policy !== undefined) payload.policy = input.policy;
      if (input.nombaPlatform !== undefined) payload.nomba_platform = input.nombaPlatform;
      if (input.adapterStatus !== undefined) payload.adapter_status = input.adapterStatus;
      const body = await api.patch<ReadResponse>("/platform/settings", payload);
      if (!body.ok) throw new Error(body.reason || "Update failed.");
      setSettings(body.settings);
      return body.settings;
    },
    [],
  );

  return { settings, loading, error, reload, update };
}
