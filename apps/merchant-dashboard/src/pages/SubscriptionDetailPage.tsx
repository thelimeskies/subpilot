import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Modal,
  SelectInput,
  Sheet,
  StatCard,
  Tabs,
  TextInput
} from "@subpilot/ui";
import { ArrowLeft, BadgeDollarSign, CreditCard, Pause, Play, RefreshCcw, X } from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { useData } from "../data/store";
import { isApiError } from "../api/client";
import { createPortalSession } from "../api/billing";
import {
  loadSubscriptionEvents,
  previewSubscriptionPlanChange,
  type SubscriptionEvent,
  type SubscriptionPlanChangePreview
} from "../api/subscriptions";
import { usePermissions } from "../auth/AuthContext";
import {
  findCustomerById,
  findInvoicesByCustomer,
  findPlanById,
  formatCurrency,
  formatRelative
} from "../data/selectors";

type TabKey = "lifecycle" | "invoices" | "events" | "notes";

export function SubscriptionDetailPage() {
  const { subId } = useParams<{ subId: string }>();
  const {
    subscriptions,
    resourcesLoading,
    customers,
    plans,
    invoices,
    cancelSubscription,
    pauseSubscription,
    resumeSubscription,
    applySubscriptionCredit,
    updateSubscription,
    logAuditEvent
  } = useData();
  const { notify, confirm } = useFeedback();
  const { can } = usePermissions();
  const canChangePlan = can("create_subscription");
  const canPauseResume = can("pause_resume_subscription");
  const canCancel = can("cancel_subscription");
  const canApplyCredit = can("apply_credit_note");
  const canManageMethod = can("create_payment_method_session");
  const canEditNotes = can("create_subscription");
  const [tab, setTab] = useState<TabKey>("lifecycle");
  const [changePlanOpen, setChangePlanOpen] = useState(false);
  const [newPlanId, setNewPlanId] = useState<string>("");
  const [methodOpen, setMethodOpen] = useState(false);
  const [creditOpen, setCreditOpen] = useState(false);
  const [creditAmount, setCreditAmount] = useState("");
  const [notes, setNotes] = useState("");
  const [savingChangePlan, setSavingChangePlan] = useState(false);
  const [savingMethodId, setSavingMethodId] = useState<string | null>(null);
  const [savingLifecycle, setSavingLifecycle] = useState<"cancel" | "pause" | "resume" | null>(null);
  const [savingNote, setSavingNote] = useState(false);
  const [savingCredit, setSavingCredit] = useState(false);
  const [sendingPortalLink, setSendingPortalLink] = useState(false);
  const [events, setEvents] = useState<SubscriptionEvent[]>([]);
  const [eventsLoading, setEventsLoading] = useState(false);
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [planPreview, setPlanPreview] = useState<SubscriptionPlanChangePreview | null>(null);
  const [planPreviewLoading, setPlanPreviewLoading] = useState(false);
  const [planPreviewError, setPlanPreviewError] = useState<string | null>(null);

  const sub = subscriptions.find((s) => s.id === subId);
  const customer = sub ? findCustomerById(customers, sub.customerId) : null;
  const plan = sub ? findPlanById(plans, sub.planId) : null;
  const subInvoices = useMemo(
    () => (sub ? invoices.filter((i) => i.subscriptionId === sub.id) : []),
    [sub, invoices]
  );
  const customerInvoices = useMemo(
    () => (customer ? findInvoicesByCustomer(invoices, customer.id) : []),
    [customer, invoices]
  );

  useEffect(() => {
    if (tab !== "events" || !subId) return;
    let cancelled = false;
    setEventsLoading(true);
    setEventsError(null);
    loadSubscriptionEvents(subId)
      .then((items) => {
        if (!cancelled) setEvents(items);
      })
      .catch((err) => {
        if (!cancelled) {
          setEventsError(isApiError(err) ? err.reason : err instanceof Error ? err.message : "Could not load subscription events.");
        }
      })
      .finally(() => {
        if (!cancelled) setEventsLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [subId, tab]);

  useEffect(() => {
    if (!changePlanOpen || !subId || !newPlanId || newPlanId === sub?.planId) {
      setPlanPreview(null);
      setPlanPreviewError(null);
      setPlanPreviewLoading(false);
      return;
    }
    let cancelled = false;
    setPlanPreviewLoading(true);
    setPlanPreviewError(null);
    previewSubscriptionPlanChange(subId, newPlanId)
      .then((preview) => {
        if (!cancelled) setPlanPreview(preview);
      })
      .catch((err) => {
        if (!cancelled) {
          setPlanPreview(null);
          setPlanPreviewError(isApiError(err) ? err.reason : err instanceof Error ? err.message : "Could not preview this plan change.");
        }
      })
      .finally(() => {
        if (!cancelled) setPlanPreviewLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [changePlanOpen, newPlanId, sub?.planId, subId]);

  if (!sub || !customer) {
    if (resourcesLoading) {
      return (
        <div className="mer-boot" role="status" aria-live="polite">
          <span className="mer-boot__spinner" aria-hidden="true" />
          <span>Loading...</span>
        </div>
      );
    }
    return (
      <div className="mer-empty-state">
        <h2>Subscription not found</h2>
        <p>We couldn&rsquo;t locate <code>{subId}</code>.</p>
        <Link to="/subscriptions" className="mer-card-link">
          <ArrowLeft size={14} aria-hidden="true" /> Back to subscriptions
        </Link>
      </div>
    );
  }

  async function handleCancel() {
    if (!sub) return;
    const ok = await confirm({
      destructive: true,
      title: "Cancel subscription?",
      description: `Stop billing for ${customer?.name ?? "this customer"}. End-of-period keeps service until ${sub.currentPeriodEnd}.`,
      confirmLabel: "Cancel immediately"
    });
    if (!ok) return;
    setSavingLifecycle("cancel");
    try {
      await cancelSubscription(sub.id, "immediate");
      logAuditEvent({ actor: "You", action: "Cancelled subscription", target: sub.id });
      notify({ tone: "info", title: "Subscription cancelled", description: "Customer was notified by email." });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not cancel subscription",
        description: isApiError(err) ? err.reason : err instanceof Error ? err.message : "The backend rejected the cancellation."
      });
    } finally {
      setSavingLifecycle(null);
    }
  }

  async function handlePauseToggle() {
    if (!sub) return;
    if (sub.status === "paused") {
      const ok = await confirm({ title: "Resume subscription?", description: "Billing resumes next period.", confirmLabel: "Resume" });
      if (!ok) return;
      setSavingLifecycle("resume");
      try {
        await resumeSubscription(sub.id);
        logAuditEvent({ actor: "You", action: "Resumed subscription", target: sub.id });
        notify({ tone: "success", title: "Subscription resumed" , description: "Scheduler is back online for this customer."});
      } catch (err) {
        notify({
          tone: "danger",
          title: "Could not resume subscription",
          description: isApiError(err) ? err.reason : err instanceof Error ? err.message : "The backend rejected the resume request."
        });
      } finally {
        setSavingLifecycle(null);
      }
    } else {
      setSavingLifecycle("pause");
      try {
        await pauseSubscription(sub.id, sub.currentPeriodEnd, "Paused from subscription detail");
        logAuditEvent({ actor: "You", action: "Paused subscription", target: sub.id });
        notify({ tone: "info", title: "Subscription paused", description: `Resume target set for ${sub.currentPeriodEnd}.` });
      } catch (err) {
        notify({
          tone: "danger",
          title: "Could not pause subscription",
          description: isApiError(err) ? err.reason : err instanceof Error ? err.message : "The backend rejected the pause request."
        });
      } finally {
        setSavingLifecycle(null);
      }
    }
  }

  async function submitChangePlan() {
    if (!sub) return;
    const next = plans.find((p) => p.id === newPlanId);
    if (!next) {
      notify({ tone: "warning", title: "Pick a plan", description: "Select a target plan to switch to." });
      return;
    }
    if (next.id === sub.planId) {
      notify({ tone: "warning", title: "Already on this plan", description: "Select a different active plan to continue." });
      return;
    }
    if (planPreviewError) {
      notify({ tone: "danger", title: "Preview required", description: planPreviewError });
      return;
    }
    if (!planPreview || planPreviewLoading) {
      notify({ tone: "warning", title: "Preview still loading", description: "Wait for the backend proration preview before applying the change." });
      return;
    }
    setSavingChangePlan(true);
    try {
      await updateSubscription(sub.id, { planId: next.id });
      logAuditEvent({ actor: "You", action: "Changed plan", target: `${sub.id} → ${next.name}` });
      notify({
        tone: "success",
        title: "Plan updated",
        description: `Now on ${next.name}. Net next-invoice impact: ${formatMinorCurrency(planPreview.netMinor, planPreview.currency)}.`
      });
      setChangePlanOpen(false);
      setPlanPreview(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not change plan",
        description: isApiError(err) ? err.reason : err instanceof Error ? err.message : "The backend rejected the plan change."
      });
    } finally {
      setSavingChangePlan(false);
    }
  }

  async function usePaymentMethod(methodId: string) {
    if (!sub || !customer) return;
    const method = customer.paymentMethods.find((m) => m.id === methodId);
    if (!method) return;
    setSavingMethodId(methodId);
    try {
      await updateSubscription(sub.id, { paymentMethodId: method.id });
      logAuditEvent({ actor: "You", action: "Changed subscription payment method", target: `${sub.id} → ${method.brand} •••• ${method.last4}` });
      notify({ tone: "success", title: "Payment method updated", description: `Now charging ${method.brand} •••• ${method.last4}.` });
      setMethodOpen(false);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not update payment method",
        description: isApiError(err) ? err.reason : err instanceof Error ? err.message : "The backend rejected the payment method change."
      });
    } finally {
      setSavingMethodId(null);
    }
  }

  async function applyCredit() {
    if (!sub) return;
    const amount = Number(creditAmount);
    if (Number.isNaN(amount) || amount <= 0) {
      notify({ tone: "warning", title: "Invalid amount", description: "Enter a positive credit amount." });
      return;
    }
    setSavingCredit(true);
    try {
      await applySubscriptionCredit(sub.id, amount, "Applied from subscription detail");
      logAuditEvent({ actor: "You", action: "Applied credit", target: `${sub.id} — ${formatCurrency(amount)}` });
      notify({ tone: "success", title: "Credit applied", description: `${formatCurrency(amount)} will reduce the next invoice.` });
      setCreditOpen(false);
      setCreditAmount("");
      if (tab === "events") {
        setEvents(await loadSubscriptionEvents(sub.id));
      }
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not apply credit",
        description: isApiError(err) ? err.reason : err instanceof Error ? err.message : "The backend rejected the credit."
      });
    } finally {
      setSavingCredit(false);
    }
  }

  async function sendPortalLink() {
    if (!sub || !customer) return;
    setSendingPortalLink(true);
    try {
      const session = await createPortalSession(customer.id, { subscriptionId: sub.id, sendEmail: true });
      if (!session.emailQueued && navigator.clipboard?.writeText) {
        await navigator.clipboard.writeText(session.url).catch(() => undefined);
      }
      logAuditEvent({ actor: "You", action: "Created subscription portal link", target: `${customer.email} · ${sub.id}` });
      notify({
        tone: "success",
        title: session.emailQueued ? "Portal email queued" : "Portal link created",
        description: session.emailQueued
          ? `${customer.email} will receive the update-payment link shortly.`
          : `${customer.email} can update payment details at ${session.url}`
      });
      setMethodOpen(false);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not create portal link",
        description: isApiError(err) ? err.reason : err instanceof Error ? err.message : "The backend rejected the portal session request."
      });
    } finally {
      setSendingPortalLink(false);
    }
  }

  async function saveNote() {
    if (!sub) return;
    if (!notes.trim()) {
      notify({ tone: "warning", title: "Empty note", description: "Type something before saving." });
      return;
    }
    setSavingNote(true);
    try {
      await updateSubscription(sub.id, { notes: notes.trim() });
      logAuditEvent({ actor: "You", action: "Added subscription note", target: sub.id });
      notify({ tone: "success", title: "Note saved", description: "Internal note attached to this subscription." });
      setNotes("");
      if (tab === "events") {
        setEvents(await loadSubscriptionEvents(sub.id));
      }
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not save note",
        description: isApiError(err) ? err.reason : err instanceof Error ? err.message : "The backend rejected the note."
      });
    } finally {
      setSavingNote(false);
    }
  }

  return (
    <>
      <PageHeader
        eyebrow={
          <span className="mer-breadcrumb-eyebrow">
            <Link to="/subscriptions" className="mer-card-link">
              <ArrowLeft size={12} aria-hidden="true" /> Subscriptions
            </Link>
            <span> / {sub.id}</span>
          </span>
        }
        title={`${customer.name} — ${plan?.name ?? sub.planId}`}
        description={`${formatCurrency(sub.amount)} per ${sub.interval} · started ${sub.startedAt}`}
        actions={
          <>
            {canChangePlan ? (
              <Button variant="secondary" icon={<RefreshCcw size={16} />} onClick={() => { setNewPlanId(sub.planId); setChangePlanOpen(true); }}>
                Change plan
              </Button>
            ) : null}
            {canManageMethod ? (
              <Button variant="secondary" icon={<CreditCard size={16} />} onClick={() => setMethodOpen(true)}>
                Update method
              </Button>
            ) : null}
            {canApplyCredit ? (
              <Button variant="secondary" icon={<BadgeDollarSign size={16} />} onClick={() => setCreditOpen(true)}>
                Apply credit
              </Button>
            ) : null}
            {sub.status === "paused" && canPauseResume ? (
              <Button icon={<Play size={16} />} onClick={handlePauseToggle} disabled={savingLifecycle !== null}>
                {savingLifecycle === "resume" ? "Resuming..." : "Resume"}
              </Button>
            ) : sub.status !== "cancelled" && canPauseResume ? (
              <Button variant="secondary" icon={<Pause size={16} />} onClick={handlePauseToggle} disabled={savingLifecycle !== null}>
                {savingLifecycle === "pause" ? "Pausing..." : "Pause"}
              </Button>
            ) : null}
            {sub.status !== "cancelled" && canCancel ? (
              <Button variant="danger" icon={<X size={16} />} onClick={handleCancel} disabled={savingLifecycle !== null}>
                {savingLifecycle === "cancel" ? "Cancelling..." : "Cancel"}
              </Button>
            ) : null}
          </>
        }
      />

      <div className="mer-detail-meta">
        <Badge tone={subTone(sub.status)}>{prettyStatus(sub.status)}</Badge>
        <span>Period {sub.currentPeriodStart} → {sub.currentPeriodEnd}</span>
        {sub.trialEnd ? <span>Trial ends {sub.trialEnd}</span> : null}
        {sub.cancelAt ? <span>Cancels {sub.cancelAt}</span> : null}
      </div>

      <Tabs
        value={tab}
        onChange={(v) => setTab(v as TabKey)}
        items={[
          { label: "Lifecycle", value: "lifecycle" },
          { label: "Invoices", value: "invoices", count: subInvoices.length },
          { label: "Events", value: "events" },
          { label: "Notes", value: "notes" }
        ]}
      />

      {tab === "lifecycle" ? (
        <>
          <section className="sp-grid sp-grid-4">
            <StatCard label="Status" value={prettyStatus(sub.status)} delta={sub.status === "active" ? "Live" : "—"} tone={subTone(sub.status)} />
            <StatCard label="Amount" value={formatCurrency(sub.amount)} delta={`per ${sub.interval}`} tone="teal" />
            <StatCard label="Customer MRR" value={formatCurrency(customer.mrr)} delta="across all subs" tone="info" />
            <StatCard label="Invoices" value={String(customerInvoices.length)} delta={`${customerInvoices.filter((i) => i.status === "paid").length} paid`} tone="success" />
          </section>
          <Card>
            <CardHeader title="Lifecycle" description="Key transitions on this subscription." />
            <div className="mer-timeline">
              <TimelineRow when={sub.startedAt} label="Subscription created" detail={`${customer.name} subscribed to ${plan?.name ?? sub.planId}`} />
              {sub.trialEnd ? (
                <TimelineRow when={sub.trialEnd} label="Trial ends" detail="First charge will run after this date." tone="warning" />
              ) : null}
              <TimelineRow when={sub.currentPeriodStart} label="Current period started" detail={`Will renew on ${sub.currentPeriodEnd}.`} tone="neutral" />
              {sub.cancelAt ? (
                <TimelineRow when={sub.cancelAt} label="Cancellation scheduled" detail="No further invoices will be issued." tone="danger" />
              ) : null}
              {sub.notes ? <TimelineRow when={sub.startedAt} label="Note" detail={sub.notes} tone="neutral" /> : null}
            </div>
          </Card>
        </>
      ) : null}

      {tab === "invoices" ? (
        <Card>
          <CardHeader title="Invoices" description={`${subInvoices.length} invoice${subInvoices.length === 1 ? "" : "s"} for this subscription.`} />
          <div className="mer-stack">
            {subInvoices.length === 0 ? (
              <p className="mer-empty">No invoices yet. The next billing cycle will create the first one.</p>
            ) : (
              subInvoices.map((inv) => (
                <Link key={inv.id} to={`/invoices/${inv.id}`} className="mer-overview-row">
                  <span className="mer-overview-row__icon" aria-hidden="true">
                    <BadgeDollarSign size={14} />
                  </span>
                  <div className="mer-entity-cell">
                    <strong>{inv.number}</strong>
                    <small>{inv.issuedAt} · due {inv.dueAt}</small>
                  </div>
                  <Badge tone={invoiceTone(inv.status)}>{prettyStatus(inv.status)}</Badge>
                  <span className="mer-overview-row__metric">
                    <strong>{formatCurrency(inv.amountDue)}</strong>
                    <small>{inv.amountPaid > 0 ? `${formatCurrency(inv.amountPaid)} paid` : "unpaid"}</small>
                  </span>
                </Link>
              ))
            )}
          </div>
        </Card>
      ) : null}

      {tab === "events" ? (
        <Card>
          <CardHeader title="Events" description="System and team activity for this subscription." />
          <div className="mer-timeline">
            {eventsLoading ? <p className="mer-empty">Loading events...</p> : null}
            {eventsError ? <p className="mer-empty">{eventsError}</p> : null}
            {!eventsLoading && !eventsError && events.length === 0 ? (
              <p className="mer-empty">No backend events have been recorded for this subscription yet.</p>
            ) : null}
            {!eventsLoading && !eventsError ? events.map((event) => (
              <TimelineRow
                key={event.id}
                when={event.occurredAt}
                label={event.eventType}
                detail={`${event.detail}${event.actor ? ` · ${event.actor}` : ""}`}
                tone={event.eventType.toLowerCase().includes("cancel") ? "danger" : "neutral"}
              />
            )) : null}
          </div>
        </Card>
      ) : null}

      {tab === "notes" ? (
        <Card>
          <CardHeader title="Internal notes" description="Visible to your team only — never shown to customers." />
          <div className="mer-stack">
            {sub.notes ? <p className="mer-muted" style={{ fontSize: 13 }}>“{sub.notes}”</p> : null}
            {canEditNotes ? (
              <>
                <Field label="Add a note">
                  <TextInput placeholder="Type a note…" value={notes} onChange={(e) => setNotes(e.target.value)} />
                </Field>
                <div style={{ display: "flex", justifyContent: "flex-end" }}>
                  <Button onClick={saveNote} disabled={savingNote}>
                    {savingNote ? "Saving..." : "Save note"}
                  </Button>
                </div>
              </>
            ) : null}
          </div>
        </Card>
      ) : null}

      {/* Change plan */}
      <Sheet
        open={changePlanOpen}
        title="Change plan"
        description="Switch this subscription to a different plan. Prorate is automatic on the next renewal."
        onClose={() => setChangePlanOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setChangePlanOpen(false)}>Cancel</Button>
              <Button onClick={submitChangePlan} disabled={savingChangePlan}>
                {savingChangePlan ? "Changing..." : "Change plan"}
              </Button>
          </>
        }
      >
        <div className="mer-stack">
          <Field label="Target plan">
            <SelectInput value={newPlanId} onChange={(e) => setNewPlanId(e.target.value)}>
              {plans.filter((p) => p.status === "active").map((p) => (
                <option key={p.id} value={p.id}>{p.name} — {formatCurrency(p.amount, p.currency)}/{p.interval}</option>
              ))}
            </SelectInput>
          </Field>
          {newPlanId === sub.planId ? (
            <p className="mer-hint">Select a different active plan to preview the billing impact.</p>
          ) : planPreviewLoading ? (
            <div className="mer-plan-preview" role="status" aria-live="polite">
              <strong>Previewing plan change...</strong>
              <small>Fetching backend proration details.</small>
            </div>
          ) : planPreviewError ? (
            <div className="mer-plan-preview mer-plan-preview--danger" role="alert">
              <strong>Preview unavailable</strong>
              <small>{planPreviewError}</small>
            </div>
          ) : planPreview ? (
            <div className="mer-plan-preview" aria-label="Plan change preview">
              <div>
                <span>Unused-time credit</span>
                <strong>{formatMinorCurrency(planPreview.prorationCreditMinor, planPreview.currency)}</strong>
              </div>
              <div>
                <span>New-plan charge</span>
                <strong>{formatMinorCurrency(planPreview.prorationChargeMinor, planPreview.currency)}</strong>
              </div>
              <div>
                <span>Net next-invoice impact</span>
                <strong>{formatMinorCurrency(planPreview.netMinor, planPreview.currency)}</strong>
              </div>
              <small>Effective {formatRelative(planPreview.effectiveAt)}. The backend stores these proration values on the subscription change.</small>
            </div>
          ) : null}
        </div>
      </Sheet>

      {/* Update method */}
      <Modal
        open={methodOpen}
        title="Update payment method"
        description="Pick an existing card on file or send a portal link to the customer."
        onClose={() => setMethodOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setMethodOpen(false)}>Close</Button>
            <Button onClick={() => void sendPortalLink()} disabled={sendingPortalLink}>
              {sendingPortalLink ? "Sending..." : "Send portal link"}
            </Button>
          </>
        }
      >
        <div className="mer-stack">
          {customer.paymentMethods.length === 0 ? (
            <p className="mer-empty">No payment methods on file. Send a portal link to collect one.</p>
          ) : (
            customer.paymentMethods.map((m) => (
              <div key={m.id} className="mer-overview-row mer-overview-row--compact">
                <span className="mer-overview-row__icon" aria-hidden="true"><CreditCard size={14} /></span>
                <div className="mer-entity-cell">
                  <strong>{m.brand} •••• {m.last4}</strong>
                  <small>Expires {m.expiry}{m.isDefault ? " · default" : ""}</small>
                </div>
                <Button
                  variant="ghost"
                  onClick={() => usePaymentMethod(m.id)}
                  disabled={savingMethodId === m.id}
                >
                  {savingMethodId === m.id ? "Updating..." : "Use this card"}
                </Button>
              </div>
            ))
          )}
        </div>
      </Modal>

      {/* Apply credit */}
      <Modal
        open={creditOpen}
        title="Apply credit"
        description="Adds a one-time credit to the next invoice for this subscription."
        onClose={() => setCreditOpen(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => setCreditOpen(false)}>Cancel</Button>
            <Button onClick={applyCredit} disabled={savingCredit}>
              {savingCredit ? "Applying..." : "Apply credit"}
            </Button>
          </>
        }
      >
        <div className="mer-stack">
          <Field label={`Amount in ${plan?.currency ?? "NGN"}`}>
            <TextInput type="number" inputMode="numeric" value={creditAmount} onChange={(e) => setCreditAmount(e.target.value)} />
          </Field>
        </div>
      </Modal>
    </>
  );
}

function TimelineRow({
  when,
  label,
  detail,
  tone = "default"
}: {
  when: string;
  label: string;
  detail: string;
  tone?: "default" | "danger" | "warning" | "neutral";
}) {
  return (
    <div className="mer-timeline__row">
      <span
        className={`mer-timeline__dot${
          tone === "danger" ? " mer-timeline__dot--danger" : tone === "warning" ? " mer-timeline__dot--warning" : tone === "neutral" ? " mer-timeline__dot--neutral" : ""
        }`}
        aria-hidden="true"
      />
      <div>
        <strong>{label}</strong>
        <small>{detail}</small>
      </div>
      <time>{formatRelative(when)}</time>
    </div>
  );
}

function subTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
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

function invoiceTone(status: string): "success" | "warning" | "danger" | "info" | "neutral" {
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

function formatMinorCurrency(amountMinor: number, currency: "NGN" | "USD" | "GBP" | "KES") {
  return new Intl.NumberFormat("en-NG", {
    style: "currency",
    currency,
    maximumFractionDigits: 0
  }).format(amountMinor / 100);
}

function prettyStatus(status: string): string {
  return status
    .split("_")
    .map((p) => p.charAt(0).toUpperCase() + p.slice(1))
    .join(" ");
}
