import { useState } from "react";
import { Button, Field, SelectInput, TextInput } from "@subpilot/ui";
import { CheckCircle2, ShieldCheck } from "lucide-react";
import type { OnboardingDraft } from "../useOnboardingDraft";
import { useFeedback } from "../../feedback/ActionFeedback";

const NIGERIAN_BANKS = [
  "Access Bank",
  "Ecobank Nigeria",
  "Fidelity Bank",
  "First Bank of Nigeria",
  "GTBank",
  "Kuda Microfinance Bank",
  "Polaris Bank",
  "Providus Bank",
  "Stanbic IBTC",
  "Sterling Bank",
  "UBA",
  "Union Bank",
  "Wema Bank",
  "Zenith Bank"
];

interface Props {
  draft: OnboardingDraft;
  updateSection: <K extends "payout">(section: K, patch: Partial<OnboardingDraft[K]>) => void;
}

const sampleNames = ["Acme Learning Hub Ltd", "Acme Holdings Ltd", "Acme Operations Ltd"];

export function PayoutBankStep({ draft, updateSection }: Props) {
  const { notify } = useFeedback();
  const [resolving, setResolving] = useState(false);

  async function resolveAccount() {
    if (draft.payout.accountNumber.trim().length < 6 || !draft.payout.bank) {
      notify({
        tone: "warning",
        title: "Enter bank and account first",
        description: "We need both fields to look up your account name."
      });
      return;
    }
    setResolving(true);
    await new Promise((r) => setTimeout(r, 800));
    setResolving(false);
    const idx = (draft.payout.accountNumber.charCodeAt(0) || 0) % sampleNames.length;
    updateSection("payout", { accountName: sampleNames[idx], resolved: true });
    notify({
      tone: "success",
      title: "Account resolved",
      description: "We'll route settlements to this account daily."
    });
  }

  return (
    <div className="mer-step">
      <header className="mer-step__head">
        <h2>Where should we send payouts?</h2>
        <p>
          We settle in your local currency. You can change this later under Settings → Billing &amp; payouts.
        </p>
      </header>

      <div className="mer-step__grid">
        <Field label="Bank">
          <SelectInput
            value={draft.payout.bank}
            onChange={(e) => updateSection("payout", { bank: e.target.value, resolved: false })}
          >
            <option value="">Select your bank…</option>
            {NIGERIAN_BANKS.map((b) => (
              <option key={b} value={b}>
                {b}
              </option>
            ))}
          </SelectInput>
        </Field>

        <Field label="Account number">
          <TextInput
            value={draft.payout.accountNumber}
            onChange={(e) =>
              updateSection("payout", {
                accountNumber: e.target.value.replace(/\D/g, "").slice(0, 12),
                resolved: false
              })
            }
            inputMode="numeric"
            placeholder="0123456789"
            maxLength={12}
            required
          />
        </Field>

        <div className="mer-bank-resolve">
          <Button
            type="button"
            variant="secondary"
            icon={<ShieldCheck size={16} />}
            onClick={resolveAccount}
            disabled={resolving}
          >
            {resolving ? "Looking up name…" : "Resolve account name"}
          </Button>
          {draft.payout.resolved && draft.payout.accountName ? (
            <span className="mer-bank-resolve__name">
              <CheckCircle2 size={14} aria-hidden="true" /> {draft.payout.accountName}
            </span>
          ) : null}
        </div>

        <Field label="Settlement frequency" hint="Choose how often we wire payouts to your bank.">
          <SelectInput
            value={draft.payout.settlementFrequency}
            onChange={(e) =>
              updateSection("payout", {
                settlementFrequency: e.target.value as OnboardingDraft["payout"]["settlementFrequency"]
              })
            }
          >
            <option value="daily">Daily (T+1)</option>
            <option value="weekly">Weekly (Mondays)</option>
            <option value="monthly">Monthly (1st of month)</option>
          </SelectInput>
        </Field>
      </div>
    </div>
  );
}

export function validatePayoutStep(draft: OnboardingDraft) {
  return Boolean(
    draft.payout.bank &&
      draft.payout.accountNumber.trim().length >= 6 &&
      draft.payout.resolved &&
      draft.payout.accountName.trim().length > 0
  );
}
