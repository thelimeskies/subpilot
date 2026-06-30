import { Building2, CreditCard, Globe2, ShieldCheck, Sparkles, Users } from "lucide-react";
import type { OnboardingDraft } from "../useOnboardingDraft";

interface Props {
  draft: OnboardingDraft;
}

export function FinishStep({ draft }: Props) {
  const items = [
    {
      icon: <Building2 size={16} aria-hidden="true" />,
      label: "Business",
      value: draft.business.legalName || "—",
      hint: draft.business.country
    },
    {
      icon: <CreditCard size={16} aria-hidden="true" />,
      label: "Payouts",
      value: draft.payout.bank ? `${draft.payout.bank} · ••${draft.payout.accountNumber.slice(-4)}` : "—",
      hint: `Settles ${draft.payout.settlementFrequency}`
    },
    {
      icon: <Globe2 size={16} aria-hidden="true" />,
      label: "Customer portal",
      value: `${draft.branding.subdomain}.subpilot.dev`,
      hint: `Brand color ${draft.branding.primaryColor.toUpperCase()}`
    },
    {
      icon: <Sparkles size={16} aria-hidden="true" />,
      label: "Plans",
      value: draft.plans.mode === "import" ? "3 sample plans imported" : "Empty — add plans later",
      hint: "Editable from Plans page"
    },
    {
      icon: <ShieldCheck size={16} aria-hidden="true" />,
      label: "Two-factor",
      value: draft.mfa.enabled ? "Enabled" : "Skipped",
      hint: draft.mfa.enabled ? "Required at sign-in" : "Enable later in Security"
    },
    {
      icon: <Users size={16} aria-hidden="true" />,
      label: "Team",
      value: draft.team.length === 0 ? "Just you" : `${draft.team.length} invite${draft.team.length === 1 ? "" : "s"}`,
      hint: draft.team.length === 0 ? "Invite later from Team" : "Invites will be sent on finish"
    }
  ];

  return (
    <div className="mer-step">
      <header className="mer-step__head">
        <h2>You're ready to launch</h2>
        <p>Review the summary below. You can change any of these settings later.</p>
      </header>

      <ul className="mer-summary">
        {items.map((item) => (
          <li key={item.label} className="mer-summary__item">
            <span className="mer-summary__icon">{item.icon}</span>
            <div className="mer-summary__copy">
              <span className="mer-summary__label">{item.label}</span>
              <strong>{item.value}</strong>
              <small>{item.hint}</small>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function validateFinishStep(_draft: OnboardingDraft) {
  void _draft;
  return true;
}
