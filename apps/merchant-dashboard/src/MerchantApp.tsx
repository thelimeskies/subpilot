import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { AuthProvider } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { RequireOnboarded } from "./auth/RequireOnboarded";
import { PublicOnly } from "./auth/PublicOnly";
import { SignInPage } from "./auth/SignInPage";
import { SignUpPage } from "./auth/SignUpPage";
import { VerifyEmailPage } from "./auth/VerifyEmailPage";
import { ForgotPasswordPage } from "./auth/ForgotPasswordPage";
import { ResetPasswordPage } from "./auth/ResetPasswordPage";
import { MfaChallengePage } from "./auth/MfaChallengePage";
import { OnboardingShell } from "./onboarding/OnboardingShell";
import { ActionFeedbackProvider } from "./feedback/ActionFeedback";
import { DataProvider } from "./data/store";
import { FeatureFlagsProvider } from "./features/FeatureFlagsContext";
import { MerchantLayout } from "./layout/MerchantLayout";
import { OverviewPage } from "./pages/OverviewPage";
import { NotFoundPage } from "./pages/NotFoundPage";
import { ErrorBoundary } from "./components/ErrorBoundary";

// Auth + onboarding pages stay eager — small bundles, always on the critical
// path. Dashboard pages will be lazy-loaded as they ship in later milestones.
const PlansPage = lazy(() => import("./pages/PlansPage").then((m) => ({ default: m.PlansPage })));
const PlanDetailPage = lazy(() => import("./pages/PlanDetailPage").then((m) => ({ default: m.PlanDetailPage })));
const SubscriptionsPage = lazy(() => import("./pages/SubscriptionsPage").then((m) => ({ default: m.SubscriptionsPage })));
const SubscriptionDetailPage = lazy(() => import("./pages/SubscriptionDetailPage").then((m) => ({ default: m.SubscriptionDetailPage })));
const InvoicesPage = lazy(() => import("./pages/InvoicesPage").then((m) => ({ default: m.InvoicesPage })));
const InvoiceDetailPage = lazy(() => import("./pages/InvoiceDetailPage").then((m) => ({ default: m.InvoiceDetailPage })));
const PaymentsPage = lazy(() => import("./pages/PaymentsPage").then((m) => ({ default: m.PaymentsPage })));
const CustomersPage = lazy(() => import("./pages/CustomersPage").then((m) => ({ default: m.CustomersPage })));
const CustomerDetailPage = lazy(() => import("./pages/CustomerDetailPage").then((m) => ({ default: m.CustomerDetailPage })));
const RecoveryPage = lazy(() => import("./pages/RecoveryPage").then((m) => ({ default: m.RecoveryPage })));
const DevelopersPage = lazy(() => import("./pages/DevelopersPage").then((m) => ({ default: m.DevelopersPage })));
const TeamPage = lazy(() => import("./pages/TeamPage").then((m) => ({ default: m.TeamPage })));
const SettingsPage = lazy(() => import("./pages/SettingsPage").then((m) => ({ default: m.SettingsPage })));
const PortalPreviewPage = lazy(() => import("./pages/PortalPreviewPage").then((m) => ({ default: m.PortalPreviewPage })));

function PageFallback() {
  return (
    <div className="mer-boot" role="status" aria-live="polite">
      <span className="mer-boot__spinner" aria-hidden="true" />
      <span>Loading…</span>
    </div>
  );
}

export function MerchantApp() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <FeatureFlagsProvider>
          <ActionFeedbackProvider>
            <DataProvider>
              <ErrorBoundary>
            <Routes>
            <Route path="/sign-in" element={<PublicOnly><SignInPage /></PublicOnly>} />
            <Route path="/sign-up" element={<PublicOnly><SignUpPage /></PublicOnly>} />
            <Route path="/verify-email" element={<PublicOnly><VerifyEmailPage /></PublicOnly>} />
            <Route path="/forgot" element={<PublicOnly><ForgotPasswordPage /></PublicOnly>} />
            <Route path="/reset" element={<PublicOnly><ResetPasswordPage /></PublicOnly>} />
            <Route path="/mfa-challenge" element={<PublicOnly><MfaChallengePage /></PublicOnly>} />

            <Route
              path="/onboarding"
              element={
                <RequireAuth>
                  <OnboardingShell />
                </RequireAuth>
              }
            />

            <Route
              element={
                <RequireAuth>
                  <RequireOnboarded>
                    <MerchantLayout />
                  </RequireOnboarded>
                </RequireAuth>
              }
            >
              <Route index element={<OverviewPage />} />
              <Route path="plans" element={<Suspense fallback={<PageFallback />}><PlansPage /></Suspense>} />
              <Route path="plans/:planId" element={<Suspense fallback={<PageFallback />}><PlanDetailPage /></Suspense>} />
              <Route path="subscriptions" element={<Suspense fallback={<PageFallback />}><SubscriptionsPage /></Suspense>} />
              <Route path="subscriptions/:subId" element={<Suspense fallback={<PageFallback />}><SubscriptionDetailPage /></Suspense>} />
              <Route path="invoices" element={<Suspense fallback={<PageFallback />}><InvoicesPage /></Suspense>} />
              <Route path="invoices/:invoiceId" element={<Suspense fallback={<PageFallback />}><InvoiceDetailPage /></Suspense>} />
              <Route path="payments" element={<Suspense fallback={<PageFallback />}><PaymentsPage /></Suspense>} />
              <Route path="customers" element={<Suspense fallback={<PageFallback />}><CustomersPage /></Suspense>} />
              <Route path="customers/:customerId" element={<Suspense fallback={<PageFallback />}><CustomerDetailPage /></Suspense>} />
              <Route path="recovery" element={<Suspense fallback={<PageFallback />}><RecoveryPage /></Suspense>} />
              <Route path="developers" element={<Suspense fallback={<PageFallback />}><DevelopersPage /></Suspense>} />
              <Route path="team" element={<Suspense fallback={<PageFallback />}><TeamPage /></Suspense>} />
              <Route path="settings" element={<Suspense fallback={<PageFallback />}><SettingsPage /></Suspense>} />
              <Route path="portal-preview" element={<Suspense fallback={<PageFallback />}><PortalPreviewPage /></Suspense>} />
            </Route>

            <Route path="*" element={<NotFoundPage />} />
            </Routes>
            </ErrorBoundary>
            </DataProvider>
          </ActionFeedbackProvider>
        </FeatureFlagsProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
