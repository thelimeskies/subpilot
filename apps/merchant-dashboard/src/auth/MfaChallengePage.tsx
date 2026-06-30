import { useEffect, useRef, useState, type ChangeEvent, type ClipboardEvent, type KeyboardEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@subpilot/ui";
import { ArrowRight, ShieldCheck } from "lucide-react";
import { useAuth } from "./AuthContext";
import { useFeedback } from "../feedback/ActionFeedback";

const CELL_COUNT = 6;

export function MfaChallengePage() {
  const { verifyMfa } = useAuth();
  const { notify } = useFeedback();
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const challengeId = params.get("cid") ?? "";

  const [digits, setDigits] = useState<string[]>(Array.from({ length: CELL_COUNT }, () => ""));
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRefs = useRef<Array<HTMLInputElement | null>>([]);

  useEffect(() => {
    inputRefs.current[0]?.focus();
  }, []);

  function setCell(index: number, value: string) {
    setDigits((prev) => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
  }

  function focusCell(index: number) {
    inputRefs.current[index]?.focus();
    inputRefs.current[index]?.select();
  }

  function onCellChange(index: number, event: ChangeEvent<HTMLInputElement>) {
    const raw = event.target.value.replace(/\D/g, "");
    if (raw.length <= 1) {
      setCell(index, raw);
      if (raw && index < CELL_COUNT - 1) focusCell(index + 1);
      return;
    }
    // Multi-char paste-into-cell: spread across following cells.
    const chars = raw.slice(0, CELL_COUNT - index).split("");
    setDigits((prev) => {
      const next = [...prev];
      chars.forEach((char, i) => {
        next[index + i] = char;
      });
      return next;
    });
    const lastIdx = Math.min(index + chars.length, CELL_COUNT - 1);
    focusCell(lastIdx);
  }

  function onKeyDown(index: number, event: KeyboardEvent<HTMLInputElement>) {
    if (event.key === "Backspace" && !digits[index] && index > 0) {
      focusCell(index - 1);
      return;
    }
    if (event.key === "ArrowLeft" && index > 0) {
      event.preventDefault();
      focusCell(index - 1);
    }
    if (event.key === "ArrowRight" && index < CELL_COUNT - 1) {
      event.preventDefault();
      focusCell(index + 1);
    }
  }

  function onPaste(event: ClipboardEvent<HTMLInputElement>) {
    const text = event.clipboardData.getData("text").replace(/\D/g, "").slice(0, CELL_COUNT);
    if (!text) return;
    event.preventDefault();
    const next = Array.from({ length: CELL_COUNT }, (_, i) => text[i] ?? "");
    setDigits(next);
    focusCell(Math.min(text.length, CELL_COUNT - 1));
  }

  function fillDemoCode() {
    const code = "123456".split("");
    setDigits(code);
    focusCell(CELL_COUNT - 1);
  }

  async function handleVerify() {
    setError(null);
    if (!challengeId) {
      setError("Missing challenge id. Sign in again to continue.");
      return;
    }
    const code = digits.join("");
    if (code.length !== CELL_COUNT) {
      setError("Enter all 6 digits of your authenticator code.");
      return;
    }
    setSubmitting(true);
    const result = await verifyMfa(challengeId, code);
    setSubmitting(false);
    if (!result.ok) {
      setError(result.reason);
      setDigits(Array.from({ length: CELL_COUNT }, () => ""));
      focusCell(0);
      return;
    }
    notify({ tone: "success", title: "Welcome back", description: "Two-factor verification complete." });
    navigate("/", { replace: true });
  }

  return (
    <div className="mer-auth mer-auth--single">
      <div className="mer-auth__card mer-auth__card--narrow">
        <header>
          <span className="mer-auth__icon-bubble" aria-hidden="true">
            <ShieldCheck size={20} />
          </span>
          <h2>Two-factor verification</h2>
          <p>Enter the 6-digit code from your authenticator app to finish signing in.</p>
        </header>

        <div className="mer-mfa-form">
          <label className="mer-mfa-form__label" htmlFor="mfa-cell-0">
            Authenticator code
          </label>
          <div className="mer-mfa-cells" role="group" aria-label="6-digit verification code">
            {digits.map((value, index) => (
              <input
                key={index}
                id={`mfa-cell-${index}`}
                ref={(el) => {
                  inputRefs.current[index] = el;
                }}
                className="mer-mfa-cell"
                type="text"
                inputMode="numeric"
                pattern="\d*"
                maxLength={1}
                autoComplete="one-time-code"
                value={value}
                onChange={(e) => onCellChange(index, e)}
                onKeyDown={(e) => onKeyDown(index, e)}
                onPaste={onPaste}
                aria-label={`Digit ${index + 1}`}
              />
            ))}
          </div>

          {error ? (
            <div className="mer-auth__error" role="alert">
              {error}
            </div>
          ) : null}

          <Button type="button" icon={<ArrowRight size={16} />} onClick={handleVerify} disabled={submitting}>
            {submitting ? "Verifying…" : "Verify and sign in"}
          </Button>

          <div className="mer-auth__demo mer-auth__demo--note">
            <span className="mer-auth__demo-label">Demo helper</span>
            <p>
              This workspace accepts the demo code <code>123456</code> on every MFA-enabled account.
            </p>
            <Button type="button" variant="secondary" onClick={fillDemoCode}>
              Use demo code 123456
            </Button>
          </div>
        </div>

        <footer className="mer-auth__footer">
          <Link to="/sign-in" className="mer-auth__link">Use a different account</Link>
        </footer>
      </div>
    </div>
  );
}
