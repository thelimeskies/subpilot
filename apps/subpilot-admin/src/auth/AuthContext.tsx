import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, isApiError, setUnauthorizedHandler } from "../api/client";

export interface AdminUser {
  id: string;
  name: string;
  email: string;
  role: "Owner" | "Operator" | "Support" | "Read-only";
  initials: string;
}

interface AuthContextValue {
  user: AdminUser | null;
  status: "loading" | "authenticated" | "unauthenticated";
  signIn: (email: string, password: string) => Promise<{ ok: true } | { ok: false; reason: string }>;
  signOut: () => Promise<void>;
  updateProfile: (input: { name?: string; email?: string }) => Promise<{ ok: true; user: AdminUser } | { ok: false; reason: string }>;
}

interface MeResponse {
  ok: boolean;
  user: AdminUser | null;
}

interface SignInResponse {
  ok: boolean;
  user?: AdminUser;
  reason?: string;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AdminUser | null>(null);
  const [status, setStatus] = useState<AuthContextValue["status"]>("loading");

  // Bootstrap: ask the backend who we are. The /me endpoint always returns 200
  // with `user: null` when there's no session (so we never have to swallow a 401
  // here).
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await api.get<MeResponse>("/platform/auth/me");
        if (cancelled) return;
        if (res.user) {
          setUser(res.user);
          setStatus("authenticated");
        } else {
          setUser(null);
          setStatus("unauthenticated");
        }
      } catch {
        if (cancelled) return;
        setUser(null);
        setStatus("unauthenticated");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  // When any non-auth API call returns 401, treat the session as expired:
  // clear user state so RequireAuth bounces the next render to /sign-in.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      setUser(null);
      setStatus("unauthenticated");
    });
    return () => setUnauthorizedHandler(null);
  }, []);

  const signIn = useCallback<AuthContextValue["signIn"]>(async (email, password) => {
    try {
      const res = await api.post<SignInResponse>("/platform/auth/sign-in", { email, password });
      if (res.ok && res.user) {
        setUser(res.user);
        setStatus("authenticated");
        return { ok: true };
      }
      return { ok: false, reason: res.reason ?? "Sign-in failed." };
    } catch (err) {
      const reason = isApiError(err)
        ? err.reason
        : "Could not reach the SubPilot platform API.";
      return { ok: false, reason };
    }
  }, []);

  const signOut = useCallback(async () => {
    try {
      await api.post("/platform/auth/sign-out");
    } catch {
      // Even if the network call fails, drop local state so the UI reflects sign-out.
    }
    setUser(null);
    setStatus("unauthenticated");
  }, []);

  const updateProfile = useCallback<AuthContextValue["updateProfile"]>(async (input) => {
    try {
      const payload: Record<string, string> = {};
      if (input.name !== undefined) payload.display_name = input.name;
      if (input.email !== undefined) payload.email = input.email;
      const res = await api.patch<{ ok: boolean; user?: AdminUser; reason?: string }>(
        "/platform/auth/me",
        payload
      );
      if (res.ok && res.user) {
        setUser(res.user);
        return { ok: true, user: res.user };
      }
      return { ok: false, reason: res.reason ?? "Profile update failed." };
    } catch (err) {
      const reason = isApiError(err) ? err.reason : "Could not save profile changes.";
      return { ok: false, reason };
    }
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ user, status, signIn, signOut, updateProfile }),
    [user, status, signIn, signOut, updateProfile],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/**
 * Role-based UI permission helpers for the platform admin console.
 *
 * The backend is the security source of truth (HasCapability + OwnerRequiredError
 * in apps/platform_admin/permissions.py and services). These helpers mirror the
 * same gates so the FE can hide or disable buttons the user can never use.
 *
 * Role hierarchy:
 * - Owner     : full access; only role allowed for sensitive mutations
 *               (settings/team writes, merchant config edit, rotate secrets,
 *                force-close subscriptions, webhook rotate-key).
 * - Operator  : Owner-1; can take operational actions on merchants and support.
 * - Support   : read-mostly; can perform low-risk support actions.
 * - Read-only : strict view-only across the console.
 */
export function usePlatformPermissions() {
  const { user } = useAuth();
  const role = user?.role ?? null;

  const isOwner = role === "Owner";
  const isOperator = role === "Operator";
  const isSupport = role === "Support";
  const isReadOnly = role === "Read-only" || role === null;

  // Owner-only mutations (mirrors IsPlatformOwner / OwnerRequiredError on backend).
  const canEditSettings = isOwner;
  const canManageTeam = isOwner;
  const canEditMerchantConfig = isOwner;
  const canRotateMerchantSecret = isOwner;
  const canForceCloseSubscription = isOwner;
  const canRotateWebhookKey = isOwner;

  // Operator+Owner (mirrors IsPlatformOperatorOrOwner): operational mutations.
  const canOperate = isOwner || isOperator;

  // Support+ can perform low-risk support actions (impersonation links etc.).
  const canSupportAct = isOwner || isOperator || isSupport;

  return {
    role,
    isOwner,
    isOperator,
    isSupport,
    isReadOnly,
    canEditSettings,
    canManageTeam,
    canEditMerchantConfig,
    canRotateMerchantSecret,
    canForceCloseSubscription,
    canRotateWebhookKey,
    canOperate,
    canSupportAct
  };
}
