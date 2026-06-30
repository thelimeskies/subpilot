import { useCallback, useEffect, useMemo, useRef } from "react";
import { useLocalStorage } from "../hooks/useLocalStorage";
import { useDebounced } from "../hooks/useDebounced";
import {
  clearMerchantOnboardingDraft,
  loadMerchantOnboardingDraft,
  saveMerchantOnboardingDraft
} from "../api/onboarding";

export type StepId =
  | "business"
  | "kyc"
  | "payout"
  | "branding"
  | "plans"
  | "mfa"
  | "team"
  | "finish";

export const STEP_ORDER: StepId[] = [
  "business",
  "kyc",
  "payout",
  "branding",
  "plans",
  "mfa",
  "team",
  "finish"
];

export interface BusinessProfile {
  legalName: string;
  tradingName: string;
  country: string;
  industry: string;
  website: string;
  description: string;
}

export interface KycDocuments {
  rcNumber: string;
  directorIdName: string;
  directorIdData: string | null;
  addressProofName: string;
  addressProofData: string | null;
}

export interface PayoutBank {
  bank: string;
  accountNumber: string;
  accountName: string;
  resolved: boolean;
  settlementFrequency: "daily" | "weekly" | "monthly";
}

export interface Branding {
  primaryColor: string;
  logoData: string | null;
  subdomain: string;
}

export interface PlanSetup {
  mode: "import" | "skip" | null;
}

export interface MfaSetup {
  secret: string;
  enabled: boolean;
}

export interface TeamInvite {
  email: string;
  role: "Admin" | "Finance" | "Support" | "Read-only";
}

export interface OnboardingDraft {
  version: 1;
  currentStepId: StepId;
  completedSteps: StepId[];
  business: BusinessProfile;
  kyc: KycDocuments;
  payout: PayoutBank;
  branding: Branding;
  plans: PlanSetup;
  mfa: MfaSetup;
  team: TeamInvite[];
  completed: boolean;
}

const SECRET_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

function deterministicSecret(seed: string) {
  let hash = 5381;
  for (let i = 0; i < seed.length; i += 1) {
    hash = ((hash << 5) + hash + seed.charCodeAt(i)) | 0;
  }
  let value = Math.abs(hash);
  const out: string[] = [];
  for (let i = 0; i < 16; i += 1) {
    out.push(SECRET_ALPHABET[value % SECRET_ALPHABET.length]);
    value = Math.floor(value / 7) + (i + 1) * 31;
  }
  return out.join("");
}

function buildDefaultDraft(seedEmail: string, seedOrgName: string, seedName: string): OnboardingDraft {
  const slug = seedOrgName
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/(^-|-$)/g, "")
    .slice(0, 32) || "your-brand";
  return {
    version: 1,
    currentStepId: "business",
    completedSteps: [],
    business: {
      legalName: seedOrgName,
      tradingName: seedOrgName,
      country: "Nigeria",
      industry: "",
      website: "",
      description: ""
    },
    kyc: {
      rcNumber: "",
      directorIdName: "",
      directorIdData: null,
      addressProofName: "",
      addressProofData: null
    },
    payout: {
      bank: "",
      accountNumber: "",
      accountName: "",
      resolved: false,
      settlementFrequency: "daily"
    },
    branding: {
      primaryColor: "#056058",
      logoData: null,
      subdomain: slug
    },
    plans: { mode: null },
    mfa: { secret: deterministicSecret(seedEmail || seedName || "subpilot"), enabled: false },
    team: [],
    completed: false
  };
}

export function useOnboardingDraft(opts: { userId: string; email: string; orgName: string; name: string }) {
  const storageKey = `subpilot.merchant.onboarding.v1.${opts.userId}`;
  const initial = useMemo(
    () => buildDefaultDraft(opts.email, opts.orgName, opts.name),
    [opts.email, opts.orgName, opts.name]
  );

  // We hold the live state in localStorage for refresh-resume; debounce writes
  // to keep `localStorage.setItem` off the keystroke path.
  const [draft, setDraft, clear] = useLocalStorage<OnboardingDraft>(storageKey, initial);

  // Debounced mirror — used only by consumers who need a stable read; the
  // primary state is `draft`. We still expose this for completeness.
  const debouncedDraft = useDebounced(draft, 250);
  const backendLoadedRef = useRef(false);
  const skipNextBackendSaveRef = useRef(true);

  const update = useCallback(
    <K extends keyof OnboardingDraft>(patch: Partial<OnboardingDraft> | ((prev: OnboardingDraft) => Partial<OnboardingDraft>)) => {
      setDraft((prev) => {
        const computed = typeof patch === "function" ? patch(prev) : patch;
        return { ...prev, ...computed } as OnboardingDraft;
      });
      void ({} as K);
    },
    [setDraft]
  );

  const updateSection = useCallback(
    <K extends "business" | "kyc" | "payout" | "branding" | "plans" | "mfa">(
      section: K,
      patch: Partial<OnboardingDraft[K]>
    ) => {
      setDraft((prev) => ({
        ...prev,
        [section]: { ...prev[section], ...patch }
      }));
    },
    [setDraft]
  );

  const setTeam = useCallback(
    (team: TeamInvite[]) => {
      setDraft((prev) => ({ ...prev, team }));
    },
    [setDraft]
  );

  const setStep = useCallback(
    (stepId: StepId) => {
      setDraft((prev) => ({ ...prev, currentStepId: stepId }));
    },
    [setDraft]
  );

  const markStepCompleted = useCallback(
    (stepId: StepId) => {
      setDraft((prev) => ({
        ...prev,
        completedSteps: prev.completedSteps.includes(stepId)
          ? prev.completedSteps
          : [...prev.completedSteps, stepId]
      }));
    },
    [setDraft]
  );

  const reset = useCallback(() => {
    clear();
    void clearMerchantOnboardingDraft().catch(() => undefined);
  }, [clear]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const remoteDraft = await loadMerchantOnboardingDraft();
        if (cancelled) return;
        if (remoteDraft?.version === 1) {
          skipNextBackendSaveRef.current = true;
          setDraft(remoteDraft);
        }
      } catch {
        // Local storage remains the offline/legacy fallback.
      } finally {
        if (!cancelled) backendLoadedRef.current = true;
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [setDraft]);

  useEffect(() => {
    if (!backendLoadedRef.current) return;
    if (skipNextBackendSaveRef.current) {
      skipNextBackendSaveRef.current = false;
      return;
    }
    void saveMerchantOnboardingDraft(debouncedDraft).catch(() => undefined);
  }, [debouncedDraft]);

  // Defensive bootstrap: if a stored draft predates this user/org rename,
  // patch the legalName/tradingName/subdomain seed values once.
  const bootstrappedRef = useRef(false);
  useEffect(() => {
    if (bootstrappedRef.current) return;
    bootstrappedRef.current = true;
    setDraft((prev) => {
      if (prev.business.legalName) return prev;
      return { ...prev, business: { ...prev.business, legalName: opts.orgName, tradingName: opts.orgName } };
    });
  }, [opts.orgName, setDraft]);

  return {
    draft,
    debouncedDraft,
    update,
    updateSection,
    setTeam,
    setStep,
    markStepCompleted,
    reset
  };
}
