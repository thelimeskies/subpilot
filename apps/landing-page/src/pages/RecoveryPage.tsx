import { motion } from "framer-motion";
import { AlarmClock, MailCheck, RefreshCw, ShieldCheck, Sparkles, BellOff } from "lucide-react";
import {
  PageHero,
  ContentSection,
  FeatureGrid,
  BulletList,
  CtaBand,
  StatGrid
} from "../components/PageBuilders";
import { dunningSteps } from "../lib/data";
import { fadeUp, stagger, inView } from "../lib/motion";

export function RecoveryPage() {
  return (
    <>
      <PageHero
        eyebrow="Dunning and recovery"
        crumbs={[
          { label: "Product", to: "/" },
          { label: "Recovery" }
        ]}
        title={
          <>
            Recover failed renewals —{" "}
            <span className="lp-hero__title-accent">without writing a cron job.</span>
          </>
        }
        lede="Smart retries, customer recovery emails, secure update-card sessions, and a final-action policy in one builder. Recovery is built in, not bolted on."
        primaryCta={{ label: "See the queue", to: "/merchant" }}
        secondaryCta={{ label: "How webhooks help", to: "/developers/webhooks" }}
        badges={["Bank-aware retries", "Self-serve recovery", "Policy-driven finale"]}
      />

      <ContentSection
        kicker="The recovery flow"
        title="Five steps from failure to outcome."
        lede="Configure once at the plan level. The engine handles the rest, while operators see the timeline live."
      >
        <motion.ol className="lp-timeline" variants={stagger} {...inView}>
          {dunningSteps.map((step, idx) => (
            <motion.li
              key={step.label}
              className="lp-timeline__step"
              data-tone={step.tone}
              variants={fadeUp}
            >
              <span className="lp-timeline__index lp-mono">{String(idx + 1).padStart(2, "0")}</span>
              <div>
                <span className="lp-timeline__day lp-mono">{step.day}</span>
                <strong>{step.label}</strong>
                <p>{step.detail}</p>
              </div>
            </motion.li>
          ))}
        </motion.ol>
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="Why it works"
        title="Recovery is a product surface, not a script."
      >
        <FeatureGrid
          items={[
            {
              icon: AlarmClock,
              title: "Smart retry schedules",
              body: "Bank-aware timing avoids back-to-back declines. Configurable per plan with sensible defaults that just work.",
              proof: "Day 0 · 1 · 3 · 5 · 7"
            },
            {
              icon: MailCheck,
              title: "Customer comms",
              body: "Branded recovery emails fire automatically with secure portal links — no template wrangling required.",
              proof: "email → portal"
            },
            {
              icon: RefreshCw,
              title: "Tokenized retries",
              body: "Renewals replay against the stored card token. Raw card data never enters SubPilot or your servers.",
              proof: "token → charge"
            },
            {
              icon: ShieldCheck,
              title: "Policy-driven final action",
              body: "Decide upfront: cancel, keep unpaid, or pause. The engine enforces the policy when the schedule is exhausted.",
              proof: "cancel · unpaid · pause"
            },
            {
              icon: Sparkles,
              title: "Self-serve update sessions",
              body: "Secure portal sessions let customers update their card without contacting support — high recovery, low ops cost.",
              proof: "session → resolved"
            },
            {
              icon: BellOff,
              title: "Operator overrides",
              body: "Admins can pause, retry now, or cancel from the recovery queue with full audit on every override.",
              proof: "override → audited"
            }
          ]}
        />
      </ContentSection>

      <ContentSection
        kicker="By the numbers"
        title="Operators see recovery as a metric, not a guess."
      >
        <StatGrid
          stats={[
            { value: "62%", label: "Typical recovery rate", hint: "with self-serve update card" },
            { value: "5", label: "Default retry steps", hint: "fully configurable" },
            { value: "<2 m", label: "Median time to retry", hint: "after a successful card update" },
            { value: "0", label: "Manual retries needed", hint: "the engine drives the flow" }
          ]}
        />
      </ContentSection>

      <ContentSection
        kicker="What ops sees"
        title="A queue, a timeline, and zero spreadsheets."
      >
        <BulletList
          items={[
            "Recovery queue with filters by plan, age in past_due, and retry attempt count.",
            "Per-subscription timeline with every retry, email send, portal session, and final action.",
            "Bulk actions to send portal links, retry now, or pause across selected subscriptions.",
            "Webhook replay to verify downstream systems caught up after recovery.",
            "Audit log of every override with actor, reason, and outcome."
          ]}
        />
      </ContentSection>

      <CtaBand
        title="Get back the revenue you already earned."
        body="Recovery in production should not require a sprint."
        primary={{ label: "Open the recovery queue", to: "/merchant" }}
        secondary={{ label: "Read the lifecycle", to: "/lifecycle" }}
      />
    </>
  );
}
