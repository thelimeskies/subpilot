import { Link } from "react-router-dom";
import { Button, Field, TextInput } from "@subpilot/ui";
import { ArrowLeft, Mail } from "lucide-react";
import { useState, type FormEvent } from "react";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [submitted, setSubmitted] = useState(false);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitted(true);
  }

  return (
    <div className="adm-auth adm-auth--single">
      <div className="adm-auth__card">
        <header>
          <h2>Reset your password</h2>
          <p>We&rsquo;ll email a magic link to your SubPilot admin address. The link expires in 15 minutes.</p>
        </header>

        {submitted ? (
          <div className="adm-auth__success" role="status">
            <strong>Check your inbox.</strong>
            <span>If <code>{email || "that email"}</code> matches a SubPilot admin, you&rsquo;ll receive reset instructions shortly.</span>
          </div>
        ) : (
          <form className="adm-auth__form" onSubmit={onSubmit} noValidate>
            <Field label="Work email">
              <span className="adm-input-wrap">
                <Mail size={16} aria-hidden="true" />
                <TextInput
                  type="email"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@subpilot.dev"
                />
              </span>
            </Field>
            <Button type="submit">Send reset link</Button>
          </form>
        )}

        <footer className="adm-auth__footer">
          <Link to="/sign-in" className="adm-auth__link">
            <ArrowLeft size={14} aria-hidden="true" /> Back to sign in
          </Link>
        </footer>
      </div>
    </div>
  );
}
