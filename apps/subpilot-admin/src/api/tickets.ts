/**
 * Support tickets hook (S8).
 * Backed by:
 *   GET    /api/v1/platform/tickets
 *   POST   /api/v1/platform/tickets
 *   GET    /api/v1/platform/tickets/<id>
 *   PATCH  /api/v1/platform/tickets/<id>
 *   POST   /api/v1/platform/tickets/<id>/replies
 */
import { useCallback, useEffect, useState } from "react";
import { api, isApiError } from "./client";

export interface TicketReply {
  id: string;
  author: string;
  authorId: string | null;
  body: string;
  createdAt: string;
}

export interface TicketRow {
  id: string;
  rawId: string;
  subject: string;
  merchant: string;
  merchantId: string;
  priority: "Low" | "Normal" | "High" | "Urgent" | string;
  rawPriority: string;
  status: "Open" | "Awaiting" | "Resolved" | "Closed" | string;
  rawStatus: string;
  assignee: string;
  assigneeId: string | null;
  requesterEmail?: string;
  updatedAt: string;
  createdAt: string;
}

export interface TicketDetail extends TicketRow {
  body: string;
  replies: TicketReply[];
}

interface ListResponse {
  ok: boolean;
  page: number;
  pageSize: number;
  total: number;
  results: TicketRow[];
}

export interface UseTicketsParams {
  q?: string;
  status?: string;
  priority?: string;
  merchantId?: string;
  assigneeId?: string;
  page?: number;
  pageSize?: number;
}

export interface CreateTicketInput {
  merchantId: string;
  subject: string;
  body?: string;
  priority?: string;
  requesterEmail?: string;
}

export interface UpdateTicketInput {
  rawId: string;
  status?: string;
  priority?: string;
  assigneeId?: string | null;
}

export interface ReplyInput {
  rawId: string;
  body: string;
}

export interface UseTicketsResult {
  rows: TicketRow[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
  create: (input: CreateTicketInput) => Promise<TicketDetail>;
  update: (input: UpdateTicketInput) => Promise<TicketDetail>;
  reply: (input: ReplyInput) => Promise<TicketReply>;
  fetchDetail: (rawId: string) => Promise<TicketDetail>;
}

function buildQuery(params: UseTicketsParams): string {
  const usp = new URLSearchParams();
  if (params.q) usp.set("q", params.q);
  if (params.status) usp.set("status", params.status);
  if (params.priority) usp.set("priority", params.priority);
  if (params.merchantId) usp.set("merchant_id", params.merchantId);
  if (params.assigneeId) usp.set("assignee_id", params.assigneeId);
  if (params.page) usp.set("page", String(params.page));
  if (params.pageSize) usp.set("page_size", String(params.pageSize));
  const qs = usp.toString();
  return qs ? `?${qs}` : "";
}

export function useTickets(params: UseTicketsParams = {}): UseTicketsResult {
  const [rows, setRows] = useState<TicketRow[]>([]);
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
      const body = await api.get<ListResponse>(`/platform/tickets${buildQuery(params)}`);
      if (body.ok) {
        setRows(body.results ?? []);
        setTotal(body.total ?? 0);
        setPage(body.page ?? 1);
        setPageSize(body.pageSize ?? 25);
      } else {
        setError("Could not load tickets.");
      }
    } catch (err) {
      setError(isApiError(err) ? err.reason : "Could not load tickets.");
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  useEffect(() => {
    void reload();
  }, [reload]);

  const create = useCallback(
    async (input: CreateTicketInput): Promise<TicketDetail> => {
      const body = await api.post<{ ok: boolean; ticket: TicketDetail; reason?: string }>(
        "/platform/tickets",
        {
          merchant_id: input.merchantId,
          subject: input.subject,
          body: input.body ?? "",
          priority: input.priority ?? "normal",
          requester_email: input.requesterEmail ?? "",
        },
      );
      if (!body.ok) throw new Error(body.reason || "Create failed.");
      void reload();
      return body.ticket;
    },
    [reload],
  );

  const update = useCallback(
    async (input: UpdateTicketInput): Promise<TicketDetail> => {
      const payload: Record<string, unknown> = {};
      if (input.status !== undefined) payload.status = input.status;
      if (input.priority !== undefined) payload.priority = input.priority;
      if (input.assigneeId !== undefined)
        payload.assignee_id = input.assigneeId === null ? "" : input.assigneeId;
      const body = await api.patch<{ ok: boolean; ticket: TicketDetail; reason?: string }>(
        `/platform/tickets/${input.rawId}`,
        payload,
      );
      if (!body.ok) throw new Error(body.reason || "Update failed.");
      void reload();
      return body.ticket;
    },
    [reload],
  );

  const reply = useCallback(
    async (input: ReplyInput): Promise<TicketReply> => {
      const body = await api.post<{ ok: boolean; reply: TicketReply; reason?: string }>(
        `/platform/tickets/${input.rawId}/replies`,
        { body: input.body },
      );
      if (!body.ok) throw new Error(body.reason || "Reply failed.");
      void reload();
      return body.reply;
    },
    [reload],
  );

  const fetchDetail = useCallback(async (rawId: string): Promise<TicketDetail> => {
    const body = await api.get<{ ok: boolean; ticket: TicketDetail; reason?: string }>(
      `/platform/tickets/${rawId}`,
    );
    if (!body.ok) throw new Error(body.reason || "Fetch failed.");
    return body.ticket;
  }, []);

  return {
    rows, total, page, pageSize, loading, error,
    reload, create, update, reply, fetchDetail,
  };
}
