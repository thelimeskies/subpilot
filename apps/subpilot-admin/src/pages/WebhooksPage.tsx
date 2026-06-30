import { createContext, useContext, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DataTable,
  Pagination,
  StatCard,
  type DataTableColumn,
} from "@subpilot/ui";
import { RotateCcw, ShieldCheck } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { api } from "../api/client";
import { useWebhooks, type DeliveryRow, type UseWebhooksResult } from "../api/webhooks";
import { usePlatformPermissions } from "../auth/AuthContext";

const PAGE_SIZE = 10;

const columns: DataTableColumn<DeliveryRow>[] = [
  { key: "event", header: "Event", render: (w) => <code className="adm-code">{w.event || w.id}</code> },
  { key: "merchant", header: "Merchant", render: (w) => w.merchant },
  {
    key: "endpoint",
    header: "Endpoint",
    render: (w) => <span className="adm-muted">{w.endpoint}</span>,
  },
  {
    key: "status",
    header: "Status",
    render: (w) => (
      <Badge
        tone={w.status === "Delivered" ? "success" : w.status === "Retrying" ? "warning" : "danger"}
      >
        {w.status}
      </Badge>
    ),
  },
  { key: "attempts", header: "Attempts", align: "right", render: (w) => w.attempts },
  { key: "code", header: "HTTP", align: "right", render: (w) => w.responseCode || "—" },
  {
    key: "lastAttempt",
    header: "Last attempt",
    render: (w) =>
      w.lastAttempt
        ? new Date(w.lastAttempt).toLocaleString(undefined, {
            dateStyle: "medium",
            timeStyle: "short",
          })
        : "—",
  },
  {
    key: "actions",
    header: "Actions",
    render: (w) => <DeliveryRowActions row={w} />,
  },
];

function DeliveryRowActions({ row }: { row: DeliveryRow }) {
  const { retry } = useWebhooksContext();
  const { notify } = useFeedback();
  const { canOperate } = usePlatformPermissions();
  const [busy, setBusy] = useState(false);

  if (row.status === "Delivered") {
    return <span className="adm-muted">—</span>;
  }

  if (!canOperate) {
    return <span className="adm-muted">—</span>;
  }

  const handle = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await retry({ rawId: row.rawId });
      notify({
        tone: "success",
        title: "Retry queued",
        description: `${row.event || row.id} will be re-emitted shortly.`,
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Retry failed",
        description: err instanceof Error ? err.message : "Unable to schedule retry.",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <Button variant="ghost" icon={<RotateCcw size={14} />} onClick={handle} disabled={busy}>
      {busy ? "Replaying…" : "Replay"}
    </Button>
  );
}

// --- Tiny context to share retry() with the row renderer ----------------

const WebhooksCtx = createContext<UseWebhooksResult | null>(null);
function useWebhooksContext() {
  const ctx = useContext(WebhooksCtx);
  if (!ctx) throw new Error("Webhooks context missing");
  return ctx;
}

// -----------------------------------------------------------------------

export function WebhooksPage() {
  const { notify, confirm } = useFeedback();
  const { canRotateWebhookKey } = usePlatformPermissions();
  const [page, setPage] = useState(1);

  const result = useWebhooks({ page, pageSize: PAGE_SIZE });
  const { rows, total, loading, error, health } = result;

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const totalLabel = useMemo(() => `${total.toLocaleString()} deliveries`, [total]);

  async function rotateKey() {
    const ok = await confirm({
      title: "Rotate platform signing key?",
      description:
        "All previously signed webhooks remain valid for 24 hours. New deliveries will use the new key immediately.",
      confirmLabel: "Rotate key",
      destructive: true,
    });
    if (!ok) return;
    try {
      const body = await api.post<{
        ok: boolean;
        fingerprint: string;
        rotatedAt: string;
        gracePeriod: string;
        reason?: string;
      }>("/platform/webhooks/rotate-key", { grace_period: "24h", notify_channel: "email-webhook" });
      if (!body.ok) throw new Error(body.reason || "Could not rotate key.");
      notify({
        tone: "warning",
        title: "Signing key rotated",
        description: `New fingerprint ${body.fingerprint}. Previous key honored for ${body.gracePeriod}.`,
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not rotate key",
        description: err instanceof Error ? err.message : "Unable to rotate signing key.",
      });
    }
  }

  const delivered = health?.delivered ?? 0;
  const retrying = health?.retrying ?? 0;
  const failed = health?.failed ?? 0;
  const successRate = health?.successRate ?? 0;

  return (
    <WebhooksCtx.Provider value={result}>
      <PageHeader
        eyebrow="Outbound delivery"
        title="Webhooks"
        description="Inspect signed deliveries, retry queues, and verify HMAC signatures across every merchant endpoint."
        actions={
          canRotateWebhookKey ? (
            <Button icon={<ShieldCheck size={16} />} onClick={rotateKey}>
              Rotate signing key
            </Button>
          ) : null
        }
      />

      <section className="sp-grid sp-grid-4">
        <StatCard label="Delivered" value={String(delivered)} delta="2xx in last 24h" tone="success" />
        <StatCard label="Retrying" value={String(retrying)} delta="exponential backoff" tone="warning" />
        <StatCard label="Failed" value={String(failed)} delta="needs replay" tone="danger" />
        <StatCard
          label="Success rate"
          value={`${successRate}%`}
          delta={`${health?.total ?? 0} attempts`}
          tone="teal"
        />
      </section>

      <Card>
        <CardHeader
          title="Recent deliveries"
          description={
            loading
              ? "Loading…"
              : `${rows.length} of ${total} deliveries visible — tap replay on any row to re-emit the event with a fresh signature.`
          }
          action={<Badge tone="teal">Signed v1</Badge>}
        />
        {error ? (
          <div className="adm-empty-state">
            <p className="adm-muted">{error}</p>
          </div>
        ) : null}
        <DataTable columns={columns} rows={rows} getRowKey={(w) => w.rawId} />
        <Pagination page={page} pageCount={pageCount} totalLabel={totalLabel} onPageChange={setPage} />
      </Card>
    </WebhooksCtx.Provider>
  );
}
