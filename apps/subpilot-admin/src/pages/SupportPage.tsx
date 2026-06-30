import { createContext, useContext, useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DataTable,
  Field,
  Modal,
  Pagination,
  SelectInput,
  Sheet,
  TextInput,
  type DataTableColumn,
} from "@subpilot/ui";
import { Eye, MessageSquarePlus, Search, Send } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { useAuth, usePlatformPermissions } from "../auth/AuthContext";
import {
  useTickets,
  type TicketDetail,
  type TicketRow,
  type UseTicketsResult,
} from "../api/tickets";
import { useMerchants } from "../api/merchants";

type StatusFilter = "All" | "Open" | "Awaiting" | "Resolved" | "Closed";
type PriorityFilter = "All" | "Low" | "Normal" | "High" | "Urgent";

const STATUSES: StatusFilter[] = ["All", "Open", "Awaiting", "Resolved", "Closed"];
const PRIORITIES: PriorityFilter[] = ["All", "Low", "Normal", "High", "Urgent"];
const PAGE_SIZE = 10;

const STATUS_LABEL: Record<string, string> = {
  open: "Open",
  in_progress: "Awaiting",
  resolved: "Resolved",
  closed: "Closed",
};

const PRIORITY_LABEL: Record<string, string> = {
  low: "Low",
  normal: "Normal",
  high: "High",
  urgent: "Urgent",
};

const TicketsCtx = createContext<UseTicketsResult | null>(null);
function useTicketsContext() {
  const ctx = useContext(TicketsCtx);
  if (!ctx) throw new Error("TicketsCtx not provided");
  return ctx;
}

interface ViewerCtx {
  open: (rawId: string) => void;
}
const ViewerContext = createContext<ViewerCtx | null>(null);
function useViewer() {
  const ctx = useContext(ViewerContext);
  if (!ctx) throw new Error("ViewerContext not provided");
  return ctx;
}

const linkButtonStyle: React.CSSProperties = {
  background: "none",
  border: 0,
  padding: 0,
  textAlign: "left",
  font: "inherit",
  color: "inherit",
  cursor: "pointer",
};

const columns: DataTableColumn<TicketRow>[] = [
  {
    key: "id",
    header: "Ticket",
    render: (t) => <TicketIdCell row={t} />,
  },
  {
    key: "subject",
    header: "Subject",
    render: (t) => <TicketSubjectCell row={t} />,
  },
  {
    key: "priority",
    header: "Priority",
    render: (t) => (
      <Badge
        tone={
          t.priority === "Urgent"
            ? "danger"
            : t.priority === "High"
              ? "warning"
              : t.priority === "Normal"
                ? "info"
                : "neutral"
        }
      >
        {t.priority}
      </Badge>
    ),
  },
  {
    key: "status",
    header: "Status",
    render: (t) => (
      <Badge
        tone={
          t.status === "Open"
            ? "warning"
            : t.status === "Awaiting"
              ? "info"
              : t.status === "Resolved"
                ? "success"
                : "neutral"
        }
      >
        {t.status}
      </Badge>
    ),
  },
  { key: "assignee", header: "Assignee", render: (t) => t.assignee },
  {
    key: "updated",
    header: "Updated",
    render: (t) =>
      new Date(t.updatedAt).toLocaleString(undefined, {
        dateStyle: "medium",
        timeStyle: "short",
      }),
  },
  {
    key: "actions",
    header: "",
    align: "right",
    render: (t) => <TicketRowActions row={t} />,
  },
];

function TicketIdCell({ row }: { row: TicketRow }) {
  const { open } = useViewer();
  return (
    <button type="button" style={linkButtonStyle} onClick={() => open(row.rawId)}>
      <code className="adm-code">{row.id}</code>
    </button>
  );
}

function TicketSubjectCell({ row }: { row: TicketRow }) {
  const { open } = useViewer();
  return (
    <button
      type="button"
      className="adm-entity-cell"
      style={linkButtonStyle}
      onClick={() => open(row.rawId)}
    >
      <strong>{row.subject}</strong>
      <small className="adm-muted">{row.merchant}</small>
    </button>
  );
}

function TicketRowActions({ row }: { row: TicketRow }) {
  const { update } = useTicketsContext();
  const { open } = useViewer();
  const { notify, confirm } = useFeedback();
  const { canSupportAct } = usePlatformPermissions();
  const [busy, setBusy] = useState(false);

  const isClosed = row.status === "Resolved" || row.status === "Closed";
  const target = isClosed ? null : row.status === "Open" ? "Awaiting" : "Resolved";
  const targetInternal = target === "Awaiting" ? "in_progress" : "resolved";

  const onAdvance = async () => {
    if (!target) return;
    const ok = await confirm({
      title: target === "Resolved" ? "Resolve ticket?" : "Mark as awaiting?",
      description:
        target === "Resolved"
          ? `Mark "${row.subject}" as resolved.`
          : `Move "${row.subject}" to awaiting.`,
      confirmLabel: target,
      destructive: target === "Resolved",
    });
    if (!ok) return;
    setBusy(true);
    try {
      await update({ rawId: row.rawId, status: targetInternal });
      notify({
        tone: "success",
        title: "Updated",
        description: `${row.id} → ${target}`,
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Update failed",
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="adm-row-actions">
      <Button variant="ghost" icon={<Eye size={14} />} onClick={() => open(row.rawId)}>
        View
      </Button>
      {target && canSupportAct ? (
        <Button variant="ghost" onClick={onAdvance} disabled={busy}>
          {busy ? "…" : target}
        </Button>
      ) : (
        <span className="adm-muted">—</span>
      )}
    </div>
  );
}

export function SupportPage() {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("All");
  const [priorityFilter, setPriorityFilter] = useState<PriorityFilter>("All");
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const { notify } = useFeedback();
  const auth = useAuth();
  const { canSupportAct } = usePlatformPermissions();

  const params = useMemo(
    () => ({
      status: statusFilter === "All" ? undefined : statusFilter.toLowerCase(),
      priority: priorityFilter === "All" ? undefined : priorityFilter.toLowerCase(),
      q: q.trim() || undefined,
      page,
      pageSize: PAGE_SIZE,
    }),
    [statusFilter, priorityFilter, q, page],
  );

  const tickets = useTickets(params);
  const { rows, total, loading, error } = tickets;

  // Merchant picker for creating new tickets.
  const merchantList = useMerchants({ pageSize: 50 });

  // ---------- Create ticket modal ----------
  const [createOpen, setCreateOpen] = useState(false);
  const [createSubmitting, setCreateSubmitting] = useState(false);
  const [newSubject, setNewSubject] = useState("");
  const [newMerchantId, setNewMerchantId] = useState("");
  const [newPriority, setNewPriority] = useState("normal");
  const [newRequester, setNewRequester] = useState("");
  const [newBody, setNewBody] = useState("");

  // Default the merchant select once data lands.
  useEffect(() => {
    if (!newMerchantId && merchantList.rows.length > 0) {
      setNewMerchantId(merchantList.rows[0].id);
    }
  }, [merchantList.rows, newMerchantId]);

  const resetCreateForm = () => {
    setNewSubject("");
    setNewBody("");
    setNewRequester("");
    setNewPriority("normal");
    setNewMerchantId(merchantList.rows[0]?.id ?? "");
  };

  const openCreate = () => {
    if (!merchantList.rows.length) {
      notify({
        tone: "danger",
        title: "No merchants",
        description: "Add a merchant before creating a ticket.",
      });
      return;
    }
    setCreateOpen(true);
  };

  const closeCreate = () => {
    if (createSubmitting) return;
    setCreateOpen(false);
  };

  // ---------- Detail sheet ----------
  const [viewRawId, setViewRawId] = useState<string | null>(null);
  const [detail, setDetail] = useState<TicketDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState<string | null>(null);
  const [replyBody, setReplyBody] = useState("");
  const [replySubmitting, setReplySubmitting] = useState(false);
  const [statusSaving, setStatusSaving] = useState(false);
  const [prioritySaving, setPrioritySaving] = useState(false);
  const [assigneeSaving, setAssigneeSaving] = useState(false);

  const openViewer = (rawId: string) => {
    setViewRawId(rawId);
  };

  const closeViewer = () => {
    setViewRawId(null);
    setDetail(null);
    setDetailError(null);
    setReplyBody("");
  };

  // Load ticket detail when the sheet target changes.
  useEffect(() => {
    if (!viewRawId) return;
    let cancelled = false;
    setDetailLoading(true);
    setDetailError(null);
    tickets
      .fetchDetail(viewRawId)
      .then((d) => {
        if (cancelled) return;
        setDetail(d);
      })
      .catch((err) => {
        if (cancelled) return;
        setDetailError(err instanceof Error ? err.message : String(err));
      })
      .finally(() => {
        if (cancelled) return;
        setDetailLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [viewRawId]);

  const submitCreate = async () => {
    const subject = newSubject.trim();
    if (!subject) {
      notify({
        tone: "danger",
        title: "Subject required",
        description: "Enter a short summary so the team can triage this ticket.",
      });
      return;
    }
    if (!newMerchantId) {
      notify({
        tone: "danger",
        title: "Pick a merchant",
        description: "Select the merchant this ticket belongs to.",
      });
      return;
    }
    setCreateSubmitting(true);
    try {
      const t = await tickets.create({
        merchantId: newMerchantId,
        subject,
        body: newBody.trim() || undefined,
        priority: newPriority,
        requesterEmail: newRequester.trim() || undefined,
      });
      const merchantName =
        merchantList.rows.find((m) => m.id === newMerchantId)?.name ?? newMerchantId;
      notify({
        tone: "success",
        title: "Ticket created",
        description: `${t.id} • ${merchantName}`,
      });
      setCreateOpen(false);
      resetCreateForm();
      // Open the detail view for the freshly created ticket.
      setDetail(t);
      setViewRawId(t.rawId);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Create failed",
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setCreateSubmitting(false);
    }
  };

  const submitReply = async () => {
    if (!detail) return;
    const body = replyBody.trim();
    if (!body) {
      notify({
        tone: "danger",
        title: "Reply is empty",
        description: "Type a message before sending.",
      });
      return;
    }
    setReplySubmitting(true);
    try {
      await tickets.reply({ rawId: detail.rawId, body });
      const fresh = await tickets.fetchDetail(detail.rawId);
      setDetail(fresh);
      setReplyBody("");
      notify({
        tone: "success",
        title: "Reply sent",
        description: `${detail.id} updated.`,
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Reply failed",
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setReplySubmitting(false);
    }
  };

  const changeStatus = async (next: string) => {
    if (!detail || next === detail.rawStatus) return;
    setStatusSaving(true);
    try {
      const updated = await tickets.update({ rawId: detail.rawId, status: next });
      setDetail(updated);
      notify({
        tone: "success",
        title: "Status updated",
        description: `${detail.id} → ${STATUS_LABEL[next] ?? next}`,
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Update failed",
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setStatusSaving(false);
    }
  };

  const changePriority = async (next: string) => {
    if (!detail || next === detail.rawPriority) return;
    setPrioritySaving(true);
    try {
      const updated = await tickets.update({ rawId: detail.rawId, priority: next });
      setDetail(updated);
      notify({
        tone: "success",
        title: "Priority updated",
        description: `${detail.id} → ${PRIORITY_LABEL[next] ?? next}`,
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Update failed",
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setPrioritySaving(false);
    }
  };

  const toggleAssignment = async () => {
    if (!detail || !auth.user) return;
    const mine = detail.assigneeId === auth.user.id;
    setAssigneeSaving(true);
    try {
      const updated = await tickets.update({
        rawId: detail.rawId,
        assigneeId: mine ? null : auth.user.id,
      });
      setDetail(updated);
      notify({
        tone: "success",
        title: mine ? "Unassigned" : "Assigned to you",
        description: `${detail.id} • ${updated.assignee}`,
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Update failed",
        description: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setAssigneeSaving(false);
    }
  };

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const totalLabel = `${total} ticket${total === 1 ? "" : "s"}`;

  return (
    <TicketsCtx.Provider value={tickets}>
      <ViewerContext.Provider value={{ open: openViewer }}>
        <PageHeader
          eyebrow="Customer success"
          title="Support queue"
          description="Triage merchant escalations, webhook complaints, and adapter issues with the platform support team."
          actions={
            canSupportAct ? (
              <Button icon={<MessageSquarePlus size={16} />} onClick={openCreate}>
                New ticket
              </Button>
            ) : null
          }
        />

        <Card>
          <CardHeader
            title="Open tickets"
            description={
              loading ? "Loading…" : `${total} active conversation${total === 1 ? "" : "s"}`
            }
            action={<Badge tone="teal">SLA on track</Badge>}
          />
          <div className="adm-filter-row">
            <span className="adm-input-wrap adm-input-wrap--flex">
              <Search size={16} aria-hidden="true" />
              <TextInput
                type="search"
                placeholder="Search by subject or merchant"
                value={q}
                onChange={(e) => {
                  setQ(e.target.value);
                  setPage(1);
                }}
              />
            </span>
            <div className="adm-segmented" role="tablist" aria-label="Ticket status">
              {STATUSES.map((s) => (
                <button
                  key={s}
                  type="button"
                  role="tab"
                  aria-selected={statusFilter === s}
                  className={`adm-segmented__item${statusFilter === s ? " is-active" : ""}`}
                  onClick={() => {
                    setStatusFilter(s);
                    setPage(1);
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
            <div className="adm-segmented" role="tablist" aria-label="Ticket priority">
              {PRIORITIES.map((p) => (
                <button
                  key={p}
                  type="button"
                  role="tab"
                  aria-selected={priorityFilter === p}
                  className={`adm-segmented__item${priorityFilter === p ? " is-active" : ""}`}
                  onClick={() => {
                    setPriorityFilter(p);
                    setPage(1);
                  }}
                >
                  {p}
                </button>
              ))}
            </div>
          </div>
          {error ? (
            <div className="adm-empty-state">
              <p className="adm-muted">{error}</p>
            </div>
          ) : null}
          <DataTable columns={columns} rows={rows} getRowKey={(t) => t.rawId} />
          <Pagination
            page={page}
            pageCount={pageCount}
            totalLabel={totalLabel}
            onPageChange={setPage}
          />
        </Card>

        {/* ---------- New ticket modal ---------- */}
        <Modal
          open={createOpen}
          title="Create support ticket"
          description="Log a merchant escalation, webhook complaint, or adapter issue."
          onClose={closeCreate}
          footer={
            <>
              <Button variant="ghost" onClick={closeCreate} disabled={createSubmitting}>
                Cancel
              </Button>
              <Button
                onClick={submitCreate}
                disabled={createSubmitting}
                icon={<MessageSquarePlus size={14} />}
              >
                {createSubmitting ? "Creating…" : "Create ticket"}
              </Button>
            </>
          }
        >
          <div className="adm-form-grid">
            <Field label="Merchant">
              <SelectInput
                value={newMerchantId}
                onChange={(e) => setNewMerchantId(e.target.value)}
                disabled={merchantList.loading || !merchantList.rows.length}
              >
                {merchantList.rows.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.name}
                  </option>
                ))}
              </SelectInput>
            </Field>
            <Field label="Priority">
              <SelectInput
                value={newPriority}
                onChange={(e) => setNewPriority(e.target.value)}
              >
                <option value="low">Low</option>
                <option value="normal">Normal</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </SelectInput>
            </Field>
            <Field label="Subject">
              <TextInput
                value={newSubject}
                onChange={(e) => setNewSubject(e.target.value)}
                placeholder="Webhook signing rotation failed"
              />
            </Field>
            <Field label="Requester email" hint="Optional — who reported this issue.">
              <TextInput
                type="email"
                value={newRequester}
                onChange={(e) => setNewRequester(e.target.value)}
                placeholder="ops@merchant.com"
              />
            </Field>
          </div>
          <Field label="Description" hint="Context the on-call team needs to triage.">
            <textarea
              className="sp-input"
              value={newBody}
              onChange={(e) => setNewBody(e.target.value)}
              placeholder="What is happening, what was expected, and any reference IDs."
              rows={4}
              style={{ minHeight: 96, padding: "10px 12px", fontFamily: "inherit" }}
            />
          </Field>
        </Modal>

        {/* ---------- Detail sheet ---------- */}
        <Sheet
          open={viewRawId !== null}
          title={detail ? detail.subject : detailLoading ? "Loading ticket…" : "Ticket"}
          description={
            detail
              ? `${detail.id} • ${detail.merchant}`
              : detailError
                ? "Could not load this ticket."
                : undefined
          }
          onClose={closeViewer}
          footer={
            detail ? (
              <>
                <Button variant="ghost" onClick={closeViewer}>
                  Close
                </Button>
                {canSupportAct ? (
                  <Button
                    onClick={submitReply}
                    disabled={replySubmitting || !replyBody.trim()}
                    icon={<Send size={14} />}
                  >
                    {replySubmitting ? "Sending…" : "Send reply"}
                  </Button>
                ) : null}
              </>
            ) : (
              <Button variant="ghost" onClick={closeViewer}>
                Close
              </Button>
            )
          }
        >
          {detailLoading && !detail ? (
            <p className="adm-muted">Loading ticket…</p>
          ) : detailError && !detail ? (
            <p className="adm-muted">{detailError}</p>
          ) : detail ? (
            <>
              <div className="adm-form-grid">
                <Field label="Status">
                  <SelectInput
                    value={detail.rawStatus}
                    onChange={(e) => void changeStatus(e.target.value)}
                    disabled={statusSaving || !canSupportAct}
                  >
                    <option value="open">Open</option>
                    <option value="in_progress">Awaiting</option>
                    <option value="resolved">Resolved</option>
                    <option value="closed">Closed</option>
                  </SelectInput>
                </Field>
                <Field label="Priority">
                  <SelectInput
                    value={detail.rawPriority}
                    onChange={(e) => void changePriority(e.target.value)}
                    disabled={prioritySaving || !canSupportAct}
                  >
                    <option value="low">Low</option>
                    <option value="normal">Normal</option>
                    <option value="high">High</option>
                    <option value="urgent">Urgent</option>
                  </SelectInput>
                </Field>
                <Field label="Assignee">
                  <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span style={{ flex: 1, fontSize: 13, fontWeight: 600 }}>
                      {detail.assignee}
                    </span>
                    {auth.user && canSupportAct ? (
                      <Button
                        variant="ghost"
                        onClick={toggleAssignment}
                        disabled={assigneeSaving}
                      >
                        {detail.assigneeId === auth.user.id ? "Unassign" : "Assign to me"}
                      </Button>
                    ) : null}
                  </div>
                </Field>
                <Field label="Requester">
                  <span style={{ fontSize: 13, fontWeight: 600 }}>
                    {detail.requesterEmail || "—"}
                  </span>
                </Field>
              </div>

              <h3 className="adm-sheet-section">Conversation</h3>
              <ul className="adm-timeline">
                <li className="adm-timeline__item">
                  <span className="adm-timeline__dot" aria-hidden="true" />
                  <div>
                    <span className="adm-timeline__head">
                      <strong>{detail.requesterEmail || detail.merchant}</strong>
                      <Badge tone="neutral">Opened</Badge>
                    </span>
                    <p style={{ whiteSpace: "pre-wrap" }}>
                      {detail.body || "(No description provided.)"}
                    </p>
                    <small>
                      {new Date(detail.createdAt).toLocaleString(undefined, {
                        dateStyle: "medium",
                        timeStyle: "short",
                      })}
                    </small>
                  </div>
                </li>
                {detail.replies.map((r) => (
                  <li className="adm-timeline__item" key={r.id}>
                    <span className="adm-timeline__dot" aria-hidden="true" />
                    <div>
                      <span className="adm-timeline__head">
                        <strong>{r.author}</strong>
                        <Badge tone="info">Reply</Badge>
                      </span>
                      <p style={{ whiteSpace: "pre-wrap" }}>{r.body}</p>
                      <small>
                        {new Date(r.createdAt).toLocaleString(undefined, {
                          dateStyle: "medium",
                          timeStyle: "short",
                        })}
                      </small>
                    </div>
                  </li>
                ))}
              </ul>

              <h3 className="adm-sheet-section">Reply</h3>
              <Field label="Message">
                <textarea
                  className="sp-input"
                  value={replyBody}
                  onChange={(e) => setReplyBody(e.target.value)}
                  placeholder="Reply to the merchant or leave an internal note for the on-call team."
                  rows={4}
                  style={{ minHeight: 110, padding: "10px 12px", fontFamily: "inherit" }}
                />
              </Field>
            </>
          ) : null}
        </Sheet>
      </ViewerContext.Provider>
    </TicketsCtx.Provider>
  );
}
