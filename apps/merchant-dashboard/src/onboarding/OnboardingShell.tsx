import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@subpilot/ui";
import { ArrowLeft, ArrowRight, Check, LogOut } from "lucide-react";
import { useAuth, type MerchantUser } from "../auth/AuthContext";
import { completeMerchantOnboarding } from "../api/onboarding";
import { useFeedback } from "../feedback/ActionFeedback";
import {
  STEP_ORDER,
  useOnboardingDraft,
  type OnboardingDraft,
  type StepId,
  type TeamInvite
} from "./useOnboardingDraft";
import { BusinessProfileStep, validateBusinessStep } from "./steps/BusinessProfileStep";
import { KycDocumentsStep, validateKycStep } from "./steps/KycDocumentsStep";
import { PayoutBankStep, validatePayoutStep } from "./steps/PayoutBankStep";
import { BrandingStep, validateBrandingStep } from "./steps/BrandingStep";
import { PlanSetupStep, validatePlansStep } from "./steps/PlanSetupStep";
import { MfaEnrollStep, validateMfaStep } from "./steps/MfaEnrollStep";
import { InviteTeamStep, validateTeamStep } from "./steps/InviteTeamStep";
import { FinishStep, validateFinishStep } from "./steps/FinishStep";

interface StepConfig {
  id: StepId;
  label: string;
  description: string;
  validate: (draft: OnboardingDraft) => boolean;
  optional?: boolean;
}

const STEP_META: StepConfig[] = [
  {
    id: "business",
    label: "Business profile",
    description: "Legal name, country, industry",
    validate: validateBusinessStep
  },
  {
    id: "kyc",
    label: "Verification",
    description: "RC number & documents",
    validate: validateKycStep
  },
  {
    id: "payout",
    label: "Payout bank",
    description: "Settlements & account",
    validate: validatePayoutStep
  },
  {
    id: "branding",
    label: "Branding",
    description: "Color, logo, portal URL",
    validate: validateBrandingStep
  },
  {
    id: "plans",
    label: "Plans setup",
    description: "Import samples or skip",
    validate: validatePlansStep
  },
  {
    id: "mfa",
    label: "Two-factor",
    description: "Protect your workspace",
    validate: validateMfaStep,
    optional: true
  },
  {
    id: "team",
    label: "Invite team",
    description: "Optional teammates",
    validate: validateTeamStep,
    optional: true
  },
  {
    id: "finish",
    label: "Finish",
    description: "Review and launch",
    validate: validateFinishStep
  }
];

export function OnboardingShell() {
  const { user } = useAuth();
  if (!user) return null;
  return <OnboardingShellInner user={user} />;
}

function OnboardingShellInner({ user }: { user: MerchantUser }) {
  const { refreshUser, signOut } = useAuth();
  const { notify } = useFeedback();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);

  const onboarding = useOnboardingDraft({
    userId: user.id,
    email: user.email,
    orgName: user.orgName,
    name: user.name
  });
  const { draft, updateSection, setTeam, setStep, markStepCompleted, reset } = onboarding;

  const currentIndex = useMemo(
    () => Math.max(0, STEP_ORDER.indexOf(draft.currentStepId)),
    [draft.currentStepId]
  );
  const currentMeta = STEP_META[currentIndex];

  // If user has already completed onboarding, bounce them to overview.
  useEffect(() => {
    if (user.onboardingComplete) {
      navigate("/", { replace: true });
    }
  }, [user.onboardingComplete, navigate]);

  const stepIsValid = currentMeta.validate(draft);
  const isLast = currentIndex === STEP_ORDER.length - 1;

  function handleBack() {
    if (currentIndex === 0) return;
    const prevId = STEP_ORDER[currentIndex - 1];
    setStep(prevId);
  }

  async function handleContinue() {
    if (submitting) return;
    if (!stepIsValid && !currentMeta.optional) {
      notify({
        tone: "warning",
        title: "Almost there",
        description: "Complete the required fields on this step to continue."
      });
      return;
    }
    markStepCompleted(currentMeta.id);
    if (isLast) {
      await handleFinish();
      return;
    }
    const nextId = STEP_ORDER[currentIndex + 1];
    setStep(nextId);
    notify({ tone: "info", title: "Step saved", description: `${currentMeta.label} saved.` });
  }

  async function handleFinish() {
    setSubmitting(true);
    try {
      const result = await completeMerchantOnboarding(draft);
      refreshUser(result.user);
      notify({
        tone: "success",
        title: "Workspace ready",
        description: result.importedPlans.length
          ? `Imported ${result.importedPlans.length} sample plans and saved your setup.`
          : "Your setup has been saved."
      });
      reset();
      navigate("/", { replace: true });
    } catch (err) {
      const reason = err instanceof Error ? err.message : "Could not complete onboarding.";
      notify({
        tone: "danger",
        title: "Could not complete onboarding",
        description: reason
      });
    } finally {
      setSubmitting(false);
    }
  }

  function handleSaveAndExit() {
    notify({
      tone: "info",
      title: "Progress saved",
      description: "Resume your setup any time — we'll pick up where you left off."
    });
    signOut();
    navigate("/sign-in", { replace: true });
  }

  function jumpToStep(id: StepId) {
    const targetIndex = STEP_ORDER.indexOf(id);
    if (targetIndex < 0) return;
    // Allow jumping back to any visited step or the immediate next step if current is valid.
    if (
      targetIndex <= currentIndex ||
      draft.completedSteps.includes(STEP_ORDER[targetIndex - 1])
    ) {
      setStep(id);
    }
  }

  function renderActiveStep() {
    switch (currentMeta.id) {
      case "business":
        return <BusinessProfileStep draft={draft} updateSection={updateSection} />;
      case "kyc":
        return <KycDocumentsStep draft={draft} updateSection={updateSection} />;
      case "payout":
        return <PayoutBankStep draft={draft} updateSection={updateSection} />;
      case "branding":
        return <BrandingStep draft={draft} updateSection={updateSection} />;
      case "plans":
        return <PlanSetupStep draft={draft} updateSection={updateSection} />;
      case "mfa":
        return <MfaEnrollStep draft={draft} updateSection={updateSection} />;
      case "team":
        return <InviteTeamStep draft={draft} setTeam={(team: TeamInvite[]) => setTeam(team)} />;
      case "finish":
        return <FinishStep draft={draft} />;
      default:
        return null;
    }
  }

  return (
    <div className="mer-onboarding">
      <header className="mer-onboarding__topbar">
        <div className="mer-onboarding__brand">
          <span className="mer-auth__mark" aria-hidden="true">S</span>
          <span className="mer-onboarding__brand-text">
            <strong>SubPilot</strong>
            <small>Workspace setup</small>
          </span>
        </div>
        <div className="mer-onboarding__topbar-actions">
          <span className="mer-onboarding__user">
            <strong>{user.name}</strong>
            <small>{user.orgName}</small>
          </span>
          <Button type="button" variant="ghost" icon={<LogOut size={14} />} onClick={handleSaveAndExit}>
            Save &amp; exit
          </Button>
        </div>
      </header>

      <div className="mer-onboarding__body">
        <aside className="mer-onboarding__rail" aria-label="Setup steps">
          <ol>
            {STEP_META.map((step, idx) => {
              const completed = draft.completedSteps.includes(step.id);
              const isActive = step.id === currentMeta.id;
              const isUnlocked =
                idx <= currentIndex ||
                draft.completedSteps.includes(STEP_ORDER[idx - 1] as StepId);
              return (
                <li
                  key={step.id}
                  className={`mer-onboarding__step${isActive ? " is-active" : ""}${
                    completed ? " is-done" : ""
                  }${!isUnlocked ? " is-locked" : ""}`}
                >
                  <button
                    type="button"
                    onClick={() => jumpToStep(step.id)}
                    disabled={!isUnlocked}
                  >
                    <span className="mer-onboarding__step-marker" aria-hidden="true">
                      {completed ? <Check size={12} /> : idx + 1}
                    </span>
                    <span className="mer-onboarding__step-text">
                      <strong>{step.label}</strong>
                      <small>{step.description}</small>
                    </span>
                  </button>
                </li>
              );
            })}
          </ol>
        </aside>

        <main className="mer-onboarding__pane">
          <div className="mer-onboarding__progress" aria-hidden="true">
            <div
              className="mer-onboarding__progress-fill"
              style={{ width: `${((currentIndex + 1) / STEP_ORDER.length) * 100}%` }}
            />
          </div>

          <div className="mer-onboarding__content">{renderActiveStep()}</div>

          <footer className="mer-onboarding__footer">
            <Button
              type="button"
              variant="ghost"
              icon={<ArrowLeft size={14} />}
              onClick={handleBack}
              disabled={currentIndex === 0}
            >
              Back
            </Button>
            <div className="mer-onboarding__footer-right">
              {currentMeta.optional && !stepIsValid ? (
                <Button type="button" variant="ghost" onClick={handleContinue}>
                  Skip for now
                </Button>
              ) : null}
              <Button
                type="button"
                icon={<ArrowRight size={14} />}
                onClick={handleContinue}
                disabled={submitting || (!stepIsValid && !currentMeta.optional)}
              >
                {isLast && submitting ? "Saving setup..." : isLast ? "Go to dashboard" : "Continue"}
              </Button>
            </div>
          </footer>
        </main>
      </div>
    </div>
  );
}
