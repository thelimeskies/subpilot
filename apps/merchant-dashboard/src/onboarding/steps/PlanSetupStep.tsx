import type { OnboardingDraft } from "../useOnboardingDraft";

interface Props {
  draft: OnboardingDraft;
  updateSection: <K extends "plans">(section: K, patch: Partial<OnboardingDraft[K]>) => void;
}

const SAMPLE_PLANS = [
  { name: "Starter", price: "$19 / month", description: "5 seats · email support · basic analytics" },
  { name: "Growth", price: "$79 / month", description: "25 seats · priority support · API access" },
  { name: "Scale", price: "$249 / month", description: "Unlimited seats · SSO · custom dunning rules" }
];

export function PlanSetupStep({ draft, updateSection }: Props) {
  const mode = draft.plans.mode;
  return (
    <div className="mer-step">
      <header className="mer-step__head">
        <h2>Set up your first plans</h2>
        <p>You can edit, duplicate, or archive everything later from the Plans page.</p>
      </header>

      <div className="mer-plan-choices">
        <button
          type="button"
          className={`mer-plan-choice${mode === "import" ? " is-selected" : ""}`}
          onClick={() => updateSection("plans", { mode: "import" })}
        >
          <header>
            <strong>Import 3 sample plans</strong>
            <span>Recommended</span>
          </header>
          <p>Get a Starter / Growth / Scale ladder pre-filled and ready to publish.</p>
          <ul>
            {SAMPLE_PLANS.map((plan) => (
              <li key={plan.name}>
                <strong>{plan.name}</strong>
                <span>{plan.price}</span>
                <small>{plan.description}</small>
              </li>
            ))}
          </ul>
        </button>

        <button
          type="button"
          className={`mer-plan-choice${mode === "skip" ? " is-selected" : ""}`}
          onClick={() => updateSection("plans", { mode: "skip" })}
        >
          <header>
            <strong>Skip — I'll create plans later</strong>
            <span>Empty workspace</span>
          </header>
          <p>Start with no plans. You can build your catalog from scratch on the Plans page.</p>
        </button>
      </div>
    </div>
  );
}

export function validatePlansStep(draft: OnboardingDraft) {
  return draft.plans.mode !== null;
}
