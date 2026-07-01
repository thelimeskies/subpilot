import { api } from "./client";
import type { WebhookEndpoint, WebhookEvent, WebhookEventRecord } from "../data/seed";

export type NombaIntegrationMode = "platform" | "byok";

export interface NombaIntegrationConfig {
  mode: "test" | "live";
  integrationMode: NombaIntegrationMode;
  accountId: string;
  clientId: string;
  hasClientSecret: boolean;
  hasWebhookSecret: boolean;
  subAccountId: string;
  credentialsValidatedAt: string | null;
  liveActive: boolean;
  lastValidation: Record<string, unknown>;
  tokenExpiresAt: string | null;
}

export interface NombaCredentialInput {
  integrationMode: NombaIntegrationMode;
  accountId: string;
  clientId: string;
  clientSecret?: string;
  webhookSecret?: string;
  subAccountId: string;
}

interface WebhookEndpointResponse {
  endpoint: {
    id: string;
  };
  secret?: string;
}

function eventFilters(events: WebhookEvent[]): string[] {
  return events;
}

export async function retryInvoicePayment(invoiceId: string, paymentMethodId?: string): Promise<void> {
  await api.post(`/payment-attempts/charge/${invoiceId}/`, {
    payment_method_id: paymentMethodId || null,
    adapter: "mock"
  });
}

export async function markInvoiceUncollectible(invoiceId: string): Promise<void> {
  await api.post(`/invoices/${invoiceId}/uncollectible/`, {
    reason: "Marked uncollectible from merchant recovery cockpit"
  });
}

export async function cancelDunningRun(runId: string, reason: string): Promise<void> {
  await api.post(`/dunning-runs/${runId}/cancel/`, { reason });
}

export async function pauseDunningRun(runId: string, reason: string, pausedUntil?: string): Promise<void> {
  await api.post(`/dunning-runs/${runId}/pause/`, {
    reason,
    paused_until: pausedUntil ?? null
  });
}

export async function resumeDunningRun(runId: string): Promise<void> {
  await api.post(`/dunning-runs/${runId}/resume/`, {});
}

export async function createBackendWebhookEndpoint(
  input: Omit<WebhookEndpoint, "id" | "createdAt" | "lastDeliveryAt" | "successRate">
): Promise<{ id: string; secret: string | null }> {
  const body = await api.post<WebhookEndpointResponse>("/webhook-endpoints/", {
    url: input.url,
    description: "",
    event_filters: eventFilters(input.events),
    enabled: input.status !== "disabled"
  });
  return { id: body.endpoint.id, secret: body.secret ?? null };
}

export async function updateBackendWebhookEndpoint(id: string, patch: Partial<WebhookEndpoint>): Promise<void> {
  await api.patch(`/webhook-endpoints/${id}/`, {
    ...(patch.url !== undefined ? { url: patch.url } : {}),
    ...(patch.events !== undefined ? { event_filters: eventFilters(patch.events) } : {}),
    ...(patch.status !== undefined ? { enabled: patch.status !== "disabled" } : {})
  });
}

export async function removeBackendWebhookEndpoint(id: string): Promise<void> {
  await api.delete(`/webhook-endpoints/${id}/`);
}

export async function rotateBackendWebhookSecret(id: string): Promise<string> {
  const body = await api.post<{ secret: string }>(`/webhook-endpoints/${id}/rotate-secret/`);
  return body.secret;
}

export async function replayBackendWebhookEvent(eventId: string): Promise<void> {
  await api.post(`/events/${eventId}/replay/`);
}

export async function loadNombaIntegration(): Promise<NombaIntegrationConfig> {
  return api.get<NombaIntegrationConfig>("/nomba/");
}

export async function saveNombaIntegration(input: NombaCredentialInput): Promise<NombaIntegrationConfig> {
  return api.post<NombaIntegrationConfig>("/nomba/", {
    integration_mode: input.integrationMode,
    account_id: input.accountId.trim(),
    client_id: input.clientId.trim(),
    client_secret: input.clientSecret?.trim() ?? "",
    webhook_secret: input.webhookSecret?.trim() ?? "",
    sub_account_id: input.subAccountId.trim()
  });
}

export async function validateNombaIntegration(): Promise<{ ok: boolean; validatedAt?: string; reason?: string }> {
  return api.post("/nomba/validate/", {});
}

export async function activateNombaIntegration(): Promise<{ ok: boolean; mode?: string; live_active?: boolean; reason?: string }> {
  return api.post("/nomba/activate/", {});
}

export async function syncNombaAccounts(): Promise<Record<string, unknown>> {
  return api.post("/nomba/accounts/sync/", {});
}

export async function mapNombaSubAccount(subAccountId: string): Promise<{ ok: boolean; sub_account_id: string }> {
  return api.post("/nomba/sub-account/", { sub_account_id: subAccountId.trim() });
}

export function webhookEventId(event: WebhookEventRecord): string {
  return event.id;
}
