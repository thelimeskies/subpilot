/**
 * Platform-admin team management hook (S9).
 * Backed by:
 *   GET    /api/v1/platform/team
 *   POST   /api/v1/platform/team/invite
 *   GET    /api/v1/platform/team/<id>
 *   PATCH  /api/v1/platform/team/<id>
 *   POST   /api/v1/platform/team/<id>/suspend
 *   POST   /api/v1/platform/team/<id>/reactivate
 *   POST   /api/v1/platform/team/accept-invite (public)
 */
import { useCallback, useEffect, useState } from "react";
import { api, isApiError } from "./client";

export type TeamRole = "Owner" | "Operator" | "Support" | "Read-only" | string;
export type TeamStatus = "Active" | "Invited" | "Suspended" | string;

export interface TeamMemberRow {
  id: string;
  rawId: string;
  name: string;
  email: string;
  role: TeamRole;
  rawRole: string;
  status: TeamStatus;
  rawStatus: string;
  mfa: boolean;
  lastActive: string;
  invitedBy: string;
  initials: string;
  createdAt: string;
}

export interface InviteTokenInfo {
  token: string;
  expiresAt: string;
  url: string;
}

interface ListResponse {
  ok: boolean;
  page: number;
  pageSize: number;
  total: number;
  results: TeamMemberRow[];
}

export interface UseTeamParams {
  q?: string;
  role?: string;
  status?: string;
  page?: number;
  pageSize?: number;
}

export interface InviteInput {
  email: string;
  displayName?: string;
  role?: string;
}

export interface UpdateMemberInput {
  rawId: string;
  role?: string;
  status?: string;
  displayName?: string;
  mfaEnabled?: boolean;
}

export interface AcceptInviteInput {
  token: string;
  password: string;
  displayName?: string;
}

export interface UseTeamResult {
  rows: TeamMemberRow[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  invite: (input: InviteInput) => Promise<{ admin: TeamMemberRow; invite: InviteTokenInfo }>;
  update: (input: UpdateMemberInput) => Promise<TeamMemberRow>;
  suspend: (rawId: string) => Promise<TeamMemberRow>;
  reactivate: (rawId: string) => Promise<TeamMemberRow>;
}

function buildQuery(params: UseTeamParams): string {
  const usp = new URLSearchParams();
  if (params.q) usp.set("q", params.q);
  if (params.role && params.role !== "all") usp.set("role", params.role);
  if (params.status && params.status !== "all") usp.set("status", params.status);
  if (params.page) usp.set("page", String(params.page));
  if (params.pageSize) usp.set("page_size", String(params.pageSize));
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function useTeam(params: UseTeamParams = {}): UseTeamResult {
  const [rows, setRows] = useState<TeamMemberRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(params.page ?? 1);
  const [pageSize, setPageSize] = useState(params.pageSize ?? 25);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const key = JSON.stringify(params);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const body = await api.get<ListResponse>(`/platform/team${buildQuery(params)}`);
      if (body.ok) {
        setRows(body.results ?? []);
        setTotal(body.total ?? 0);
        setPage(body.page ?? 1);
        setPageSize(body.pageSize ?? 25);
      } else {
        setError("Could not load team.");
      }
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not load team.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const invite = useCallback(
    async (input: InviteInput) => {
      const body = await api.post<{
        ok: boolean;
        admin: TeamMemberRow;
        invite: InviteTokenInfo;
        reason?: string;
      }>("/platform/team/invite", {
        email: input.email,
        display_name: input.displayName ?? "",
        role: input.role ?? "operator",
      });
      if (!body.ok) throw new Error(body.reason || "Invite failed.");
      void reload();
      return { admin: body.admin, invite: body.invite };
    },
    [reload],
  );

  const update = useCallback(
    async (input: UpdateMemberInput) => {
      const payload: Record<string, unknown> = {};
      if (input.role !== undefined) payload.role = input.role;
      if (input.status !== undefined) payload.status = input.status;
      if (input.displayName !== undefined) payload.display_name = input.displayName;
      if (input.mfaEnabled !== undefined) payload.mfa_enabled = input.mfaEnabled;
      const body = await api.patch<{ ok: boolean; admin: TeamMemberRow; reason?: string }>(
        `/platform/team/${input.rawId}`,
        payload,
      );
      if (!body.ok) throw new Error(body.reason || "Update failed.");
      void reload();
      return body.admin;
    },
    [reload],
  );

  const suspend = useCallback(
    async (rawId: string) => {
      const body = await api.post<{ ok: boolean; admin: TeamMemberRow; reason?: string }>(
        `/platform/team/${rawId}/suspend`,
        {},
      );
      if (!body.ok) throw new Error(body.reason || "Suspend failed.");
      void reload();
      return body.admin;
    },
    [reload],
  );

  const reactivate = useCallback(
    async (rawId: string) => {
      const body = await api.post<{ ok: boolean; admin: TeamMemberRow; reason?: string }>(
        `/platform/team/${rawId}/reactivate`,
        {},
      );
      if (!body.ok) throw new Error(body.reason || "Reactivate failed.");
      void reload();
      return body.admin;
    },
    [reload],
  );

  return {
    rows, total, page, pageSize, loading, error,
    reload, invite, update, suspend, reactivate,
  };
}

export async function acceptTeamInvite(input: AcceptInviteInput): Promise<TeamMemberRow> {
  const body = await api.post<{ ok: boolean; admin: TeamMemberRow; reason?: string }>(
    "/platform/team/accept-invite",
    {
      token: input.token,
      password: input.password,
      display_name: input.displayName ?? "",
    },
  );
  if (!body.ok) throw new Error(body.reason || "Accept failed.");
  return body.admin;
}
