import { api } from "./client";

export interface PublishableKey {
  mode: "test" | "live";
  publishableKey: string;
}

interface BackendPublishableKey {
  mode: "test" | "live" | string;
  publishable_key: string;
}

interface ListPublishableKeysResponse {
  keys: BackendPublishableKey[];
}

interface RotatePublishableKeyResponse extends BackendPublishableKey {}

function mapKey(key: BackendPublishableKey): PublishableKey {
  return {
    mode: key.mode === "live" ? "live" : "test",
    publishableKey: key.publishable_key
  };
}

export async function loadPublishableKeys(): Promise<PublishableKey[]> {
  const body = await api.get<ListPublishableKeysResponse>("/api-keys/publishable-key/");
  return body.keys.map(mapKey);
}

export async function rotatePublishableKey(mode: "test" | "live"): Promise<PublishableKey> {
  const body = await api.post<RotatePublishableKeyResponse>("/api-keys/publishable-key/", { mode });
  return mapKey(body);
}
