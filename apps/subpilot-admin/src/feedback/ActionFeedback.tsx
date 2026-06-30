import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { Button, Modal, Toast, type AlertTone } from "@subpilot/ui";

/**
 * Lightweight, app-wide feedback layer.
 *
 * - `notify(...)` → renders a stacked toast in the bottom-right (auto-dismiss).
 * - `confirm(...)` → renders a modal that resolves on user choice. Use this
 *   for any destructive or non-trivial action (revoke, suspend, rotate).
 *
 * The goal is to give every admin button a real, audible side effect so the
 * UI never silently no-ops or fires destructive work without confirmation.
 */

export type FeedbackTone = AlertTone;

type ToastItem = {
  id: number;
  tone: FeedbackTone;
  title: string;
  description: string;
};

type ConfirmOptions = {
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  /** Mark the action as destructive — uses danger button + warning copy. */
  destructive?: boolean;
};

type FeedbackContextValue = {
  notify: (item: { tone?: FeedbackTone; title: string; description: string }) => void;
  confirm: (options: ConfirmOptions) => Promise<boolean>;
};

const FeedbackContext = createContext<FeedbackContextValue | null>(null);

let nextId = 1;

export function ActionFeedbackProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const [pending, setPending] = useState<
    | (ConfirmOptions & { resolve: (value: boolean) => void })
    | null
  >(null);

  const notify = useCallback<FeedbackContextValue["notify"]>((item) => {
    const id = nextId++;
    setToasts((current) => [...current, { id, tone: item.tone ?? "success", title: item.title, description: item.description }]);
    // Auto-dismiss after 3.6s.
    window.setTimeout(() => {
      setToasts((current) => current.filter((t) => t.id !== id));
    }, 3600);
  }, []);

  const confirm = useCallback<FeedbackContextValue["confirm"]>((options) => {
    return new Promise<boolean>((resolve) => {
      setPending({ ...options, resolve });
    });
  }, []);

  // Esc closes any open confirm dialog (treated as cancel).
  useEffect(() => {
    if (!pending) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        pending.resolve(false);
        setPending(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pending]);

  const value = useMemo<FeedbackContextValue>(() => ({ notify, confirm }), [notify, confirm]);

  function resolvePending(result: boolean) {
    if (!pending) return;
    pending.resolve(result);
    setPending(null);
  }

  return (
    <FeedbackContext.Provider value={value}>
      {children}

      {/* Toast stack */}
      <div className="adm-toast-stack" aria-live="polite" aria-atomic="false">
        {toasts.map((t) => (
          <Toast key={t.id} tone={t.tone} title={t.title} description={t.description} />
        ))}
      </div>

      {/* Confirm dialog */}
      <Modal
        open={pending !== null}
        title={pending?.title ?? ""}
        description={pending?.description}
        onClose={() => resolvePending(false)}
        footer={
          <>
            <Button variant="ghost" onClick={() => resolvePending(false)}>
              {pending?.cancelLabel ?? "Cancel"}
            </Button>
            <Button
              variant={pending?.destructive ? "danger" : "primary"}
              onClick={() => resolvePending(true)}
            >
              {pending?.confirmLabel ?? (pending?.destructive ? "Confirm" : "Continue")}
            </Button>
          </>
        }
      >
        {pending?.destructive ? (
          <p className="adm-confirm-warning">
            This action is destructive and audit-logged. Make sure you have communicated the change before continuing.
          </p>
        ) : (
          <p className="adm-confirm-note">Confirm the action to apply changes platform-wide.</p>
        )}
      </Modal>
    </FeedbackContext.Provider>
  );
}

export function useFeedback(): FeedbackContextValue {
  const ctx = useContext(FeedbackContext);
  if (!ctx) {
    throw new Error("useFeedback must be used inside <ActionFeedbackProvider>.");
  }
  return ctx;
}
