import { useMemo, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Button, Field, TextInput } from "@subpilot/ui";
import { ArrowRight, Briefcase, Eye, EyeOff, Lock, Mail, Sparkles, User } from "lucide-react";
import { useAuth, evaluatePassword } from "./AuthContext";
import { PasswordStrengthMeter } from "../components/PasswordStrengthMeter";
import { useFeedback } from "../feedback/ActionFeedback";

export function SignUpPage() {
  const { signUp } = useAuth();
  const { notify } = useFeedback();
  const navigate = useNavigate();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [orgName, setOrgName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const evaluation = useMemo(() => evaluatePassword(password), [password]);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    const result = await signUp({ fullName, email, password, orgName });
    setSubmitting(false);
    if (!result.ok) {
      setError(result.reason);
      return;
    }
    notify({
      tone: "success",
      title: "Verification link sent",
      description: "Open the email or use the demo link on the verify page to continue."
    });
    navigate(`/verify-email?email=${encodeURIComponent(email)}&token=${encodeURIComponent(result.verifyToken)}`);
  }

  return (
    <div className="mer-auth">
      <div className="mer-auth__panel">
        <div className="mer-auth__brand">
          <span className="mer-auth__mark" aria-hidden="true">S</span>
          <span className="mer-auth__brand-text">
            <strong>SubPilot</strong>
            <small>Merchant workspace</small>
          </span>
        </div>

        <div className="mer-auth__copy">
          <span className="mer-auth__kicker">Get set up in minutes</span>
          <h1>Launch a workspace, plug in payouts, start charging.</h1>
          <p>
            Bring your team, your customers, and your subscriptions onto one billing engine —
            with a customer portal, signed webhooks, and an automated dunning cockpit included.
          </p>
        </div>

        <ul className="mer-auth__features" aria-label="What you get">
          <li>
            <Sparkles size={16} aria-hidden="true" />
            <span>14-day setup workspace with sample plans &amp; data</span>
          </li>
          <li>
            <Briefcase size={16} aria-hidden="true" />
            <span>Bring your own brand — colors, logo, portal subdomain</span>
          </li>
          <li>
            <User size={16} aria-hidden="true" />
            <span>Invite your finance &amp; support teams with role-based access</span>
          </li>
        </ul>
      </div>

      <div className="mer-auth__card">
        <header>
          <h2>Create your workspace</h2>
          <p>Already have an account? <Link to="/sign-in" className="mer-auth__link">Sign in</Link>.</p>
        </header>

        <form className="mer-auth__form" onSubmit={onSubmit} noValidate>
          <Field label="Your full name">
            <span className="mer-input-wrap">
              <User size={16} aria-hidden="true" />
              <TextInput
                autoComplete="name"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Ada Okafor"
                required
              />
            </span>
          </Field>

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

          <Field label="Workspace / company name">
            <span className="mer-input-wrap">
              <Briefcase size={16} aria-hidden="true" />
              <TextInput
                autoComplete="organization"
                value={orgName}
                onChange={(e) => setOrgName(e.target.value)}
                placeholder="Acme Learning Hub"
                required
              />
            </span>
          </Field>

          <Field label="Password">
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

          <Field label="Confirm password">
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
            {submitting ? "Creating workspace…" : "Create workspace"}
          </Button>

          <p className="mer-auth__legal">
            By continuing you agree to the SubPilot Terms of Service and Privacy Policy.
          </p>
        </form>

        <footer className="mer-auth__footer">
          <span>© SubPilot 2026</span>
          <Link to="/sign-in" className="mer-auth__link">Have an account?</Link>
        </footer>
      </div>
    </div>
  );
}
