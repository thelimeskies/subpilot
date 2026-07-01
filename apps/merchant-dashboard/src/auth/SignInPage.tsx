import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button, Field, TextInput } from "@subpilot/ui";
import { ArrowRight, Eye, EyeOff, Lock, Mail, ShieldCheck, Sparkles, Webhook } from "lucide-react";
import { useAuth } from "./AuthContext";

const demoAccounts = [
  { label: "Owner", email: "owner@acme.test" },
  { label: "Admin", email: "admin@fitplus.test" },
  { label: "New (onboarding)", email: "new@startup.test" },
  { label: "Finance", email: "finance@acme.test" },
  { label: "Support", email: "support@acme.test" }
];

const demoPassword = import.meta.env.VITE_DEMO_PASSWORD ?? "";

export function SignInPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/";

  const [email, setEmail] = useState("owner@acme.test");
  const [password, setPassword] = useState(demoPassword);
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    setError(null);
    const result = await signIn(email, password);
    setSubmitting(false);
    if (!result.ok) {
      setError(result.reason);
      return;
    }
    if ("requiresMfa" in result && result.requiresMfa) {
      navigate(`/mfa-challenge?cid=${encodeURIComponent(result.challengeId)}`, {
        replace: true,
        state: { from: location.state }
      });
      return;
    }
    navigate(from === "/sign-in" ? "/" : from, { replace: true });
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
          <span className="mer-auth__kicker">Subscription operations</span>
          <h1>Run subscriptions, recover revenue, ship faster.</h1>
          <p>
            SubPilot gives your team a tokenized-card billing engine, a recovery cockpit for failed invoices,
            a customer portal, and signed webhooks — all in one workspace.
          </p>
        </div>

        <ul className="mer-auth__features" aria-label="Platform highlights">
          <li>
            <ShieldCheck size={16} aria-hidden="true" />
            <span>Tokenized cards with PSD2-grade strong auth</span>
          </li>
          <li>
            <Webhook size={16} aria-hidden="true" />
            <span>Signed webhooks with replay &amp; deliveries log</span>
          </li>
          <li>
            <Sparkles size={16} aria-hidden="true" />
            <span>Recovery cockpit that turns dunning into revenue</span>
          </li>
        </ul>
      </div>

      <div className="mer-auth__card">
        <header>
          <h2>Welcome back</h2>
          <p>Sign in to your merchant workspace. New here? <Link to="/sign-up" className="mer-auth__link">Create an account</Link>.</p>
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

          <Field label="Password">
            <span className="mer-input-wrap">
              <Lock size={16} aria-hidden="true" />
              <TextInput
                type={showPassword ? "text" : "password"}
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
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

          <div className="mer-auth__row">
            <label className="mer-auth__remember">
              <input type="checkbox" defaultChecked />
              <span>Keep me signed in</span>
            </label>
            <Link to="/forgot" className="mer-auth__link">Forgot password?</Link>
          </div>

          {error ? (
            <div className="mer-auth__error" role="alert">
              {error}
            </div>
          ) : null}

          <Button type="submit" icon={<ArrowRight size={16} />} disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <div className="mer-auth__demo">
          <span className="mer-auth__demo-label">Demo access</span>
          <p>Select a demo seat to preview the merchant workspace.</p>
          <div className="mer-auth__demo-grid">
            {demoAccounts.map((account) => (
              <button
                key={account.email}
                type="button"
                className="mer-auth__demo-chip"
                onClick={() => {
                  setEmail(account.email);
                  setPassword(demoPassword);
                }}
              >
                <strong>{account.label}</strong>
                <small>{account.email}</small>
              </button>
            ))}
          </div>
        </div>

        <footer className="mer-auth__footer">
          <span>© SubPilot 2026</span>
          <Link to="/sign-up" className="mer-auth__link">Need an account?</Link>
        </footer>
      </div>
    </div>
  );
}
