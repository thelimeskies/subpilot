import { Route, Routes, useParams, useSearchParams } from "react-router-dom";
import { SubPilotPortal } from "@subpilot/portal-js";

const publishableKey = import.meta.env.VITE_SUBPILOT_PUBLISHABLE_KEY ?? "pk_test_local";
const apiBaseUrl = import.meta.env.VITE_API_BASE ?? "/api/v1";

export function CustomerPortalApp() {
  return (
    <Routes>
      <Route path="/session/:token" element={<CustomerPortalScreen />} />
      <Route path="/portal/:token" element={<CustomerPortalScreen />} />
      <Route path="*" element={<CustomerPortalScreen />} />
    </Routes>
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
