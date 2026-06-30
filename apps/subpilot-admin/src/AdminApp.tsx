import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import { AuthProvider, useAuth } from "./auth/AuthContext";
import { RequireAuth } from "./auth/RequireAuth";
import { SignInPage } from "./auth/SignInPage";
import { ForgotPasswordPage } from "./auth/ForgotPasswordPage";
import { AdminLayout } from "./layout/AdminLayout";
import { ActionFeedbackProvider } from "./feedback/ActionFeedback";
import { OverviewPage } from "./pages/OverviewPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { MerchantsPage } from "./pages/MerchantsPage";
import { MerchantDetailPage } from "./pages/MerchantDetailPage";
import { PaymentsPage } from "./pages/PaymentsPage";
import { WebhooksPage } from "./pages/WebhooksPage";
import { ApiKeysPage } from "./pages/ApiKeysPage";
import { SupportPage } from "./pages/SupportPage";
import { SettingsPage } from "./pages/SettingsPage";
import { TeamPage } from "./pages/TeamPage";
import { NotFoundPage } from "./pages/NotFoundPage";

function PublicOnly({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  if (status === "authenticated") {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}

export function AdminApp() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ActionFeedbackProvider>
          <Routes>
            <Route path="/sign-in" element={<PublicOnly><SignInPage /></PublicOnly>} />
            <Route path="/forgot" element={<PublicOnly><ForgotPasswordPage /></PublicOnly>} />

            <Route
              element={
                <RequireAuth>
                  <AdminLayout />
                </RequireAuth>
              }
            >
              <Route index element={<OverviewPage />} />
              <Route path="analytics" element={<AnalyticsPage />} />
              <Route path="merchants" element={<MerchantsPage />} />
              <Route path="merchants/:merchantId" element={<MerchantDetailPage />} />
              <Route path="payments" element={<PaymentsPage />} />
              <Route path="webhooks" element={<WebhooksPage />} />
              <Route path="api-keys" element={<ApiKeysPage />} />
              <Route path="support" element={<SupportPage />} />
              <Route path="team" element={<TeamPage />} />
              <Route path="settings" element={<SettingsPage />} />
            </Route>

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </ActionFeedbackProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
