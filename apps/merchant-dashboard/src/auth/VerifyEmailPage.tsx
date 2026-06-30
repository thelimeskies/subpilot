import { useEffect, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "@subpilot/ui";
import { ArrowRight, MailCheck } from "lucide-react";
import { useAuth } from "./AuthContext";
import { useFeedback } from "../feedback/ActionFeedback";

export function VerifyEmailPage() {
  const { verifyEmail } = useAuth();
  const { notify } = useFeedback();
  const navigate = useNavigate();
  const [params] = useSearchParams();

  const email = params.get("email") ?? "";
  const tokenFromQuery = params.get("token");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [verified, setVerified] = useState(false);

  // If token arrives directly in the link, attempt auto-verify (one-shot).
  useEffect(() => {
    if (!tokenFromQuery || verified || submitting) return;
    let cancelled = false;
    (async () => {
      setSubmitting(true);
      const result = await verifyEmail(tokenFromQuery);
      if (cancelled) return;
      setSubmitting(false);
      if (result.ok) {
        setVerified(true);
        notify({ tone: "success", title: "Email verified", description: "Welcome to SubPilot." });
        setTimeout(() => navigate("/onboarding", { replace: true }), 600);
      } else {
        setError(result.reason);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [tokenFromQuery, verified, submitting, verifyEmail, notify, navigate]);

  async function handleManualVerify() {
    if (!tokenFromQuery) {
      setError("No verification token in this link. Use the demo link from the sign-up flow.");
      return;
    }
    setSubmitting(true);
    setError(null);
    const result = await verifyEmail(tokenFromQuery);
    setSubmitting(false);
    if (!result.ok) {
      setError(result.reason);
      return;
    }
    setVerified(true);
    notify({ tone: "success", title: "Email verified", description: "Welcome to SubPilot." });
    navigate("/onboarding", { replace: true });
  }

  return (
    <div className="mer-auth mer-auth--single">
      <div className="mer-auth__card mer-auth__card--narrow">
        <header>
          <span className="mer-auth__icon-bubble" aria-hidden="true">
            <MailCheck size={20} />
          </span>
          <h2>Verify your email</h2>
          <p>
            {email ? (
              <>We sent a verification link to <strong>{email}</strong>.</>
            ) : (
              <>Click the verification link from your email to continue.</>
            )}
          </p>
        </header>

        <div className="mer-auth__demo mer-auth__demo--note">
          <span className="mer-auth__demo-label">Demo helper</span>
          <p>
            This is a demo workspace — there's no real inbox. Use the button below to simulate
            opening the verification link.
          </p>
          <Button
            type="button"
            icon={<ArrowRight size={16} />}
            onClick={handleManualVerify}
            disabled={submitting || verified || !tokenFromQuery}
          >
            {verified ? "Verified ✓" : submitting ? "Verifying…" : "Use demo verify link"}
          </Button>
        </div>

        {error ? (
          <div className="mer-auth__error" role="alert">
            {error}
          </div>
        ) : null}

        <footer className="mer-auth__footer">
          <Link to="/sign-up" className="mer-auth__link">Use a different email</Link>
          <Link to="/sign-in" className="mer-auth__link">Back to sign in</Link>
        </footer>
      </div>
    </div>
  );
}
