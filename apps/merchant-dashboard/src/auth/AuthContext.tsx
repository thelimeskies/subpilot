import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode
} from "react";
import { api, isApiError, setUnauthorizedHandler } from "../api/client";

export type MerchantRole = "Owner" | "Admin" | "Finance" | "Support" | "Read-only";

/**
 * Stable capability identifiers exposed by the backend RBAC matrix
 * (`backend/apps/accounts/rbac.py`). These map 1:1 to the keys of
 * ``CAPABILITIES`` and are the authoritative source for UI gating.
 */
export type Capability =
  | "view_dashboard"
  | "create_product"
  | "edit_product"
  | "create_plan"
  | "edit_plan"
  | "activate_archive_plan"
  | "view_customers"
  | "create_customer"
  | "create_subscription"
  | "pause_resume_subscription"
  | "cancel_subscription"
  | "preview_proration"
  | "retry_invoice"
  | "apply_credit_note"
  | "refund_payment"
  | "void_invoice"
  | "mark_uncollectible"
  | "export_invoices"
  | "view_payment_methods_masked"
  | "create_payment_method_session"
  | "manage_dunning_policies"
  | "view_event_logs"
  | "replay_webhooks"
  | "manage_webhook_endpoints"
  | "manage_payment_integrations"
  | "manage_api_keys"
  | "manage_team_roles"
  | "export_workspace_data"
  | "force_workspace_signout"
  | "transfer_workspace_ownership"
  | "close_workspace"
  | "view_audit_logs";

export interface MerchantUser {
  id: string;
  name: string;
  email: string;
  role: MerchantRole;
  initials: string;
  orgId: string;
  orgName: string;
  mfaEnabled: boolean;
  onboardingComplete: boolean;
  /**
   * Capability strings the user is allowed to perform, copied verbatim from
   * the backend RBAC matrix. UI must treat this as advisory: every protected
   * action is *also* enforced server-side and will return 403 if the role
   * doesn't allow it.
   */
  capabilities: Capability[];
}

export interface SignUpInput {
  fullName: string;
  email: string;
  password: string;
  orgName: string;
}

export interface PasswordIssue {
  id: "length" | "upper" | "digit" | "special";
  label: string;
  ok: boolean;
}

export interface PasswordEvaluation {
  score: 0 | 1 | 2 | 3 | 4;
  label: "Too short" | "Weak" | "Fair" | "Strong" | "Excellent";
  issues: PasswordIssue[];
  ok: boolean;
}

interface AuthContextValue {
  user: MerchantUser | null;
  status: "loading" | "authenticated" | "unauthenticated";
  signIn: (
    email: string,
    password: string
  ) => Promise<
    | { ok: true }
    | { ok: true; requiresMfa: true; challengeId: string }
    | { ok: false; reason: string }
  >;
  signOut: () => Promise<void>;
  signUp: (input: SignUpInput) => Promise<{ ok: true; verifyToken: string } | { ok: false; reason: string }>;
  verifyEmail: (token: string) => Promise<{ ok: true; user: MerchantUser } | { ok: false; reason: string }>;
  requestReset: (email: string) => Promise<{ ok: true; resetToken: string } | { ok: false; reason: string }>;
  resetPassword: (
    token: string,
    newPassword: string
  ) => Promise<{ ok: true } | { ok: false; reason: string }>;
  verifyMfa: (challengeId: string, code: string) => Promise<{ ok: true } | { ok: false; reason: string }>;
  refreshUser: (patch: Partial<MerchantUser>) => void;
  evaluatePassword: (password: string) => PasswordEvaluation;
}

type AuthEnvelope =
  | { ok: true; user: MerchantUser }
  | { ok: true; requiresMfa: true; challengeId: string }
  | { ok: false; reason: string };

interface MeResponse {
  user: MerchantUser | null;
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined);

function emailIsValid(email: string) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
}

function failureReason(err: unknown, fallback: string) {
  return isApiError(err) ? err.reason : fallback;
}

function unwrapReason(body: { ok: boolean; reason?: string }, fallback: string) {
  return body.ok ? fallback : body.reason ?? fallback;
}

// Fallback capability sets keyed by FE role. Used only if the backend payload
// somehow omits the `capabilities` field (e.g. an older deploy or fixtures).
// The runtime UI always prefers the backend-provided array when present.
const FALLBACK_CAPS: Record<MerchantRole, Capability[]> = {
  Owner: [
    "view_dashboard", "create_product", "edit_product", "create_plan", "edit_plan",
    "activate_archive_plan", "view_customers", "create_customer", "create_subscription",
    "pause_resume_subscription", "cancel_subscription", "preview_proration",
    "retry_invoice", "apply_credit_note", "refund_payment", "void_invoice",
    "mark_uncollectible", "export_invoices", "view_payment_methods_masked",
    "create_payment_method_session", "manage_dunning_policies", "view_event_logs",
    "replay_webhooks", "manage_webhook_endpoints", "manage_payment_integrations", "manage_api_keys",
    "manage_team_roles", "export_workspace_data", "force_workspace_signout",
    "transfer_workspace_ownership", "close_workspace", "view_audit_logs"
  ],
  // FE "Admin" maps to backend Billing Admin (per FRONTEND_TO_ROLE in
  // backend/apps/accounts/serializers.py). Legacy Developer-role users also
  // display as Admin; in that case the backend payload supplies the correct
  // capability list and overrides this fallback.
  Admin: [
    "view_dashboard", "create_product", "edit_product", "create_plan", "edit_plan",
    "activate_archive_plan", "view_customers", "create_customer", "create_subscription",
    "pause_resume_subscription", "cancel_subscription", "preview_proration",
    "retry_invoice", "apply_credit_note", "refund_payment", "void_invoice",
    "mark_uncollectible", "export_invoices", "view_payment_methods_masked",
    "create_payment_method_session", "manage_dunning_policies", "view_event_logs",
    "view_audit_logs"
  ],
  Finance: [
    "view_dashboard", "view_customers", "preview_proration", "retry_invoice",
    "apply_credit_note", "refund_payment", "void_invoice", "mark_uncollectible",
    "export_invoices", "view_payment_methods_masked", "view_event_logs",
    "view_audit_logs"
  ],
  Support: [
    "view_dashboard", "view_customers", "create_customer", "create_subscription",
    "pause_resume_subscription", "cancel_subscription", "preview_proration",
    "retry_invoice", "view_payment_methods_masked", "create_payment_method_session",
    "view_event_logs", "view_audit_logs"
  ],
  "Read-only": [
    "view_dashboard", "view_customers", "preview_proration", "export_invoices"
  ]
};

function normalizeUser(raw: MerchantUser | null | undefined): MerchantUser | null {
  if (!raw) return null;
  if (Array.isArray(raw.capabilities) && raw.capabilities.length > 0) {
    return raw;
  }
  const role = (raw.role || "Read-only") as MerchantRole;
  return { ...raw, capabilities: FALLBACK_CAPS[role] ?? [] };
}

export function evaluatePassword(password: string): PasswordEvaluation {
  const issues: PasswordIssue[] = [
    { id: "length", label: "At least 8 characters", ok: password.length >= 8 },
    { id: "upper", label: "One uppercase letter", ok: /[A-Z]/.test(password) },
    { id: "digit", label: "One digit", ok: /\d/.test(password) },
    { id: "special", label: "One special character", ok: /[^A-Za-z0-9]/.test(password) }
  ];
  const passed = issues.filter((issue) => issue.ok).length;
  const score = (password.length === 0 ? 0 : passed) as PasswordEvaluation["score"];
  const label: PasswordEvaluation["label"] =
    password.length === 0
      ? "Too short"
      : passed <= 1
      ? "Weak"
      : passed === 2
      ? "Fair"
      : passed === 3
      ? "Strong"
      : "Excellent";
  return { score, label, issues, ok: passed === 4 };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<MerchantUser | null>(null);
  const [status, setStatus] = useState<AuthContextValue["status"]>("loading");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const body = await api.get<MeResponse>("/auth/me");
        if (cancelled) return;
        const next = normalizeUser(body.user);
        setUser(next);
        setStatus(next ? "authenticated" : "unauthenticated");
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
      const body = await api.post<AuthEnvelope>("/auth/sign-in", { email, password });
      if (!body.ok) return { ok: false, reason: body.reason };
      if ("requiresMfa" in body && body.requiresMfa) {
        setUser(null);
        setStatus("unauthenticated");
        return { ok: true, requiresMfa: true, challengeId: body.challengeId };
      }
      if ("user" in body) {
        const next = normalizeUser(body.user);
        setUser(next);
        setStatus(next ? "authenticated" : "unauthenticated");
        return { ok: true };
      }
      return { ok: false, reason: "Sign-in response was missing a user." };
    } catch (err) {
      return { ok: false, reason: failureReason(err, "Could not sign in. Try again.") };
    }
  }, []);

  const signOut = useCallback<AuthContextValue["signOut"]>(async () => {
    try {
      await api.post("/auth/sign-out");
    } catch {
      // Local state still needs to clear if the session is already expired.
    } finally {
      setUser(null);
      setStatus("unauthenticated");
    }
  }, []);

  const signUp = useCallback<AuthContextValue["signUp"]>(async ({ fullName, email, password, orgName }) => {
    if (fullName.trim().length < 2) return { ok: false, reason: "Please enter your full name." };
    if (!emailIsValid(email)) return { ok: false, reason: "Enter a valid work email." };
    if (orgName.trim().length < 2) return { ok: false, reason: "Workspace name is required." };
    if (!evaluatePassword(password).ok) {
      return { ok: false, reason: "Password does not meet the strength requirements." };
    }
    try {
      const body = await api.post<{ ok: true; verifyToken: string } | { ok: false; reason: string }>(
        "/auth/sign-up",
        { fullName, email, password, orgName }
      );
      return body.ok ? body : { ok: false, reason: unwrapReason(body, "Could not create workspace.") };
    } catch (err) {
      return { ok: false, reason: failureReason(err, "Could not create workspace.") };
    }
  }, []);

  const verifyEmail = useCallback<AuthContextValue["verifyEmail"]>(async (token) => {
    try {
      const body = await api.post<{ ok: true; user: MerchantUser } | { ok: false; reason: string }>(
        "/auth/verify-email",
        { token }
      );
      if (!body.ok) return { ok: false, reason: body.reason };
      const next = normalizeUser(body.user);
      setUser(next);
      setStatus(next ? "authenticated" : "unauthenticated");
      return { ok: true, user: next ?? body.user };
    } catch (err) {
      return { ok: false, reason: failureReason(err, "Could not verify email.") };
    }
  }, []);

  const requestReset = useCallback<AuthContextValue["requestReset"]>(async (email) => {
    try {
      const body = await api.post<{ ok: true; resetToken: string } | { ok: false; reason: string }>(
        "/auth/request-reset",
        { email }
      );
      return body.ok ? body : { ok: false, reason: body.reason };
    } catch (err) {
      return { ok: false, reason: failureReason(err, "Could not request password reset.") };
    }
  }, []);

  const resetPassword = useCallback<AuthContextValue["resetPassword"]>(async (token, newPassword) => {
    if (!evaluatePassword(newPassword).ok) {
      return { ok: false, reason: "Password does not meet the strength requirements." };
    }
    try {
      const body = await api.post<{ ok: true } | { ok: false; reason: string }>(
        "/auth/reset-password",
        { token, newPassword }
      );
      return body.ok ? { ok: true } : { ok: false, reason: body.reason };
    } catch (err) {
      return { ok: false, reason: failureReason(err, "Could not reset password.") };
    }
  }, []);

  const verifyMfa = useCallback<AuthContextValue["verifyMfa"]>(async (challengeId, code) => {
    try {
      const body = await api.post<{ ok: true; user: MerchantUser } | { ok: false; reason: string }>(
        "/auth/verify-mfa",
        { challengeId, code }
      );
      if (!body.ok) return { ok: false, reason: body.reason };
      const next = normalizeUser(body.user);
      setUser(next);
      setStatus(next ? "authenticated" : "unauthenticated");
      return { ok: true };
    } catch (err) {
      return { ok: false, reason: failureReason(err, "Could not verify two-factor code.") };
    }
  }, []);

  const refreshUser = useCallback<AuthContextValue["refreshUser"]>(
    (patch) => {
      if (!user) return;
      const merged = normalizeUser({ ...user, ...patch } as MerchantUser);
      setUser(merged);
      setStatus("authenticated");
    },
    [user]
  );

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      status,
      signIn,
      signOut,
      signUp,
      verifyEmail,
      requestReset,
      resetPassword,
      verifyMfa,
      refreshUser,
      evaluatePassword
    }),
    [user, status, signIn, signOut, signUp, verifyEmail, requestReset, resetPassword, verifyMfa, refreshUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}

/**
 * Capability-based permission helper.
 *
 * Reads `user.capabilities` from {@link useAuth} and exposes ergonomic
 * helpers for hiding/disabling action UI. Always pair UI gates with the
 * server's own RBAC enforcement (`HasCapability` in DRF) — this hook is a
 * UX hint, not a security boundary.
 *
 * @example
 *   const { can } = usePermissions();
 *   {can("create_plan") && <Button onClick={openCreate}>Create plan</Button>}
 */
export function usePermissions() {
  const { user } = useAuth();
  const role = user?.role ?? null;
  const caps = useMemo<ReadonlySet<Capability>>(
    () => new Set((user?.capabilities ?? []) as Capability[]),
    [user]
  );
  const can = useCallback((capability: Capability) => caps.has(capability), [caps]);
  const canAny = useCallback(
    (...needed: Capability[]) => needed.some((c) => caps.has(c)),
    [caps]
  );
  const canAll = useCallback(
    (...needed: Capability[]) => needed.every((c) => caps.has(c)),
    [caps]
  );
  return { role, can, canAny, canAll, capabilities: caps };
}
