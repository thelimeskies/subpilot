import { useRef, type ChangeEvent } from "react";
import { Button, Field, TextInput } from "@subpilot/ui";
import { FileText, Upload } from "lucide-react";
import type { OnboardingDraft } from "../useOnboardingDraft";
import { useFeedback } from "../../feedback/ActionFeedback";

interface Props {
  draft: OnboardingDraft;
  updateSection: <K extends "kyc">(section: K, patch: Partial<OnboardingDraft[K]>) => void;
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

export function KycDocumentsStep({ draft, updateSection }: Props) {
  const { notify } = useFeedback();
  const directorRef = useRef<HTMLInputElement | null>(null);
  const addressRef = useRef<HTMLInputElement | null>(null);

  async function pickFile(
    field: "directorId" | "addressProof",
    event: ChangeEvent<HTMLInputElement>
  ) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 4 * 1024 * 1024) {
      notify({ tone: "warning", title: "File too large", description: "Keep documents under 4 MB." });
      return;
    }
    const data = await readFileAsDataUrl(file);
    if (field === "directorId") {
      updateSection("kyc", { directorIdName: file.name, directorIdData: data });
    } else {
      updateSection("kyc", { addressProofName: file.name, addressProofData: data });
    }
    notify({
      tone: "success",
      title: "Document uploaded",
      description: `${file.name} is ready for review.`
    });
  }

  return (
    <div className="mer-step">
      <header className="mer-step__head">
        <h2>Verify your business</h2>
        <p>We use this to enable real payouts. In demo mode, files stay on your device.</p>
      </header>

      <div className="mer-step__grid">
        <Field label="Registration / RC number">
          <TextInput
            value={draft.kyc.rcNumber}
            onChange={(e) => updateSection("kyc", { rcNumber: e.target.value })}
            placeholder="e.g. RC-1234567"
            required
          />
        </Field>

        <div className="mer-upload">
          <span className="mer-upload__label">Director ID (passport / driver's license)</span>
          <div className="mer-upload__row">
            <Button
              type="button"
              variant="secondary"
              icon={<Upload size={16} />}
              onClick={() => directorRef.current?.click()}
            >
              {draft.kyc.directorIdName ? "Replace file" : "Upload file"}
            </Button>
            <span className="mer-upload__hint">
              {draft.kyc.directorIdName ? (
                <>
                  <FileText size={14} aria-hidden="true" /> {draft.kyc.directorIdName}
                </>
              ) : (
                "PDF, JPG or PNG · up to 4 MB"
              )}
            </span>
          </div>
          <input
            ref={directorRef}
            type="file"
            accept="image/*,application/pdf"
            hidden
            onChange={(e) => pickFile("directorId", e)}
          />
        </div>

        <div className="mer-upload">
          <span className="mer-upload__label">Proof of address (utility bill, lease)</span>
          <div className="mer-upload__row">
            <Button
              type="button"
              variant="secondary"
              icon={<Upload size={16} />}
              onClick={() => addressRef.current?.click()}
            >
              {draft.kyc.addressProofName ? "Replace file" : "Upload file"}
            </Button>
            <span className="mer-upload__hint">
              {draft.kyc.addressProofName ? (
                <>
                  <FileText size={14} aria-hidden="true" /> {draft.kyc.addressProofName}
                </>
              ) : (
                "PDF, JPG or PNG · up to 4 MB"
              )}
            </span>
          </div>
          <input
            ref={addressRef}
            type="file"
            accept="image/*,application/pdf"
            hidden
            onChange={(e) => pickFile("addressProof", e)}
          />
        </div>
      </div>
    </div>
  );
}

export function validateKycStep(draft: OnboardingDraft) {
  return (
    draft.kyc.rcNumber.trim().length >= 3 &&
    Boolean(draft.kyc.directorIdData) &&
    Boolean(draft.kyc.addressProofData)
  );
}
