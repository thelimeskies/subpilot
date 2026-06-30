import { createContext, useContext, useMemo, useState } from "react";
import { Badge, Button, Card, CardHeader, DataTable, Pagination, TextInput, type DataTableColumn } from "@subpilot/ui";
import { Download, Filter, Search } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { usePayments, type PaymentRow, type UsePaymentsResult } from "../api/payments";
import { usePlatformPermissions } from "../auth/AuthContext";

type StatusFilter = "All" | "Captured" | "Failed" | "Recovered" | "Refunded";

const statuses: StatusFilter[] = ["All", "Captured", "Failed", "Recovered", "Refunded"];

const PAGE_SIZE = 10;

const columns: DataTableColumn<PaymentRow>[] = [
  { key: "id", header: "Payment", render: (p) => <code className="adm-code">{p.id}</code> },
  { key: "merchant", header: "Merchant", render: (p) => p.merchant },
  { key: "customer", header: "Customer", render: (p) => p.customer },
  { key: "amount", header: "Amount", align: "right", render: (p) => p.amount },
  {
    key: "status",
    header: "Status",
    render: (p) => (
      <Badge tone={p.status === "Captured" ? "success" : p.status === "Failed" ? "danger" : p.status === "Recovered" ? "info" : "warning"}>
        {p.status}
      </Badge>
    )
  },
  { key: "method", header: "Method", render: (p) => p.method },
  { key: "gateway", header: "Gateway", render: (p) => p.gateway },
  { key: "reason", header: "Reason", render: (p) => <span className="adm-muted">{p.reason ?? "—"}</span> },
  {
    key: "occurred",
    header: "When",
    render: (p) => new Date(p.occurredAt).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })
  },
  {
    key: "actions",
    header: "",
    align: "right",
    render: (p) => <PaymentRowActions row={p} />
  }
];

function PaymentRowActions({ row }: { row: PaymentRow }) {
  const { refund } = usePaymentsContext();
  const { notify } = useFeedback();
  const { canOperate } = usePlatformPermissions();
  const [busy, setBusy] = useState(false);

  if (row.status !== "Captured" && row.status !== "Recovered") {
    return <span className="adm-muted">—</span>;
  }

  if (!canOperate) {
    return <span className="adm-muted">—</span>;
  }

  const handle = async () => {
    if (busy) return;
    const reason = window.prompt("Reason for refund?", "Customer request");
    if (reason === null) return;
    setBusy(true);
    try {
      await refund({ rawId: row.rawId, reason: reason || "Customer request" });
      notify({ tone: "success", title: "Refund issued", description: `Payment ${row.id} refunded.` });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Refund failed",
        description: err instanceof Error ? err.message : "Unable to issue refund."
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button variant="ghost" onClick={handle} disabled={busy}>
      {busy ? "Refunding…" : "Refund"}
    </Button>
  );
}

// --- Tiny context to share refund() with the row renderer ---------------

const PaymentsCtx = createContext<UsePaymentsResult | null>(null);
function usePaymentsContext() {
  const ctx = useContext(PaymentsCtx);
  if (!ctx) throw new Error("Payments context missing");
  return ctx;
}

// -----------------------------------------------------------------------

export function PaymentsPage() {
  const { notify } = useFeedback();
  const [query, setQuery] = useState("");
  const [status, setStatus] = useState<StatusFilter>("All");
  const [page, setPage] = useState(1);

  const result = usePayments({
    q: query || undefined,
    status: status !== "All" ? status.toLowerCase() : undefined,
    page,
    pageSize: PAGE_SIZE
  });
  const { rows, total, loading, error } = result;

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const totalLabel = useMemo(() => `${total.toLocaleString()} payments`, [total]);

  return (
    <PaymentsCtx.Provider value={result}>
      <PageHeader
        eyebrow="Money movement"
        title="Payments"
        description="Captures, failures, refunds, and dunning recoveries across every merchant and gateway adapter."
        actions={
          <Button
            variant="ghost"
            icon={<Download size={16} />}
            onClick={() =>
              notify({
                tone: "info",
                title: "Export queued",
                description: `Preparing CSV export of ${total.toLocaleString()} payments. We'll email the file when ready.`
              })
            }
          >
            Export CSV
          </Button>
        }
      />

      <Card>
        <CardHeader
          title="Activity"
          description={loading ? "Loading…" : `${rows.length} of ${total} payments visible`}
          action={<Badge tone="teal">Streaming</Badge>}
        />
        <div className="adm-filter-row">
          <span className="adm-input-wrap adm-input-wrap--flex">
            <Search size={16} aria-hidden="true" />
            <TextInput
              type="search"
              placeholder="Search by merchant, customer, invoice, or reference"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value);
                setPage(1);
              }}
            />
          </span>
          <div className="adm-segmented" role="tablist" aria-label="Payment status">
            {statuses.map((s) => (
              <button
                key={s}
                type="button"
                role="tab"
                aria-selected={status === s}
                className={`adm-segmented__item${status === s ? " is-active" : ""}`}
                onClick={() => {
                  setStatus(s);
                  setPage(1);
                }}
              >
                {s}
              </button>
            ))}
          </div>
          <Button
            variant="ghost"
            icon={<Filter size={16} />}
            onClick={() =>
              notify({
                tone: "info",
                title: "Advanced filters",
                description: "Multi-field filter builder will open in a side sheet."
              })
            }
          >
            Advanced
          </Button>
        </div>
        {error ? (
          <div className="adm-empty-state">
            <p className="adm-muted">{error}</p>
          </div>
        ) : null}
        <DataTable columns={columns} rows={rows} getRowKey={(p) => p.rawId} />
        <Pagination page={page} pageCount={pageCount} totalLabel={totalLabel} onPageChange={setPage} />
      </Card>
    </PaymentsCtx.Provider>
  );
}
