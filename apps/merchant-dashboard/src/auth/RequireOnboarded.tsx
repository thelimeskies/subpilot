import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function RequireOnboarded({ children }: { children: ReactNode }) {
  const { user, status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <div className="mer-boot" role="status" aria-live="polite">
        <span className="mer-boot__spinner" aria-hidden="true" />
        <span>Preparing your workspace…</span>
      </div>
    );
  }

  if (user && !user.onboardingComplete) {
    return <Navigate to="/onboarding" replace state={{ from: location }} />;
  }

  return <>{children}</>;
}
