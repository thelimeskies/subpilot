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
  StatCard,
  Tabs,
  TextInput,
  type BadgeTone,
  type DataTableColumn
} from "@subpilot/ui";
import {
  AlertTriangle,
  Ban,
  Mail,
  PauseCircle,
  RotateCcw,
  Settings as SettingsIcon,
  SkipForward
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { usePagination } from "../hooks/usePagination";
import { useFeedback } from "../feedback/ActionFeedback";
import { createPortalSession } from "../api/billing";
import { isApiError } from "../api/client";
import { useData } from "../data/store";
import { usePermissions } from "../auth/AuthContext";
import { formatCurrency, formatRelative } from "../data/selectors";
import type { Customer, RecoveryItem } from "../data/seed";

type TabKey = "retry" | "manual";

interface RetryNowState {
  item: RecoveryItem;
  paymentMethodId: string;
}

interface PortalLinkState {
  item: RecoveryItem;
  channel: "email" | "sms";
}

interface PauseState {
  item: RecoveryItem;
  duration: "3" | "7" | "14" | "30";
  reason: string;
}

function formatPausedUntil(iso: string): string {
  const timestamp = Date.parse(iso);
  if (Number.isNaN(timestamp)) return iso;
  return new Intl.DateTimeFormat("en-NG", {
    day: "numeric",
    month: "short",
    year: "numeric"
  }).format(new Date(timestamp));
}

export function RecoveryPage() {
  const { recoveryItems, customers, invoices, resolveRecoveryItem, logAuditEvent } = useData();
  const { notify, confirm } = useFeedback();
  const { can } = usePermissions();
  const canRetry = can("retry_invoice");
  const canPause = can("pause_resume_subscription");
  const canSendPortal = can("create_payment_method_session");
  const canWriteOff = can("mark_uncollectible");
  const canConfigureDunning = can("manage_dunning_policies");
  const [tab, setTab] = useState<TabKey>("retry");
  const [retryOpen, setRetryOpen] = useState<RetryNowState | null>(null);
  const [portalOpen, setPortalOpen] = useState<PortalLinkState | null>(null);
  const [pauseOpen, setPauseOpen] = useState<PauseState | null>(null);
  const [retrying, setRetrying] = useState(false);
  const [sendingPortal, setSendingPortal] = useState(false);
  const [pausing, setPausing] = useState(false);

  const retryQueue = useMemo(
    () => recoveryItems.filter((r) => r.stage === "retry_queue"),
    [recoveryItems]
  );
  // Manual review tab also surfaces paused items so operators can resume them.
  const manualReview = useMemo(
    () => recoveryItems.filter((r) => r.stage === "manual_review" || r.stage === "paused"),
    [recoveryItems]
  );

  const stats = useMemo(() => {
    const totalAtRisk = recoveryItems.reduce((sum, r) => sum + r.amount, 0);
    const totalAttempts = recoveryItems.reduce((sum, r) => sum + r.attempts, 0);
    const avgAttempts = recoveryItems.length ? totalAttempts / recoveryItems.length : 0;
    return {
      totalAtRisk,
      retryCount: retryQueue.length,
      manualCount: manualReview.length,
      avgAttempts
    };
  }, [recoveryItems, retryQueue, manualReview]);

  const visible = tab === "retry" ? retryQueue : manualReview;
  const { page, setPage, pageCount, slice, totalLabel } = usePagination(visible, 10, "items");

  function customerFor(item: RecoveryItem): Customer | null {
    return customers.find((c) => c.id === item.customerId) ?? null;
  }

  function invoiceNumberFor(item: RecoveryItem): string {
    return invoices.find((inv) => inv.id === item.invoiceId)?.number ?? item.invoiceId;
  }

  // ---------- Retry now ----------
  function openRetry(item: RecoveryItem) {
    const customer = customerFor(item);
    setRetryOpen({
      item,
      paymentMethodId: customer?.defaultMethodId ?? customer?.paymentMethods[0]?.id ?? ""
    });
  }
  async function submitRetry() {
    if (!retryOpen) return;
    const { item } = retryOpen;
    setRetrying(true);
    try {
      await resolveRecoveryItem(item.id, "retried");
      logAuditEvent({
        actor: "You",
        action: "Retried failed invoice",
        target: invoiceNumberFor(item)
      });
      notify({
        tone: "success",
        title: "Retry queued",
        description: `${formatCurrency(item.amount)} will be charged within the next minute.`
      });
      setRetryOpen(null);
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

  // ---------- Skip retry ----------
  async function handleSkip(item: RecoveryItem) {
    const ok = await confirm({
      title: "Skip this retry?",
      description: "The invoice stays open but we won't auto-retry. You can manually retry later.",
      confirmLabel: "Skip retry"
    });
    if (!ok) return;
    try {
      await resolveRecoveryItem(item.id, "skipped", "Skipped from recovery cockpit");
      logAuditEvent({
        actor: "You",
        action: "Skipped retry",
        target: invoiceNumberFor(item)
      });
      notify({ tone: "info", title: "Retry skipped", description: "Invoice removed from the queue." });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not skip retry",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }

  // ---------- Send portal link ----------
  function openPortal(item: RecoveryItem) {
    setPortalOpen({ item, channel: "email" });
  }
  async function submitPortal() {
    if (!portalOpen) return;
    const customer = customerFor(portalOpen.item);
    const dest = portalOpen.channel === "email" ? customer?.email : customer?.phone;
    if (!customer) return;
    if (portalOpen.channel !== "email") {
      notify({ tone: "warning", title: "SMS delivery is not configured", description: "Use email for portal-link delivery in this build." });
      return;
    }
    setSendingPortal(true);
    try {
      const session = await createPortalSession(customer.id, { sendEmail: true });
      logAuditEvent({
        actor: "You",
        action: `Created portal link via ${portalOpen.channel.toUpperCase()}`,
        target: dest ?? portalOpen.item.customerId
      });
      notify({
        tone: "success",
        title: session.emailQueued ? "Portal link sent" : "Portal link created",
        description: session.emailQueued
          ? `${customer.name} will receive the update payment link via email.`
          : session.url
      });
      setPortalOpen(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not create portal link",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setSendingPortal(false);
    }
  }

  // ---------- Mark uncollectible ----------
  async function handleUncollectible(item: RecoveryItem) {
    const ok = await confirm({
      destructive: true,
      title: "Mark as uncollectible?",
      description: `${formatCurrency(item.amount)} on ${invoiceNumberFor(item)} will be written off. The invoice status changes to "Uncollectible" and the customer is no longer auto-charged. This cannot be undone.`,
      confirmLabel: "Write off"
    });
    if (!ok) return;
    try {
      await resolveRecoveryItem(item.id, "uncollectible");
      logAuditEvent({
        actor: "You",
        action: "Marked invoice uncollectible",
        target: invoiceNumberFor(item)
      });
      notify({
        tone: "warning",
        title: "Marked uncollectible",
        description: `${formatCurrency(item.amount)} written off.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not mark uncollectible",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }

  // ---------- Pause dunning ----------
  function openPause(item: RecoveryItem) {
    setPauseOpen({ item, duration: "7", reason: "" });
  }
  function patchPause(patch: Partial<PauseState>) {
    setPauseOpen((prev) => (prev ? { ...prev, ...patch } : prev));
  }
  async function submitPause() {
    if (!pauseOpen) return;
    const days = Number(pauseOpen.duration);
    const pausedUntil = new Date(Date.now() + days * 24 * 60 * 60 * 1000).toISOString();
    setPausing(true);
    try {
      await resolveRecoveryItem(
        pauseOpen.item.id,
        "paused",
        `Paused for ${days} days${pauseOpen.reason ? `: ${pauseOpen.reason}` : ""}`,
        { pausedUntil }
      );
      logAuditEvent({
        actor: "You",
        action: `Paused dunning for ${days} day${days === 1 ? "" : "s"}`,
        target: invoiceNumberFor(pauseOpen.item)
      });
      notify({
        tone: "info",
        title: "Dunning paused",
        description: `Auto-retries are paused until ${new Date(pausedUntil).toLocaleDateString()}.${pauseOpen.reason ? ` Reason logged: ${pauseOpen.reason}` : ""}`
      });
      setPauseOpen(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not pause dunning",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    } finally {
      setPausing(false);
    }
  }

  async function handleResume(item: RecoveryItem) {
    try {
      await resolveRecoveryItem(item.id, "resumed");
      logAuditEvent({
        actor: "You",
        action: "Resumed dunning",
        target: invoiceNumberFor(item)
      });
      notify({
        tone: "success",
        title: "Dunning resumed",
        description: "The invoice is back in the retry queue."
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not resume dunning",
        description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
      });
    }
  }

  const columns: DataTableColumn<RecoveryItem>[] = [
    {
      key: "customer",
      header: "Customer",
      render: (item) => {
        const customer = customerFor(item);
        if (!customer) return <span className="mer-muted">{item.customerId}</span>;
        return (
          <Link to={`/customers/${customer.id}`} className="mer-entity-cell">
            <strong>{customer.name}</strong>
            <small>{customer.email} · {invoiceNumberFor(item)}</small>
          </Link>
        );
      }
    },
    {
      key: "amount",
      header: "Amount",
      align: "right",
      render: (item) => <strong>{formatCurrency(item.amount)}</strong>
    },
    {
      key: "reason",
      header: "Reason",
      render: (item) => (
        <span className="mer-entity-cell">
          <strong>{prettyReason(item.reason)}</strong>
          <small>{item.attempts} attempt{item.attempts === 1 ? "" : "s"}</small>
        </span>
      )
    },
    {
      key: "stage",
      header: "Stage",
      render: (item) => <Badge tone={stageTone(item.stage)}>{prettyStage(item.stage)}</Badge>
    },
    {
      key: "next",
      header: "Next retry",
      render: (item) =>
        item.stage === "paused" ? (
          <span className="mer-entity-cell">
            <strong>{item.nextRetryAt ? `Until ${formatPausedUntil(item.nextRetryAt)}` : "Paused"}</strong>
            <small>Last: {formatRelative(item.lastAttemptAt)}</small>
          </span>
        ) :
        item.nextRetryAt ? (
          <span className="mer-entity-cell">
            <strong>{formatRelative(item.nextRetryAt)}</strong>
            <small>Last: {formatRelative(item.lastAttemptAt)}</small>
          </span>
        ) : (
          <span className="mer-muted">Paused</span>
        )
    },
    {
      key: "actions",
      header: "",
      render: (item) => (
        <div className="mer-row-actions">
          {canRetry && item.stage !== "paused" ? (
            <Button variant="ghost" icon={<RotateCcw size={14} />} onClick={() => openRetry(item)}>
              Retry
            </Button>
          ) : canPause && item.stage === "paused" ? (
            <Button variant="ghost" icon={<RotateCcw size={14} />} onClick={() => handleResume(item)}>
              Resume
            </Button>
          ) : null}
          {canRetry && item.stage === "retry_queue" ? (
            <Button variant="ghost" icon={<SkipForward size={14} />} onClick={() => handleSkip(item)}>
              Skip
            </Button>
          ) : null}
          {canSendPortal ? (
            <Button variant="ghost" icon={<Mail size={14} />} onClick={() => openPortal(item)}>
              Portal link
            </Button>
          ) : null}
          {canPause && item.stage !== "paused" ? (
            <Button variant="ghost" icon={<PauseCircle size={14} />} onClick={() => openPause(item)}>
              Pause
            </Button>
          ) : null}
          {canWriteOff ? (
            <Button variant="ghost" icon={<Ban size={14} />} onClick={() => handleUncollectible(item)}>
              Write off
            </Button>
          ) : null}
        </div>
      )
    }
  ];

  const retryCustomer = retryOpen ? customerFor(retryOpen.item) : null;
  const portalCustomer = portalOpen ? customerFor(portalOpen.item) : null;

  return (
    <>
      <PageHeader
        eyebrow="Recovery cockpit"
        title="Failed payment recovery"
        description="Triage failed charges, retry intelligently, and keep your churn from involuntary failures low."
        actions={
          canConfigureDunning ? (
            <Link to="/settings#dunning" className="sp-button sp-button--secondary">
              <SettingsIcon size={16} aria-hidden="true" />
              Configure dunning rules
            </Link>
          ) : null
        }
      />

      <section className="sp-grid sp-grid-4">
        <StatCard
          label="Total at risk"
          value={formatCurrency(stats.totalAtRisk)}
          delta={`${recoveryItems.length} invoice${recoveryItems.length === 1 ? "" : "s"}`}
          tone={stats.totalAtRisk > 0 ? "warning" : "neutral"}
        />
        <StatCard
          label="Retry queue"
          value={String(stats.retryCount)}
          delta={stats.retryCount === 0 ? "All clear" : "Auto-retrying"}
          tone={stats.retryCount === 0 ? "success" : "info"}
        />
        <StatCard
          label="Manual review"
          value={String(stats.manualCount)}
          delta={stats.manualCount === 0 ? "Nothing pending" : "Needs you"}
          tone={stats.manualCount === 0 ? "neutral" : "danger"}
        />
        <StatCard
          label="Avg attempts"
          value={stats.avgAttempts.toFixed(1)}
          delta="Per failed invoice"
          tone="neutral"
        />
      </section>

      <Card>
        <CardHeader
          title="Recovery queue"
          description="Each row corresponds to a failed invoice that automation could not collect on its first attempt."
          action={
            <Badge tone={stats.totalAtRisk > 0 ? "warning" : "success"}>
              {formatCurrency(stats.totalAtRisk)} at risk
            </Badge>
          }
        />
        <Tabs
          value={tab}
          onChange={(v) => {
            setTab(v as TabKey);
            setPage(1);
          }}
          items={[
            { label: "Retry queue", value: "retry", count: retryQueue.length },
            { label: "Manual review", value: "manual", count: manualReview.length }
          ]}
        />
        <DataTable
          columns={columns}
          rows={slice}
          getRowKey={(item) => item.id}
          emptyText={
            tab === "retry"
              ? "Nothing in the retry queue — all charges are succeeding."
              : "No invoices waiting on manual review."
          }
        />
        <Pagination page={page} pageCount={pageCount} onPageChange={setPage} totalLabel={totalLabel} />
      </Card>

      {/* Retry now Modal */}
      <Modal
        open={!!retryOpen}
        onClose={() => setRetryOpen(null)}
        title="Retry payment now"
        description={
          retryOpen
            ? `Charge ${formatCurrency(retryOpen.item.amount)} for ${invoiceNumberFor(retryOpen.item)}.`
            : ""
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setRetryOpen(null)}>Cancel</Button>
            <Button onClick={submitRetry} icon={<RotateCcw size={14} />} disabled={retrying}>
              {retrying ? "Retrying…" : "Retry now"}
            </Button>
          </>
        }
      >
        {retryOpen && retryCustomer ? (
          <div className="sp-form-grid">
            <div className="mer-totals">
              <div className="mer-totals__row"><span>Customer</span><strong>{retryCustomer.name}</strong></div>
              <div className="mer-totals__row"><span>Invoice</span><strong>{invoiceNumberFor(retryOpen.item)}</strong></div>
              <div className="mer-totals__row"><span>Amount</span><strong>{formatCurrency(retryOpen.item.amount)}</strong></div>
              <div className="mer-totals__row"><span>Reason</span><strong>{prettyReason(retryOpen.item.reason)}</strong></div>
            </div>
            <Field label="Payment method">
              {retryCustomer.paymentMethods.length === 0 ? (
                <p className="mer-hint">Backend will use the tokenized/default payment method from the failed attempt.</p>
              ) : (
                <SelectInput
                  value={retryOpen.paymentMethodId}
                  onChange={(e) =>
                    setRetryOpen((prev) => (prev ? { ...prev, paymentMethodId: e.target.value } : prev))
                  }
                >
                  {retryCustomer.paymentMethods.map((pm) => (
                    <option key={pm.id} value={pm.id}>
                      {pm.brand.toUpperCase()} •••• {pm.last4}
                      {pm.id === retryCustomer.defaultMethodId ? " (default)" : ""}
                    </option>
                  ))}
                </SelectInput>
              )}
            </Field>
            <p className="mer-hint">
              <AlertTriangle size={12} aria-hidden="true" /> Failed retries will be billed again
              automatically per your dunning schedule.
            </p>
          </div>
        ) : null}
      </Modal>

      {/* Send portal link Modal */}
      <Modal
        open={!!portalOpen}
        onClose={() => setPortalOpen(null)}
        title="Send portal link"
        description={
          portalCustomer
            ? `${portalCustomer.name} will receive a self-service link to update payment details.`
            : ""
        }
        footer={
          <>
            <Button variant="ghost" onClick={() => setPortalOpen(null)}>Cancel</Button>
            <Button onClick={submitPortal} icon={<Mail size={14} />} disabled={sendingPortal}>
              {sendingPortal ? "Sending…" : "Send link"}
            </Button>
          </>
        }
      >
        {portalOpen && portalCustomer ? (
          <div className="sp-form-grid">
            <Field label="Channel">
              <SelectInput
                value={portalOpen.channel}
                onChange={(e) =>
                  setPortalOpen((prev) => (prev ? { ...prev, channel: e.target.value as "email" | "sms" } : prev))
                }
              >
                <option value="email">Email — {portalCustomer.email}</option>
                <option value="sms" disabled>SMS — not configured</option>
              </SelectInput>
            </Field>
            <div className="mer-pre">
              Hi {portalCustomer.name.split(" ")[0]}, your last payment of {formatCurrency(portalOpen.item.amount)}
              {" "}didn't go through ({prettyReason(portalOpen.item.reason).toLowerCase()}). Update your card through the secure link we generate when you send.
            </div>
          </div>
        ) : null}
      </Modal>

      {/* Pause dunning Sheet */}
      <Sheet
        open={!!pauseOpen}
        onClose={() => setPauseOpen(null)}
        title="Pause dunning"
        description="Stop auto-retries while you resolve this with the customer."
        footer={
          <>
            <Button variant="ghost" onClick={() => setPauseOpen(null)}>Cancel</Button>
            <Button onClick={submitPause} icon={<PauseCircle size={14} />} disabled={pausing}>
              {pausing ? "Pausing…" : "Pause dunning"}
            </Button>
          </>
        }
      >
        {pauseOpen ? (
          <div className="sp-form-grid">
            <div className="mer-totals">
              <div className="mer-totals__row">
                <span>Invoice</span><strong>{invoiceNumberFor(pauseOpen.item)}</strong>
              </div>
              <div className="mer-totals__row">
                <span>Amount</span><strong>{formatCurrency(pauseOpen.item.amount)}</strong>
              </div>
            </div>
            <Field label="Pause duration">
              <SelectInput
                value={pauseOpen.duration}
                onChange={(e) => patchPause({ duration: e.target.value as PauseState["duration"] })}
              >
                <option value="3">3 days</option>
                <option value="7">7 days</option>
                <option value="14">14 days</option>
                <option value="30">30 days</option>
              </SelectInput>
            </Field>
            <Field label="Reason (optional)" hint="Logged in audit trail.">
              <TextInput
                placeholder="e.g. Customer requested grace period until 1st of next month"
                value={pauseOpen.reason}
                onChange={(e) => patchPause({ reason: e.target.value })}
              />
            </Field>
            <p className="mer-hint">
              The invoice stays open. You can resume by retrying manually before the pause window ends.
            </p>
          </div>
        ) : null}
      </Sheet>
    </>
  );
}

function stageTone(stage: RecoveryItem["stage"]): BadgeTone {
  switch (stage) {
    case "manual_review":
      return "danger";
    case "paused":
      return "info";
    default:
      return "warning";
  }
}

function prettyStage(stage: RecoveryItem["stage"]): string {
  switch (stage) {
    case "retry_queue":
      return "Retry queue";
    case "manual_review":
      return "Manual review";
    case "paused":
      return "Paused";
    default:
      return stage;
  }
}

function prettyReason(reason: string): string {
  return reason
    .split("_")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}
