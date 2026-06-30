import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
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
  type BadgeTone,
  type DataTableColumn
} from "@subpilot/ui";
import { Ban, Mail, Plus, Search, Slash, UserPlus } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePagination } from "../hooks/usePagination";
import { useFeedback } from "../feedback/ActionFeedback";
import { createPortalSession } from "../api/billing";
import { isApiError } from "../api/client";
import { useData } from "../data/store";
import { usePermissions } from "../auth/AuthContext";
import { findSubscriptionsByCustomer, formatCurrency, formatRelative } from "../data/selectors";
import type { Customer, CustomerStatus } from "../data/seed";

const STATUS_OPTIONS: Array<{ label: string; value: CustomerStatus | "all" }> = [
  { label: "All statuses", value: "all" },
  { label: "Active", value: "active" },
  { label: "Delinquent", value: "delinquent" },
  { label: "Churned", value: "churned" },
  { label: "Blocked", value: "blocked" }
];

interface AddCustomerForm {
  name: string;
  email: string;
  phone: string;
  country: string;
  paymentTerms: "net_7" | "net_14" | "net_30" | "due_on_receipt";
}

interface PortalLinkState {
  customer: Customer;
}

export function CustomersPage() {
  const { customers, subscriptions, plans, createCustomer, blockCustomer, logAuditEvent } = useData();
  const { notify, confirm } = useFeedback();
  const { can } = usePermissions();
  const canAdd = can("create_customer");
  // Portal links use ``create_payment_method_session`` server-side; reuse for UI gating.
  const canSendPortal = can("create_payment_method_session");
  // Blocking a customer is a destructive lifecycle change — only Owner/Billing Admin
  // get this via the cancel/pause capability set.
  const canBlock = can("cancel_subscription");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>("all");
  const [addOpen, setAddOpen] = useState(false);
  const [addForm, setAddForm] = useState<AddCustomerForm>(emptyAddForm());
  const [portalLink, setPortalLink] = useState<PortalLinkState | null>(null);
  const [savingCustomer, setSavingCustomer] = useState(false);
  const [portalBusy, setPortalBusy] = useState(false);
  const [blockingCustomerId, setBlockingCustomerId] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return customers.filter((c) => {
      if (statusFilter !== "all" && c.status !== statusFilter) return false;
      if (!q) return true;
      return [c.id, c.name, c.email, c.phone].some((field) => field.toLowerCase().includes(q));
    });
  }, [customers, query, statusFilter]);

  const { page, setPage, pageCount, slice, totalLabel } = usePagination(filtered, 12, "customers");

  function openAdd() {
    setAddForm(emptyAddForm());
    setAddOpen(true);
  }

  function patchAdd(patch: Partial<AddCustomerForm>) {
    setAddForm((prev) => ({ ...prev, ...patch }));
  }

  async function submitAdd() {
    if (!addForm.name.trim() || !addForm.email.trim()) {
      notify({ tone: "warning", title: "Missing details", description: "Name and email are required." });
      return;
    }
    setSavingCustomer(true);
    try {
      const id = await createCustomer({
        name: addForm.name.trim(),
        email: addForm.email.trim(),
        phone: addForm.phone.trim(),
        country: addForm.country,
        status: "active",
        notes: `Default payment terms: ${addForm.paymentTerms.replace("_", " ")}`
      });
      logAuditEvent({ actor: "You", action: "Added customer", target: addForm.email });
      notify({
        tone: "success",
        title: "Customer added",
        description: `${addForm.name} is now in your customer book (${id}).`
      });
      setAddOpen(false);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not add customer",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSavingCustomer(false);
    }
  }

  function openPortalLink(customer: Customer) {
    setPortalLink({ customer });
  }

  async function copyPortalLink() {
    if (!portalLink) return;
    setPortalBusy(true);
    try {
      const session = await createPortalSession(portalLink.customer.id);
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        navigator.clipboard.writeText(session.url).catch(() => {
          // Clipboard is best-effort; the generated link is still shown in the toast.
        });
      }
      logAuditEvent({ actor: "You", action: "Created portal link", target: portalLink.customer.email });
      notify({
        tone: "info",
        title: "Portal link copied",
        description: `${session.url} is now on your clipboard.`
      });
      setPortalLink(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not create portal link",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setPortalBusy(false);
    }
  }

  async function emailPortalLink() {
    if (!portalLink) return;
    setPortalBusy(true);
    try {
      const session = await createPortalSession(portalLink.customer.id, { sendEmail: true });
      logAuditEvent({ actor: "You", action: "Created portal email link", target: portalLink.customer.email });
      notify({
        tone: "success",
        title: session.emailQueued ? "Portal email queued" : "Portal link created",
        description: session.emailQueued
          ? `Magic link will reach ${portalLink.customer.email} shortly.`
          : session.url
      });
      setPortalLink(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not create portal email",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setPortalBusy(false);
    }
  }

  async function handleBlock(customer: Customer) {
    const ok = await confirm({
      destructive: true,
      title: `Block ${customer.name}?`,
      description: "Blocking pauses all subscriptions and stops new charges. They will be notified by email.",
      confirmLabel: "Block customer"
    });
    if (!ok) return;
    setBlockingCustomerId(customer.id);
    try {
      const result = await blockCustomer(customer.id);
      logAuditEvent({ actor: "You", action: "Blocked customer", target: customer.email });
      const countLabel = `${result.pausedSubscriptions} subscription${result.pausedSubscriptions === 1 ? "" : "s"}`;
      notify({
        tone: "info",
        title: "Customer blocked",
        description: result.emailSent
          ? `${countLabel} paused and ${customer.email} was notified.`
          : `${countLabel} paused.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not block customer",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setBlockingCustomerId(null);
    }
  }

  const columns: DataTableColumn<Customer>[] = [
    {
      key: "name",
      header: "Customer",
      render: (c) => (
        <Link to={`/customers/${c.id}`} className="mer-entity-cell">
          <strong>{c.name}</strong>
          <small>{c.email} · {c.phone}</small>
        </Link>
      )
    },
    {
      key: "plans",
      header: "Plans",
      render: (c) => {
        const subs = findSubscriptionsByCustomer(subscriptions, c.id);
        if (!subs.length) return <span className="mer-muted">—</span>;
        const planNames = Array.from(new Set(subs.map((s) => plans.find((p) => p.id === s.planId)?.name ?? s.planId)));
        return <span className="mer-pill-row">{planNames.slice(0, 2).map((n) => <Badge key={n} tone="neutral">{n}</Badge>)}{planNames.length > 2 ? <Badge tone="neutral">+{planNames.length - 2}</Badge> : null}</span>;
      }
    },
    {
      key: "status",
      header: "Status",
      render: (c) => <Badge tone={customerTone(c.status)}>{prettyStatus(c.status)}</Badge>
    },
    { key: "mrr", header: "MRR", align: "right", render: (c) => formatCurrency(c.mrr) },
    { key: "lastPayment", header: "Last payment", render: (c) => c.lastPaymentAt && c.lastPaymentAt !== "—" ? formatRelative(c.lastPaymentAt) : "—" },
    {
      key: "actions",
      header: "",
      render: (c) => (
        <div className="mer-row-actions">
          <Link to={`/customers/${c.id}`} className="sp-button sp-button--ghost mer-row-actions__link">View</Link>
          {canSendPortal ? (
            <Button variant="ghost" icon={<Mail size={14} />} onClick={() => openPortalLink(c)}>Portal link</Button>
          ) : null}
          {canBlock && c.status !== "blocked" ? (
            <Button
              variant="ghost"
              icon={<Ban size={14} />}
              onClick={() => handleBlock(c)}
              disabled={blockingCustomerId === c.id}
            >
              {blockingCustomerId === c.id ? "Blocking..." : "Block"}
            </Button>
          ) : null}
        </div>
      )
    }
  ];

  return (
    <>
      <PageHeader
        eyebrow="Your book"
        title="Customers"
        description="Everyone you bill — from a 1-seat starter to your largest enterprise account."
        actions={
          canAdd ? (
            <Button icon={<UserPlus size={16} />} onClick={openAdd}>
              Add customer
            </Button>
          ) : null
        }
      />

      <Card>
        <CardHeader
          title="All customers"
          description={`${filtered.length} of ${customers.length} match · ${customers.filter((c) => c.status === "active").length} active · ${customers.filter((c) => c.status === "delinquent").length} delinquent`}
          action={<Badge tone="info">{customers.filter((c) => c.status === "active").length} active</Badge>}
        />
        <div className="mer-filter-row">
          <span className="mer-input-wrap mer-input-wrap--flex">
            <Search size={16} aria-hidden="true" />
            <TextInput
              type="search"
              placeholder="Search name, email, or id"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </span>
          <SelectInput value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} aria-label="Status filter">
            {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </SelectInput>
          {(statusFilter !== "all" || query) ? (
            <Button variant="ghost" icon={<Slash size={14} />} onClick={() => { setStatusFilter("all"); setQuery(""); }}>Reset</Button>
          ) : null}
        </div>
        <DataTable columns={columns} rows={slice} getRowKey={(c) => c.id} />
        <Pagination page={page} pageCount={pageCount} totalLabel={totalLabel} onPageChange={setPage} />
      </Card>

      {/* Add customer sheet */}
      <Sheet
        open={addOpen}
        title="Add customer"
        description="Add someone you'll bill. You can attach plans and payment methods on their detail page."
        onClose={() => setAddOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setAddOpen(false)}>Cancel</Button>
            <Button onClick={submitAdd} icon={<Plus size={14} />} disabled={savingCustomer}>
              {savingCustomer ? "Adding…" : "Add customer"}
            </Button>
          </>
        }
      >
        <div className="mer-stack">
          <Field label="Full name">
            <TextInput
              placeholder="e.g. Ada Okafor"
              value={addForm.name}
              onChange={(e) => patchAdd({ name: e.target.value })}
            />
          </Field>
          <Field label="Email">
            <TextInput
              type="email"
              placeholder="ada@example.com"
              value={addForm.email}
              onChange={(e) => patchAdd({ email: e.target.value })}
            />
          </Field>
          <div className="mer-form-grid">
            <Field label="Phone">
              <TextInput
                placeholder="+234 ..."
                value={addForm.phone}
                onChange={(e) => patchAdd({ phone: e.target.value })}
              />
            </Field>
            <Field label="Country">
              <SelectInput value={addForm.country} onChange={(e) => patchAdd({ country: e.target.value })}>
                <option value="Nigeria">Nigeria</option>
                <option value="Ghana">Ghana</option>
                <option value="Kenya">Kenya</option>
                <option value="South Africa">South Africa</option>
              </SelectInput>
            </Field>
          </div>
          <Field label="Default payment terms">
            <SelectInput
              value={addForm.paymentTerms}
              onChange={(e) => patchAdd({ paymentTerms: e.target.value as AddCustomerForm["paymentTerms"] })}
            >
              <option value="due_on_receipt">Due on receipt</option>
              <option value="net_7">Net 7</option>
              <option value="net_14">Net 14</option>
              <option value="net_30">Net 30</option>
            </SelectInput>
          </Field>
        </div>
      </Sheet>

      {/* Portal link modal */}
      <Modal
        open={!!portalLink}
        title="Send portal link"
        description={portalLink ? `${portalLink.customer.name} can manage their subscription, payment methods, and invoices from their portal.` : ""}
        onClose={() => setPortalLink(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPortalLink(null)}>Cancel</Button>
            <Button variant="secondary" onClick={copyPortalLink} disabled={portalBusy}>
              {portalBusy ? "Creating…" : "Copy link"}
            </Button>
            <Button onClick={emailPortalLink} icon={<Mail size={14} />} disabled={portalBusy}>
              {portalBusy ? "Creating…" : "Email link"}
            </Button>
          </>
        }
      >
        {portalLink ? (
          <div className="mer-stack">
            <Field label="Portal URL">
              <TextInput
                readOnly
                value="Generated after you choose Copy link or Email link"
              />
            </Field>
            <p className="mer-hint">Magic links expire in 24 hours and are single-use.</p>
          </div>
        ) : null}
      </Modal>
    </>
  );
}

function emptyAddForm(): AddCustomerForm {
  return { name: "", email: "", phone: "", country: "Nigeria", paymentTerms: "due_on_receipt" };
}

function customerTone(status: CustomerStatus): BadgeTone {
  switch (status) {
    case "active": return "success";
    case "delinquent": return "warning";
    case "churned": return "neutral";
    case "blocked": return "danger";
    default: return "neutral";
  }
}

function prettyStatus(status: string): string {
  return status.charAt(0).toUpperCase() + status.slice(1);
}
