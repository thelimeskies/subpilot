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
  StatCard,
  TextInput,
  type BadgeTone,
  type DataTableColumn
} from "@subpilot/ui";
import { Download, Eye, RefreshCcw, Search, Slash, Undo2 } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePagination } from "../hooks/usePagination";
import { useFeedback } from "../feedback/ActionFeedback";
import { isApiError } from "../api/client";
import { useData } from "../data/store";
import { useFeatureFlags } from "../features/FeatureFlagsContext";
import { usePermissions } from "../auth/AuthContext";
import { findCustomerById, findInvoiceById, formatCurrency, formatRelative } from "../data/selectors";
import type { PaymentChannel, PaymentRecord, PaymentRecordStatus } from "../data/seed";

const STATUS_OPTIONS: Array<{ label: string; value: PaymentRecordStatus | "all" }> = [
  { label: "All statuses", value: "all" },
  { label: "Captured", value: "captured" },
  { label: "Failed", value: "failed" },
  { label: "Refunded", value: "refunded" },
  { label: "Recovered", value: "recovered" },
  { label: "Pending", value: "pending" }
];

const CHANNEL_OPTIONS: Array<{ label: string; value: PaymentChannel | "all" }> = [
  { label: "All channels", value: "all" },
  { label: "Card", value: "card" },
  { label: "Bank transfer", value: "bank_transfer" },
  { label: "USSD", value: "ussd" },
  { label: "Wallet", value: "wallet" }
];

interface RetryState {
  payment: PaymentRecord;
  paymentMethodId: string;
}

interface RefundState {
  payment: PaymentRecord;
  amount: string;
  reason: string;
  full: boolean;
}

interface ReceiptState {
  payment: PaymentRecord;
}

export function PaymentsPage() {
  const {
    payments,
    customers,
    invoices,
    retryPayment,
    refundPayment,
    downloadPaymentReceipt,
    exportPaymentsCsv,
    logAuditEvent
  } = useData();
  const { notify, confirm } = useFeedback();
  const { isEnabled } = useFeatureFlags();
  const { can } = usePermissions();
  const manualRefundsEnabled = isEnabled("manual_refunds");
  // Retry maps to ``retry_invoice``; refund to ``refund_payment`` (Owner/Billing
  // Admin/Finance only). Read-only and Support can't refund.
  const canRetry = can("retry_invoice");
  const canRefund = can("refund_payment");
  const canExport = can("export_invoices");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState<PaymentRecordStatus | "all">("all");
  const [channelFilter, setChannelFilter] = useState<PaymentChannel | "all">("all");
  const [retry, setRetry] = useState<RetryState | null>(null);
  const [refund, setRefund] = useState<RefundState | null>(null);
  const [receipt, setReceipt] = useState<ReceiptState | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [refunding, setRefunding] = useState(false);
  const [downloadingReceipt, setDownloadingReceipt] = useState(false);
  const [exportingCsv, setExportingCsv] = useState(false);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return payments.filter((p) => {
      if (statusFilter !== "all" && p.status !== statusFilter) return false;
      if (channelFilter !== "all" && p.channel !== channelFilter) return false;
      if (!q) return true;
      const customer = findCustomerById(customers, p.customerId);
      const invoice = findInvoiceById(invoices, p.invoiceId);
      return [p.id, customer?.name, customer?.email, invoice?.number]
        .filter(Boolean)
        .some((field) => field!.toLowerCase().includes(q));
    });
  }, [payments, customers, invoices, query, statusFilter, channelFilter]);

  const { page, setPage, pageCount, slice, totalLabel } = usePagination(filtered, 12, "payments");

  const stats = useMemo(() => {
    const captured = payments.filter((p) => p.status === "captured" || p.status === "recovered");
    const failed = payments.filter((p) => p.status === "failed");
    const refunded = payments.filter((p) => p.status === "refunded");
    const grossVolume = captured.reduce((s, p) => s + p.amount, 0);
    const refundedVolume = refunded.reduce((s, p) => s + Math.abs(p.amount), 0);
    return {
      grossVolume,
      refundedVolume,
      successCount: captured.length,
      failedCount: failed.length,
      successRate: captured.length + failed.length > 0 ? Math.round((captured.length / (captured.length + failed.length)) * 100) : 100
    };
  }, [payments]);

  function openRetry(payment: PaymentRecord) {
    const customer = findCustomerById(customers, payment.customerId);
    setRetry({
      payment,
      paymentMethodId: customer?.defaultMethodId ?? customer?.paymentMethods[0]?.id ?? ""
    });
  }

  async function submitRetry() {
    if (!retry) return;
    setRetrying(true);
    try {
      await retryPayment(retry.payment.id, retry.paymentMethodId || undefined);
      logAuditEvent({ actor: "You", action: "Retried payment", target: retry.payment.id });
      notify({
        tone: "success",
        title: "Retry queued",
        description: retry.paymentMethodId
          ? "We will attempt the charge with the selected card."
          : "We will attempt the charge with the backend default card."
      });
      setRetry(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not retry payment",
        description: isApiError(err) ? err.reason : err instanceof Error ? err.message : "The backend rejected the request. Try again."
      });
    } finally {
      setRetrying(false);
    }
  }

  function openRefund(payment: PaymentRecord) {
    setRefund({
      payment,
      amount: String(Math.abs(payment.amount)),
      reason: "Customer requested refund",
      full: true
    });
  }

  async function submitRefund() {
    if (!refund) return;
    const amount = Number(refund.amount) || 0;
    if (amount <= 0) {
      notify({ tone: "warning", title: "Enter a positive amount", description: "" });
      return;
    }
    if (refund.full) {
      const ok = await confirm({
        destructive: true,
        title: `Issue full refund?`,
        description: `${formatCurrency(refund.payment.amount, refund.payment.currency)} will be returned to the customer. This cannot be undone.`,
        confirmLabel: "Issue full refund"
      });
      if (!ok) return;
    }
    setRefunding(true);
    try {
      await refundPayment(refund.payment.id, amount, refund.full, refund.reason);
      logAuditEvent({
        actor: "You",
        action: refund.full ? "Issued full refund" : "Issued partial refund",
        target: `${refund.payment.id} · ${formatCurrency(amount)}`
      });
      notify({
        tone: refund.full ? "info" : "success",
        title: refund.full ? "Full refund processed" : "Partial refund processed",
        description: `${formatCurrency(amount)} returned via ${refund.payment.channel.replace("_", " ")}.`
      });
      setRefund(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not process refund",
        description: isApiError(err) ? err.reason : err instanceof Error ? err.message : "The backend rejected the request. Try again."
      });
    } finally {
      setRefunding(false);
    }
  }

  async function handleReceiptDownload() {
    if (!receipt) return;
    setDownloadingReceipt(true);
    try {
      await downloadPaymentReceipt(receipt.payment.id);
      notify({
        tone: "success",
        title: "Receipt downloaded",
        description: `${receipt.payment.id} was generated by the backend.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not download receipt",
        description: isApiError(err) ? err.reason : err instanceof Error ? err.message : "The backend rejected the receipt request."
      });
    } finally {
      setDownloadingReceipt(false);
    }
  }

  async function handleExportCsv() {
    setExportingCsv(true);
    try {
      await exportPaymentsCsv({ status: statusFilter, channel: channelFilter, q: query });
      logAuditEvent({
        actor: "You",
        action: "Exported payments CSV",
        target: `${statusFilter}/${channelFilter}`
      });
      notify({
        tone: "success",
        title: "CSV downloaded",
        description: `${filtered.length} matching payments exported from the backend.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not export payments",
        description: err instanceof Error ? err.message : "The backend rejected the export request."
      });
    } finally {
      setExportingCsv(false);
    }
  }

  const columns: DataTableColumn<PaymentRecord>[] = [
    {
      key: "id",
      header: "Payment",
      render: (p) => (
        <button
          type="button"
          className="mer-entity-cell mer-entity-cell--button"
          onClick={() => setReceipt({ payment: p })}
        >
          <strong>{p.id}</strong>
          <small>{p.channel === "card" && p.cardBrand ? `${p.cardBrand.toUpperCase()} ···· ${p.last4}` : p.channel.replace("_", " ")} · gateway: {p.gateway}</small>
        </button>
      )
    },
    {
      key: "customer",
      header: "Customer",
      render: (p) => {
        const c = findCustomerById(customers, p.customerId);
        return c ? (
          <Link to={`/customers/${c.id}`} className="mer-entity-cell">
            <strong>{c.name}</strong>
            <small>{c.email}</small>
          </Link>
        ) : <span>{p.customerId}</span>;
      }
    },
    {
      key: "invoice",
      header: "Invoice",
      render: (p) => {
        const inv = findInvoiceById(invoices, p.invoiceId);
        return inv ? <Link to={`/invoices/${inv.id}`} className="mer-card-link">{inv.number}</Link> : <span>—</span>;
      }
    },
    {
      key: "status",
      header: "Status",
      render: (p) => <Badge tone={paymentTone(p.status)}>{prettyStatus(p.status)}</Badge>
    },
    {
      key: "amount",
      header: "Amount",
      align: "right",
      render: (p) => (
        <strong className={p.amount < 0 ? "mer-amount-negative" : ""}>
          {p.amount < 0 ? "−" : ""}{formatCurrency(Math.abs(p.amount), p.currency)}
        </strong>
      )
    },
    { key: "occurred", header: "When", render: (p) => formatRelative(p.occurredAt) },
    {
      key: "actions",
      header: "",
      render: (p) => (
        <div className="mer-row-actions">
          <Button variant="ghost" icon={<Eye size={14} />} onClick={() => setReceipt({ payment: p })}>Receipt</Button>
          {canRetry && p.status === "failed" ? (
            <Button variant="ghost" icon={<RefreshCcw size={14} />} onClick={() => openRetry(p)}>Retry</Button>
          ) : null}
          {canRefund && (p.status === "captured" || p.status === "recovered") ? (
            manualRefundsEnabled ? (
              <Button variant="ghost" icon={<Undo2 size={14} />} onClick={() => openRefund(p)}>Refund</Button>
            ) : null
          ) : null}
        </div>
      )
    }
  ];

  return (
    <>
      <PageHeader
        eyebrow="Money in"
        title="Payments"
        description="Every charge, refund, and chargeback that touched a customer's payment method."
        actions={
          canExport ? (
            <Button
              variant="secondary"
              icon={<Download size={16} />}
              onClick={() => void handleExportCsv()}
              disabled={exportingCsv}
            >
              {exportingCsv ? "Exporting..." : "Export CSV"}
            </Button>
          ) : null
        }
      />

      <section className="sp-grid sp-grid-4">
        <StatCard
          label="Gross volume"
          value={formatCurrency(stats.grossVolume)}
          delta={`${stats.successCount} successful charges`}
          tone="success"
        />
        <StatCard
          label="Success rate"
          value={`${stats.successRate}%`}
          delta={`${stats.failedCount} failures`}
          tone="info"
        />
        <StatCard
          label="Refunded volume"
          value={formatCurrency(stats.refundedVolume)}
          delta={`${payments.filter((p) => p.status === "refunded").length} refunds`}
          tone="warning"
        />
        <StatCard
          label="Pending"
          value={String(payments.filter((p) => p.status === "pending").length)}
          delta="Awaiting capture"
          tone="neutral"
        />
      </section>

      <Card>
        <CardHeader
          title="All payments"
          description={`${filtered.length} of ${payments.length} match`}
          action={<Badge tone={stats.successRate >= 90 ? "success" : "warning"}>{stats.successRate}% success</Badge>}
        />
        <div className="mer-filter-row">
          <span className="mer-input-wrap mer-input-wrap--flex">
            <Search size={16} aria-hidden="true" />
            <TextInput
              type="search"
              placeholder="Search by id, customer, or invoice"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </span>
          <SelectInput value={statusFilter} onChange={(e) => setStatusFilter(e.target.value as PaymentRecordStatus | "all")} aria-label="Status filter">
            {STATUS_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </SelectInput>
          <SelectInput value={channelFilter} onChange={(e) => setChannelFilter(e.target.value as PaymentChannel | "all")} aria-label="Channel filter">
            {CHANNEL_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
          </SelectInput>
          {(statusFilter !== "all" || channelFilter !== "all" || query) ? (
            <Button variant="ghost" icon={<Slash size={14} />} onClick={() => { setStatusFilter("all"); setChannelFilter("all"); setQuery(""); }}>Reset</Button>
          ) : null}
        </div>
        <DataTable columns={columns} rows={slice} getRowKey={(p) => p.id} />
        <Pagination page={page} pageCount={pageCount} totalLabel={totalLabel} onPageChange={setPage} />
      </Card>

      {/* Receipt modal */}
      <Modal
        open={!!receipt}
        title="Payment receipt"
        description={receipt ? `${receipt.payment.id} · ${formatRelative(receipt.payment.occurredAt)}` : ""}
        onClose={() => setReceipt(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setReceipt(null)}>Close</Button>
            <Button variant="secondary" icon={<Download size={14} />} onClick={handleReceiptDownload} disabled={downloadingReceipt}>
              {downloadingReceipt ? "Downloading..." : "Download"}
            </Button>
          </>
        }
      >
        {receipt ? (
          <div className="mer-totals">
            <div className="mer-totals__row"><span>Status</span><Badge tone={paymentTone(receipt.payment.status)}>{prettyStatus(receipt.payment.status)}</Badge></div>
            <div className="mer-totals__row"><span>Customer</span><span>{findCustomerById(customers, receipt.payment.customerId)?.name ?? receipt.payment.customerId}</span></div>
            <div className="mer-totals__row"><span>Invoice</span><span>{findInvoiceById(invoices, receipt.payment.invoiceId)?.number ?? "—"}</span></div>
            <div className="mer-totals__row"><span>Channel</span><span>{receipt.payment.channel.replace("_", " ")}</span></div>
            {receipt.payment.cardBrand && receipt.payment.last4 ? (
              <div className="mer-totals__row"><span>Card</span><span>{receipt.payment.cardBrand.toUpperCase()} ···· {receipt.payment.last4}</span></div>
            ) : null}
            <div className="mer-totals__row"><span>Gateway</span><span>{receipt.payment.gateway}</span></div>
            {receipt.payment.failureReason ? (
              <div className="mer-totals__row"><span>Failure reason</span><span>{receipt.payment.failureReason}</span></div>
            ) : null}
            <div className="mer-totals__row mer-totals__row--total">
              <span>Amount</span>
              <span className={receipt.payment.amount < 0 ? "mer-amount-negative" : ""}>
                {receipt.payment.amount < 0 ? "−" : ""}{formatCurrency(Math.abs(receipt.payment.amount), receipt.payment.currency)}
              </span>
            </div>
          </div>
        ) : null}
      </Modal>

      {/* Retry modal */}
      <Modal
        open={!!retry}
        title="Retry payment"
        description="Pick a card on file to attempt the charge again."
        onClose={() => setRetry(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRetry(null)}>Cancel</Button>
            <Button onClick={submitRetry} icon={<RefreshCcw size={14} />} disabled={retrying}>
              {retrying ? "Retrying…" : "Retry now"}
            </Button>
          </>
        }
      >
        {retry ? (
          <div className="mer-stack">
            <Field label="Charge card">
              <SelectInput
                value={retry.paymentMethodId}
                onChange={(e) => setRetry({ ...retry, paymentMethodId: e.target.value })}
              >
                {findCustomerById(customers, retry.payment.customerId)?.paymentMethods.length ? (
                  findCustomerById(customers, retry.payment.customerId)!.paymentMethods.map((m) => (
                    <option key={m.id} value={m.id}>
                      {m.brand?.toUpperCase()} ···· {m.last4}
                    </option>
                  ))
                ) : (
                  <option value="">Backend default/tokenized method</option>
                )}
              </SelectInput>
            </Field>
            <p className="mer-hint">Original failure: {retry.payment.failureReason ?? "Unknown"}.</p>
          </div>
        ) : null}
      </Modal>

      {/* Refund modal */}
      <Modal
        open={!!refund}
        title="Issue refund"
        description="Partial refunds keep the original transaction intact. Full refunds reverse it completely."
        onClose={() => setRefund(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRefund(null)}>Cancel</Button>
            <Button variant={refund?.full ? "danger" : "primary"} onClick={submitRefund} disabled={refunding}>
              {refunding ? "Refunding..." : refund?.full ? "Issue full refund" : "Issue partial refund"}
            </Button>
          </>
        }
      >
        {refund ? (
          <div className="mer-stack">
            <div className="mer-pill-row">
              <button
                type="button"
                className={`sp-button ${refund.full ? "sp-button--primary" : "sp-button--ghost"}`}
                onClick={() => setRefund({ ...refund, full: true, amount: String(Math.abs(refund.payment.amount)) })}
              >
                Full ({formatCurrency(Math.abs(refund.payment.amount), refund.payment.currency)})
              </button>
              <button
                type="button"
                className={`sp-button ${!refund.full ? "sp-button--primary" : "sp-button--ghost"}`}
                onClick={() => setRefund({ ...refund, full: false })}
              >
                Partial
              </button>
            </div>
            <Field label="Amount">
              <TextInput
                type="number"
                min="0"
                value={refund.amount}
                onChange={(e) => setRefund({ ...refund, amount: e.target.value })}
                disabled={refund.full}
              />
            </Field>
            <Field label="Reason" hint="Logged in audit and visible to your team.">
              <TextInput
                value={refund.reason}
                onChange={(e) => setRefund({ ...refund, reason: e.target.value })}
              />
            </Field>
            {refund.full ? (
              <p className="mer-hint">Full refunds require an extra confirmation step.</p>
            ) : null}
          </div>
        ) : null}
      </Modal>
    </>
  );
}

function paymentTone(status: PaymentRecordStatus): BadgeTone {
  switch (status) {
    case "captured": return "success";
    case "recovered": return "teal";
    case "failed": return "danger";
    case "refunded": return "neutral";
    case "pending": return "warning";
    default: return "neutral";
  }
}

function prettyStatus(status: string): string {
  return status
    .split("_")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}
