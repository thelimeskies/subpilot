import { Route, Routes, useParams, useSearchParams } from "react-router-dom";
import { SubPilotPortal } from "@subpilot/portal-js";

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
  const portalHref = portalToken ? `/session/${portalToken}` : "";

  return (
    <main className="sp-portal-app">
      <section className="sp-portal-status" role="status">
        <strong>Payment submitted</strong>
        <p>
          We are confirming this payment with Nomba. Your billing status will update
          after the payment confirmation is received.
        </p>
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
