import { Field, SelectInput, TextInput } from "@subpilot/ui";
import type { OnboardingDraft, BusinessProfile } from "../useOnboardingDraft";

const COUNTRIES = ["Nigeria", "Ghana", "Kenya", "South Africa", "Egypt", "United Kingdom", "United States"];
const INDUSTRIES = [
  "SaaS / software",
  "E-learning / education",
  "Health & fitness",
  "Media & publishing",
  "Marketplace",
  "Professional services",
  "Other"
];

interface Props {
  draft: OnboardingDraft;
  updateSection: <K extends "business">(section: K, patch: Partial<OnboardingDraft[K]>) => void;
}

export function BusinessProfileStep({ draft, updateSection }: Props) {
  const value: BusinessProfile = draft.business;
  return (
    <div className="mer-step">
      <header className="mer-step__head">
        <h2>Tell us about your business</h2>
        <p>This is what shows on invoices, the customer portal, and statements.</p>
      </header>

      <div className="mer-step__grid">
        <Field label="Legal name">
          <TextInput
            value={value.legalName}
            onChange={(e) => updateSection("business", { legalName: e.target.value })}
            placeholder="Acme Learning Hub Ltd."
            required
          />
        </Field>
        <Field label="Trading name (optional)" hint="What customers see on receipts.">
          <TextInput
            value={value.tradingName}
            onChange={(e) => updateSection("business", { tradingName: e.target.value })}
            placeholder="Acme Learning Hub"
          />
        </Field>
        <Field label="Country of registration">
          <SelectInput
            value={value.country}
            onChange={(e) => updateSection("business", { country: e.target.value })}
          >
            {COUNTRIES.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </SelectInput>
        </Field>
        <Field label="Industry">
          <SelectInput
            value={value.industry}
            onChange={(e) => updateSection("business", { industry: e.target.value })}
          >
            <option value="">Select an industry…</option>
            {INDUSTRIES.map((i) => (
              <option key={i} value={i}>
                {i}
              </option>
            ))}
          </SelectInput>
        </Field>
        <Field label="Website (optional)">
          <TextInput
            type="url"
            value={value.website}
            onChange={(e) => updateSection("business", { website: e.target.value })}
            placeholder="https://"
          />
        </Field>
        <Field label="Short description" hint="One sentence — used in dunning emails and the portal.">
          <TextInput
            value={value.description}
            onChange={(e) => updateSection("business", { description: e.target.value })}
            placeholder="We sell live cohort-based courses for product managers."
          />
        </Field>
      </div>
    </div>
  );
}

export function validateBusinessStep(draft: OnboardingDraft) {
  return draft.business.legalName.trim().length >= 2 && draft.business.industry.trim().length > 0;
}
