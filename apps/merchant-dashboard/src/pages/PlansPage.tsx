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
  type DataTableColumn
} from "@subpilot/ui";
import { Archive, Copy, Pencil, Plus, Search } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePagination } from "../hooks/usePagination";
import { useFeedback } from "../feedback/ActionFeedback";
import { isApiError } from "../api/client";
import { useData } from "../data/store";
import { usePermissions } from "../auth/AuthContext";
import { formatCurrency } from "../data/selectors";
import type { Plan, PlanInterval, PlanStatus } from "../data/seed";

interface PlanForm {
  name: string;
  code: string;
  amount: string;
  currency: Plan["currency"];
  interval: PlanInterval;
  trialDays: string;
  description: string;
  status: PlanStatus;
}

const EMPTY_FORM: PlanForm = {
  name: "",
  code: "",
  amount: "",
  currency: "NGN",
  interval: "monthly",
  trialDays: "14",
  description: "",
  status: "active"
};

export function PlansPage() {
  const { plans, createPlan, updatePlan, archivePlan, duplicatePlan, logAuditEvent } = useData();
  const { notify, confirm } = useFeedback();
  const { can } = usePermissions();
  const canCreate = can("create_plan");
  const canEdit = can("edit_plan");
  const canArchive = can("activate_archive_plan");
  const [query, setQuery] = useState("");
  const [editing, setEditing] = useState<{ mode: "create" | "edit"; planId: string | null; form: PlanForm } | null>(null);
  const [saving, setSaving] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return plans;
    return plans.filter((p) =>
      [p.name, p.code, p.description, p.status].some((field) => field.toLowerCase().includes(q))
    );
  }, [plans, query]);

  const { page, setPage, pageCount, slice, totalLabel } = usePagination(filtered, 10, "plans");

  function openCreate() {
    setEditing({ mode: "create", planId: null, form: { ...EMPTY_FORM } });
  }

  function openEdit(plan: Plan) {
    setEditing({
      mode: "edit",
      planId: plan.id,
      form: {
        name: plan.name,
        code: plan.code,
        amount: String(plan.amount),
        currency: plan.currency,
        interval: plan.interval,
        trialDays: String(plan.trialDays),
        description: plan.description,
        status: plan.status
      }
    });
  }

  function patchForm(patch: Partial<PlanForm>) {
    setEditing((prev) => (prev ? { ...prev, form: { ...prev.form, ...patch } } : prev));
  }

  async function submitForm() {
    if (!editing) return;
    const amount = Number(editing.form.amount);
    const trialDays = Number(editing.form.trialDays);
    if (!editing.form.name.trim() || !editing.form.code.trim() || Number.isNaN(amount) || amount <= 0) {
      notify({ tone: "warning", title: "Missing fields", description: "Name, code, and a positive amount are required." });
      return;
    }
    const payload = {
      name: editing.form.name.trim(),
      code: editing.form.code.trim().toUpperCase(),
      amount,
      currency: editing.form.currency,
      interval: editing.form.interval,
      trialDays: Number.isNaN(trialDays) ? 0 : trialDays,
      description: editing.form.description.trim(),
      status: editing.form.status
    };

    setSaving(true);
    try {
      if (editing.mode === "create") {
        await createPlan(payload);
        logAuditEvent({ actor: "You", action: "Created plan", target: editing.form.name });
        notify({ tone: "success", title: "Plan created", description: `${editing.form.name} is ready for new subscriptions.` });
      } else if (editing.planId) {
        await updatePlan(editing.planId, payload);
        logAuditEvent({ actor: "You", action: "Updated plan", target: editing.form.name });
        notify({ tone: "success", title: "Plan updated", description: `${editing.form.name} changes saved.` });
      }
      setEditing(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: editing.mode === "create" ? "Could not create plan" : "Could not update plan",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSaving(false);
    }
  }

  async function handleArchive(plan: Plan) {
    const ok = await confirm({
      destructive: true,
      title: `Archive ${plan.name}?`,
      description: "Archived plans can't be assigned to new subscriptions. Existing subscriptions keep billing as usual.",
      confirmLabel: "Archive plan"
    });
    if (!ok) return;
    try {
      await archivePlan(plan.id);
      logAuditEvent({ actor: "You", action: "Archived plan", target: plan.name });
      notify({ tone: "info", title: "Plan archived", description: `${plan.name} is closed to new subscriptions.` });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not archive plan",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }

  async function handleDuplicate(plan: Plan) {
    try {
      const newId = await duplicatePlan(plan.id);
    if (!newId) return;
      logAuditEvent({ actor: "You", action: "Duplicated plan", target: plan.name });
      notify({ tone: "success", title: "Plan duplicated", description: `Copy of ${plan.name} created as draft.` });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not duplicate plan",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }

  const columns: DataTableColumn<Plan>[] = [
    {
      key: "name",
      header: "Plan",
      render: (p) => (
        <Link to={`/plans/${p.id}`} className="mer-entity-cell">
          <strong>{p.name}</strong>
          <small>{p.code} · {p.description.slice(0, 48)}{p.description.length > 48 ? "…" : ""}</small>
        </Link>
      )
    },
    {
      key: "price",
      header: "Price",
      align: "right",
      render: (p) => (
        <span className="mer-entity-cell" style={{ textAlign: "right" }}>
          <strong>{formatCurrency(p.amount, p.currency)}</strong>
          <small>per {p.interval}</small>
        </span>
      )
    },
    { key: "trial", header: "Trial", align: "right", render: (p) => (p.trialDays > 0 ? `${p.trialDays}d` : "—") },
    { key: "subs", header: "Subscribers", align: "right", render: (p) => p.subscribers.toLocaleString("en-NG") },
    {
      key: "status",
      header: "Status",
      render: (p) => (
        <Badge tone={p.status === "active" ? "success" : p.status === "draft" ? "info" : "neutral"}>
          {p.status[0].toUpperCase() + p.status.slice(1)}
        </Badge>
      )
    },
    // Row-action column is only useful for roles that can mutate plans;
    // for read-only viewers we drop it entirely so the table stays clean.
    ...((canEdit || canCreate || canArchive)
      ? [{
          key: "actions",
          header: "",
          render: (p: Plan) => (
            <div className="mer-row-actions">
              {canEdit ? (
                <Button variant="ghost" icon={<Pencil size={14} />} onClick={() => openEdit(p)}>
                  Edit
                </Button>
              ) : null}
              {canCreate ? (
                <Button variant="ghost" icon={<Copy size={14} />} onClick={() => handleDuplicate(p)}>
                  Duplicate
                </Button>
              ) : null}
              {canArchive ? (
                <Button variant="ghost" icon={<Archive size={14} />} onClick={() => handleArchive(p)}>
                  Archive
                </Button>
              ) : null}
            </div>
          )
        } as DataTableColumn<Plan>]
      : [])
  ];

  return (
    <>
      <PageHeader
        eyebrow="Catalogue"
        title="Plans"
        description="Define what customers pay. Plans here power your subscriptions and the customer portal."
        actions={
          canCreate ? (
            <Button icon={<Plus size={16} />} onClick={openCreate}>
              Create plan
            </Button>
          ) : null
        }
      />

      <Card>
        <CardHeader
          title="All plans"
          description={`${filtered.length} of ${plans.length} plans visible`}
          action={<Badge tone="teal">{plans.filter((p) => p.status === "active").length} active</Badge>}
        />
        <div className="mer-search-row">
          <span className="mer-input-wrap mer-input-wrap--flex">
            <Search size={16} aria-hidden="true" />
            <TextInput
              type="search"
              placeholder="Search plans by name, code, or description"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </span>
        </div>
        <DataTable columns={columns} rows={slice} getRowKey={(p) => p.id} />
        <Pagination page={page} pageCount={pageCount} totalLabel={totalLabel} onPageChange={setPage} />
      </Card>

      <Sheet
        open={!!editing}
        title={editing?.mode === "edit" ? "Edit plan" : "Create plan"}
        description="Plans are blueprint pricing. Subscriptions inherit defaults but can override per-customer."
        onClose={() => setEditing(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
            <Button onClick={submitForm} disabled={saving}>
              {saving ? "Saving…" : editing?.mode === "edit" ? "Save changes" : "Create plan"}
            </Button>
          </>
        }
      >
        {editing ? (
          <div className="mer-stack">
            <Field label="Plan name" hint="Visible to customers in checkout and the portal.">
              <TextInput value={editing.form.name} onChange={(e) => patchForm({ name: e.target.value })} />
            </Field>
            <Field label="Plan code" hint="Internal identifier. Uppercase, no spaces.">
              <TextInput value={editing.form.code} onChange={(e) => patchForm({ code: e.target.value.toUpperCase() })} />
            </Field>
            <div className="mer-form-grid">
              <Field label="Amount">
                <TextInput
                  type="number"
                  inputMode="numeric"
                  value={editing.form.amount}
                  onChange={(e) => patchForm({ amount: e.target.value })}
                />
              </Field>
              <Field label="Currency">
                <SelectInput
                  value={editing.form.currency}
                  onChange={(e) => patchForm({ currency: e.target.value as Plan["currency"] })}
                >
                  <option value="NGN">NGN</option>
                  <option value="USD">USD</option>
                  <option value="GBP">GBP</option>
                  <option value="KES">KES</option>
                </SelectInput>
              </Field>
            </div>
            <div className="mer-form-grid">
              <Field label="Billing interval">
                <SelectInput
                  value={editing.form.interval}
                  onChange={(e) => patchForm({ interval: e.target.value as PlanInterval })}
                >
                  <option value="monthly">Monthly</option>
                  <option value="yearly">Yearly</option>
                  <option value="weekly">Weekly</option>
                </SelectInput>
              </Field>
              <Field label="Trial days">
                <TextInput
                  type="number"
                  inputMode="numeric"
                  value={editing.form.trialDays}
                  onChange={(e) => patchForm({ trialDays: e.target.value })}
                />
              </Field>
            </div>
            <Field label="Description" hint="One line — appears on receipts and in the portal.">
              <TextInput value={editing.form.description} onChange={(e) => patchForm({ description: e.target.value })} />
            </Field>
            <Field label="Status">
              <SelectInput
                value={editing.form.status}
                onChange={(e) => patchForm({ status: e.target.value as PlanStatus })}
              >
                <option value="active">Active</option>
                <option value="draft">Draft</option>
                <option value="archived">Archived</option>
              </SelectInput>
            </Field>
          </div>
        ) : null}
      </Sheet>
    </>
  );
}
