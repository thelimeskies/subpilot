import { api } from "./client";
import type { MerchantUser } from "../auth/AuthContext";
import type { OnboardingDraft } from "../onboarding/useOnboardingDraft";

export interface CompleteOnboardingResponse {
  ok: true;
  user: MerchantUser;
  importedPlans: string[];
  invitedTeam: string[];
}

export async function completeMerchantOnboarding(
  draft: OnboardingDraft
): Promise<CompleteOnboardingResponse> {
  return api.post<CompleteOnboardingResponse>("/onboarding/complete/", {
    business: draft.business,
    kyc: draft.kyc,
    payout: draft.payout,
    branding: draft.branding,
    plans: draft.plans,
    mfa: draft.mfa,
    team: draft.team
  });
}

export async function loadMerchantOnboardingDraft(): Promise<OnboardingDraft | null> {
  const body = await api.get<{ draft: OnboardingDraft | null }>("/onboarding/draft/");
  return body.draft;
}

export async function saveMerchantOnboardingDraft(draft: OnboardingDraft): Promise<OnboardingDraft> {
  const body = await api.patch<{ ok: true; draft: OnboardingDraft }>("/onboarding/draft/", { draft });
  return body.draft;
}

export async function clearMerchantOnboardingDraft(): Promise<void> {
  await api.delete("/onboarding/draft/");
}

export interface ResolvePayoutAccountResponse {
  ok: true;
  accountName: string;
  bankName: string;
  bankCode: string;
  raw: unknown;
}

export async function resolvePayoutAccount(input: {
  bank: string;
  accountNumber: string;
}): Promise<ResolvePayoutAccountResponse> {
  return api.post<ResolvePayoutAccountResponse>("/nomba/bank-account/lookup/", input);
}
