import { Compass, Heart, Lightbulb, Target } from "lucide-react";
import {
  PageHero,
  ContentSection,
  FeatureGrid,
  BulletList,
  CtaBand,
  StatGrid
} from "../components/PageBuilders";

export function AboutPage() {
  return (
    <>
      <PageHero
        eyebrow="About SubPilot"
        crumbs={[
          { label: "Company" },
          { label: "About" }
        ]}
        title={
          <>
            Subscription operations should be{" "}
            <span className="lp-hero__title-accent">a product, not a project.</span>
          </>
        }
        lede="We build SubPilot for finance, ops, support, and developer teams who are tired of bespoke billing infrastructure. Plans, lifecycle, dunning, portal, and signed webhooks — in one place."
        primaryCta={{ label: "Open the console", to: "/merchant" }}
        secondaryCta={{ label: "Read the docs", to: "/developers" }}
        badges={["Independent", "Multi-tenant by default", "Built for ops"]}
      />

      <ContentSection
        kicker="What we believe"
        title="Four convictions that shape every line of code."
      >
        <FeatureGrid
          items={[
            {
              icon: Compass,
              title: "Billing is a state machine.",
              body: "Subscriptions live in explicit states. Every transition is audited, idempotent, and reversible where it should be."
            },
            {
              icon: Heart,
              title: "Recovery is a product surface.",
              body: "Self-service update sessions and bank-aware retries recover more revenue than ops queues ever will."
            },
            {
              icon: Lightbulb,
              title: "Developers ship faster with shape.",
              body: "Signed events, idempotency keys, and a tight resource model beat tutorials and stack-overflow archeology."
            },
            {
              icon: Target,
              title: "Operators deserve better tools.",
              body: "Filters, timelines, replay buttons, and audit logs are first-class — not an afterthought wrapped in spreadsheets."
            }
          ]}
        />
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="What we ship"
        title="A focused product surface, not a kitchen sink."
      >
        <BulletList
          items={[
            "Plan catalog with version-controlled prices and proration-safe edits.",
            "Ten-state subscription lifecycle with audited, idempotent transitions.",
            "Invoicing and tokenized renewal charges with refunds and credits as first-class operations.",
            "Dunning and recovery with smart retries, customer comms, and policy-driven final actions.",
            "Customer self-service portal for card update, pause, resume, and cancellation.",
            "Signed developer webhooks, replay tooling, and a delivery log developers can trust.",
            "Multi-tenant operations with environment switcher, RBAC, and an actor-stamped audit trail."
          ]}
        />
      </ContentSection>

      <ContentSection
        kicker="The shape"
        title="Numbers that describe how we operate."
      >
        <StatGrid
          stats={[
            { value: "10", label: "Subscription states", hint: "fully audited" },
            { value: "5", label: "Default retry steps", hint: "fully configurable" },
            { value: "100%", label: "Idempotent writes", hint: "safe retries everywhere" },
            { value: "3", label: "First-class personas", hint: "ops, devs, customers" }
          ]}
        />
      </ContentSection>

      <CtaBand
        title="Recurring billing without recurring rebuilds."
        body="Spend your engineering on product, not on patching billing."
        primary={{ label: "Open the console", to: "/merchant" }}
        secondary={{ label: "Talk to us", to: "/contact" }}
      />
    </>
  );
}
