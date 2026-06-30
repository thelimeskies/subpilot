import { useState, type ChangeEvent } from "react";
import { Button, Field } from "@subpilot/ui";
import { Copy, ShieldCheck, Smartphone } from "lucide-react";
import type { OnboardingDraft } from "../useOnboardingDraft";
import { useFeedback } from "../../feedback/ActionFeedback";

interface Props {
  draft: OnboardingDraft;
  updateSection: <K extends "mfa">(section: K, patch: Partial<OnboardingDraft[K]>) => void;
}

export function MfaEnrollStep({ draft, updateSection }: Props) {
  const { notify } = useFeedback();
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);

  function handleCodeChange(event: ChangeEvent<HTMLInputElement>) {
    setCode(event.target.value.replace(/\D/g, "").slice(0, 6));
    setError(null);
  }

  function fillDemo() {
    setCode("123456");
    setError(null);
  }

  function verify() {
    if (code !== "123456" && !/^\d{6}$/.test(code)) {
      setError("Enter the 6-digit code from your authenticator or use the demo helper.");
      return;
    }
    updateSection("mfa", { enabled: true });
    notify({
      tone: "success",
      title: "MFA enabled",
      description: "Two-factor will now be required when you sign in."
    });
  }

  function copySecret() {
    if (typeof navigator !== "undefined" && navigator.clipboard) {
      navigator.clipboard.writeText(draft.mfa.secret).catch(() => undefined);
    }
    notify({ tone: "info", title: "Secret copied", description: "Paste it into your authenticator app." });
  }

  return (
    <div className="mer-step">
      <header className="mer-step__head">
        <h2>Lock down your workspace</h2>
        <p>
          We strongly recommend turning on MFA — it protects your team's billing access.
        </p>
      </header>

      <div className="mer-mfa-enroll">
        <div className="mer-mfa-enroll__qr" aria-hidden="true">
          <ShieldCheck size={56} />
          <span>QR code (demo)</span>
        </div>

        <div className="mer-mfa-enroll__details">
          <span className="mer-mfa-enroll__step">Step 1 — Add to your authenticator</span>
          <p>
            Scan the QR or paste this secret into Google Authenticator, 1Password, or any TOTP app.
          </p>
          <div className="mer-mfa-enroll__secret">
            <code>{draft.mfa.secret}</code>
            <Button type="button" variant="ghost" icon={<Copy size={14} />} onClick={copySecret}>
              Copy
            </Button>
          </div>

          <span className="mer-mfa-enroll__step">Step 2 — Enter the 6-digit code</span>
          <Field label="Authenticator code">
            <input
              className="sp-input"
              inputMode="numeric"
              autoComplete="one-time-code"
              maxLength={6}
              value={code}
              onChange={handleCodeChange}
              placeholder="123456"
            />
          </Field>

          {error ? <div className="mer-auth__error" role="alert">{error}</div> : null}

          <div className="mer-mfa-enroll__actions">
            <Button type="button" icon={<Smartphone size={16} />} onClick={verify} disabled={draft.mfa.enabled}>
              {draft.mfa.enabled ? "MFA enabled ✓" : "Verify and enable MFA"}
            </Button>
            <Button type="button" variant="ghost" onClick={fillDemo}>
              Use demo code 123456
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

export function validateMfaStep(draft: OnboardingDraft) {
  // MFA is strongly recommended but optional for the demo so people can finish quickly.
  void draft;
  return true;
}
