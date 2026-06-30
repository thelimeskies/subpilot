import { createContext, useContext, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DataTable,
  Pagination,
  type DataTableColumn,
} from "@subpilot/ui";
import { Copy, ShieldOff } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { useApiKeys, type ApiKeyRow, type UseApiKeysResult } from "../api/api-keys";
import { usePlatformPermissions } from "../auth/AuthContext";

const PAGE_SIZE = 10;

const columns: DataTableColumn<ApiKeyRow>[] = [
  {
    key: "label",
    header: "Key",
    render: (k) => (
      <span className="adm-entity-cell">
        <strong>{k.label}</strong>
        <small>
          <code className="adm-code">{k.prefix}</code>
        </small>
      </span>
    ),
  },
  {
    key: "scope",
    header: "Scope",
    render: (k) => <Badge tone={k.scope === "Live" ? "teal" : "neutral"}>{k.scope}</Badge>,
  },
  { key: "merchant", header: "Merchant", render: (k) => k.merchant },
  { key: "createdBy", header: "Created by", render: (k) => k.createdBy },
  {
    key: "createdAt",
    header: "Created",
    render: (k) =>
      k.createdAt
        ? new Date(k.createdAt).toLocaleDateString(undefined, { dateStyle: "medium" })
        : "—",
  },
  {
    key: "lastUsed",
    header: "Last used",
    render: (k) =>
      k.lastUsed
        ? new Date(k.lastUsed).toLocaleString(undefined, {
            dateStyle: "medium",
            timeStyle: "short",
          })
        : "—",
  },
  {
    key: "status",
    header: "Status",
    render: (k) => (
      <Badge tone={k.status === "Active" ? "success" : "neutral"}>{k.status}</Badge>
    ),
  },
  {
    key: "actions",
    header: "Actions",
    render: (k) => <ApiKeyRowActions row={k} />,
  },
];

function ApiKeyRowActions({ row }: { row: ApiKeyRow }) {
  const { revoke } = useApiKeysContext();
  const { notify, confirm } = useFeedback();
  const { canOperate } = usePlatformPermissions();
  const [busy, setBusy] = useState(false);

  async function copyText(value: string, label: string) {
    try {
      await navigator.clipboard?.writeText(value);
      notify({ tone: "success", title: "Copied", description: `${label} copied to clipboard.` });
    } catch {
      notify({
        tone: "warning",
        title: "Copy unavailable",
        description: "Clipboard access was blocked by the browser.",
      });
    }
  }

  const handleRevoke = async () => {
    if (busy) return;
    const ok = await confirm({
      title: `Revoke ${row.label}?`,
      description:
        "Outstanding requests using this key will start failing immediately. This cannot be undone.",
      confirmLabel: "Revoke key",
      destructive: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await revoke({ rawId: row.rawId });
      notify({
        tone: "danger",
        title: "Key revoked",
        description: `${row.label} (${row.prefix}) has been revoked.`,
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Revoke failed",
        description: err instanceof Error ? err.message : "Unable to revoke key.",
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <span className="adm-row-actions">
      <Button
        variant="ghost"
        icon={<Copy size={14} />}
        aria-label="Copy prefix"
        onClick={() => copyText(row.prefix, "Key prefix")}
      />
      {row.status === "Active" && canOperate ? (
        <Button
          variant="danger"
          icon={<ShieldOff size={14} />}
          onClick={handleRevoke}
          disabled={busy}
        >
          {busy ? "Revoking…" : "Revoke"}
        </Button>
      ) : (
        <span className="adm-muted">{row.status === "Active" ? "—" : "Revoked"}</span>
      )}
    </span>
  );
}

// --- Tiny context to share revoke() with the row renderer ---------------

const ApiKeysCtx = createContext<UseApiKeysResult | null>(null);
function useApiKeysContext() {
  const ctx = useContext(ApiKeysCtx);
  if (!ctx) throw new Error("ApiKeys context missing");
  return ctx;
}

// -----------------------------------------------------------------------

export function ApiKeysPage() {
  const [page, setPage] = useState(1);

  const result = useApiKeys({ page, pageSize: PAGE_SIZE });
  const { rows, total, loading, error } = result;

  const pageCount = Math.max(1, Math.ceil(total / PAGE_SIZE));
  const totalLabel = useMemo(() => `${total.toLocaleString()} keys`, [total]);

  return (
    <ApiKeysCtx.Provider value={result}>
      <PageHeader
        eyebrow="Platform credentials"
        title="API keys"
        description="Audit and revoke service credentials issued by SubPilot merchants. Live keys grant production scope; test keys hit the sandbox adapter. Keys are created merchant-side; the platform team can only inspect and revoke."
      />

      <Card>
        <CardHeader
          title="Active &amp; revoked keys"
          description={
            loading
              ? "Loading…"
              : `${rows.length} of ${total} keys visible — audit who created which credential and when it was last used.`
          }
        />
        {error ? (
          <div className="adm-empty-state">
            <p className="adm-muted">{error}</p>
          </div>
        ) : null}
        <DataTable columns={columns} rows={rows} getRowKey={(k) => k.rawId} />
        <Pagination page={page} pageCount={pageCount} totalLabel={totalLabel} onPageChange={setPage} />
      </Card>
    </ApiKeysCtx.Provider>
  );
}
