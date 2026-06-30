import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "./AuthContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <div className="mer-boot" role="status" aria-live="polite">
        <span className="mer-boot__spinner" aria-hidden="true" />
        <span>Restoring session…</span>
      </div>
    );
  }

  if (status === "unauthenticated") {
    return <Navigate to="/sign-in" state={{ from: location }} replace />;
  }

  return <>{children}</>;
}
