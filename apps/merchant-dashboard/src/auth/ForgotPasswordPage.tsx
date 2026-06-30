import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button, Field, TextInput } from "@subpilot/ui";
import { ArrowRight, KeyRound, Mail } from "lucide-react";
import { useAuth } from "./AuthContext";
import { useFeedback } from "../feedback/ActionFeedback";

export function ForgotPasswordPage() {
  const { requestReset } = useAuth();
  const { notify } = useFeedback();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resetToken, setResetToken] = useState<string | null>(null);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const result = await requestReset(email);
    setSubmitting(false);
    if (!result.ok) {
      setError(result.reason);
      return;
    }
    setResetToken(result.resetToken);
    notify({
      tone: "info",
      title: "Reset link sent",
      description: `If an account exists for ${email}, a reset link is on its way.`
    });
  }

  return (
    <div className="mer-auth mer-auth--single">
      <div className="mer-auth__card mer-auth__card--narrow">
        <header>
          <span className="mer-auth__icon-bubble" aria-hidden="true">
            <KeyRound size={20} />
          </span>
          <h2>Reset your password</h2>
          <p>Enter the email associated with your SubPilot workspace and we'll send a reset link.</p>
        </header>

        <form className="mer-auth__form" onSubmit={onSubmit} noValidate>
          <Field label="Work email">
            <span className="mer-input-wrap">
              <Mail size={16} aria-hidden="true" />
              <TextInput
                type="email"
                autoComplete="email"
                inputMode="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@yourbrand.com"
                required
              />
            </span>
          </Field>

          {error ? (
            <div className="mer-auth__error" role="alert">
              {error}
            </div>
          ) : null}

          <Button type="submit" icon={<ArrowRight size={16} />} disabled={submitting}>
            {submitting ? "Sending link…" : "Send reset link"}
          </Button>
        </form>

        {resetToken ? (
          <div className="mer-auth__demo mer-auth__demo--note">
            <span className="mer-auth__demo-label">Demo helper</span>
            <p>This is a demo workspace — there's no real inbox. Use the button below to open the reset page.</p>
            <Button
              type="button"
              variant="secondary"
              icon={<ArrowRight size={16} />}
              onClick={() => navigate(`/reset?token=${encodeURIComponent(resetToken)}&email=${encodeURIComponent(email)}`)}
            >
              Use reset link
            </Button>
          </div>
        ) : null}

        <footer className="mer-auth__footer">
          <Link to="/sign-in" className="mer-auth__link">Back to sign in</Link>
          <Link to="/sign-up" className="mer-auth__link">Need an account?</Link>
        </footer>
      </div>
    </div>
  );
}
