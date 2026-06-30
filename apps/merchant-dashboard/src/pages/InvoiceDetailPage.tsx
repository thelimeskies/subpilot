import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Modal,
  SelectInput,
  StatCard,
  TextInput,
  type BadgeTone
} from "@subpilot/ui";
import { ArrowLeft, BadgePlus, Bell, Download, Mail, RefreshCcw, X } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { isApiError } from "../api/client";
import { useData } from "../data/store";
import { findCustomerById, formatCurrency, formatRelative } from "../data/selectors";
import type { Invoice, InvoiceStatus, PaymentRecord } from "../data/seed";

interface RetryState {
  paymentMethodId: string;
}

interface ReminderState {
  channel: "email" | "sms";
  message: string;
}

interface MarkPaidState {
  amount: string;
  method: "card" | "bank_transfer" | "cash" | "manual";
}

interface CreditState {
  amount: string;
  reason: string;
}

export function InvoiceDetailPage() {
  const { invoiceId } = useParams<{ invoiceId: string }>();
  const {
    invoices,
    customers,
    payments,
    voidInvoice,
    markInvoicePaid,
    applyInvoiceCredit,
    sendInvoiceReminder,
    downloadInvoicePdf,
    retryInvoice,
    logAuditEvent
  } = useData();
  const { notify, confirm } = useFeedback();

  const [reminder, setReminder] = useState<ReminderState | null>(null);
  const [retry, setRetry] = useState<RetryState | null>(null);
  const [paid, setPaid] = useState<MarkPaidState | null>(null);
  const [credit, setCredit] = useState<CreditState | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [markingPaid, setMarkingPaid] = useState(false);
  const [applyingCredit, setApplyingCredit] = useState(false);
  const [voiding, setVoiding] = useState(false);
  const [sendingReminder, setSendingReminder] = useState(false);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  const invoice = invoices.find((i) => i.id === invoiceId);
  const customer = invoice ? findCustomerById(customers, invoice.customerId) : null;

  const invoicePayments = useMemo<PaymentRecord[]>(
    () => (invoice ? payments.filter((p) => p.invoiceId === invoice.id) : []),
    [invoice, payments]
  );

  if (!invoice || !customer) {
    return (
      <div className="mer-empty-state">
        <h2>Invoice not found</h2>
        <p>We couldn&rsquo;t locate <code>{invoiceId}</code>.</p>
        <Link to="/invoices" className="mer-card-link">
          <ArrowLeft size={14} aria-hidden="true" /> Back to invoices
        </Link>
      </div>
    );
  }

  const lineSubtotal = invoice.lineItems.reduce((s, li) => s + li.quantity * li.unitAmount, 0);
  const subtotal = invoice.subtotal ?? lineSubtotal;
  const tax = invoice.tax ?? 0;
  const total = invoice.total ?? invoice.amountDue;
  const balance = invoice.amountDue - invoice.amountPaid;

  function openReminder() {
    setReminder({
      channel: "email",
      message: `Hi ${customer!.name.split(" ")[0]}, just a friendly reminder that ${invoice!.number} (${formatCurrency(balance, invoice!.currency)}) is due on ${invoice!.dueAt}.`
    });
  }

  async function submitReminder() {
    if (!reminder) return;
    setSendingReminder(true);
    try {
      await sendInvoiceReminder(invoice!.id, reminder.channel, reminder.message);
      logAuditEvent({ actor: "You", action: "Sent invoice reminder", target: `${invoice!.number} via ${reminder.channel}` });
      notify({
        tone: "info",
        title: reminder.channel === "email" ? "Reminder sent" : "SMS reminder recorded",
        description:
          reminder.channel === "email"
            ? `Email sent to ${customer!.email}.`
            : `SMS reminder recorded for ${customer!.phone}; no SMS provider is configured in this environment.`
      });
      setReminder(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not send reminder",
        description: isApiError(err) ? err.reason : "The backend rejected the reminder request."
      });
    } finally {
      setSendingReminder(false);
    }
  }

  function openRetry() {
    setRetry({ paymentMethodId: customer!.defaultMethodId ?? customer!.paymentMethods[0]?.id ?? "" });
  }

  async function submitRetry() {
    if (!retry) return;
    setRetrying(true);
    try {
      await retryInvoice(invoice!.id, retry.paymentMethodId || undefined);
      logAuditEvent({ actor: "You", action: "Retried invoice payment", target: invoice!.number });
      notify({
        tone: "success",
        title: "Retry completed",
        description: "The invoice charge was submitted to the backend."
      });
      setRetry(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not retry payment",
        description: isApiError(err) ? err.reason : "The backend rejected the retry request."
      });
    } finally {
      setRetrying(false);
    }
  }

  function openMarkPaid() {
    setPaid({ amount: String(balance > 0 ? balance : invoice!.amountDue), method: "card" });
  }

  async function submitMarkPaid() {
    if (!paid) return;
    const amount = Number(paid.amount) || 0;
    if (amount <= 0) {
      notify({ tone: "warning", title: "Enter a positive amount", description: "" });
      return;
    }
    setMarkingPaid(true);
    try {
      await markInvoicePaid(invoice!.id, amount);
      logAuditEvent({ actor: "You", action: "Marked invoice paid", target: invoice!.number });
      notify({
        tone: "success",
        title: "Invoice marked paid",
        description: `${formatCurrency(amount)} reconciled via ${prettyMethod(paid.method)}.`
      });
      setPaid(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not mark invoice paid",
        description: isApiError(err) ? err.reason : "The backend rejected the payment reconciliation."
      });
    } finally {
      setMarkingPaid(false);
    }
  }

  function openCredit() {
    setCredit({ amount: String(Math.min(balance, 5000)), reason: "Goodwill credit" });
  }

  async function submitCredit() {
    if (!credit) return;
    const amount = Number(credit.amount) || 0;
    if (amount <= 0) {
      notify({ tone: "warning", title: "Enter a positive amount", description: "" });
      return;
    }
    setApplyingCredit(true);
    try {
      await applyInvoiceCredit(invoice!.id, amount, credit.reason);
      logAuditEvent({ actor: "You", action: "Applied credit", target: `${invoice!.number} · ${formatCurrency(amount)}` });
      notify({
        tone: "success",
        title: "Credit applied",
        description: `${formatCurrency(amount)} credited against the invoice balance.`
      });
      setCredit(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not apply credit",
        description: isApiError(err) ? err.reason : "The backend rejected the credit note."
      });
    } finally {
      setApplyingCredit(false);
    }
  }

  async function handleVoid() {
    const ok = await confirm({
      destructive: true,
      title: `Void ${invoice!.number}?`,
      description: "Voiding is permanent. Customers keep their copy for records but the balance disappears from your books.",
      confirmLabel: "Void invoice"
    });
    if (!ok) return;
    setVoiding(true);
    try {
      await voidInvoice(invoice!.id);
      logAuditEvent({ actor: "You", action: "Voided invoice", target: invoice!.number });
      notify({ tone: "info", title: "Invoice voided", description: `${invoice!.number} was zeroed out.` });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not void invoice",
        description: isApiError(err) ? err.reason : "The backend rejected the void request."
      });
    } finally {
      setVoiding(false);
    }
  }

  async function handleDownload() {
    setDownloadingPdf(true);
    try {
      await downloadInvoicePdf(invoice!.id, invoice!.number);
      logAuditEvent({ actor: "You", action: "Downloaded invoice PDF", target: invoice!.number });
      notify({
        tone: "success",
        title: "PDF downloaded",
        description: `${invoice!.number}.pdf was generated by the backend.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not download PDF",
        description: err instanceof Error ? err.message : "The backend rejected the PDF request."
      });
    } finally {
      setDownloadingPdf(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={
          <span className="mer-breadcrumb-eyebrow">
            <Link to="/invoices" className="mer-card-link">
              <ArrowLeft size={12} aria-hidden="true" /> Invoices
            </Link>
            <span> / {invoice.number}</span>
          </span>
        }
        title={invoice.number}
        description={`Issued ${invoice.issuedAt} · Due ${invoice.dueAt} · ${customer.name}`}
        actions={
          <>
            <Button variant="secondary" icon={<Download size={16} />} onClick={handleDownload} disabled={downloadingPdf}>
              {downloadingPdf ? "Downloading..." : "Download PDF"}
            </Button>
            {invoice.status !== "void" && invoice.status !== "paid" ? (
              <Button variant="secondary" icon={<Bell size={16} />} onClick={openReminder}>Send reminder</Button>
            ) : null}
            {invoice.status === "past_due" || invoice.status === "open" ? (
              <Button variant="secondary" icon={<RefreshCcw size={16} />} onClick={openRetry}>Retry payment</Button>
            ) : null}
            {invoice.status !== "void" && invoice.status !== "paid" ? (
              <Button variant="secondary" onClick={openMarkPaid}>Mark paid</Button>
            ) : null}
            {invoice.status !== "void" && invoice.status !== "paid" ? (
              <Button variant="secondary" icon={<BadgePlus size={16} />} onClick={openCredit}>Apply credit</Button>
            ) : null}
            {invoice.status !== "void" && invoice.status !== "paid" ? (
              <Button variant="danger" icon={<X size={16} />} onClick={handleVoid} disabled={voiding}>
                {voiding ? "Voiding..." : "Void"}
              </Button>
            ) : null}
          </>
        }
      />

      <div className="mer-detail-meta">
        <Badge tone={invoiceTone(invoice.status)}>{prettyStatus(invoice.status)}</Badge>
        <span>Customer <Link to={`/customers/${customer.id}`} className="mer-card-link">{customer.name}</Link></span>
        <span>Attempts <strong>{invoice.attempts}</strong></span>
        {invoice.subscriptionId ? (
          <span>Subscription <Link to={`/subscriptions/${invoice.subscriptionId}`} className="mer-card-link">{invoice.subscriptionId}</Link></span>
        ) : <span>One-off invoice</span>}
      </div>

      <section className="sp-grid sp-grid-4">
        <StatCard
          label="Amount due"
          value={formatCurrency(invoice.amountDue, invoice.currency)}
          delta={invoice.status === "paid" ? "Settled" : `${formatCurrency(balance, invoice.currency)} balance`}
          tone={invoice.status === "paid" ? "success" : balance > 0 ? "warning" : "neutral"}
        />
        <StatCard
          label="Collected"
          value={formatCurrency(invoice.amountPaid, invoice.currency)}
          delta={`${invoicePayments.filter((p) => p.status === "captured" || p.status === "recovered").length} successful charges`}
          tone="info"
        />
        <StatCard
          label="Tax"
          value={formatCurrency(tax, invoice.currency)}
          delta={tax > 0 ? "Backend tax total" : "No tax"}
          tone="neutral"
        />
        <StatCard
          label="Total"
          value={formatCurrency(total, invoice.currency)}
          delta={`Subtotal ${formatCurrency(subtotal, invoice.currency)}`}
          tone="teal"
        />
      </section>

      <Card>
        <CardHeader title="Line items" description="Description, quantity, and unit pricing." />
        <div className="mer-line-items">
          <div className="mer-line-items__row mer-line-items__row--head">
            <strong>Description</strong>
            <span style={{ textAlign: "right" }}>Qty × Unit</span>
            <span style={{ textAlign: "right" }}>Total</span>
          </div>
          {invoice.lineItems.map((li, idx) => (
            <div key={idx} className="mer-line-items__row">
              <div>
                <strong>{li.description}</strong>
              </div>
              <span style={{ textAlign: "right" }}>
                {li.quantity} × {formatCurrency(li.unitAmount, invoice.currency)}
              </span>
              <strong style={{ textAlign: "right" }}>
                {formatCurrency(li.quantity * li.unitAmount, invoice.currency)}
              </strong>
            </div>
          ))}
        </div>
        <div className="mer-totals">
          <div className="mer-totals__row"><span>Subtotal</span><span>{formatCurrency(subtotal, invoice.currency)}</span></div>
          <div className="mer-totals__row"><span>Tax</span><span>{formatCurrency(tax, invoice.currency)}</span></div>
          <div className="mer-totals__row mer-totals__row--total"><span>Total due</span><span>{formatCurrency(total, invoice.currency)}</span></div>
          <div className="mer-totals__row"><span>Collected</span><span>{formatCurrency(invoice.amountPaid, invoice.currency)}</span></div>
          <div className="mer-totals__row mer-totals__row--total"><span>Balance</span><span>{formatCurrency(balance, invoice.currency)}</span></div>
        </div>
      </Card>

      <Card>
        <CardHeader title="Payment attempts" description={`${invoicePayments.length} attempt${invoicePayments.length === 1 ? "" : "s"} on this invoice.`} />
        {invoicePayments.length ? (
          <ul className="mer-timeline">
            {invoicePayments.map((p) => (
              <li key={p.id} className="mer-timeline__row">
                <span className={`mer-timeline__dot mer-timeline__dot--${paymentDot(p.status)}`} />
                <div className="mer-timeline__text">
                  <strong>{prettyPaymentStatus(p.status)} · {formatCurrency(p.amount, p.currency)}</strong>
                  <small>
                    {p.channel.replace("_", " ")}
                    {p.cardBrand && p.last4 ? ` · ${p.cardBrand.toUpperCase()} ···· ${p.last4}` : ""}
                    {p.failureReason ? ` · ${p.failureReason}` : ""}
                    {" · gateway: "}{p.gateway}
                  </small>
                </div>
                <span className="mer-timeline__time">{formatRelative(p.occurredAt)}</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mer-empty">No payment attempts have been made yet.</p>
        )}
      </Card>

      {invoice.notes ? (
        <Card>
          <CardHeader title="Internal notes" description="Visible to your team only." />
          <pre className="mer-pre">{invoice.notes}</pre>
        </Card>
      ) : null}

      {/* Send reminder modal */}
      <Modal
        open={!!reminder}
        title="Send reminder"
        description={`Notify ${customer.name} that ${invoice.number} is due.`}
        onClose={() => setReminder(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setReminder(null)}>Cancel</Button>
            <Button onClick={submitReminder} icon={<Mail size={14} />} disabled={sendingReminder}>
              {sendingReminder ? "Sending..." : "Send reminder"}
            </Button>
          </>
        }
      >
        {reminder ? (
          <div className="mer-stack">
            <Field label="Channel">
              <SelectInput
                value={reminder.channel}
                onChange={(e) => setReminder({ ...reminder, channel: e.target.value as ReminderState["channel"] })}
              >
                <option value="email">Email — {customer.email}</option>
                <option value="sms">SMS — {customer.phone}</option>
              </SelectInput>
            </Field>
            <Field label="Message" hint="You can edit this before sending.">
              <TextInput
                value={reminder.message}
                onChange={(e) => setReminder({ ...reminder, message: e.target.value })}
              />
            </Field>
          </div>
        ) : null}
      </Modal>

      {/* Retry payment modal */}
      <Modal
        open={!!retry}
        title="Retry payment"
        description="Pick a card on file to attempt the charge again. We will notify you when it completes."
        onClose={() => setRetry(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setRetry(null)}>Cancel</Button>
            <Button onClick={submitRetry} icon={<RefreshCcw size={14} />} disabled={retrying}>
              {retrying ? "Retrying..." : "Retry now"}
            </Button>
          </>
        }
      >
        {retry ? (
          <div className="mer-stack">
            <Field label="Charge card">
              <SelectInput
                value={retry.paymentMethodId}
                onChange={(e) => setRetry({ paymentMethodId: e.target.value })}
              >
                {customer.paymentMethods.length === 0 ? (
                  <option value="">No cards on file</option>
                ) : null}
                {customer.paymentMethods.map((m) => (
                  <option key={m.id} value={m.id}>
                    {m.brand?.toUpperCase()} ···· {m.last4} {m.id === customer.defaultMethodId ? "(default)" : ""}
                  </option>
                ))}
              </SelectInput>
            </Field>
            <p className="mer-hint">
              Attempt #{invoice.attempts + 1}. The customer will receive an email confirmation if it succeeds.
            </p>
          </div>
        ) : null}
      </Modal>

      {/* Mark paid modal */}
      <Modal
        open={!!paid}
        title="Mark invoice paid"
        description="Use this for payments received outside SubPilot (cash, bank transfer, etc)."
        onClose={() => setPaid(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setPaid(null)}>Cancel</Button>
            <Button onClick={submitMarkPaid} disabled={markingPaid}>
              {markingPaid ? "Saving..." : "Confirm payment"}
            </Button>
          </>
        }
      >
        {paid ? (
          <div className="mer-stack">
            <Field label="Amount received">
              <TextInput type="number" min="0" value={paid.amount} onChange={(e) => setPaid({ ...paid, amount: e.target.value })} />
            </Field>
            <Field label="Method">
              <SelectInput
                value={paid.method}
                onChange={(e) => setPaid({ ...paid, method: e.target.value as MarkPaidState["method"] })}
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

      {/* Apply credit modal */}
      <Modal
        open={!!credit}
        title="Apply credit"
        description="Reduce the balance on this invoice with a non-cash credit."
        onClose={() => setCredit(null)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCredit(null)}>Cancel</Button>
            <Button onClick={submitCredit} disabled={applyingCredit}>
              {applyingCredit ? "Applying..." : "Apply credit"}
            </Button>
          </>
        }
      >
        {credit ? (
          <div className="mer-stack">
            <Field label="Credit amount" hint={`Max ${formatCurrency(balance, invoice.currency)} (current balance).`}>
              <TextInput type="number" min="0" value={credit.amount} onChange={(e) => setCredit({ ...credit, amount: e.target.value })} />
            </Field>
            <Field label="Reason" hint="Logged in audit and visible to teammates.">
              <TextInput value={credit.reason} onChange={(e) => setCredit({ ...credit, reason: e.target.value })} />
            </Field>
          </div>
        ) : null}
      </Modal>
    </>
  );
}

function invoiceTone(status: InvoiceStatus): BadgeTone {
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

function paymentDot(status: PaymentRecord["status"]): "success" | "danger" | "warning" | "neutral" {
  switch (status) {
    case "captured":
    case "recovered":
      return "success";
    case "failed":
      return "danger";
    case "pending":
      return "warning";
    case "refunded":
    default:
      return "neutral";
  }
}

function prettyStatus(status: string): string {
  return status
    .split("_")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}

function prettyPaymentStatus(status: PaymentRecord["status"]): string {
  switch (status) {
    case "captured": return "Captured";
    case "failed": return "Failed";
    case "refunded": return "Refunded";
    case "recovered": return "Recovered";
    case "pending": return "Pending";
  }
}

function prettyMethod(method: MarkPaidState["method"]): string {
  switch (method) {
    case "card": return "card on file";
    case "bank_transfer": return "bank transfer";
    case "cash": return "cash";
    case "manual": return "manual entry";
  }
}
