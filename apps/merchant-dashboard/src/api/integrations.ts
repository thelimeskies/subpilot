import { api } from "./client";
import type { WebhookEndpoint, WebhookEvent, WebhookEventRecord } from "../data/seed";

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

export function webhookEventId(event: WebhookEventRecord): string {
  return event.id;
}
