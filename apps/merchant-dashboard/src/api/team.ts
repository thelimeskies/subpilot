import { api } from "./client";
import type { TeamMember } from "../data/seed";

interface BackendTeamMember {
  id: string;
  name: string;
  email: string;
  role: TeamMember["role"] | string;
  mfa_enabled?: boolean | null;
  status?: "active" | "invited" | "suspended" | string | null;
  last_seen_at?: string | null;
}

function status(value: BackendTeamMember["status"]): TeamMember["status"] {
  if (value === "active" || value === "invited") return value;
  return "disabled";
}

function role(value: BackendTeamMember["role"]): TeamMember["role"] {
  if (value === "Owner" || value === "Admin" || value === "Finance" || value === "Support" || value === "Read-only") {
    return value;
  }
  return "Read-only";
}

export function mapTeamMember(member: BackendTeamMember): TeamMember {
  return {
    id: member.id,
    name: member.name,
    email: member.email,
    role: role(member.role),
    mfaEnabled: Boolean(member.mfa_enabled),
    status: status(member.status),
    lastSeenAt: member.last_seen_at ?? "—"
  };
}

export async function inviteBackendTeamMember(input: {
  email: string;
  name: string;
  role: TeamMember["role"];
  message?: string;
}): Promise<string> {
  const member = await api.post<BackendTeamMember>("/team-members/", {
    email: input.email,
    name: input.name,
    role: input.role,
    message: input.message ?? ""
  });
  return member.id;
}

export async function updateBackendTeamMemberRole(id: string, role: TeamMember["role"]): Promise<void> {
  await api.patch(`/team-members/${id}/`, { role });
}

export async function resendBackendTeamInvite(id: string): Promise<void> {
  await api.post(`/team-members/${id}/resend-invite/`, {});
}

export async function resetBackendTeamMemberMfa(id: string): Promise<void> {
  await api.post(`/team-members/${id}/reset-mfa/`, {});
}

export async function removeBackendTeamMember(id: string): Promise<void> {
  await api.delete(`/team-members/${id}/`);
}
