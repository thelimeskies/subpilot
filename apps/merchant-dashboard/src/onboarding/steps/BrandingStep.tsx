import { useRef, type ChangeEvent } from "react";
import { Button, Field, TextInput } from "@subpilot/ui";
import { ImagePlus, Palette } from "lucide-react";
import type { OnboardingDraft } from "../useOnboardingDraft";
import { useFeedback } from "../../feedback/ActionFeedback";
import { customerPortalUrl } from "../../lib/urls";

interface Props {
  draft: OnboardingDraft;
  updateSection: <K extends "branding">(section: K, patch: Partial<OnboardingDraft[K]>) => void;
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
}

const PRESET_COLORS = ["#056058", "#1f7a52", "#1f4d7a", "#7a4d1f", "#7a1f4d", "#262626"];

export function BrandingStep({ draft, updateSection }: Props) {
  const { notify } = useFeedback();
  const logoRef = useRef<HTMLInputElement | null>(null);

  async function pickLogo(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;
    if (file.size > 1.5 * 1024 * 1024) {
      notify({ tone: "warning", title: "Logo too large", description: "Keep logos under 1.5 MB." });
      return;
    }
    const data = await readFileAsDataUrl(file);
    updateSection("branding", { logoData: data });
    notify({ tone: "success", title: "Logo uploaded", description: "We'll show this on the portal and emails." });
  }

  function handleSubdomain(value: string) {
    const slug = value
      .toLowerCase()
      .replace(/[^a-z0-9-]+/g, "-")
      .replace(/-+/g, "-")
      .replace(/(^-|-$)/g, "")
      .slice(0, 32);
    updateSection("branding", { subdomain: slug });
  }

  return (
    <div className="mer-step">
      <header className="mer-step__head">
        <h2>Brand your customer experience</h2>
        <p>These show on the customer portal, hosted invoices, and dunning emails.</p>
      </header>

      <div className="mer-step__grid mer-step__grid--two">
        <div className="mer-brand-card">
          <span className="mer-brand-card__label">Primary color</span>
          <div className="mer-brand-card__swatches">
            {PRESET_COLORS.map((color) => (
              <button
                key={color}
                type="button"
                className={`mer-brand-card__swatch${draft.branding.primaryColor === color ? " is-selected" : ""}`}
                style={{ background: color }}
                onClick={() => updateSection("branding", { primaryColor: color })}
                aria-label={`Pick color ${color}`}
              />
            ))}
            <label className="mer-brand-card__custom">
              <Palette size={14} aria-hidden="true" />
              <input
                type="color"
                value={draft.branding.primaryColor}
                onChange={(e) => updateSection("branding", { primaryColor: e.target.value })}
                aria-label="Custom color"
              />
            </label>
          </div>

          <span className="mer-brand-card__label" style={{ marginTop: 16 }}>
            Logo
          </span>
          <div className="mer-brand-card__logo">
            <div className="mer-brand-card__logo-preview" style={{ background: draft.branding.primaryColor }}>
              {draft.branding.logoData ? (
                <img src={draft.branding.logoData} alt="Logo preview" />
              ) : (
                <span>{draft.business.tradingName?.[0] ?? "S"}</span>
              )}
            </div>
            <Button
              type="button"
              variant="secondary"
              icon={<ImagePlus size={16} />}
              onClick={() => logoRef.current?.click()}
            >
              {draft.branding.logoData ? "Replace logo" : "Upload logo"}
            </Button>
            <input ref={logoRef} type="file" accept="image/*" hidden onChange={pickLogo} />
          </div>
        </div>

        <div className="mer-brand-card">
          <Field
            label="Portal URL slug"
            hint="Your customers will use this link to access self-service."
          >
            <TextInput
              value={draft.branding.subdomain}
              onChange={(e) => handleSubdomain(e.target.value)}
              placeholder="your-brand"
              required
            />
          </Field>
          <div className="mer-brand-card__url">
            <span>{customerPortalUrl(draft.branding.subdomain)}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export function validateBrandingStep(draft: OnboardingDraft) {
  return draft.branding.subdomain.trim().length >= 3 && /^[a-z0-9-]+$/.test(draft.branding.subdomain);
}
