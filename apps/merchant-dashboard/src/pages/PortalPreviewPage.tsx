import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Badge,
  Button,
  Card,
  CardHeader,
  Field,
  Modal,
  SegmentedControl,
  SelectInput,
  TextInput,
  type BadgeTone
} from "@subpilot/ui";
import {
  CreditCard,
  Download,
  ExternalLink,
  Eye,
  Lock,
  Sparkles,
  XCircle
} from "lucide-react";
import { PageHeader } from "../components/PageHeader";
import { useFeedback } from "../feedback/ActionFeedback";
import { createPortalSession } from "../api/billing";
import { isApiError } from "../api/client";
import {
  attachPortalPaymentMethod,
  cancelPortalSubscription,
  downloadPortalInvoicePdf,
  loadPortalPreview,
  payPortalInvoice,
  type PortalPreviewData,
  type PortalSubscription
} from "../api/portal";
import { useData } from "../data/store";
import {
  findSubscriptionsByCustomer,
  formatCurrency,
  formatRelative
} from "../data/selectors";
import type { Customer, Invoice, PaymentMethod } from "../data/seed";

interface UpdateCardState {
  brand: PaymentMethod["brand"];
  number: string;
  expiry: string;
  cvc: string;
  name: string;
}

export function PortalPreviewPage() {
  const { org, customers, subscriptions, resourcesLoading, logAuditEvent } = useData();
  const { notify, confirm } = useFeedback();

  const eligible = useMemo(
    () =>
      customers.filter(
        (c) =>
          c.status !== "blocked" &&
          findSubscriptionsByCustomer(subscriptions, c.id).length > 0
      ),
    [customers, subscriptions]
  );

  const [customerId, setCustomerId] = useState<string>(() => eligible[0]?.id ?? customers[0]?.id ?? "");
  const [device, setDevice] = useState<"desktop" | "mobile">("desktop");
  const [updateOpen, setUpdateOpen] = useState<UpdateCardState | null>(null);
  const [portalToken, setPortalToken] = useState<string | null>(null);
  const [portalLink, setPortalLink] = useState<string | null>(null);
  const [portalData, setPortalData] = useState<PortalPreviewData | null>(null);
  const [portalLoading, setPortalLoading] = useState(false);
  const [portalError, setPortalError] = useState<string | null>(null);
  const [savingCard, setSavingCard] = useState(false);
  const [canceling, setCanceling] = useState(false);
  const [payingInvoiceId, setPayingInvoiceId] = useState<string | null>(null);
  const [downloadingInvoiceId, setDownloadingInvoiceId] = useState<string | null>(null);

  const fallbackCustomer: Customer | undefined = customers.find((c) => c.id === customerId);
  const customer: Customer | undefined = portalData?.customer ?? fallbackCustomer;
  const customerSubs: PortalSubscription[] = portalData?.subscriptions ?? [];
  const customerInvoices: Invoice[] = portalData?.invoices ?? [];
  const activeSub = customerSubs.find((s) => s.status === "active") ?? customerSubs[0] ?? null;
  const activePlan = activeSub
    ? {
        name: activeSub.planName,
        amount: activeSub.amount,
        currency: activeSub.currency,
        interval: activeSub.interval
      }
    : null;
  const upcoming = customerInvoices.find((inv) => inv.status === "open" || inv.status === "past_due");
  const paidHistory = customerInvoices
    .filter((inv) => inv.status === "paid")
    .slice(0, 5);
  const defaultMethod =
    portalData?.paymentMethods.find((pm) => pm.id === customer?.defaultMethodId) ??
    portalData?.paymentMethods[0] ??
    customer?.paymentMethods.find((pm) => pm.id === customer.defaultMethodId) ??
    customer?.paymentMethods[0] ??
    null;
  const canPayInvoice = portalData?.allowedActions.includes("pay_invoice") ?? false;

  const refreshPortal = useCallback(
    async (token = portalToken) => {
      if (!token) return;
      const data = await loadPortalPreview(token);
      setPortalData(data);
    },
    [portalToken]
  );

  useEffect(() => {
    if (resourcesLoading || eligible.length === 0) return;
    if (!eligible.some((c) => c.id === customerId)) {
      setCustomerId(eligible[0].id);
    }
  }, [customerId, eligible, resourcesLoading]);

  useEffect(() => {
    if (resourcesLoading || !customerId || !eligible.some((c) => c.id === customerId)) return;
    let cancelled = false;
    setPortalLoading(true);
    setPortalError(null);
    setPortalData(null);
    setPortalToken(null);
    setPortalLink(null);

    (async () => {
      try {
        const session = await createPortalSession(customerId);
        const data = await loadPortalPreview(session.token);
        if (cancelled) return;
        setPortalToken(session.token);
        setPortalLink(session.url);
        setPortalData(data);
      } catch (err) {
        if (cancelled) return;
        setPortalError(isApiError(err) ? err.reason : "Could not load the customer portal preview.");
      } finally {
        if (!cancelled) setPortalLoading(false);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [customerId, eligible, resourcesLoading]);

  // ---------- Open in new tab ----------
  async function copyPortalLink() {
    if (!customer) return;
    let link = portalLink;
    if (!link) {
      try {
        const session = await createPortalSession(customer.id);
        setPortalToken(session.token);
        setPortalLink(session.url);
        link = session.url;
      } catch (err) {
        notify({
          tone: "danger",
          title: "Could not create portal link",
          description: isApiError(err) ? err.reason : "The backend rejected the request. Try again."
        });
        return;
      }
    }
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(link).catch(() => undefined);
    }
    logAuditEvent({ actor: "You", action: "Copied portal link", target: customer.email });
    notify({
      tone: "info",
      title: "Portal link copied",
      description: `${link} is now on your clipboard.`
    });
  }

  // ---------- Update card ----------
  function openUpdate() {
    setUpdateOpen({ brand: "Visa", number: "", expiry: "", cvc: "", name: customer?.name ?? "" });
  }
  function patchUpdate(patch: Partial<UpdateCardState>) {
    setUpdateOpen((prev) => (prev ? { ...prev, ...patch } : prev));
  }
  async function submitUpdate() {
    if (!customer || !updateOpen || !portalToken) return;
    const last4 = updateOpen.number.replace(/\s+/g, "").slice(-4);
    if (last4.length < 4 || !/^\d{2}\/\d{2}$/.test(updateOpen.expiry) || !updateOpen.cvc) {
      notify({
        tone: "warning",
        title: "Card details required",
        description: "Card number, expiry in MM/YY format, and CVC are required."
      });
      return;
    }
    setSavingCard(true);
    try {
      await attachPortalPaymentMethod(portalToken, customer.id, {
        brand: updateOpen.brand,
        last4,
        expiry: updateOpen.expiry
      });
      await refreshPortal(portalToken);
      logAuditEvent({
        actor: customer.name,
        action: "Updated payment method via portal",
        target: `${updateOpen.brand} ending ${last4}`
      });
      notify({
        tone: "success",
        title: "Card updated",
        description: `${updateOpen.brand} ending ${last4} is now the default payment method.`
      });
      setUpdateOpen(null);
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not update card",
        description: isApiError(err) ? err.reason : "The portal API rejected the request."
      });
    } finally {
      setSavingCard(false);
    }
  }

  // ---------- Cancel subscription ----------
  async function handleCancel() {
    if (!customer || !activeSub || !activePlan || !portalToken) return;
    const ok = await confirm({
      destructive: true,
      title: `Cancel ${activePlan.name}?`,
      description: `Access ends on ${activeSub.currentPeriodEnd}. ${customer.name} will not be charged again.`,
      confirmLabel: "Cancel subscription"
    });
    if (!ok) return;
    setCanceling(true);
    try {
      await cancelPortalSubscription(portalToken, activeSub.id);
      await refreshPortal(portalToken);
      logAuditEvent({
        actor: customer.name,
        action: "Cancelled subscription via portal",
        target: `${activePlan.name} (${activeSub.id})`
      });
      notify({
        tone: "info",
        title: "Cancellation scheduled",
        description: `${customer.name} keeps access until ${activeSub.currentPeriodEnd}.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not cancel subscription",
        description: isApiError(err) ? err.reason : "The portal API rejected the request."
      });
    } finally {
      setCanceling(false);
    }
  }

  async function handlePayInvoice(invoice: Invoice) {
    if (!portalToken) return;
    setPayingInvoiceId(invoice.id);
    try {
      await payPortalInvoice(portalToken, invoice.id);
      await refreshPortal(portalToken);
      notify({
        tone: "success",
        title: "Invoice paid",
        description: `${invoice.number} was charged to the default payment method.`
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not pay invoice",
        description: isApiError(err) ? err.reason : "The portal API rejected the request."
      });
    } finally {
      setPayingInvoiceId(null);
    }
  }

  // ---------- Download invoice ----------
  async function downloadInvoice(invoice: Invoice) {
    if (!customer || !portalToken) return;
    setDownloadingInvoiceId(invoice.id);
    try {
      await downloadPortalInvoicePdf(portalToken, invoice.id, invoice.number);
      logAuditEvent({
        actor: customer.name,
        action: "Downloaded invoice from portal",
        target: invoice.number
      });
      notify({
        tone: "success",
        title: `${invoice.number} downloaded`,
        description: "PDF saved to the customer's device."
      });
    } catch (err) {
      notify({
        tone: "danger",
        title: "Could not download invoice",
        description: isApiError(err) ? err.reason : "The portal API rejected the request."
      });
    } finally {
      setDownloadingInvoiceId(null);
    }
  }

  if (!customer) {
    return (
      <>
        <PageHeader
          eyebrow="Customer-facing"
          title="Portal preview"
          description="See exactly what your customers see in the self-service portal."
        />
        <Card>
          <p className="mer-empty">No customers to preview yet — add one from the Customers page.</p>
        </Card>
      </>
    );
  }

  return (
    <>
      <PageHeader
        eyebrow="Customer-facing"
        title="Portal preview"
        description="See exactly what your customers see in the self-service portal."
        actions={
          <>
            <Button variant="ghost" icon={<Eye size={14} />} onClick={copyPortalLink}>
              Open in new tab
            </Button>
          </>
        }
      />

      <Card>
        <CardHeader
          title="Preview controls"
          description="Switch the customer or device frame to see live portal data from their perspective."
        />
        <div className="mer-filter-row">
          <Field label="Customer" hint="Only customers with an active subscription appear here.">
            <SelectInput value={customer.id} onChange={(e) => setCustomerId(e.target.value)}>
              {eligible.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name} — {c.email}
                </option>
              ))}
              {eligible.length === 0 ? (
                <option value={customer.id}>{customer.name} - {customer.email}</option>
              ) : null}
            </SelectInput>
          </Field>
          <Field label="Device frame">
            <SegmentedControl
              value={device}
              onChange={(v) => setDevice(v as "desktop" | "mobile")}
              label="Device frame"
              items={[
                { label: "Desktop", value: "desktop" },
                { label: "Mobile", value: "mobile" }
              ]}
            />
          </Field>
        </div>
      </Card>

      <div className={`mer-portal-frame mer-portal-frame--${device}`}>
        <div className="mer-portal-frame__chrome">
          <span className="mer-portal-frame__dot" />
          <span className="mer-portal-frame__dot" />
          <span className="mer-portal-frame__dot" />
          <span className="mer-portal-frame__url">
            <Lock size={12} aria-hidden="true" />
            portal.subpilot.dev/{org.portalSubdomain}/{customer.id}
          </span>
        </div>

        <div className="mer-portal-page">
          {portalLoading ? (
            <section className="mer-portal-card">
              <p className="mer-empty">Loading live portal session...</p>
            </section>
          ) : null}
          {portalError ? (
            <section className="mer-portal-card mer-portal-card--accent">
              <strong>Portal preview unavailable</strong>
              <p>{portalError}</p>
            </section>
          ) : null}

          {/* Portal header */}
          <header className="mer-portal-header">
            <div className="mer-portal-brand">
              <span
                className="mer-portal-brand__mark"
                style={{ background: org.brandColor }}
                aria-hidden="true"
              >
                {org.tradingName.charAt(0)}
              </span>
              <div>
                <strong>{org.tradingName}</strong>
                <small>Member portal</small>
              </div>
            </div>
            <div className="mer-portal-user">
              <strong>{customer.name}</strong>
              <small>{customer.email}</small>
            </div>
          </header>

          {/* Hero / current plan */}
          <section className="mer-portal-hero">
            <div>
              <span className="mer-portal-hero__eyebrow">
                <Sparkles size={12} aria-hidden="true" /> Your plan
              </span>
              <h2>{activePlan ? activePlan.name : "No active plan"}</h2>
              {activeSub && activePlan ? (
                <p>
                  {formatCurrency(activePlan.amount, activePlan.currency)} per {activePlan.interval.replace("ly", "")}{" · "}
                  {activeSub.cancelAt ? `Cancels on ${activeSub.cancelAt.slice(0, 10)}` : `Next billing on ${activeSub.currentPeriodEnd}`}
                </p>
              ) : (
                <p>You don't currently have an active subscription.</p>
              )}
            </div>
            {activeSub && activePlan ? (
              <Badge tone={subscriptionTone(activeSub.status)}>{prettyStatus(activeSub.status)}</Badge>
            ) : null}
          </section>

          {/* Next invoice */}
          {upcoming ? (
            <section className="mer-portal-card mer-portal-card--accent">
              <div>
                <strong>Upcoming invoice</strong>
                <p>
                  {upcoming.number} · {formatCurrency(upcoming.amountDue - upcoming.amountPaid, upcoming.currency)} due
                  on {upcoming.dueAt}
                </p>
              </div>
              <div className="sp-button-row">
                <Badge tone={upcoming.status === "past_due" ? "danger" : "warning"}>
                  {upcoming.status === "past_due" ? "Past due" : "Open"}
                </Badge>
                {canPayInvoice ? (
                  <Button
                    variant="secondary"
                    icon={<CreditCard size={14} />}
                    onClick={() => handlePayInvoice(upcoming)}
                    disabled={payingInvoiceId === upcoming.id}
                  >
                    {payingInvoiceId === upcoming.id ? "Paying..." : "Pay now"}
                  </Button>
                ) : null}
              </div>
            </section>
          ) : null}

          {/* Payment method */}
          <section className="mer-portal-card">
            <div className="mer-portal-card__head">
              <strong>Payment method</strong>
              <Button variant="ghost" icon={<CreditCard size={14} />} onClick={openUpdate}>
                Update card
              </Button>
            </div>
            {defaultMethod ? (
              <div className="mer-portal-method">
                <span className="mer-portal-method__brand">{defaultMethod.brand}</span>
                <span>•••• •••• •••• {defaultMethod.last4}</span>
                <small>Expires {defaultMethod.expiry}</small>
              </div>
            ) : (
              <p className="mer-empty">No card on file.</p>
            )}
          </section>

          {/* Invoice history */}
          <section className="mer-portal-card">
            <div className="mer-portal-card__head">
              <strong>Invoice history</strong>
              <small>Last {paidHistory.length} payments</small>
            </div>
            {paidHistory.length === 0 ? (
              <p className="mer-empty">No paid invoices yet.</p>
            ) : (
              <ul className="mer-portal-history">
                {paidHistory.map((invoice) => (
                  <li key={invoice.id}>
                    <div>
                      <strong>{invoice.number}</strong>
                      <small>
                        {invoice.paidAt ? `Paid ${formatRelative(invoice.paidAt)}` : invoice.issuedAt}
                      </small>
                    </div>
                    <span>{formatCurrency(invoice.amountPaid, invoice.currency)}</span>
                    <Button
                      variant="ghost"
                      icon={<Download size={14} />}
                      onClick={() => downloadInvoice(invoice)}
                      disabled={downloadingInvoiceId === invoice.id}
                    >
                      {downloadingInvoiceId === invoice.id ? "Downloading..." : "PDF"}
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </section>

          {/* Footer actions */}
          <footer className="mer-portal-footer">
            <Button variant="ghost" icon={<ExternalLink size={14} />} onClick={copyPortalLink}>
              Share portal link
            </Button>
            {activeSub && activePlan && activeSub.status !== "cancelled" && !activeSub.cancelAt ? (
              <Button variant="danger" icon={<XCircle size={14} />} onClick={handleCancel} disabled={canceling}>
                {canceling ? "Cancelling..." : "Cancel subscription"}
              </Button>
            ) : null}
          </footer>
        </div>
      </div>

      {/* Update card Modal */}
      <Modal
        open={!!updateOpen}
        onClose={() => setUpdateOpen(null)}
        title="Update payment card"
        description="Enter the new card details. The previous card will be replaced."
        footer={
          <>
            <Button variant="ghost" onClick={() => setUpdateOpen(null)}>Cancel</Button>
            <Button onClick={submitUpdate} icon={<CreditCard size={14} />} disabled={savingCard}>
              {savingCard ? "Saving..." : "Save card"}
            </Button>
          </>
        }
      >
        {updateOpen ? (
          <div className="sp-form-grid">
            <Field label="Cardholder name">
              <TextInput
                value={updateOpen.name}
                onChange={(e) => patchUpdate({ name: e.target.value })}
                placeholder="Name on card"
              />
            </Field>
            <Field label="Card brand">
              <SelectInput
                value={updateOpen.brand}
                onChange={(e) => patchUpdate({ brand: e.target.value as PaymentMethod["brand"] })}
              >
                <option value="Visa">Visa</option>
                <option value="Mastercard">Mastercard</option>
                <option value="Verve">Verve</option>
                <option value="Amex">Amex</option>
              </SelectInput>
            </Field>
            <Field label="Card number">
              <TextInput
                value={updateOpen.number}
                onChange={(e) => patchUpdate({ number: e.target.value })}
                placeholder="4242 4242 4242 4242"
                maxLength={19}
              />
            </Field>
            <div className="sp-grid sp-grid-2">
              <Field label="Expiry (MM/YY)">
                <TextInput
                  value={updateOpen.expiry}
                  onChange={(e) => patchUpdate({ expiry: e.target.value })}
                  placeholder="04/28"
                  maxLength={5}
                />
              </Field>
              <Field label="CVC">
                <TextInput
                  value={updateOpen.cvc}
                  onChange={(e) => patchUpdate({ cvc: e.target.value })}
                  placeholder="123"
                  maxLength={4}
                />
              </Field>
            </div>
            <p className="mer-hint">
              <Lock size={12} aria-hidden="true" /> Card details are tokenised before saving.
            </p>
          </div>
        ) : null}
      </Modal>
    </>
  );
}

function subscriptionTone(status: string): BadgeTone {
  switch (status) {
    case "active":
      return "success";
    case "trialing":
      return "info";
    case "past_due":
      return "warning";
    case "paused":
      return "neutral";
    case "cancelled":
    case "incomplete":
      return "danger";
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
