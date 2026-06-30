import { motion } from "framer-motion";
import { CheckCircle2, KeyRound, RefreshCcw, ShieldCheck } from "lucide-react";
import {
  PageHero,
  ContentSection,
  FeatureGrid,
  BulletList,
  CtaBand
} from "../components/PageBuilders";
import { fadeUp, inView } from "../lib/motion";

const idempotentSnippet = `// Same key → same result. Always.
await client.subscriptions.create(
  {
    customer: { email: "ada@example.com" },
    items: [{ plan_id: "plan_pro_monthly" }],
  },
  { idempotencyKey: "sub-user-123-pro" }
);

// Retry on timeout — safe.
await client.subscriptions.create(
  {
    customer: { email: "ada@example.com" },
    items: [{ plan_id: "plan_pro_monthly" }],
  },
  { idempotencyKey: "sub-user-123-pro" }
); // → returns the original subscription, no double charge.`;

export function IdempotencyPage() {
  return (
    <>
      <PageHero
        eyebrow="Idempotency"
        crumbs={[
          { label: "Developers", to: "/developers" },
          { label: "Idempotency" }
        ]}
        title={
          <>
            Safe retries —{" "}
            <span className="lp-hero__title-accent">by design.</span>
          </>
        }
        lede="Pass an idempotency key on every write. SubPilot guarantees the same outcome no matter how many times you retry — across timeouts, network partitions, and webhook replays."
        primaryCta={{ label: "Webhooks reference", to: "/developers/webhooks" }}
        secondaryCta={{ label: "Back to developers", to: "/developers" }}
        badges={["24-hour key window", "Same key, same result", "Replay-safe"]}
      />

      <ContentSection
        kicker="The contract"
        title="One key. One outcome. Forever (or at least 24 hours)."
      >
        <motion.div className="lp-dev__code lp-dev__code--page" variants={fadeUp} {...inView}>
          <div className="lp-dev__tabs">
            <KeyRound size={14} className="lp-dev__tabs-icon" />
            <span className="lp-dev__tab" data-active="true">
              Idempotency-Key
            </span>
          </div>
          <pre className="lp-dev__pre">
            <code>{idempotentSnippet}</code>
          </pre>
        </motion.div>
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="Why it matters"
        title="Real networks fail. Idempotency turns failures into no-ops."
      >
        <FeatureGrid
          items={[
            {
              icon: RefreshCcw,
              title: "Safe client retries",
              body: "Network timeouts no longer mean duplicate subscriptions or double charges. Retry confidently.",
              proof: "timeout → retry → same result"
            },
            {
              icon: ShieldCheck,
              title: "Webhook replay safety",
              body: "Use the event id as your handler's dedupe key. Replays during incidents are completely safe.",
              proof: "evt_id → process once"
            },
            {
              icon: CheckCircle2,
              title: "Engine-level guarantee",
              body: "The same key always returns the same result, even across deploys and process restarts. We persist the response.",
              proof: "persisted · cached"
            },
            {
              icon: KeyRound,
              title: "24-hour key window",
              body: "Idempotency keys live for 24 hours. After that, the key may be re-used for a different intent.",
              proof: "≤ 24h"
            }
          ]}
        />
      </ContentSection>

      <ContentSection
        kicker="Choose good keys"
        title="A few rules of thumb for naming idempotency keys."
      >
        <BulletList
          items={[
            "Pick a key that is unique to the user intent: sub-{user_id}-{plan_id} works well for subscription creates.",
            "Don't reuse the same key for different intents — it will return the original response, not your new one.",
            "For webhooks, use the event id as your dedupe key. SubPilot guarantees event ids are stable.",
            "Generate keys client-side before the request, not after — so retries can replay the same key.",
            "Treat idempotency as the default for every write; do not opt out, even for low-risk endpoints."
          ]}
        />
      </ContentSection>

      <CtaBand
        title="Stop fearing the retry button."
        body="Idempotency keys make billing systems boring — in the best way."
        primary={{ label: "Read webhooks", to: "/developers/webhooks" }}
        secondary={{ label: "Back to developers", to: "/developers" }}
      />
    </>
  );
}
