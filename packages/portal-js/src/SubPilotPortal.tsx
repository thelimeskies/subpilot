import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import {
  createSubPilotPortalClient,
  formatCurrency,
  prettyStatus,
  type PortalChangePreview,
  type PortalData,
  type PortalInvoice,
  type PortalPlan,
  type SubPilotPortalOptions
} from "./portal-client";

export interface SubPilotPortalProps extends SubPilotPortalOptions {
  token: string;
  className?: string;
  closeLabel?: string;
  closeOnOverlayClick?: boolean;
  displayMode?: "inline" | "modal";
  modalTitle?: string;
  open?: boolean;
  onError?: (error: Error) => void;
  onClose?: () => void;
  onLoaded?: (data: PortalData) => void;
  showCloseButton?: boolean;
}

export function SubPilotPortal({
  token,
  publishableKey,
  apiBaseUrl,
  className,
  closeLabel = "Close",
  closeOnOverlayClick = true,
  displayMode = "inline",
  modalTitle = "Customer billing portal",
  open = true,
  onClose,
  onError,
  onLoaded,
  showCloseButton
}: SubPilotPortalProps) {
  const client = useMemo(() => createSubPilotPortalClient({ publishableKey, apiBaseUrl }), [apiBaseUrl, publishableKey]);
  const [data, setData] = useState<PortalData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [checkoutTargetId, setCheckoutTargetId] = useState<string | null>(null);
  const [settingDefaultId, setSettingDefaultId] = useState<string | null>(null);
  const [payingInvoiceId, setPayingInvoiceId] = useState<string | null>(null);
  const [canceling, setCanceling] = useState(false);
  // Plan-change modal state
  const [planModalOpen, setPlanModalOpen] = useState(false);
  const [plans, setPlans] = useState<PortalPlan[] | null>(null);
  const [plansLoading, setPlansLoading] = useState(false);
  const [selectedPlanId, setSelectedPlanId] = useState<string | null>(null);
  const [planPreview, setPlanPreview] = useState<PortalChangePreview | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [changingPlan, setChangingPlan] = useState(false);

  const load = useCallback(async () => {
    if (!token) {
      setError("This portal link is missing its secure token.");
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const next = await client.loadPortal(token);
      setData(next);
      onLoaded?.(next);
    } catch (err) {
      const error = err instanceof Error ? err : new Error("Could not open this portal link.");
      setError(error.message);
      onError?.(error);
    } finally {
      setLoading(false);
    }
  }, [client, onError, onLoaded, token]);

  useEffect(() => {
    void load();
  }, [load]);

  const customer = data?.customer;
  const merchant = data?.merchant;
  const activeSubscription = data?.subscriptions.find((sub) => sub.status === "active" || sub.status === "trialing") ?? data?.subscriptions[0] ?? null;
  const openInvoices = useMemo(
    () => (data?.invoices ?? []).filter((invoice) => invoice.status === "open" || invoice.status === "past_due"),
    [data?.invoices]
  );
  const payableInvoices = useMemo(
    () => openInvoices.filter((invoice) => invoice.amountDue - invoice.amountPaid > 0),
    [openInvoices]
  );
  const paidInvoices = useMemo(
    () => (data?.invoices ?? []).filter((invoice) => invoice.status === "paid").slice(0, 8),
    [data?.invoices]
  );
  const defaultMethod =
    data?.paymentMethods.find((method) => method.id === customer?.defaultMethodId) ??
    data?.paymentMethods[0] ??
    null;
  const orderedMethods = useMemo(() => {
    const all = data?.paymentMethods ?? [];
    if (!defaultMethod) return all;
    return [defaultMethod, ...all.filter((m) => m.id !== defaultMethod.id)];
  }, [data?.paymentMethods, defaultMethod]);
  const canPay = data?.allowedActions.includes("pay_invoice") ?? false;
  const canUpdateCard = data?.allowedActions.includes("update_payment_method") ?? false;
  const canStartPaymentMethodCheckout = canUpdateCard && payableInvoices.length > 0;
  const paymentMethodCheckoutInvoice = payableInvoices[0] ?? null;
  const paymentMethodCheckoutTargetId = paymentMethodCheckoutInvoice?.id ?? "payment-method";
  const canCancel = Boolean(data?.allowedActions.includes("cancel_subscription") && merchant?.allowCancel);
  const canChangePlan = Boolean(
    data?.allowedActions.includes("change_plan") &&
      merchant?.allowChangePlan &&
      activeSubscription &&
      ["active", "trialing", "past_due"].includes(activeSubscription.status)
  );
  const canSubscribe = Boolean(
    data?.allowedActions.includes("subscribe") &&
      merchant?.allowSubscribe &&
      !activeSubscription
  );
  const planModalMode: "change" | "subscribe" = activeSubscription ? "change" : "subscribe";
  const brandColor = merchant?.brandColor ?? "#056058";
  const shouldShowClose = showCloseButton ?? (displayMode === "modal" || Boolean(onClose));

  if (!open) {
    return null;
  }

  function renderPortal(content: ReactNode) {
    const app = (
      <main
        className={`sp-portal-app ${displayMode === "modal" ? "sp-portal-app--modal" : ""} ${className ?? ""}`}
        style={{ "--portal-brand": brandColor } as React.CSSProperties}
      >
        {shouldShowClose ? (
          <div className="sp-portal-closebar">
            <button className="sp-portal-button sp-portal-button--ghost" type="button" onClick={onClose}>
              {closeLabel}
            </button>
          </div>
        ) : null}
        {content}
      </main>
    );

    if (displayMode !== "modal") {
      return app;
    }

    return (
      <div
        className="sp-portal-host-modal"
        onMouseDown={(event) => {
          if (closeOnOverlayClick && event.target === event.currentTarget) onClose?.();
        }}
      >
        <section className="sp-portal-host-panel" role="dialog" aria-modal="true" aria-label={modalTitle}>
          {app}
        </section>
      </div>
    );
  }

  async function handlePaymentMethodCheckout(invoiceId?: string) {
    const targetId = invoiceId ?? "payment-method";
    if (checkoutTargetId) return;
    setCheckoutTargetId(targetId);
    setError(null);
    try {
      const checkout = await client.createPaymentMethodCheckout(token, invoiceId);
      if (!checkout.checkoutUrl) {
        throw new Error("Nomba did not return a checkout URL.");
      }
      window.sessionStorage?.setItem("subpilot:lastPortalToken", token);
      window.sessionStorage?.setItem("subpilot:lastNombaCheckoutInvoiceId", checkout.invoiceId);
      window.location.assign(checkout.checkoutUrl);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not open Nomba checkout.");
      setCheckoutTargetId(null);
    } finally {
      setCheckoutTargetId(null);
    }
  }

  async function handleSetDefault(methodId: string) {
    if (settingDefaultId) return;
    setSettingDefaultId(methodId);
    setError(null);
    try {
      await client.setDefaultPaymentMethod(token, methodId);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not set this card as default.");
    } finally {
      setSettingDefaultId(null);
    }
  }

  async function handlePayInvoice(invoice: PortalInvoice) {
    if (!defaultMethod && canUpdateCard) {
      await handlePaymentMethodCheckout(invoice.id);
      return;
    }
    setPayingInvoiceId(invoice.id);
    setError(null);
    try {
      await client.payInvoice(token, invoice.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not pay this invoice.");
    } finally {
      setPayingInvoiceId(null);
    }
  }

  async function handleCancelSubscription() {
    if (!activeSubscription) return;
    setCanceling(true);
    setError(null);
    try {
      await client.cancelSubscription(token, activeSubscription.id);
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not cancel this subscription.");
    } finally {
      setCanceling(false);
    }
  }

  async function openPlanModal() {
    setPlanModalOpen(true);
    setPlanPreview(null);
    setSelectedPlanId(null);
    if (plans !== null) return;
    setPlansLoading(true);
    setError(null);
    try {
      const result = await client.listPlans(token);
      setPlans(result.plans);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load available plans.");
      setPlanModalOpen(false);
    } finally {
      setPlansLoading(false);
    }
  }

  async function handleSelectPlan(plan: PortalPlan) {
    if (plan.id === activeSubscription?.planId) return;
    setSelectedPlanId(plan.id);
    setPlanPreview(null);
    if (!activeSubscription) {
      // Subscribe mode: no proration to preview, customer just confirms.
      return;
    }
    setPreviewLoading(true);
    setError(null);
    try {
      const preview = await client.previewChangePlan(token, activeSubscription.id, plan.id);
      setPlanPreview(preview);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not preview this plan change.");
      setSelectedPlanId(null);
    } finally {
      setPreviewLoading(false);
    }
  }

  async function handleConfirmChangePlan() {
    if (!selectedPlanId) return;
    setChangingPlan(true);
    setError(null);
    try {
      if (activeSubscription) {
        await client.changePlan(token, activeSubscription.id, selectedPlanId);
      } else {
        await client.subscribe(token, selectedPlanId);
      }
      setPlanModalOpen(false);
      setPlans(null); // force re-fetch on next open (current plan changed)
      setSelectedPlanId(null);
      setPlanPreview(null);
      await load();
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : activeSubscription
          ? "Could not change this plan."
          : "Could not subscribe to this plan."
      );
    } finally {
      setChangingPlan(false);
    }
  }

  function downloadInvoice(invoice: PortalInvoice) {
    const lines = [
      merchant?.name ?? "Merchant",
      invoice.number,
      `Amount: ${formatCurrency(invoice.amountDue, invoice.currency)}`,
      `Status: ${invoice.status}`,
      `Due: ${invoice.dueAt}`
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${invoice.number}.txt`;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  }

  if (loading) {
    return renderPortal(
        <section className="sp-portal-status" role="status">
          <span className="sp-portal-spinner" aria-hidden="true" />
          <strong>Opening secure billing portal...</strong>
        </section>
    );
  }

  if (!data || !customer || !merchant) {
    return renderPortal(
        <section className="sp-portal-status" role="alert">
          <strong>Portal unavailable</strong>
          <p>{error ?? "This secure billing link is no longer available."}</p>
          <button className="sp-portal-button sp-portal-button--secondary" type="button" onClick={() => void load()}>
            Retry
          </button>
        </section>
    );
  }

  return renderPortal(
    <>
      <header className="sp-portal-topbar">
        <div className="sp-portal-brand">
          <span className="sp-portal-brand__mark" aria-hidden="true">
            {merchant.logoUrl ? <img src={merchant.logoUrl} alt="" /> : merchant.name.charAt(0)}
          </span>
          <div>
            <strong>{merchant.name}</strong>
            <small>Secure billing portal</small>
          </div>
        </div>
        <div className="sp-portal-secure">
          <span aria-hidden="true">Lock</span>
          <span>{customer.email}</span>
        </div>
      </header>

      {error ? <section className="sp-portal-alert" role="alert">{error}</section> : null}

      <section className="sp-portal-hero">
        <div>
          <span className="sp-portal-eyebrow">Tokenized payments</span>
          <h1>{activeSubscription?.planName ?? "Billing portal"}</h1>
          <p>
            {activeSubscription
              ? `${formatCurrency(activeSubscription.amount, activeSubscription.currency)} per ${activeSubscription.interval.replace("ly", "")}. Next billing ${activeSubscription.currentPeriodEnd}.`
              : "Manage invoices and payment methods for your account."}
          </p>
        </div>
        {activeSubscription ? (
          <span className={`sp-portal-badge sp-portal-badge--${badgeTone(activeSubscription.status)}`}>{prettyStatus(activeSubscription.status)}</span>
        ) : null}
      </section>

      <div className="sp-portal-grid">
        <section className="sp-portal-panel sp-portal-panel--wide">
          <PanelHead title="Open invoices" description={openInvoices.length ? "Pay due invoices securely." : "No outstanding balance."} />
          {openInvoices.length ? (
            <div className="sp-portal-invoices">
              {openInvoices.map((invoice) => (
                <article key={invoice.id} className="sp-portal-invoice">
                  <div>
                    <strong>{invoice.number}</strong>
                    <small>Due {invoice.dueAt}</small>
                  </div>
                  <span>{formatCurrency(invoice.amountDue - invoice.amountPaid, invoice.currency)}</span>
                  <span className={`sp-portal-badge sp-portal-badge--${badgeTone(invoice.status)}`}>{prettyStatus(invoice.status)}</span>
                  {canPay ? (
                    <button
                      className="sp-portal-button"
                      type="button"
                      onClick={() => void handlePayInvoice(invoice)}
                      disabled={payingInvoiceId === invoice.id || checkoutTargetId === invoice.id}
                    >
                      {payingInvoiceId === invoice.id || checkoutTargetId === invoice.id ? "Opening..." : "Pay"}
                    </button>
                  ) : null}
                </article>
              ))}
            </div>
          ) : (
            <p className="sp-portal-empty">You are all caught up.</p>
          )}
        </section>

        <section className="sp-portal-panel">
          <PanelHead title="Payment method" description="Cards are stored as token references." />
          {orderedMethods.length > 0 ? (
            <div className="sp-portal-methods">
              {orderedMethods.map((method) => {
                const isDefault = method.id === (defaultMethod?.id ?? "");
                const isBusy = settingDefaultId === method.id;
                return (
                  <div key={method.id} className="sp-portal-method">
                    <div className="sp-portal-method__info">
                      <span>{method.brand}</span>
                      <strong>•••• {method.last4}</strong>
                      <small>Expires {method.expiry}</small>
                    </div>
                    <div className="sp-portal-method__actions">
                      {isDefault ? (
                        <span className="sp-portal-method__badge">Default</span>
                      ) : canUpdateCard ? (
                        <button
                          className="sp-portal-button sp-portal-button--secondary"
                          type="button"
                          onClick={() => void handleSetDefault(method.id)}
                          disabled={Boolean(settingDefaultId)}
                        >
                          {isBusy ? "Saving..." : "Make default"}
                        </button>
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <p className="sp-portal-empty">No payment methods on file.</p>
          )}
          {canStartPaymentMethodCheckout ? (
            <button
              className="sp-portal-button sp-portal-button--secondary"
              type="button"
              onClick={() => void handlePaymentMethodCheckout(paymentMethodCheckoutInvoice?.id)}
              disabled={checkoutTargetId === paymentMethodCheckoutTargetId}
            >
              {checkoutTargetId === paymentMethodCheckoutTargetId ? "Opening..." : "Open Nomba checkout"}
            </button>
          ) : canUpdateCard && orderedMethods.length === 0 ? (
            <p className="sp-portal-empty">No invoice is due right now.</p>
          ) : null}
        </section>

        <section className="sp-portal-panel">
          <PanelHead title="Subscription" description="Current access and cancellation controls." />
          {activeSubscription ? (
            <>
              <Detail label="Plan" value={activeSubscription.planName} />
              <Detail label="Renews" value={activeSubscription.currentPeriodEnd} />
              <Detail label="Status" value={prettyStatus(activeSubscription.status)} />
              {(canChangePlan || (canCancel && activeSubscription.status !== "cancelled" && !activeSubscription.cancelAt)) ? (
                <div className="sp-portal-panel__actions">
                  {canChangePlan ? (
                    <button
                      className="sp-portal-button sp-portal-button--secondary"
                      type="button"
                      onClick={() => void openPlanModal()}
                      disabled={plansLoading}
                    >
                      {plansLoading ? "Loading plans..." : "Change plan"}
                    </button>
                  ) : null}
                  {canCancel && activeSubscription.status !== "cancelled" && !activeSubscription.cancelAt ? (
                    <button
                      className="sp-portal-button sp-portal-button--danger"
                      type="button"
                      onClick={() => void handleCancelSubscription()}
                      disabled={canceling}
                    >
                      {canceling ? "Cancelling..." : "Cancel subscription"}
                    </button>
                  ) : null}
                </div>
              ) : null}
            </>
          ) : canSubscribe ? (
            <>
              <p className="sp-portal-empty">
                You don’t have an active subscription yet. Pick a plan to get started.
              </p>
              <div className="sp-portal-panel__actions">
                <button
                  className="sp-portal-button"
                  type="button"
                  onClick={() => void openPlanModal()}
                  disabled={plansLoading}
                >
                  {plansLoading ? "Loading plans..." : "Choose a plan"}
                </button>
              </div>
            </>
          ) : (
            <p className="sp-portal-empty">No active subscription.</p>
          )}
        </section>

        <section className="sp-portal-panel sp-portal-panel--wide">
          <PanelHead title="Payment history" description="Recent paid invoices." />
          {paidInvoices.length ? (
            <ul className="sp-portal-history">
              {paidInvoices.map((invoice) => (
                <li key={invoice.id}>
                  <div>
                    <strong>{invoice.number}</strong>
                    <small>{invoice.paidAt ? `Paid ${invoice.paidAt.slice(0, 10)}` : invoice.issuedAt}</small>
                  </div>
                  <span>{formatCurrency(invoice.amountPaid, invoice.currency)}</span>
                  <button className="sp-portal-button sp-portal-button--ghost" type="button" onClick={() => downloadInvoice(invoice)}>
                    Receipt
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="sp-portal-empty">No completed payments yet.</p>
          )}
        </section>
      </div>

      {planModalOpen ? (
        <div className="sp-portal-modal" role="dialog" aria-modal="true" aria-labelledby="sp-portal-plan-title">
          <div className="sp-portal-modal__panel sp-portal-modal__panel--wide">
            <div className="sp-portal-modal__head">
              <div>
                <h2 id="sp-portal-plan-title">
                  {planModalMode === "subscribe" ? "Choose a plan" : "Change plan"}
                </h2>
                <p>
                  {planModalMode === "subscribe"
                    ? "Pick a plan to start your subscription."
                    : "Pick a new plan. We will show the proration before you confirm."}
                </p>
              </div>
              <button
                className="sp-portal-button sp-portal-button--ghost"
                type="button"
                onClick={() => {
                  setPlanModalOpen(false);
                  setSelectedPlanId(null);
                  setPlanPreview(null);
                }}
                disabled={changingPlan}
              >
                Close
              </button>
            </div>

            {plansLoading ? (
              <div className="sp-portal-status" role="status">
                <span className="sp-portal-spinner" aria-hidden="true" />
                <small>Loading available plans...</small>
              </div>
            ) : plans && plans.length > 0 ? (
              <div className="sp-portal-plans">
                {plans.map((plan) => {
                  const isCurrent = activeSubscription?.planId === plan.id;
                  const isSelected = selectedPlanId === plan.id;
                  return (
                    <button
                      key={plan.id}
                      type="button"
                      className={`sp-portal-plan-card${isCurrent ? " sp-portal-plan-card--current" : ""}${isSelected ? " sp-portal-plan-card--selected" : ""}`}
                      onClick={() => void handleSelectPlan(plan)}
                      disabled={isCurrent || previewLoading || changingPlan}
                    >
                      <div className="sp-portal-plan-card__head">
                        <div>
                          <strong>{plan.name}</strong>
                          <small>{plan.productName}</small>
                        </div>
                        {isCurrent ? (
                          <span className="sp-portal-badge sp-portal-badge--success">Current</span>
                        ) : isSelected ? (
                          <span className="sp-portal-badge sp-portal-badge--success">Selected</span>
                        ) : null}
                      </div>
                      <div className="sp-portal-plan-card__price">
                        <strong>{formatCurrency(plan.amount, plan.currency)}</strong>
                        <small>/ {plan.intervalUnit.replace("ly", "")}</small>
                      </div>
                      {plan.features && plan.features.length > 0 ? (
                        <ul className="sp-portal-plan-card__features">
                          {plan.features.slice(0, 4).map((feature) => (
                            <li key={feature.label}>{feature.label}</li>
                          ))}
                        </ul>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            ) : (
              <p className="sp-portal-empty">No alternative plans are available right now.</p>
            )}

            {previewLoading ? (
              <div className="sp-portal-preview sp-portal-preview--loading">
                <span className="sp-portal-spinner" aria-hidden="true" />
                <small>Calculating proration...</small>
              </div>
            ) : planPreview ? (
              <div className="sp-portal-preview">
                <strong>Change summary</strong>
                <div className="sp-portal-preview__row">
                  <span>Unused credit</span>
                  <strong>{formatCurrency(planPreview.prorationCredit, planPreview.currency)}</strong>
                </div>
                <div className="sp-portal-preview__row">
                  <span>New plan charge</span>
                  <strong>{formatCurrency(planPreview.prorationCharge, planPreview.currency)}</strong>
                </div>
                <div className="sp-portal-preview__row sp-portal-preview__row--total">
                  <span>Net due today</span>
                  <strong>{formatCurrency(planPreview.net, planPreview.currency)}</strong>
                </div>
                <small>Effective {planPreview.effectiveAt.slice(0, 10)}.</small>
              </div>
            ) : null}

            <div className="sp-portal-modal__foot">
              <button
                className="sp-portal-button sp-portal-button--ghost"
                type="button"
                onClick={() => {
                  setPlanModalOpen(false);
                  setSelectedPlanId(null);
                  setPlanPreview(null);
                }}
                disabled={changingPlan}
              >
                Cancel
              </button>
              <button
                className="sp-portal-button"
                type="button"
                onClick={() => void handleConfirmChangePlan()}
                disabled={
                  !selectedPlanId ||
                  previewLoading ||
                  changingPlan ||
                  (planModalMode === "change" && !planPreview)
                }
              >
                {changingPlan
                  ? planModalMode === "subscribe"
                    ? "Subscribing..."
                    : "Applying..."
                  : planModalMode === "subscribe"
                  ? "Subscribe"
                  : "Confirm change"}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}

function PanelHead({ title, description }: { title: string; description: string }) {
  return (
    <div className="sp-portal-panel__head">
      <div>
        <strong>{title}</strong>
        <small>{description}</small>
      </div>
    </div>
  );
}

function Detail({ label, value }: { label: string; value: string }) {
  return (
    <div className="sp-portal-detail">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function badgeTone(status: string): "success" | "warning" | "danger" | "neutral" {
  if (status === "active" || status === "trialing" || status === "paid") return "success";
  if (status === "open" || status === "past_due") return "warning";
  if (status === "cancelled" || status === "incomplete" || status === "void" || status === "uncollectible") return "danger";
  return "neutral";
}
