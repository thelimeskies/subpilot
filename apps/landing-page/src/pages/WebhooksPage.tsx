import { motion } from "framer-motion";
import { CheckCircle2, FileCheck2, RefreshCcw, ShieldCheck, Webhook } from "lucide-react";
import {
  PageHero,
  ContentSection,
  FeatureGrid,
  BulletList,
  CtaBand
} from "../components/PageBuilders";
import { webhookEvent } from "../lib/data";
import { fadeUp, inView } from "../lib/motion";

const events = [
  { name: "subscription.created", desc: "A subscription was created in any state." },
  { name: "subscription.activated", desc: "Active reached. Access can be granted." },
  { name: "subscription.past_due", desc: "Renewal failed. Recovery flow has begun." },
  { name: "subscription.recovered", desc: "Past due cleared. Subscription is active again." },
  { name: "subscription.paused", desc: "Subscription paused without cancellation." },
  { name: "subscription.canceled", desc: "Subscription is now terminal." },
  { name: "invoice.paid", desc: "Invoice transitioned to paid." },
  { name: "invoice.payment_failed", desc: "A renewal charge failed." },
  { name: "portal.session.completed", desc: "Customer finished a portal session." }
];

export function WebhooksPage() {
  return (
    <>
      <PageHero
        eyebrow="Webhooks"
        crumbs={[
          { label: "Developers", to: "/developers" },
          { label: "Webhooks" }
        ]}
        title={
          <>
            Signed events —{" "}
            <span className="lp-hero__title-accent">replayable, idempotent, audited.</span>
          </>
        }
        lede="Webhooks are the contract between SubPilot and your systems. Every event is signed, every delivery is logged, and every payload is replayable from the console."
        primaryCta={{ label: "View delivery log", to: "/merchant" }}
        secondaryCta={{ label: "Idempotency guide", to: "/developers/idempotency" }}
        badges={["HMAC signed", "Replay safe", "At-least-once"]}
      />

      <ContentSection
        kicker="A signed event"
        title="What lands at your endpoint."
        lede="Headers carry signature and timestamp. The body is stable JSON with a typed shape per event."
      >
        <motion.div className="lp-dev__webhook lp-dev__webhook--page" variants={fadeUp} {...inView}>
          <div className="lp-dev__webhook-head">
            <Webhook size={14} />
            <strong>POST /webhooks/subpilot</strong>
            <span>Event sample</span>
          </div>
          <pre className="lp-dev__pre">
            <code>{webhookEvent}</code>
          </pre>
        </motion.div>
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="Trust the wire"
        title="Verify, dedupe, and ack — in that order."
      >
        <FeatureGrid
          items={[
            {
              icon: ShieldCheck,
              title: "Signature verification",
              body: "Every delivery includes a timestamped HMAC header. Reject anything that doesn't verify, and you're safe.",
              proof: "X-SubPilot-Signature"
            },
            {
              icon: CheckCircle2,
              title: "Idempotency by event ID",
              body: "Use the event id as your dedupe key. If you already processed it, return 200 and move on.",
              proof: "evt_01HZK4YQX2"
            },
            {
              icon: RefreshCcw,
              title: "Replay tooling",
              body: "Replay any past event from the console with one click. Use it during incidents or migrations.",
              proof: "console → replay"
            },
            {
              icon: FileCheck2,
              title: "Delivery log",
              body: "Every attempt is logged with HTTP status, latency, and response body. No more guessing if it landed.",
              proof: "delivered · 142 ms"
            }
          ]}
        />
      </ContentSection>

      <ContentSection
        kicker="Event catalog"
        title="The events you'll actually subscribe to."
      >
        <motion.div className="lp-event-list" variants={fadeUp} {...inView}>
          {events.map((e) => (
            <div key={e.name} className="lp-event-list__row">
              <code className="lp-mono">{e.name}</code>
              <span>{e.desc}</span>
            </div>
          ))}
        </motion.div>
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="Operational rules"
        title="Built for production reliability, not happy paths only."
      >
        <BulletList
          items={[
            "At-least-once delivery: design your handler to be idempotent. Retries are normal.",
            "Exponential retries on 5xx and timeouts. After exhaustion, alerts fire and the event is replayable.",
            "Tenant-scoped endpoints: separate URLs per environment to keep test and live cleanly isolated.",
            "Versioned payload shape: schema changes are additive. Removed fields go through a deprecation window.",
            "Replay from the console with one click — useful during incidents, migrations, and bug bash days."
          ]}
        />
      </ContentSection>

      <CtaBand
        title="Wire it once, sleep through renewals."
        body="Verify, dedupe, ack — and let the engine drive."
        primary={{ label: "Idempotency guide", to: "/developers/idempotency" }}
        secondary={{ label: "Back to developers", to: "/developers" }}
      />
    </>
  );
}
