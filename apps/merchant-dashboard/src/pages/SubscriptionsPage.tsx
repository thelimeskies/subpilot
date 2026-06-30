import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  DataTable,
  Field,
  Pagination,
  SelectInput,
  Sheet,
  TextInput,
  Toggle,
  type DataTableColumn
} from "@subpilot/ui";
import { Pause, Play, Plus, Search, Slash, X } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePagination } from "../hooks/usePagination";
import { useFeedback } from "../feedback/ActionFeedback";
import { isApiError } from "../api/client";
import { useData } from "../data/store";
import { usePermissions } from "../auth/AuthContext";
import { findCustomerById, findPlanById, formatCurrency } from "../data/selectors";
import type { Subscription, SubscriptionStatus } from "../data/seed";

const STATUS_FILTER_OPTIONS: Array<{ label: string; value: SubscriptionStatus | "all" }> = [
  { label: "All statuses", value: "all" },
  { label: "Active", value: "active" },
  { label: "Trialing", value: "trialing" },
  { label: "Past due", value: "past_due" },
  { label: "Paused", value: "paused" },
  { label: "Cancelled", value: "cancelled" },
  { label: "Incomplete", value: "incomplete" }
];

interface CreateForm {
  customerId: string;
  planId: string;
  startDate: string;
  trialOverride: string;
  prorate: boolean;
  paymentMethodId: string;
}

interface PauseForm {
  reason: string;
  resumeAt: string;
}

export function SubscriptionsPage() {
  const {
    subscriptions,
    customers,
    plans,
    createSubscription,
    cancelSubscription,
    pauseSubscription,
    resumeSubscription,
    logAuditEvent
  } = useData();
  const { can } = usePermissions();
  const canCreate = can("create_subscription");
  const canPause = can("pause_resume_subscription");
  const canCancel = can("cancel_subscription");
  const { notify, confirm } = useFeedback();
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [planFilter, setPlanFilter] = useState<string>("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<CreateForm>(emptyCreateForm(customers, plans));
  const [pauseTarget, setPauseTarget] = useState<{ id: string; form: PauseForm } | null>(null);
  const [savingCreate, setSavingCreate] = useState(false);
  const [savingPause, setSavingPause] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return subscriptions.filter((s) => {
      if (statusFilter !== "all" && s.status !== statusFilter) return false;
      if (planFilter !== "all" && s.planId !== planFilter) return false;
      if (!q) return true;
      const customer = findCustomerById(customers, s.customerId);
      const plan = findPlanById(plans, s.planId);
      return [s.id, customer?.name, customer?.email, plan?.name, plan?.code]
        .filter(Boolean)
        .some((field) => field!.toLowerCase().includes(q));
    });
  }, [subscriptions, customers, plans, query, statusFilter, planFilter]);

  const { page, setPage, pageCount, slice, totalLabel } = usePagination(filtered, 10, "subscriptions");

  function openCreate() {
    setCreateForm(emptyCreateForm(customers, plans));
    setCreateOpen(true);
  }

  function patchCreate(patch: Partial<CreateForm>) {
    setCreateForm((prev) => ({ ...prev, ...patch }));
  }

  async function submitCreate() {
    const customer = customers.find((c) => c.id === createForm.customerId);
    const plan = plans.find((p) => p.id === createForm.planId);
    if (!customer || !plan) {
      notify({ tone: "warning", title: "Missing details", description: "Pick a customer and a plan to continue." });
      return;
    }
    const trialEnd = createForm.trialOverride
      ? addDays(createForm.startDate, Number(createForm.trialOverride) || 0)
      : plan.trialDays > 0
      ? addDays(createForm.startDate, plan.trialDays)
      : null;
    setSavingCreate(true);
    try {
      await createSubscription({
        customerId: customer.id,
        planId: plan.id,
        status: trialEnd ? "trialing" : "active",
        startedAt: createForm.startDate,
        currentPeriodStart: createForm.startDate,
        currentPeriodEnd: addDays(createForm.startDate, plan.interval === "yearly" ? 365 : plan.interval === "weekly" ? 7 : 30),
        cancelAt: null,
        trialEnd,
        amount: plan.amount,
        interval: plan.interval,
        paymentMethodId: createForm.paymentMethodId || customer.defaultMethodId,
        notes: createForm.prorate ? "Prorated start." : ""
      });
      logAuditEvent({ actor: "You", action: "Created subscription", target: `${customer.name} → ${plan.name}` });
      notify({ tone: "success", title: "Subscription created", description: `${customer.name} is on ${plan.name}.` });
      setCreateOpen(false);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not create subscription",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSavingCreate(false);
    }
  }

  async function handleCancel(sub: Subscription) {
    const customer = findCustomerById(customers, sub.customerId);
    const ok = await confirm({
      destructive: true,
      title: `Cancel subscription?`,
      description: `${customer?.name ?? sub.customerId} — choose how to end this subscription. End-of-period stays active until ${sub.currentPeriodEnd}; immediate stops billing now.`,
      confirmLabel: "Cancel immediately"
    });
    if (!ok) return;
    try {
      await cancelSubscription(sub.id, "immediate");
      logAuditEvent({ actor: "You", action: "Cancelled subscription", target: sub.id });
      notify({ tone: "info", title: "Subscription cancelled", description: "Customer was notified by email." });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not cancel subscription",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }

  function openPause(sub: Subscription) {
    setPauseTarget({
      id: sub.id,
      form: { reason: "Customer requested pause", resumeAt: addDays(new Date().toISOString().slice(0, 10), 30) }
    });
  }

  async function submitPause() {
    if (!pauseTarget) return;
    setSavingPause(true);
    try {
      await pauseSubscription(pauseTarget.id, pauseTarget.form.resumeAt, pauseTarget.form.reason);
      logAuditEvent({ actor: "You", action: "Paused subscription", target: pauseTarget.id });
      notify({ tone: "info", title: "Subscription paused", description: `Resume target set for ${pauseTarget.form.resumeAt}.` });
      setPauseTarget(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not pause subscription",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSavingPause(false);
    }
  }

  async function handleResume(sub: Subscription) {
    const ok = await confirm({
      title: "Resume subscription?",
      description: "Billing will pick up on the next scheduled period.",
      confirmLabel: "Resume"
    });
    if (!ok) return;
    try {
      await resumeSubscription(sub.id);
      logAuditEvent({ actor: "You", action: "Resumed subscription", target: sub.id });
      notify({ tone: "success", title: "Subscription resumed", description: "Billing scheduler is active again." });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not resume subscription",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }

  const columns: DataTableColumn<Subscription>[] = [
    {
      key: "customer",
      header: "Customer",
      render: (s) => {
        const c = findCustomerById(customers, s.customerId);
        return (
          <Link to={`/subscriptions/${s.id}`} className="mer-entity-cell">
            <strong>{c?.name ?? s.customerId}</strong>
            <small>{s.id} · {c?.email ?? ""}</small>
          </Link>
        );
      }
    },
    {
      key: "plan",
      header: "Plan",
      render: (s) => {
        const p = findPlanById(plans, s.planId);
        return p ? <Link to={`/plans/${p.id}`} className="mer-entity-cell"><strong>{p.name}</strong><small>{p.code}</small></Link> : <span>{s.planId}</span>;
      }
    },
    {
      key: "status",
      header: "Status",
      render: (s) => <Badge tone={subTone(s.status)}>{prettyStatus(s.status)}</Badge>
    },
    { key: "amount", header: "Amount", align: "right", render: (s) => formatCurrency(s.amount) },
    { key: "next", header: "Next bill", render: (s) => s.cancelAt ?? s.currentPeriodEnd },
    {
      key: "actions",
      header: "",
      render: (s) => (
        <div className="mer-row-actions">
          <Link to={`/subscriptions/${s.id}`} className="sp-button sp-button--ghost mer-row-actions__link">View</Link>
          {canPause && s.status === "paused" ? (
            <Button variant="ghost" icon={<Play size={14} />} onClick={() => handleResume(s)}>Resume</Button>
          ) : canPause && s.status !== "cancelled" ? (
            <Button variant="ghost" icon={<Pause size={14} />} onClick={() => openPause(s)}>Pause</Button>
          ) : null}
          {canCancel && s.status !== "cancelled" ? (
            <Button variant="ghost" icon={<X size={14} />} onClick={() => handleCancel(s)}>Cancel</Button>
          ) : null}
        </div>
      )
    }
  ];

  return (
    <>
      <PageHeader
        eyebrow="Recurring revenue"
        title="Subscriptions"
        description="Every recurring billing relationship lives here. Create, pause, change, and cancel from a single screen."
        actions={
          canCreate ? (
            <Button icon={<Plus size={16} />} onClick={openCreate}>
              Create subscription
            </Button>
          ) : null
        }
      />

      <Card>
        <CardHeader
          title="All subscriptions"
          description={`${filtered.length} of ${subscriptions.length} subscriptions match`}
          action={<Badge tone="teal">{subscriptions.filter((s) => s.status === "active").length} active</Badge>}
        />
        <div className="mer-filter-row">
          <span className="mer-input-wrap mer-input-wrap--flex">
            <Search size={16} aria-hidden="true" />
            <TextInput
              type="search"
              placeholder="Search customer, plan, or sub id"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </span>
          <SelectInput value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Status filter">
            {STATUS_FILTER_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </SelectInput>
          <SelectInput value={planFilter} onChange={(e) => setPlanFilter(e.target.value)} aria-label="Plan filter">
            <option value="all">All plans</option>
            {plans.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </SelectInput>
          {(statusFilter !== "all" || planFilter !== "all" || query) ? (
            <Button variant="ghost" icon={<Slash size={14} />} onClick={() => { setStatusFilter("all"); setPlanFilter("all"); setQuery(""); }}>Reset</Button>
          ) : null}
        </div>
        <DataTable columns={columns} rows={slice} getRowKey={(s) => s.id} />
        <Pagination page={page} pageCount={pageCount} totalLabel={totalLabel} onPageChange={setPage} />
      </Card>

      {/* Create sheet */}
      <Sheet
        open={createOpen}
        title="Create subscription"
        description="Pick a customer and plan, then choose start, trial, and proration behavior."
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={submitCreate} disabled={savingCreate}>
              {savingCreate ? "Creating…" : "Create subscription"}
            </Button>
          </>
        }
      >
        <div className="mer-stack">
          <Field label="Customer">
            <SelectInput value={createForm.customerId} onChange={(e) => patchCreate({ customerId: e.target.value })}>
              {customers
                .filter((c) => c.status !== "blocked")
                .map((c) => <option key={c.id} value={c.id}>{c.name} ({c.email})</option>)}
            </SelectInput>
          </Field>
          <Field label="Plan">
            <SelectInput value={createForm.planId} onChange={(e) => patchCreate({ planId: e.target.value })}>
              {plans
                .filter((p) => p.status === "active")
                .map((p) => <option key={p.id} value={p.id}>{p.name} — {formatCurrency(p.amount, p.currency)}/{p.interval}</option>)}
            </SelectInput>
          </Field>
          <div className="mer-form-grid">
            <Field label="Start date">
              <TextInput type="date" value={createForm.startDate} onChange={(e) => patchCreate({ startDate: e.target.value })} />
            </Field>
            <Field label="Trial override (days)" hint="Leave blank to use plan default.">
              <TextInput type="number" value={createForm.trialOverride} onChange={(e) => patchCreate({ trialOverride: e.target.value })} />
            </Field>
          </div>
          <Toggle checked={createForm.prorate} onChange={(checked: boolean) => patchCreate({ prorate: checked })} label="Prorate first period" />
          <Field label="Payment method id" hint="Override the default card; leave blank for customer default.">
            <TextInput value={createForm.paymentMethodId} onChange={(e) => patchCreate({ paymentMethodId: e.target.value })} />
          </Field>
        </div>
      </Sheet>

      {/* Pause sheet */}
      <Sheet
        open={!!pauseTarget}
        title="Pause subscription"
        description="Provide a reason and a target date for resuming billing."
        onClose={() => setPauseTarget(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPauseTarget(null)}>Cancel</Button>
            <Button onClick={submitPause} disabled={savingPause}>
              {savingPause ? "Pausing…" : "Pause subscription"}
            </Button>
          </>
        }
      >
        {pauseTarget ? (
          <div className="mer-stack">
            <Field label="Reason">
              <TextInput
                value={pauseTarget.form.reason}
                onChange={(e) => setPauseTarget({ ...pauseTarget, form: { ...pauseTarget.form, reason: e.target.value } })}
              />
            </Field>
            <Field label="Resume on">
              <TextInput
                type="date"
                value={pauseTarget.form.resumeAt}
                onChange={(e) => setPauseTarget({ ...pauseTarget, form: { ...pauseTarget.form, resumeAt: e.target.value } })}
              />
            </Field>
          </div>
        ) : null}
      </Sheet>
    </>
  );
}

function emptyCreateForm(customers: ReturnType<typeof useData>["customers"], plans: ReturnType<typeof useData>["plans"]): CreateForm {
  return {
    customerId: customers.find((c) => c.status === "active")?.id ?? customers[0]?.id ?? "",
    planId: plans.find((p) => p.status === "active")?.id ?? plans[0]?.id ?? "",
    startDate: new Date().toISOString().slice(0, 10),
    trialOverride: "",
    prorate: true,
    paymentMethodId: ""
  };
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

function subTone(status: SubscriptionStatus): "success" | "warning" | "danger" | "info" | "neutral" {
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

function prettyStatus(status: string): string {
  return status
    .split("_")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}
