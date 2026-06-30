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
import { Download, FileText, Mail, Plus, Search, Slash } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePagination } from "../hooks/usePagination";
import { useFeedback } from "../feedback/ActionFeedback";
import { isApiError } from "../api/client";
import { useData } from "../data/store";
import { usePermissions } from "../auth/AuthContext";
import { findCustomerById, formatCurrency } from "../data/selectors";
import type { Invoice, InvoiceStatus } from "../data/seed";

const STATUS_OPTIONS: Array<{ label: string; value: InvoiceStatus | "all" }> = [
  { label: "All statuses", value: "all" },
  { label: "Draft", value: "draft" },
  { label: "Open", value: "open" },
  { label: "Paid", value: "paid" },
  { label: "Past due", value: "past_due" },
  { label: "Void", value: "void" },
  { label: "Uncollectible", value: "uncollectible" }
];

interface NewInvoiceForm {
  customerId: string;
  description: string;
  quantity: string;
  unitAmount: string;
  dueDate: string;
  notes: string;
}

interface MarkPaidState {
  id: string;
  amount: string;
  method: "card" | "bank_transfer" | "cash" | "manual";
}

export function InvoicesPage() {
  const {
	    invoices,
	    customers,
	    createInvoice,
	    downloadInvoicePdf,
	    exportInvoicesCsv,
	    voidInvoice,
    markInvoicePaid,
    sendInvoiceReminder,
    logAuditEvent
  } = useData();
  const { notify, confirm } = useFeedback();
  const { can } = usePermissions();
  // ``create_invoice`` and ``send_invoice`` aren't first-class capabilities;
  // they ride on the broader Billing Admin/Owner power set. Use the closest
  // existing capability so the gate stays in sync with the backend matrix.
  const canCreateInvoice = can("edit_plan");
  const canSendInvoice = can("retry_invoice");
  const canMarkPaid = can("apply_credit_note");
  const canVoid = can("void_invoice");
  const canExport = can("export_invoices");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<InvoiceStatus | "all">("all");
  const [createOpen, setCreateOpen] = useState(false);
  const [createForm, setCreateForm] = useState<NewInvoiceForm>(emptyCreateForm(customers));
  const [markPaid, setMarkPaid] = useState<MarkPaidState | null>(null);
  const [savingInvoice, setSavingInvoice] = useState(false);
  const [savingPayment, setSavingPayment] = useState(false);
  const [sendingInvoiceId, setSendingInvoiceId] = useState<string | null>(null);
  const [downloadingInvoiceId, setDownloadingInvoiceId] = useState<string | null>(null);
  const [exportingCsv, setExportingCsv] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return invoices.filter((inv) => {
      if (statusFilter !== "all" && inv.status !== statusFilter) return false;
      if (!q) return true;
      const customer = findCustomerById(customers, inv.customerId);
      return [inv.id, inv.number, customer?.name, customer?.email]
        .filter(Boolean)
        .some((field) => field!.toLowerCase().includes(q));
    });
  }, [invoices, customers, query, statusFilter]);

  const { page, setPage, pageCount, slice, totalLabel } = usePagination(filtered, 12, "invoices");

  function openCreate() {
    setCreateForm(emptyCreateForm(customers));
    setCreateOpen(true);
  }

  function patchCreate(patch: Partial<NewInvoiceForm>) {
    setCreateForm((prev) => ({ ...prev, ...patch }));
  }

  async function submitCreate() {
    const customer = customers.find((c) => c.id === createForm.customerId);
    const qty = Number(createForm.quantity) || 0;
    const unit = Number(createForm.unitAmount) || 0;
    if (!customer || !createForm.description.trim() || qty <= 0 || unit <= 0) {
      notify({
        tone: "warning",
        title: "Missing details",
        description: "Pick a customer and add at least one line item with a positive amount."
      });
      return;
    }
    const total = qty * unit;
    const issuedAt = new Date().toISOString().slice(0, 10);
    const dueAt = createForm.dueDate || addDays(issuedAt, 14);
    setSavingInvoice(true);
    try {
      await createInvoice({
        number: `INV-${new Date().getFullYear()}-${Math.floor(Math.random() * 9000 + 1000)}`,
        customerId: customer.id,
        subscriptionId: null,
        status: "open",
        amountDue: total,
        amountPaid: 0,
        currency: "NGN",
        issuedAt,
        dueAt,
        paidAt: null,
        lineItems: [{ description: createForm.description.trim(), quantity: qty, unitAmount: unit }],
        attempts: 0,
        notes: createForm.notes.trim()
      });
      logAuditEvent({ actor: "You", action: "Created invoice", target: `${customer.name} · ${formatCurrency(total)}` });
      notify({
        tone: "success",
        title: "Invoice created",
        description: `One-off invoice queued for ${customer.name}.`
      });
      setCreateOpen(false);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not create invoice",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSavingInvoice(false);
    }
  }

  async function handleSend(inv: Invoice) {
    const customer = findCustomerById(customers, inv.customerId);
    setSendingInvoiceId(inv.id);
    try {
      await sendInvoiceReminder(
        inv.id,
        "email",
        `Hi ${customer?.name.split(" ")[0] ?? "there"}, just a friendly reminder that ${inv.number} is due on ${inv.dueAt}.`
      );
      logAuditEvent({ actor: "You", action: "Sent invoice email", target: inv.number });
      notify({
        tone: "info",
        title: "Invoice email queued",
        description: `${inv.number} → ${customer?.email ?? "customer"}`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not send invoice",
        description: isApiError(err) ? err.reason : "The backend rejected the reminder request."
      });
    } finally {
      setSendingInvoiceId(null);
    }
  }

  async function handleDownload(inv: Invoice) {
    setDownloadingInvoiceId(inv.id);
    try {
      await downloadInvoicePdf(inv.id, inv.number);
      logAuditEvent({ actor: "You", action: "Downloaded invoice PDF", target: inv.number });
      notify({
        tone: "success",
        title: "PDF downloaded",
        description: `${inv.number}.pdf was generated by the backend.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not download PDF",
        description: err instanceof Error ? err.message : "The backend rejected the PDF request."
      });
    } finally {
      setDownloadingInvoiceId(null);
    }
  }

  async function handleExportCsv() {
    setExportingCsv(true);
    try {
      await exportInvoicesCsv({ status: statusFilter, q: query });
      logAuditEvent({ actor: "You", action: "Exported invoices CSV", target: statusFilter === "all" ? "All invoices" : statusFilter });
      notify({
        tone: "success",
        title: "CSV downloaded",
        description: `${filtered.length} matching invoices exported from the backend.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not export invoices",
        description: err instanceof Error ? err.message : "The backend rejected the export request."
      });
    } finally {
      setExportingCsv(false);
    }
  }

  function openMarkPaid(inv: Invoice) {
    setMarkPaid({
      id: inv.id,
      amount: String(inv.amountDue - inv.amountPaid),
      method: "card"
    });
  }

  async function submitMarkPaid() {
    if (!markPaid) return;
    const amount = Number(markPaid.amount) || 0;
    if (amount <= 0) {
      notify({ tone: "warning", title: "Enter a positive amount", description: "" });
      return;
    }
    setSavingPayment(true);
    try {
      await markInvoicePaid(markPaid.id, amount);
      logAuditEvent({ actor: "You", action: "Marked invoice paid", target: markPaid.id });
      notify({
        tone: "success",
        title: "Invoice marked paid",
        description: `${formatCurrency(amount)} reconciled via ${prettyMethod(markPaid.method)}.`
      });
      setMarkPaid(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not mark invoice paid",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSavingPayment(false);
    }
  }

  async function handleVoid(inv: Invoice) {
    const ok = await confirm({
      destructive: true,
      title: `Void ${inv.number}?`,
      description: "Voiding is permanent. The customer keeps a copy for records but the balance is wiped from your books.",
      confirmLabel: "Void invoice"
    });
    if (!ok) return;
    try {
      await voidInvoice(inv.id);
      logAuditEvent({ actor: "You", action: "Voided invoice", target: inv.number });
      notify({ tone: "info", title: "Invoice voided", description: `${inv.number} was zeroed out.` });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not void invoice",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }

  const columns: DataTableColumn<Invoice>[] = [
    {
      key: "number",
      header: "Invoice",
      render: (inv) => (
        <Link to={`/invoices/${inv.id}`} className="mer-entity-cell">
          <strong>{inv.number}</strong>
          <small>{inv.id} · issued {inv.issuedAt}</small>
        </Link>
      )
    },
    {
      key: "customer",
      header: "Customer",
      render: (inv) => {
        const c = findCustomerById(customers, inv.customerId);
        return c ? (
          <Link to={`/customers/${c.id}`} className="mer-entity-cell">
            <strong>{c.name}</strong>
            <small>{c.email}</small>
          </Link>
        ) : <span>{inv.customerId}</span>;
      }
    },
    {
      key: "status",
      header: "Status",
      render: (inv) => <Badge tone={invoiceTone(inv.status)}>{prettyStatus(inv.status)}</Badge>
    },
    {
      key: "amount",
      header: "Amount",
      align: "right",
      render: (inv) => (
        <div className="mer-amount-cell">
          <strong>{formatCurrency(Math.max(0, inv.amountDue - inv.amountPaid), inv.currency)}</strong>
          {inv.amountPaid > 0 ? (
            <small>{formatCurrency(inv.amountPaid, inv.currency)} collected · {formatCurrency(inv.amountDue, inv.currency)} total</small>
          ) : (
            <small>{formatCurrency(inv.amountDue, inv.currency)} total</small>
          )}
        </div>
      )
    },
    { key: "due", header: "Due", render: (inv) => inv.dueAt },
    {
      key: "actions",
      header: "",
      render: (inv) => (
        <div className="mer-row-actions">
          <Link to={`/invoices/${inv.id}`} className="sp-button sp-button--ghost mer-row-actions__link">View</Link>
          {canSendInvoice && inv.status !== "void" && inv.status !== "paid" ? (
            <Button
              variant="ghost"
              icon={<Mail size={14} />}
              onClick={() => void handleSend(inv)}
              disabled={sendingInvoiceId === inv.id}
            >
              {sendingInvoiceId === inv.id ? "Sending..." : "Send"}
            </Button>
          ) : null}
          {canMarkPaid && inv.status !== "void" && inv.status !== "paid" ? (
            <Button variant="ghost" onClick={() => openMarkPaid(inv)}>Mark paid</Button>
          ) : null}
          <Button
            variant="ghost"
            icon={<Download size={14} />}
            onClick={() => void handleDownload(inv)}
            disabled={downloadingInvoiceId === inv.id}
          >
            {downloadingInvoiceId === inv.id ? "Downloading..." : "PDF"}
          </Button>
          {canVoid && inv.status !== "void" && inv.status !== "paid" ? (
            <Button variant="ghost" onClick={() => handleVoid(inv)}>Void</Button>
          ) : null}
        </div>
      )
    }
  ];

  const stats = useMemo(() => {
    const open = invoices.filter((i) => i.status === "open" || i.status === "past_due").length;
    const totalOutstanding = invoices
      .filter((i) => i.status === "open" || i.status === "past_due" || i.status === "uncollectible")
      .reduce((s, i) => s + (i.amountDue - i.amountPaid), 0);
    return { open, totalOutstanding };
  }, [invoices]);

  return (
    <>
      <PageHeader
        eyebrow="Billing"
        title="Invoices"
        description="Issue one-off invoices, send reminders, reconcile payments, and void mistakes — all from one ledger."
        actions={
          <>
            {canExport ? (
              <Button variant="secondary" icon={<Download size={16} />} onClick={() => void handleExportCsv()} disabled={exportingCsv}>
                {exportingCsv ? "Exporting..." : "Export CSV"}
              </Button>
            ) : null}
            {canCreateInvoice ? (
              <Button icon={<Plus size={16} />} onClick={openCreate}>
                New invoice
              </Button>
            ) : null}
          </>
        }
      />

      <Card>
        <CardHeader
          title="All invoices"
          description={`${filtered.length} of ${invoices.length} match · ${stats.open} need attention · ${formatCurrency(stats.totalOutstanding)} outstanding`}
          action={<Badge tone="warning">{invoices.filter((i) => i.status === "past_due").length} past due</Badge>}
        />
        <div className="mer-filter-row">
          <span className="mer-input-wrap mer-input-wrap--flex">
            <Search size={16} aria-hidden="true" />
            <TextInput
              type="search"
              placeholder="Search invoice number, customer, or id"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </span>
          <SelectInput value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as InvoiceStatus | "all")} aria-label="Status filter">
            {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </SelectInput>
          {(statusFilter !== "all" || query) ? (
            <Button variant="ghost" icon={<Slash size={14} />} onClick={() => { setStatusFilter("all"); setQuery(""); }}>Reset</Button>
          ) : null}
        </div>
        <DataTable columns={columns} rows={slice} getRowKey={(inv) => inv.id} />
        <Pagination page={page} pageCount={pageCount} totalLabel={totalLabel} onPageChange={setPage} />
      </Card>

      {/* Create one-off invoice sheet */}
      <Sheet
        open={createOpen}
        title="New invoice"
        description="Issue a one-off invoice. For recurring charges, attach the customer to a plan instead."
        onClose={() => setCreateOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={submitCreate} icon={<FileText size={14} />} disabled={savingInvoice}>
              {savingInvoice ? "Creating…" : "Create invoice"}
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
          <Field label="Description" hint="Shown on the invoice line item.">
            <TextInput
              placeholder="e.g. Implementation services — November"
              value={createForm.description}
              onChange={(e) => patchCreate({ description: e.target.value })}
            />
          </Field>
          <div className="mer-form-grid">
            <Field label="Quantity">
              <TextInput type="number" min="1" value={createForm.quantity} onChange={(e) => patchCreate({ quantity: e.target.value })} />
            </Field>
            <Field label="Unit amount" hint={`In ${"NGN"}.`}>
              <TextInput type="number" min="0" value={createForm.unitAmount} onChange={(e) => patchCreate({ unitAmount: e.target.value })} />
            </Field>
          </div>
          <Field label="Due date">
            <TextInput type="date" value={createForm.dueDate} onChange={(e) => patchCreate({ dueDate: e.target.value })} />
          </Field>
          <Field label="Internal notes" hint="Not visible to the customer.">
            <TextInput
              placeholder="Optional — anchor link, PO number, etc."
              value={createForm.notes}
              onChange={(e) => patchCreate({ notes: e.target.value })}
            />
          </Field>
        </div>
      </Sheet>

      {/* Mark-paid modal */}
      <Modal
        open={!!markPaid}
        title="Mark invoice paid"
        description="Use this when payment was received outside SubPilot (cash, manual transfer, etc)."
        onClose={() => setMarkPaid(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setMarkPaid(null)}>Cancel</Button>
            <Button onClick={submitMarkPaid} disabled={savingPayment}>
              {savingPayment ? "Confirming…" : "Confirm payment"}
            </Button>
          </>
        }
      >
        {markPaid ? (
          <div className="mer-stack">
            <Field label="Amount received">
              <TextInput
                type="number"
                min="0"
                value={markPaid.amount}
                onChange={(e) => setMarkPaid({ ...markPaid, amount: e.target.value })}
              />
            </Field>
            <Field label="Payment method">
              <SelectInput
                value={markPaid.method}
                onChange={(e) => setMarkPaid({ ...markPaid, method: e.target.value as MarkPaidState["method"] })}
              >
                <option value="card">Card on file</option>
                <option value="bank_transfer">Bank transfer</option>
                <option value="cash">Cash</option>
                <option value="manual">Manual / Other</option>
              </SelectInput>
            </Field>
          </div>
        ) : null}
      </Modal>
    </>
  );
}

function emptyCreateForm(customers: ReturnType<typeof useData>["customers"]): NewInvoiceForm {
  const today = new Date().toISOString().slice(0, 10);
  return {
    customerId: customers.find((c) => c.status !== "blocked")?.id ?? customers[0]?.id ?? "",
    description: "",
    quantity: "1",
    unitAmount: "",
    dueDate: addDays(today, 14),
    notes: ""
  };
}

function addDays(iso: string, days: number): string {
  const d = new Date(iso);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function invoiceTone(status: InvoiceStatus): BadgeTone {
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

function prettyMethod(method: MarkPaidState["method"]): string {
  switch (method) {
    case "card": return "card on file";
    case "bank_transfer": return "bank transfer";
    case "cash": return "cash";
    case "manual": return "manual entry";
  }
}
