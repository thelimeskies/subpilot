const API_BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "/api/v1";
const ENVIRONMENT_STORAGE_KEY = "subpilot.environmentMode";

export type EnvironmentMode = "test" | "live";

export interface ApiError extends Error {
  status: number;
  reason: string;
  payload: unknown;
}

// Global 401 listener — registered by AuthContext so any expired/invalid
// session response anywhere in the app flips auth state to unauthenticated
// (RequireAuth then redirects to /sign-in). Auth endpoints are exempt so we
// don't recurse on the bootstrap /auth/me probe or sign-in failures.
type UnauthorizedHandler = (path: string) => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

const AUTH_EXEMPT_PREFIXES = [
  "/auth/sign-in",
  "/auth/sign-up",
  "/auth/sign-out",
  "/auth/me",
  "/auth/verify-email",
  "/auth/verify-mfa",
  "/auth/request-reset",
  "/auth/reset-password",
  "/auth/forgot",
];

function isAuthExempt(path: string): boolean {
  return AUTH_EXEMPT_PREFIXES.some((prefix) => path.startsWith(prefix));
}

function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const prefix = `${name}=`;
  for (const part of document.cookie.split(";")) {
    const trimmed = part.trim();
    if (trimmed.startsWith(prefix)) {
      return decodeURIComponent(trimmed.slice(prefix.length));
    }
  }
  return null;
}

function readCsrfToken(): string | null {
  return readCookie("subpilot_csrf") ?? readCookie("csrftoken");
}

export function getActiveEnvironmentMode(): EnvironmentMode {
  if (typeof window === "undefined") return "test";
  return window.localStorage.getItem(ENVIRONMENT_STORAGE_KEY) === "live" ? "live" : "test";
}

export function setActiveEnvironmentMode(mode: EnvironmentMode): void {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ENVIRONMENT_STORAGE_KEY, mode);
}

function isUnsafeMethod(method: string): boolean {
  return !["GET", "HEAD", "OPTIONS", "TRACE"].includes(method.toUpperCase());
}

function getReason(payload: unknown, fallback: string): string {
  if (typeof payload === "object" && payload && "reason" in payload) {
    return String((payload as { reason: unknown }).reason);
  }
  if (typeof payload === "object" && payload && "detail" in payload) {
    return String((payload as { detail: unknown }).detail);
  }
  return fallback;
}

async function request<T = unknown>(
  path: string,
  init: RequestInit & { json?: unknown } = {}
): Promise<T> {
  const { json, headers: rawHeaders, method = "GET", ...rest } = init;
  const headers = new Headers(rawHeaders ?? {});
  headers.set("Accept", "application/json");
  if (!headers.has("X-Environment")) {
    headers.set("X-Environment", getActiveEnvironmentMode());
  }

  let body = init.body;
  if (json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(json);
  }

  if (isUnsafeMethod(method)) {
    const csrf = readCsrfToken();
    if (csrf) headers.set("X-CSRFToken", csrf);
  }

  const url = path.startsWith("http") ? path : `${API_BASE}${path.startsWith("/") ? path : `/${path}`}`;
  const response = await fetch(url, {
    method,
    credentials: "include",
    headers,
    body,
    ...rest
  });

  let payload: unknown = null;
  const text = await response.text();
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }

  if (!response.ok) {
    if (response.status === 401 && !isAuthExempt(path) && unauthorizedHandler) {
      try {
        unauthorizedHandler(path);
      } catch {
        // Listener errors must not mask the original 401.
      }
    }
    const error = new Error(getReason(payload, `Request failed (${response.status})`)) as ApiError;
    error.status = response.status;
    error.reason = error.message;
    error.payload = payload;
    throw error;
  }

  return payload as T;
}

export const api = {
  get: <T = unknown>(path: string, init?: Omit<RequestInit, "method" | "body">) =>
    request<T>(path, { ...init, method: "GET" }),
  post: <T = unknown>(path: string, json?: unknown, init?: Omit<RequestInit, "method" | "body">) =>
    request<T>(path, { ...init, method: "POST", json }),
  patch: <T = unknown>(path: string, json?: unknown, init?: Omit<RequestInit, "method" | "body">) =>
    request<T>(path, { ...init, method: "PATCH", json }),
  put: <T = unknown>(path: string, json?: unknown, init?: Omit<RequestInit, "method" | "body">) =>
    request<T>(path, { ...init, method: "PUT", json }),
  delete: <T = unknown>(path: string, init?: Omit<RequestInit, "method" | "body">) =>
    request<T>(path, { ...init, method: "DELETE" })
};

export function isApiError(err: unknown): err is ApiError {
  return err instanceof Error && typeof (err as ApiError).status === "number";
}
