import {
  Layers,
  Repeat,
  Percent,
  Tag,
  Boxes,
  History,
  ListChecks,
  PenLine
} from "lucide-react";
import {
  PageHero,
  ContentSection,
  FeatureGrid,
  BulletList,
  CtaBand,
  StatGrid
} from "../components/PageBuilders";

export function PlansPage() {
  return (
    <>
      <PageHero
        eyebrow="Plans and billing cycles"
        crumbs={[
          { label: "Product", to: "/" },
          { label: "Plans and cycles" }
        ]}
        title={
          <>
            Pricing, packaging, and cycles —{" "}
            <span className="lp-hero__title-accent">version-controlled.</span>
          </>
        }
        lede="Define products, plans, and price versions with monthly, annual, and custom cycles. Trials, setup fees, entitlements, and policy live alongside the price — every change captured in an audit trail."
        primaryCta={{ label: "Open the plan builder", to: "/merchant" }}
        secondaryCta={{ label: "See lifecycle", to: "/lifecycle" }}
        badges={["Draft → Active", "Multi-currency ready", "Proration safe"]}
      />

      <ContentSection
        kicker="What's inside"
        title="Catalog primitives that match how billing actually works."
        lede="Three layers — product, plan, price version — keep packaging tidy without losing flexibility."
      >
        <FeatureGrid
          items={[
            {
              icon: Boxes,
              title: "Products",
              body: "Group plans under a product so reporting, entitlements, and analytics stay coherent over time.",
              proof: "active → archived"
            },
            {
              icon: Layers,
              title: "Plans",
              body: "Trial days, dunning policy, proration, and cancellation rules live on the plan, not duplicated per price.",
              proof: "draft → active"
            },
            {
              icon: Tag,
              title: "Price versions",
              body: "Every price change is a new version. Existing customers stay on their version. New signups get the latest.",
              proof: "amount · interval · currency"
            },
            {
              icon: Repeat,
              title: "Billing cycles",
              body: "Monthly, annual, or custom unit/count. Anchor billing dates with prorated first invoices.",
              proof: "month · year · custom"
            },
            {
              icon: Percent,
              title: "Trials and setup fees",
              body: "Free trials per plan, optional setup fees on first invoice, and grace windows around renewal.",
              proof: "trial → active"
            },
            {
              icon: PenLine,
              title: "Plan policy",
              body: "Set proration mode, dunning policy, and cancellation behavior at the plan level so the engine just follows.",
              proof: "policy → enforced"
            }
          ]}
        />
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="Lifecycle of a plan"
        title="Drafting, activating, and retiring plans without breaking subscribers."
        lede="A plan can be activated only when it has a current price version. Active plans block destructive edits to amount or interval. Archived plans stop new signups but never break existing customers."
      >
        <BulletList
          items={[
            "Draft plans stay editable until activation; preview proration before publishing.",
            "Activated plans are immutable for amount and interval — version a new price instead.",
            "Archived plans block new subscriptions while existing ones renew on their last version.",
            "Plan changes are stamped to an audit log with actor, timestamp, and before/after diff.",
            "Soft-archive prices to roll customers forward over time without sudden jumps."
          ]}
        />
      </ContentSection>

      <ContentSection
        kicker="Operating in production"
        title="Built for finance, ops, and product to share one source of truth."
      >
        <StatGrid
          stats={[
            { value: "10", label: "Subscription states", hint: "fully audited transitions" },
            { value: "∞", label: "Price versions per plan", hint: "old subscribers stay safe" },
            { value: "3", label: "Cycle units", hint: "month, year, custom" },
            { value: "100%", label: "Idempotent edits", hint: "no duplicate writes" }
          ]}
        />
      </ContentSection>

      <ContentSection
        kicker="Common patterns"
        title="Recipes for the plan shapes you actually ship."
      >
        <FeatureGrid
          items={[
            {
              icon: ListChecks,
              title: "Tiered SaaS",
              body: "Starter, Pro, and Team with monthly and annual prices. Annual switch previews proration and updates the next cycle anchor.",
              proof: "monthly ↔ annual"
            },
            {
              icon: ListChecks,
              title: "Membership",
              body: "Single recurring price with a generous trial and a graceful pause option from the customer portal.",
              proof: "trial → active → paused"
            },
            {
              icon: ListChecks,
              title: "Education and creators",
              body: "Term-based plans with custom interval counts, plus free trials and renewal reminders that protect lifetime value.",
              proof: "term · reminder"
            },
            {
              icon: History,
              title: "Migration friendly",
              body: "Import existing customers, plans, and tokens. Idempotency keys and replay tooling let webhooks run side-by-side.",
              proof: "import → cutover"
            }
          ]}
        />
      </ContentSection>

      <CtaBand
        title="Model the plans you actually sell."
        body="Open the plan builder and ship a clean catalog in minutes."
        primary={{ label: "Open the console", to: "/merchant" }}
        secondary={{ label: "View pricing", to: "/pricing" }}
      />
    </>
  );
}
