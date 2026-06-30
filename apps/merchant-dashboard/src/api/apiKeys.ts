import { api } from "./client";
import type { ApiKey } from "../data/seed";

interface BackendApiKey {
  id: string;
  name: string;
  prefix: string;
  environment?: "test" | "live" | string | null;
  scopes?: ApiKey["scopes"] | string[] | null;
  status?: ApiKey["status"] | string | null;
  last_used_at?: string | null;
  created_at?: string | null;
}

interface CreateApiKeyResponse {
  api_key: BackendApiKey;
  secret: string;
}

function mapApiKey(key: BackendApiKey): ApiKey {
  return {
    id: key.id,
    name: key.name,
    prefix: key.prefix,
    scopes: (key.scopes ?? []).filter((scope): scope is ApiKey["scopes"][number] =>
      scope === "read" || scope === "write" || scope === "admin"
    ),
    status: key.status === "revoked" ? "revoked" : "active",
    createdAt: key.created_at?.slice(0, 10) ?? new Date().toISOString().slice(0, 10),
    lastUsedAt: key.last_used_at ?? "—"
  };
}

export async function createBackendApiKey(input: {
  name: string;
  scopes: ApiKey["scopes"];
  mode: "live" | "test";
}): Promise<{ id: string; secret: string }> {
  const body = await api.post<CreateApiKeyResponse>("/api-keys/", {
    name: input.name,
    scopes: input.scopes,
    environment_mode: input.mode
  });
  return {
    id: body.api_key.id,
    secret: body.secret
  };
}

export async function revokeBackendApiKey(id: string): Promise<void> {
  await api.post(`/api-keys/${id}/revoke/`, {});
}

export { mapApiKey };
