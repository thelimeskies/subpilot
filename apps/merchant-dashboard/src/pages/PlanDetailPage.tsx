import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DataTable,
  Field,
  Sheet,
  StatCard,
  Tabs,
  TextInput,
  type DataTableColumn
} from "@subpilot/ui";
import { Archive, ArrowLeft } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { isApiError } from "../api/client";
import { useData } from "../data/store";
import { usePermissions } from "../auth/AuthContext";
import {
  computeMrr,
  findCustomerById,
  findSubscriptionsByPlan,
  formatCurrency
} from "../data/selectors";
import type { Subscription, Invoice } from "../data/seed";

type TabKey = "overview" | "subscribers" | "invoices" | "settings";

export function PlanDetailPage() {
  const { planId } = useParams<{ planId: string }>();
  const { plans, subscriptions, invoices, customers, archivePlan, updatePlan, logAuditEvent } = useData();
  const { notify, confirm } = useFeedback();
  const { can } = usePermissions();
  const canEditPlan = can("edit_plan");
  const canArchivePlan = can("activate_archive_plan");
  const canManagePlans = canEditPlan || canArchivePlan;
  const [tab, setTab] = useState<TabKey>("overview");
  const [priceSheet, setPriceSheet] = useState<null | { newAmount: string; grandfather: boolean }>(null);
  const [savingPrice, setSavingPrice] = useState(false);

  const plan = plans.find((p) => p.id === planId);

  const planSubs = useMemo<Subscription[]>(
    () => (plan ? findSubscriptionsByPlan(subscriptions, plan.id) : []),
    [plan, subscriptions]
  );
  const planInvoices = useMemo<Invoice[]>(
    () => (plan ? invoices.filter((i) => planSubs.some((s) => s.id === i.subscriptionId)) : []),
    [plan, invoices, planSubs]
  );

  if (!plan) {
    return (
      <div className="mer-empty-state">
        <h2>Plan not found</h2>
        <p>We couldn&rsquo;t find a plan with id <code>{planId}</code>.</p>
        <Link to="/plans" className="mer-card-link">
          <ArrowLeft size={14} aria-hidden="true" /> Back to plans
        </Link>
      </div>
    );
  }

  async function handleArchive() {
    if (!plan) return;
    const ok = await confirm({
      destructive: true,
      title: `Archive ${plan.name}?`,
      description: "Archived plans can't be assigned to new subscriptions.",
      confirmLabel: "Archive plan"
    });
    if (!ok) return;
    try {
      await archivePlan(plan.id);
      logAuditEvent({ actor: "You", action: "Archived plan", target: plan.name });
      notify({ tone: "info", title: "Plan archived", description: `${plan.name} is now closed to new subscriptions.` });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not archive plan",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }

  async function publishPriceChange() {
    if (!plan || !priceSheet) return;
    const next = Number(priceSheet.newAmount);
    if (Number.isNaN(next) || next <= 0) {
      notify({ tone: "warning", title: "Invalid amount", description: "Enter a positive amount to publish." });
      return;
    }
    setSavingPrice(true);
    try {
      await updatePlan(plan.id, { amount: next, currency: plan.currency, interval: plan.interval });
      logAuditEvent({
        actor: "You",
        action: "Published price change",
        target: `${plan.name} → ${formatCurrency(next, plan.currency)}${priceSheet.grandfather ? " (grandfathered)" : ""}`
      });
      notify({
        tone: "success",
        title: "Price change published",
        description: priceSheet.grandfather
          ? "Existing subscribers stay on the old price; new sign-ups pay the new price."
          : "New price applies on next renewal for all subscribers."
      });
      setPriceSheet(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not publish price change",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSavingPrice(false);
    }
  }

  const subColumns: DataTableColumn<Subscription>[] = [
    {
      key: "customer",
      header: "Customer",
      render: (s) => {
        const c = findCustomerById(customers, s.customerId);
        return (
          <Link to={`/customers/${s.customerId}`} className="mer-entity-cell">
            <strong>{c?.name ?? s.customerId}</strong>
            <small>{c?.email ?? ""}</small>
          </Link>
        );
      }
    },
    {
      key: "status",
      header: "Status",
      render: (s) => <Badge tone={subTone(s.status)}>{prettyStatus(s.status)}</Badge>
    },
    { key: "amount", header: "Amount", align: "right", render: (s) => formatCurrency(s.amount, plan.currency) },
    { key: "started", header: "Started", render: (s) => s.startedAt }
  ];

  const invoiceColumns: DataTableColumn<Invoice>[] = [
    {
      key: "number",
      header: "Invoice",
      render: (i) => (
        <Link to={`/invoices/${i.id}`} className="mer-entity-cell">
          <strong>{i.number}</strong>
          <small>{findCustomerById(customers, i.customerId)?.name ?? i.customerId}</small>
        </Link>
      )
    },
    {
      key: "status",
      header: "Status",
      render: (i) => <Badge tone={invoiceTone(i.status)}>{prettyStatus(i.status)}</Badge>
    },
    { key: "amount", header: "Amount", align: "right", render: (i) => formatCurrency(i.amountDue, plan.currency) },
    { key: "issued", header: "Issued", render: (i) => i.issuedAt }
  ];

  return (
    <>
      <PageHeader
        eyebrow={
          <span className="mer-breadcrumb-eyebrow">
            <Link to="/plans" className="mer-card-link">
              <ArrowLeft size={12} aria-hidden="true" /> Plans
            </Link>
            <span> / {plan.code}</span>
          </span>
        }
        title={plan.name}
        description={`${plan.description} · ${formatCurrency(plan.amount, plan.currency)} per ${plan.interval}`}
        actions={
          canManagePlans ? (
            <>
              {canEditPlan ? (
                <Button
                  variant="secondary"
                  onClick={() => setPriceSheet({ newAmount: String(plan.amount), grandfather: true })}
                >
                  Publish change
                </Button>
              ) : null}
              {canArchivePlan ? (
                <Button variant="danger" icon={<Archive size={16} />} onClick={handleArchive}>
                  Archive plan
                </Button>
              ) : null}
            </>
          ) : null
        }
      />

      <div className="mer-detail-meta">
        <Badge tone={plan.status === "active" ? "success" : plan.status === "draft" ? "info" : "neutral"}>
          {plan.status[0].toUpperCase() + plan.status.slice(1)}
        </Badge>
        <span>Code <code className="mer-code">{plan.code}</code></span>
        <span>Trial {plan.trialDays > 0 ? `${plan.trialDays} days` : "none"}</span>
        <span>Created {plan.createdAt}</span>
      </div>

      <Tabs
        value={tab}
        onChange={(v) => setTab(v as TabKey)}
        items={[
          { label: "Overview", value: "overview" },
          { label: "Subscribers", value: "subscribers", count: planSubs.length },
          { label: "Invoices", value: "invoices", count: planInvoices.length },
          { label: "Settings", value: "settings" }
        ]}
      />

      {tab === "overview" ? (
        <section className="sp-grid sp-grid-4">
          <StatCard label="Subscribers" value={String(planSubs.length)} delta={`${planSubs.filter((s) => s.status === "active").length} active`} tone="success" />
          <StatCard label="Plan MRR" value={formatCurrency(computeMrr(planSubs), plan.currency)} delta="Normalized" tone="teal" />
          <StatCard label="Invoices" value={String(planInvoices.length)} delta={`${planInvoices.filter((i) => i.status === "paid").length} paid`} tone="info" />
          <StatCard label="Past due" value={String(planInvoices.filter((i) => i.status === "past_due").length)} delta="Needs attention" tone="warning" />
        </section>
      ) : null}

      {tab === "subscribers" ? (
        <Card>
          <CardHeader title="Subscribers on this plan" description={`${planSubs.length} subscription${planSubs.length === 1 ? "" : "s"}.`} />
          {planSubs.length ? (
            <DataTable columns={subColumns} rows={planSubs} getRowKey={(s) => s.id} />
          ) : (
            <p className="mer-empty">No subscriptions on this plan yet.</p>
          )}
        </Card>
      ) : null}

      {tab === "invoices" ? (
        <Card>
          <CardHeader title="Invoices generated by this plan" description={`${planInvoices.length} invoice${planInvoices.length === 1 ? "" : "s"}.`} />
          {planInvoices.length ? (
            <DataTable columns={invoiceColumns} rows={planInvoices} getRowKey={(i) => i.id} />
          ) : (
            <p className="mer-empty">No invoices issued from this plan.</p>
          )}
        </Card>
      ) : null}

      {tab === "settings" ? (
        <Card>
          <CardHeader title="Plan settings" description="Code, status, and pricing controls live here. Use 'Publish change' to roll out a new price." />
          <div className="mer-stack">
            <div className="mer-totals__row"><span>Code</span><strong className="mer-code">{plan.code}</strong></div>
            <div className="mer-totals__row"><span>Status</span><strong>{plan.status}</strong></div>
            <div className="mer-totals__row"><span>Amount</span><strong>{formatCurrency(plan.amount, plan.currency)}</strong></div>
            <div className="mer-totals__row"><span>Interval</span><strong>{plan.interval}</strong></div>
            <div className="mer-totals__row"><span>Trial days</span><strong>{plan.trialDays}</strong></div>
            <div className="mer-totals__row"><span>Subscribers</span><strong>{plan.subscribers}</strong></div>
          </div>
        </Card>
      ) : null}

      <Sheet
        open={!!priceSheet}
        title="Publish price change"
        description="Update this plan's price. You can grandfather existing subscribers or roll out for everyone on next renewal."
        onClose={() => setPriceSheet(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPriceSheet(null)}>Cancel</Button>
            <Button onClick={publishPriceChange} disabled={savingPrice}>
              {savingPrice ? "Publishing…" : "Publish change"}
            </Button>
          </>
        }
      >
        {priceSheet ? (
          <div className="mer-stack">
            <Field label="New amount" hint={`Currency: ${plan.currency}`}>
              <TextInput
                type="number"
                inputMode="numeric"
                value={priceSheet.newAmount}
                onChange={(e) => setPriceSheet({ ...priceSheet, newAmount: e.target.value })}
              />
            </Field>
            <label className="mer-toggle-row">
              <input
                type="checkbox"
                checked={priceSheet.grandfather}
                onChange={(e) => setPriceSheet({ ...priceSheet, grandfather: e.target.checked })}
              />
              <span>Grandfather existing subscribers (keep their current price)</span>
            </label>
          </div>
        ) : null}
      </Sheet>
    </>
  );
}

function subTone(status: Subscription["status"]): "success" | "warning" | "danger" | "info" | "neutral" {
  switch (status) {
    case "active": return "success";
    case "trialing": return "info";
    case "past_due": return "warning";
    case "paused": return "info";
    case "cancelled": return "neutral";
    case "incomplete": return "warning";
    default: return "neutral";
  }
}

function invoiceTone(status: Invoice["status"]): "success" | "warning" | "danger" | "info" | "neutral" {
  switch (status) {
    case "paid": return "success";
    case "open": return "info";
    case "past_due": return "warning";
    case "uncollectible": return "danger";
    case "void": return "neutral";
    case "draft": return "neutral";
    default: return "neutral";
  }
}

function prettyStatus(status: string): string {
  return status
    .split("_")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}
