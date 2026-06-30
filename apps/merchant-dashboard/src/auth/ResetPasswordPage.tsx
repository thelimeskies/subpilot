import { useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button, Field, TextInput } from "@subpilot/ui";
import { ArrowRight, Eye, EyeOff, Lock, ShieldCheck } from "lucide-react";
import { useAuth, evaluatePassword } from "./AuthContext";
import { PasswordStrengthMeter } from "../components/PasswordStrengthMeter";
import { useFeedback } from "../feedback/ActionFeedback";

export function ResetPasswordPage() {
  const { resetPassword } = useAuth();
  const { notify } = useFeedback();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const token = params.get("token") ?? "";
  const email = params.get("email") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const evaluation = useMemo(() => evaluatePassword(password), [password]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (!token) {
      setError("This reset link is missing its token. Request a new one.");
      return;
    }
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    const result = await resetPassword(token, password);
    setSubmitting(false);
    if (!result.ok) {
      setError(result.reason);
      return;
    }
    notify({
      tone: "success",
      title: "Password updated",
      description: "Sign in with your new password to continue."
    });
    navigate("/sign-in", { replace: true });
  }

  return (
    <div className="mer-auth mer-auth--single">
      <div className="mer-auth__card mer-auth__card--narrow">
        <header>
          <span className="mer-auth__icon-bubble" aria-hidden="true">
            <ShieldCheck size={20} />
          </span>
          <h2>Choose a new password</h2>
          <p>
            {email ? (
              <>You're resetting the password for <strong>{email}</strong>.</>
            ) : (
              <>Enter and confirm your new password.</>
            )}
          </p>
        </header>

        <form className="mer-auth__form" onSubmit={onSubmit} noValidate>
          <Field label="New password">
            <span className="mer-input-wrap">
              <Lock size={16} aria-hidden="true" />
              <TextInput
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="Create a strong password"
                required
              />
              <button
                type="button"
                className="mer-input-toggle"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
              </button>
            </span>
          </Field>

          <PasswordStrengthMeter evaluation={evaluation} />

          <Field label="Confirm new password">
            <span className="mer-input-wrap">
              <Lock size={16} aria-hidden="true" />
              <TextInput
                type={showPassword ? "text" : "password"}
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => setConfirm(e.target.value)}
                placeholder="Re-enter password"
                required
              />
            </span>
          </Field>

          {error ? (
            <div className="mer-auth__error" role="alert">
              {error}
            </div>
          ) : null}

          <Button type="submit" icon={<ArrowRight size={16} />} disabled={submitting || !evaluation.ok}>
            {submitting ? "Updating password…" : "Update password"}
          </Button>
        </form>

        <footer className="mer-auth__footer">
          <Link to="/sign-in" className="mer-auth__link">Back to sign in</Link>
        </footer>
      </div>
    </div>
  );
}
