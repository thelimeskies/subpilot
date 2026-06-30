import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { Button, Field, TextInput } from "@subpilot/ui";
import { ArrowRight, Eye, EyeOff, Lock, Mail, ShieldCheck, Sparkles, Webhook } from "lucide-react";
import { useAuth } from "./AuthContext";

const demoAccounts = [
  { label: "Owner", email: "owner@subpilot.dev" },
  { label: "Operator", email: "ops@subpilot.dev" },
  { label: "Support", email: "support@subpilot.dev" }
];

const demoPassword = import.meta.env.VITE_DEMO_PASSWORD ?? "";

export function SignInPage() {
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = (location.state as { from?: { pathname?: string } } | null)?.from?.pathname ?? "/";

  const [email, setEmail] = useState("owner@subpilot.dev");
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
    navigate(from === "/sign-in" ? "/" : from, { replace: true });
  }

  return (
    <div className="adm-auth">
      <div className="adm-auth__panel">
        <div className="adm-auth__brand">
          <span className="adm-auth__mark" aria-hidden="true">S</span>
          <span className="adm-auth__brand-text">
            <strong>SubPilot</strong>
            <small>Platform admin</small>
          </span>
        </div>

        <div className="adm-auth__copy">
          <span className="adm-auth__kicker">Operator console</span>
          <h1>Sign in to keep merchants healthy.</h1>
          <p>
            Manage merchant onboarding, recovery queues, gateway adapters, and webhook signatures across the SubPilot platform —
            all behind tenant-scoped, audit-logged sessions.
          </p>
        </div>

        <ul className="adm-auth__features" aria-label="Admin highlights">
          <li>
            <ShieldCheck size={16} aria-hidden="true" />
            <span>Audit trail on every merchant action</span>
          </li>
          <li>
            <Webhook size={16} aria-hidden="true" />
            <span>Replay webhooks &amp; verify signatures</span>
          </li>
          <li>
            <Sparkles size={16} aria-hidden="true" />
            <span>Recovery cockpit for revenue at risk</span>
          </li>
        </ul>
      </div>

      <div className="adm-auth__card">
        <header>
          <h2>Welcome back</h2>
          <p>Use a SubPilot admin email. SSO &amp; MFA are enforced in production.</p>
        </header>

        <form className="adm-auth__form" onSubmit={onSubmit} noValidate>
          <Field label="Work email">
            <span className="adm-input-wrap">
              <Mail size={16} aria-hidden="true" />
              <TextInput
                type="email"
                autoComplete="email"
                inputMode="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@subpilot.dev"
                required
              />
            </span>
          </Field>

          <Field label="Password">
            <span className="adm-input-wrap">
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
                className="adm-input-toggle"
                onClick={() => setShowPassword((v) => !v)}
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff size={16} aria-hidden="true" /> : <Eye size={16} aria-hidden="true" />}
              </button>
            </span>
          </Field>

          <div className="adm-auth__row">
            <label className="adm-auth__remember">
              <input type="checkbox" defaultChecked />
              <span>Keep me signed in</span>
            </label>
            <Link to="/forgot" className="adm-auth__link">Forgot password?</Link>
          </div>

          {error ? (
            <div className="adm-auth__error" role="alert">
              {error}
            </div>
          ) : null}

          <Button type="submit" icon={<ArrowRight size={16} />} disabled={submitting}>
            {submitting ? "Signing in…" : "Sign in"}
          </Button>
        </form>

        <div className="adm-auth__demo">
          <span className="adm-auth__demo-label">Demo access</span>
          <p>{demoPassword ? "Use the configured demo password for every demo seat." : "Set VITE_DEMO_PASSWORD locally to prefill demo access."}</p>
          <div className="adm-auth__demo-grid">
            {demoAccounts.map((account) => (
              <button
                key={account.email}
                type="button"
                className="adm-auth__demo-chip"
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

        <footer className="adm-auth__footer">
          <span>© SubPilot 2026</span>
          <a href="/openapi.yaml">Status</a>
        </footer>
      </div>
    </div>
  );
}
