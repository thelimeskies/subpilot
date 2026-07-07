import { useEffect, useMemo, useState } from "react";
import { Route, Routes, useParams, useSearchParams } from "react-router-dom";
import { createSubPilotPortalClient, SubPilotPortal } from "@subpilot/portal-js";

const publishableKey = import.meta.env.VITE_SUBPILOT_PUBLISHABLE_KEY ?? "pk_test_local";
const apiBaseUrl = import.meta.env.VITE_API_BASE ?? "/api/v1";

export function CustomerPortalApp() {
  return (
    <Routes>
      <Route path="/payments/nomba/callback" element={<NombaCallbackScreen />} />
      <Route path="/session/:token" element={<CustomerPortalScreen />} />
      <Route path="/portal/:token" element={<CustomerPortalScreen />} />
      <Route path="*" element={<CustomerPortalScreen />} />
    </Routes>
  );
}

function NombaCallbackScreen() {
  const [params] = useSearchParams();
  const orderReference = params.get("orderReference") ?? "";
  const orderId = params.get("orderId") ?? "";
  const portalToken = window.sessionStorage?.getItem("subpilot:lastPortalToken") ?? "";
  const invoiceId = window.sessionStorage?.getItem("subpilot:lastNombaCheckoutInvoiceId") ?? "";
  const portalHref = portalToken ? `/session/${portalToken}` : "";
  const client = useMemo(
    () => createSubPilotPortalClient({ publishableKey, apiBaseUrl }),
    []
  );
  const [confirmState, setConfirmState] = useState<"checking" | "confirmed" | "pending" | "failed">(
    portalToken && (orderReference || orderId) ? "checking" : "pending"
  );
  const [confirmMessage, setConfirmMessage] = useState(
    portalToken
      ? "We are confirming this payment with Nomba."
      : "Return to the billing portal to refresh your billing status."
  );

  useEffect(() => {
    if (!portalToken || (!orderReference && !orderId)) return;
    let cancelled = false;
    let timeoutId: number | undefined;
    let attempt = 0;

    async function poll() {
      attempt += 1;
      try {
        const result = await client.confirmPaymentMethodCheckout(portalToken, {
          orderReference,
          orderId,
          invoiceId
        });
        if (cancelled) return;
        if (result.confirmed) {
          window.sessionStorage?.removeItem("subpilot:lastNombaCheckoutInvoiceId");
          setConfirmState("confirmed");
          setConfirmMessage(
            result.paymentMethodAttached
              ? "Payment confirmed. Your card has been saved for future billing."
              : "Payment confirmed. Your invoice status has been updated."
          );
          return;
        }
        setConfirmState("checking");
        setConfirmMessage("Nomba has not marked this payment complete yet. Checking again...");
      } catch (error) {
        if (cancelled) return;
        setConfirmState(attempt >= 8 ? "failed" : "checking");
        setConfirmMessage(
          error instanceof Error
            ? error.message
            : "Could not confirm this payment with Nomba yet."
        );
      }

      if (attempt < 8) {
        timeoutId = window.setTimeout(poll, 3000);
      } else if (!cancelled) {
        setConfirmState((current) => (current === "confirmed" ? current : "pending"));
        setConfirmMessage(
          "We could not confirm this automatically. Return to the billing portal and refresh in a moment."
        );
      }
    }

    void poll();
    return () => {
      cancelled = true;
      if (timeoutId !== undefined) window.clearTimeout(timeoutId);
    };
  }, [client, invoiceId, orderId, orderReference, portalToken]);

  const title =
    confirmState === "confirmed"
      ? "Payment confirmed"
      : confirmState === "failed"
        ? "Confirmation delayed"
        : "Payment submitted";

  return (
    <main className="sp-portal-app">
      <section className="sp-portal-status" role="status">
        <strong>{title}</strong>
        <p>{confirmMessage}</p>
        {orderReference || orderId ? (
          <p>
            Reference: <span>{orderReference || orderId}</span>
          </p>
        ) : null}
        {portalHref ? (
          <a className="sp-portal-button" href={portalHref}>
            Return to billing portal
          </a>
        ) : null}
      </section>
    </main>
  );
}

function CustomerPortalScreen() {
  const { token: tokenParam } = useParams();
  const [params] = useSearchParams();
  const token = tokenParam ?? params.get("token") ?? "";

  return (
    <SubPilotPortal
      token={token}
      publishableKey={publishableKey}
      apiBaseUrl={apiBaseUrl}
    />
  );
}
