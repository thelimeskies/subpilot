import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Badge, Button, Card, CardHeader, DataTable, Pagination, TextInput, type DataTableColumn } from "@subpilot/ui";
import { Plus, Search } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePagination } from "../hooks/usePagination";
import { useFeedback } from "../feedback/ActionFeedback";
import { useMerchants, type MerchantRow } from "../api/merchants";
import { usePlatformPermissions } from "../auth/AuthContext";

const columns: DataTableColumn<MerchantRow>[] = [
  {
    key: "merchant",
    header: "Merchant",
    render: (m) => (
      <Link to={`/merchants/${m.id}`} className="adm-entity-cell">
        <strong>{m.name}</strong>
        <small>{m.id} · {m.region}</small>
      </Link>
    )
  },
  { key: "owner", header: "Owner", render: (m) => <span><strong>{m.owner}</strong><br /><small className="adm-muted">{m.ownerEmail}</small></span> },
  { key: "plan", header: "Plan", render: (m) => m.plan },
  { key: "mrr", header: "MRR", align: "right", render: (m) => m.mrr },
  {
    key: "status",
    header: "Status",
    render: (m) => (
      <Badge tone={m.status === "Healthy" ? "success" : m.status === "At risk" ? "warning" : "danger"}>{m.status}</Badge>
    )
  },
  { key: "failed", header: "Failed", align: "right", render: (m) => m.failedInvoices },
  { key: "recovery", header: "Recovery", align: "right", render: (m) => m.recoveryRate },
  {
    key: "env",
    header: "Env",
    render: (m) => <Badge tone={m.environment === "Live" ? "teal" : "neutral"}>{m.environment}</Badge>
  }
];

export function MerchantsPage() {
  const { notify } = useFeedback();
  const { canEditMerchantConfig } = usePlatformPermissions();
  const [query, setQuery] = useState("");
  const { rows, total, loading, error } = useMerchants({ pageSize: 100 });

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((m) =>
      [m.name, m.id, m.owner, m.ownerEmail, m.region, m.plan].some((field) =>
        (field ?? "").toLowerCase().includes(q)
      )
    );
  }, [rows, query]);

  const { page, setPage, pageCount, slice, totalLabel } = usePagination(filtered, 10, "merchants");

  return (
    <>
      <PageHeader
        eyebrow="Tenant directory"
        title="Merchants"
        description="Search, filter, and open any merchant workspace to inspect billing volume, recovery posture, and adapter health."
        actions={
          canEditMerchantConfig ? (
            <Button
              icon={<Plus size={16} />}
              onClick={() =>
                notify({
                  tone: "info",
                  title: "Invite a new merchant",
                  description: "The onboarding wizard will start in a fresh tab. We'll send you a copy of the invite."
                })
              }
            >
              Add merchant
            </Button>
          ) : null
        }
      />

      {error ? (
        <Card>
          <CardHeader title="Could not load merchants" description={error} />
        </Card>
      ) : null}

      <Card>
        <CardHeader
          title="All merchants"
          description={`${filtered.length} of ${total} tenants visible${loading ? " · loading…" : ""}`}
          action={<Badge tone="teal">Live data</Badge>}
        />
        <div className="adm-search-row">
          <span className="adm-input-wrap adm-input-wrap--flex">
            <Search size={16} aria-hidden="true" />
            <TextInput
              type="search"
              placeholder="Search merchants, owners, or merchant IDs"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </span>
        </div>
        <DataTable columns={columns} rows={slice} getRowKey={(m) => m.id} />
        <Pagination page={page} pageCount={pageCount} totalLabel={totalLabel} onPageChange={setPage} />
      </Card>
    </>
  );
}
