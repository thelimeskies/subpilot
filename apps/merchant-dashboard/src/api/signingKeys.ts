import { api } from "./client";

export interface SigningKeys {
  mode: "test" | "live" | string;
  primary: string;
  primaryMasked: string;
  previous: string;
  previousMasked: string;
  rotatedAt: string | null;
  previousExpiresAt: string | null;
  graceHours: number;
}

interface BackendSigningKeys {
  mode: "test" | "live" | string;
  primary?: string | null;
  primary_masked?: string | null;
  previous?: string | null;
  previous_masked?: string | null;
  rotated_at?: string | null;
  previous_expires_at?: string | null;
  grace_hours?: number | null;
}

function mapSigningKeys(body: BackendSigningKeys): SigningKeys {
  return {
    mode: body.mode,
    primary: body.primary ?? "",
    primaryMasked: body.primary_masked ?? "",
    previous: body.previous ?? "",
    previousMasked: body.previous_masked ?? "",
    rotatedAt: body.rotated_at ?? null,
    previousExpiresAt: body.previous_expires_at ?? null,
    graceHours: body.grace_hours ?? 0
  };
}

export async function loadSigningKeys(): Promise<SigningKeys> {
  return mapSigningKeys(await api.get<BackendSigningKeys>("/signing-keys/"));
}

export async function rotateSigningKeys(graceHours: number): Promise<SigningKeys> {
  return mapSigningKeys(await api.post<BackendSigningKeys>("/signing-keys/rotate/", {
    grace_hours: graceHours
  }));
}
