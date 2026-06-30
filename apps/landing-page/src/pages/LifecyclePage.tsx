import { motion } from "framer-motion";
import { Activity, ShieldCheck, History, Workflow } from "lucide-react";
import {
  PageHero,
  ContentSection,
  FeatureGrid,
  BulletList,
  CtaBand
} from "../components/PageBuilders";
import { lifecycleNodes } from "../lib/data";
import { fadeUp, stagger, inView } from "../lib/motion";

export function LifecyclePage() {
  return (
    <>
      <PageHero
        eyebrow="Subscription lifecycle"
        crumbs={[
          { label: "Product", to: "/" },
          { label: "Lifecycle" }
        ]}
        title={
          <>
            A ten-state machine —{" "}
            <span className="lp-hero__title-accent">every transition auditable.</span>
          </>
        }
        lede="Subscriptions are a state machine, not a flag. SubPilot models ten explicit states with idempotent transitions, actor-stamped audit logs, and reversible recovery paths."
        primaryCta={{ label: "See it in the console", to: "/merchant" }}
        secondaryCta={{ label: "Read recovery flow", to: "/recovery" }}
        badges={["10 states", "Idempotent transitions", "Reversible where it should be"]}
      />

      <ContentSection
        tone="ink"
        kicker="The states"
        title="Ten subscription states, color-coded by tone."
        lede="Each state names a real-world condition the team needs to act on."
      >
        <motion.div className="lp-state-grid" variants={stagger} {...inView}>
          {lifecycleNodes.map((node) => (
            <motion.article
              key={node.id}
              className="lp-state-card"
              data-tone={node.tone}
              variants={fadeUp}
            >
              <header>
                <span className="lp-state-card__dot" aria-hidden="true" />
                <strong>{node.label}</strong>
                <code className="lp-mono">{node.id}</code>
              </header>
              <p>{node.description}</p>
            </motion.article>
          ))}
        </motion.div>
      </ContentSection>

      <ContentSection
        kicker="Transition rules"
        title="What can move where, and what stays locked."
        lede="The engine validates every transition. Illegal moves never reach the database."
      >
        <FeatureGrid
          items={[
            {
              icon: Workflow,
              title: "Forward paths",
              body: "incomplete → trialing → active is the happy path. Each step requires a verified payment or trial activation event.",
              proof: "incomplete → trialing → active"
            },
            {
              icon: Activity,
              title: "Recovery loop",
              body: "active → past_due → active is fully recoverable. Customers can update cards and the next retry succeeds without ops intervention.",
              proof: "active ↔ past_due"
            },
            {
              icon: ShieldCheck,
              title: "Terminal states",
              body: "canceled and expired are terminal. unpaid is reachable only after dunning is exhausted, never directly.",
              proof: "canceled · expired · unpaid"
            },
            {
              icon: History,
              title: "Audit on every move",
              body: "Each transition stamps actor, reason, source event, and before/after state. Replay any history without losing context.",
              proof: "actor · reason · source"
            }
          ]}
        />
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="Why it matters"
        title="Predictable billing means fewer 2 a.m. pages."
      >
        <BulletList
          items={[
            "Idempotent transitions: replaying a webhook never double-charges or double-cancels.",
            "Reversibility: paused, canceling, and past_due can return to active with a single, audited action.",
            "Reason codes: every transition explains itself — system retry, customer pause, admin override.",
            "Multi-tenant: states are scoped per merchant and environment with strict isolation.",
            "Operator UX: the merchant console exposes states with timeline filters and bulk actions."
          ]}
        />
      </ContentSection>

      <CtaBand
        title="Stop guessing what state a subscription is in."
        body="See the timeline, replay events, and trust the transition log."
        primary={{ label: "Open the console", to: "/merchant" }}
        secondary={{ label: "View recovery", to: "/recovery" }}
      />
    </>
  );
}
