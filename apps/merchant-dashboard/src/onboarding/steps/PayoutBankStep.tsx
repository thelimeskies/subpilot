import { useEffect, useState } from "react";
import { Button, Field, SelectInput, TextInput } from "@subpilot/ui";
import { CheckCircle2, RefreshCw, ShieldCheck } from "lucide-react";
import type { OnboardingDraft } from "../useOnboardingDraft";
import { useFeedback } from "../../feedback/ActionFeedback";
import { isApiError } from "../../api/client";
import { loadNombaBanks, resolvePayoutAccount, type NombaBank } from "../../api/onboarding";

interface Props {
  draft: OnboardingDraft;
  updateSection: <K extends "payout">(section: K, patch: Partial<OnboardingDraft[K]>) => void;
}

export function PayoutBankStep({ draft, updateSection }: Props) {
  const { notify } = useFeedback();
  const [banks, setBanks] = useState<NombaBank[]>([]);
  const [loadingBanks, setLoadingBanks] = useState(false);
  const [banksError, setBanksError] = useState("");
  const [resolving, setResolving] = useState(false);

  async function loadBanks() {
    setLoadingBanks(true);
    setBanksError("");
    try {
      setBanks(await loadNombaBanks());
    } catch (err) {
      const reason = isApiError(err) ? err.reason : "Nomba banks could not be loaded.";
      setBanksError(reason);
      notify({
        tone: "danger",
        title: "Could not load Nomba banks",
        description: reason
      });
    } finally {
      setLoadingBanks(false);
    }
  }

  useEffect(() => {
    void loadBanks();
  }, []);

  async function resolveAccount() {
    if (draft.payout.accountNumber.trim().length < 10 || !draft.payout.bank) {
      notify({
        tone: "warning",
        title: "Enter bank and account first",
        description: "We need a bank and 10-digit account number to look up your account name."
      });
      return;
    }
    setResolving(true);
    try {
      const result = await resolvePayoutAccount({
        bank: draft.payout.bank,
        accountNumber: draft.payout.accountNumber
      });
      updateSection("payout", {
        bank: result.bankName || draft.payout.bank,
        accountName: result.accountName,
        resolved: true
      });
      notify({
        tone: "success",
        title: "Account resolved",
        description: `${result.accountName} was verified by Nomba.`
      });
    } catch (err) {
      updateSection("payout", { accountName: "", resolved: false });
      notify({
        tone: "danger",
        title: "Could not resolve account",
        description: isApiError(err) ? err.reason : "Nomba could not verify this account right now."
      });
    } finally {
      setResolving(false);
    }
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
        <Field
          label="Bank"
          hint={banksError ? "Bank list could not be loaded from Nomba. Retry before resolving payouts." : undefined}
          error={banksError || undefined}
        >
          <SelectInput
            value={draft.payout.bank}
            disabled={loadingBanks || banks.length === 0}
            onChange={(e) => updateSection("payout", { bank: e.target.value, accountName: "", resolved: false })}
          >
            <option value="">{loadingBanks ? "Loading banks from Nomba…" : "Select your bank…"}</option>
            {banks.map((bank) => (
              <option key={bank.code} value={bank.name}>
                {bank.name}
              </option>
            ))}
          </SelectInput>
        </Field>
        {banksError ? (
          <div className="mer-bank-resolve">
            <Button
              type="button"
              variant="secondary"
              icon={<RefreshCw size={16} />}
              onClick={loadBanks}
              disabled={loadingBanks}
            >
              {loadingBanks ? "Loading banks…" : "Retry Nomba banks"}
            </Button>
          </div>
        ) : null}

        <Field label="Account number">
          <TextInput
            value={draft.payout.accountNumber}
            onChange={(e) =>
              updateSection("payout", {
                accountNumber: e.target.value.replace(/\D/g, "").slice(0, 12),
                accountName: "",
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
