/**
 * Platform-wide audit log hook (Settings → Audit tab).
 * Backed by GET /api/v1/platform/audit-log.
 */
import { useCallback, useEffect, useState } from "react";
import { api, isApiError } from "./client";

export type AuditCategory = "merchant" | "platform" | "team" | "security";

export interface AuditEntry {
  id: string;
  rawId: string;
  merchantId: string | null;
  actor: string;
  actorRole: string;
  action: string;
  detail: string;
  targetType: string;
  targetId: string;
  category: AuditCategory;
  occurredAt: string;
  metadata: Record<string, unknown>;
}

interface AuditLogResponse {
  ok: boolean;
  rows: AuditEntry[];
  total: number;
  page: number;
  pageSize: number;
  reason?: string;
}

export interface UseAuditLogOptions {
  pageSize?: number;
  category?: AuditCategory | "";
  search?: string;
}

export interface UseAuditLogResult {
  rows: AuditEntry[];
  total: number;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

export function useAuditLog(options: UseAuditLogOptions = {}): UseAuditLogResult {
  const { pageSize = 50, category, search } = options;

  const [rows, setRows] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("pageSize", String(pageSize));
      if (category) params.set("category", category);
      if (search) params.set("search", search);
      const path = `/platform/audit-log${params.toString() ? `?${params.toString()}` : ""}`;
      const body = await api.get<AuditLogResponse>(path);
      if (body.ok) {
        setRows(body.rows ?? []);
        setTotal(body.total ?? 0);
      } else {
        setError(body.reason || "Could not load audit log.");
      }
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not load audit log.");
    } finally {
      setLoading(false);
    }
  }, [pageSize, category, search]);

  useEffect(() => {
    void reload();
  }, [reload]);

  return { rows, total, loading, error, reload };
}
