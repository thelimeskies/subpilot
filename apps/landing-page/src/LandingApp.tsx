import { Routes, Route, useLocation } from "react-router-dom";
import { useEffect, lazy, Suspense } from "react";
import { Nav } from "./sections/Nav";
import { Footer } from "./sections/Footer";
import { HomePage } from "./pages/HomePage";
import { PlansPage } from "./pages/PlansPage";
import { LifecyclePage } from "./pages/LifecyclePage";
import { RecoveryPage } from "./pages/RecoveryPage";
import { PortalPage } from "./pages/PortalPage";
import { DevelopersPage } from "./pages/DevelopersPage";
import { CustomerApiPage } from "./pages/CustomerApiPage";
import { WebhooksPage } from "./pages/WebhooksPage";
import { IdempotencyPage } from "./pages/IdempotencyPage";
import { AboutPage } from "./pages/AboutPage";
import { PricingPage } from "./pages/PricingPage";
import { SecurityPage } from "./pages/SecurityPage";
import { ContactPage } from "./pages/ContactPage";
import { NotFoundPage } from "./pages/NotFoundPage";

// Redoc is heavy; load it only when the API reference page is visited.
const ApiReferencePage = lazy(() =>
  import("./pages/ApiReferencePage").then((m) => ({ default: m.ApiReferencePage }))
);

function ScrollToTop() {
  const { pathname, hash } = useLocation();
  useEffect(() => {
    if (hash) return;
    window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
  }, [pathname, hash]);
  return null;
}

export function LandingApp() {
  return (
    <div className="lp-root">
      <ScrollToTop />
      <Nav />
      <main>
        <Routes>
          <Route path="/" element={<HomePage />} />
          <Route path="/plans" element={<PlansPage />} />
          <Route path="/lifecycle" element={<LifecyclePage />} />
          <Route path="/recovery" element={<RecoveryPage />} />
          <Route path="/portal" element={<PortalPage />} />
          <Route path="/developers" element={<DevelopersPage />} />
          <Route path="/developers/customers" element={<CustomerApiPage />} />
          <Route
            path="/developers/api"
            element={
              <Suspense
                fallback={
                  <div className="lp-redoc__loading" role="status" aria-live="polite">
                    Loading API reference…
                  </div>
                }
              >
                <ApiReferencePage />
              </Suspense>
            }
          />
          <Route path="/developers/webhooks" element={<WebhooksPage />} />
          <Route path="/developers/idempotency" element={<IdempotencyPage />} />
          <Route path="/about" element={<AboutPage />} />
          <Route path="/pricing" element={<PricingPage />} />
          <Route path="/security" element={<SecurityPage />} />
          <Route path="/contact" element={<ContactPage />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
