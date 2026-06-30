import { api } from "./client";
import { defaultSettings, org as seedOrg, type MerchantOrg, type MerchantSettings } from "../data/seed";

interface BackendWorkspaceOrg {
  id: string;
  legal_name?: string | null;
  trading_name?: string | null;
  country?: string | null;
  timezone?: string | null;
  currency?: string | null;
  tax_id?: string | null;
  statement_descriptor?: string | null;
  brand_color?: string | null;
  portal_subdomain?: string | null;
  created_at?: string | null;
}

interface BackendWorkspaceDunning {
  schedule?: number[] | null;
  max_attempts?: number | null;
  grace_days?: number | null;
  final_action?: string | null;
}

interface BackendWorkspaceSettingsDocument {
  branding?: {
    primary_color?: string | null;
    logo_url?: string | null;
    logo_data?: string | null;
    portal_subdomain?: string | null;
  } | null;
  payouts?: {
    bank?: string | null;
    account_number?: string | null;
    settlement_frequency?: string | null;
    descriptor?: string | null;
    paused?: boolean | null;
  } | null;
  plan_defaults?: {
    trial_days?: number | null;
    proration?: string | null;
    currency?: string | null;
    tax_behavior?: string | null;
  } | null;
  dunning_templates?: Array<{
    id: string;
    label: string;
    body: string;
  }> | null;
  notifications?: Record<string, Record<string, boolean>> | null;
  security?: {
    require_mfa?: boolean | null;
    ip_allowlist?: string[] | null;
    session_timeout_minutes?: number | null;
  } | null;
  portal?: {
    allow_cancel?: boolean | null;
    allow_pause?: boolean | null;
    allow_change_plan?: boolean | null;
    success_url?: string | null;
    cancel_url?: string | null;
  } | null;
}

export interface BackendWorkspaceSettings {
  org: BackendWorkspaceOrg;
  dunning: BackendWorkspaceDunning;
  settings?: BackendWorkspaceSettingsDocument | null;
}

export interface WorkspaceSettingsResource {
  org: MerchantOrg;
  settings: MerchantSettings;
}

export interface WorkspaceExportRequest {
  id: string;
  status: "queued" | "processing" | "ready" | "failed";
  requested_at: string;
  estimated_ready_at: string;
  delivery_email: string;
}

export interface WorkspaceForceSignOutResult {
  ok: true;
  sessionsInvalidated: number;
}

export interface WorkspaceTransferOwnershipResult {
  ok: true;
  new_owner: unknown;
  previous_owner: unknown;
}

export interface WorkspaceCloseResult {
  ok: true;
  status: "closed";
  sessionsInvalidated: number;
}

function currency(value: string | null | undefined): MerchantOrg["currency"] {
  const normalized = (value ?? seedOrg.currency).toUpperCase();
  return normalized === "USD" || normalized === "GBP" || normalized === "KES" ? normalized : "NGN";
}

function finalAction(value: string | null | undefined): MerchantSettings["dunning"]["finalAction"] {
  return value === "cancel" ? "cancel" : "uncollectible";
}

function settlementFrequency(value: string | null | undefined): MerchantOrg["settlementFrequency"] {
  return value === "weekly" || value === "monthly" ? value : "daily";
}

function proration(value: string | null | undefined): MerchantSettings["planDefaults"]["proration"] {
  return value === "none" ? "none" : "create_proration";
}

function taxBehavior(value: string | null | undefined): MerchantSettings["planDefaults"]["taxBehavior"] {
  return value === "inclusive" ? "inclusive" : "exclusive";
}

export function mapWorkspaceSettings(payload: BackendWorkspaceSettings): WorkspaceSettingsResource {
  const backendOrg = payload.org;
  const backendSettings = payload.settings ?? {};
  const mappedOrg: MerchantOrg = {
    ...seedOrg,
    id: backendOrg.id,
    legalName: backendOrg.legal_name || backendOrg.trading_name || seedOrg.legalName,
    tradingName: backendOrg.trading_name || backendOrg.legal_name || seedOrg.tradingName,
    country: backendOrg.country || seedOrg.country,
    timezone: backendOrg.timezone || seedOrg.timezone,
    currency: currency(backendOrg.currency),
    brandColor: backendSettings.branding?.primary_color || backendOrg.brand_color || seedOrg.brandColor,
    portalSubdomain: backendSettings.branding?.portal_subdomain || backendOrg.portal_subdomain || seedOrg.portalSubdomain,
    taxId: backendOrg.tax_id || seedOrg.taxId,
    statementDescriptor: backendOrg.statement_descriptor || seedOrg.statementDescriptor,
    createdAt: backendOrg.created_at ? backendOrg.created_at.slice(0, 10) : seedOrg.createdAt
  };

  const dunning = payload.dunning;
  const settings: MerchantSettings = {
    ...defaultSettings,
    branding: {
      ...defaultSettings.branding,
      primaryColor: backendSettings.branding?.primary_color || mappedOrg.brandColor,
      logoUrl: backendSettings.branding?.logo_url ?? backendSettings.branding?.logo_data ?? defaultSettings.branding.logoUrl,
      portalSubdomain: backendSettings.branding?.portal_subdomain || mappedOrg.portalSubdomain
    },
    payouts: {
      ...defaultSettings.payouts,
      bank: backendSettings.payouts?.bank || defaultSettings.payouts.bank,
      accountNumber: backendSettings.payouts?.account_number || defaultSettings.payouts.accountNumber,
      settlementFrequency: settlementFrequency(backendSettings.payouts?.settlement_frequency),
      descriptor: backendSettings.payouts?.descriptor || mappedOrg.statementDescriptor,
      paused: backendSettings.payouts?.paused ?? defaultSettings.payouts.paused
    },
    planDefaults: {
      ...defaultSettings.planDefaults,
      trialDays: backendSettings.plan_defaults?.trial_days ?? defaultSettings.planDefaults.trialDays,
      proration: proration(backendSettings.plan_defaults?.proration),
      currency: currency(backendSettings.plan_defaults?.currency ?? mappedOrg.currency),
      taxBehavior: taxBehavior(backendSettings.plan_defaults?.tax_behavior)
    },
    dunning: {
      schedule: dunning.schedule?.length ? dunning.schedule : defaultSettings.dunning.schedule,
      maxAttempts: dunning.max_attempts ?? defaultSettings.dunning.maxAttempts,
      graceDays: dunning.grace_days ?? defaultSettings.dunning.graceDays,
      finalAction: finalAction(dunning.final_action)
    },
    dunningTemplates: backendSettings.dunning_templates?.length
      ? backendSettings.dunning_templates
      : defaultSettings.dunningTemplates,
    notifications: backendSettings.notifications ?? defaultSettings.notifications,
    security: {
      ...defaultSettings.security,
      requireMfa: backendSettings.security?.require_mfa ?? defaultSettings.security.requireMfa,
      ipAllowlist: backendSettings.security?.ip_allowlist ?? defaultSettings.security.ipAllowlist,
      sessionTimeoutMinutes: backendSettings.security?.session_timeout_minutes ?? defaultSettings.security.sessionTimeoutMinutes
    },
    portal: {
      ...defaultSettings.portal,
      allowCancel: backendSettings.portal?.allow_cancel ?? defaultSettings.portal.allowCancel,
      allowPause: backendSettings.portal?.allow_pause ?? defaultSettings.portal.allowPause,
      allowChangePlan: backendSettings.portal?.allow_change_plan ?? defaultSettings.portal.allowChangePlan,
      successUrl: backendSettings.portal?.success_url || defaultSettings.portal.successUrl,
      cancelUrl: backendSettings.portal?.cancel_url || defaultSettings.portal.cancelUrl
    }
  };

  return { org: mappedOrg, settings };
}

export async function loadWorkspaceSettings(): Promise<WorkspaceSettingsResource> {
  const payload = await api.get<BackendWorkspaceSettings>("/workspace-settings/");
  return mapWorkspaceSettings(payload);
}

export async function updateWorkspaceOrg(patch: Partial<MerchantOrg>): Promise<WorkspaceSettingsResource> {
  const payload = await api.patch<BackendWorkspaceSettings>("/workspace-settings/", {
    org: {
      legal_name: patch.legalName,
      trading_name: patch.tradingName,
      country: patch.country,
      timezone: patch.timezone,
      currency: patch.currency,
      tax_id: patch.taxId,
      statement_descriptor: patch.statementDescriptor
    }
  });
  return mapWorkspaceSettings(payload);
}

export async function updateWorkspaceDunning(
  dunning: MerchantSettings["dunning"]
): Promise<WorkspaceSettingsResource> {
  const payload = await api.patch<BackendWorkspaceSettings>("/workspace-settings/", {
    dunning: {
      schedule: dunning.schedule,
      max_attempts: dunning.maxAttempts,
      grace_days: dunning.graceDays,
      final_action: dunning.finalAction
    }
  });
  return mapWorkspaceSettings(payload);
}

export async function updateWorkspaceSettings(
  patch: Partial<MerchantSettings>
): Promise<WorkspaceSettingsResource> {
  const payload = await api.patch<BackendWorkspaceSettings>("/workspace-settings/", {
    branding: patch.branding
      ? {
          primary_color: patch.branding.primaryColor,
          logo_url: patch.branding.logoUrl,
          portal_subdomain: patch.branding.portalSubdomain
        }
      : undefined,
    payouts: patch.payouts
      ? {
          bank: patch.payouts.bank,
          account_number: patch.payouts.accountNumber,
          settlement_frequency: patch.payouts.settlementFrequency,
          descriptor: patch.payouts.descriptor,
          paused: patch.payouts.paused
        }
      : undefined,
    plan_defaults: patch.planDefaults
      ? {
          trial_days: patch.planDefaults.trialDays,
          proration: patch.planDefaults.proration,
          currency: patch.planDefaults.currency,
          tax_behavior: patch.planDefaults.taxBehavior
        }
      : undefined,
    dunning_templates: patch.dunningTemplates,
    notifications: patch.notifications,
    security: patch.security
      ? {
          require_mfa: patch.security.requireMfa,
          ip_allowlist: patch.security.ipAllowlist,
          session_timeout_minutes: patch.security.sessionTimeoutMinutes
        }
      : undefined,
    portal: patch.portal
      ? {
          allow_cancel: patch.portal.allowCancel,
          allow_pause: patch.portal.allowPause,
          allow_change_plan: patch.portal.allowChangePlan,
          success_url: patch.portal.successUrl,
          cancel_url: patch.portal.cancelUrl
        }
      : undefined
  });
  return mapWorkspaceSettings(payload);
}

export async function exportWorkspaceData(): Promise<WorkspaceExportRequest> {
  return api.post<WorkspaceExportRequest>("/workspace-settings/export/", {});
}

export async function forceWorkspaceSignOut(): Promise<WorkspaceForceSignOutResult> {
  return api.post<WorkspaceForceSignOutResult>("/workspace-settings/force-sign-out/", {});
}

export async function transferWorkspaceOwnership(newOwnerEmail: string): Promise<WorkspaceTransferOwnershipResult> {
  return api.post<WorkspaceTransferOwnershipResult>("/workspace-settings/transfer-ownership/", {
    new_owner_email: newOwnerEmail
  });
}

export async function closeWorkspace(confirmTradingName: string): Promise<WorkspaceCloseResult> {
  return api.post<WorkspaceCloseResult>("/workspace-settings/close/", {
    confirm_trading_name: confirmTradingName
  });
}
