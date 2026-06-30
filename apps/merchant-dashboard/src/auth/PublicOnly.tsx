import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "./AuthContext";

/** Wrap auth pages so signed-in users get bounced to the dashboard. */
export function PublicOnly({ children }: { children: ReactNode }) {
  const { status } = useAuth();
  if (status === "authenticated") {
    return <Navigate to="/" replace />;
  }
  return <>{children}</>;
}
