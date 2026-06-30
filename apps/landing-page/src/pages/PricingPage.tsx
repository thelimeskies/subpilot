import { motion } from "framer-motion";
import { Check } from "lucide-react";
import { Badge, Button } from "@subpilot/ui";
import { Link } from "react-router-dom";
import { ArrowRight } from "lucide-react";
import {
  PageHero,
  ContentSection,
  CtaBand,
  BulletList
} from "../components/PageBuilders";
import { fadeUp, stagger, inView } from "../lib/motion";

interface Tier {
  name: string;
  price: string;
  cadence: string;
  blurb: string;
  highlighted?: boolean;
  cta: { label: string; to: string };
  features: string[];
}

const tiers: Tier[] = [
  {
    name: "Starter",
    price: "Free",
    cadence: "for the first 100 active subscriptions",
    blurb: "Everything you need to launch your first recurring product.",
    cta: { label: "Open the console", to: "/merchant" },
    features: [
      "Plans, prices, and billing cycles",
      "Ten-state subscription lifecycle",
      "Customer self-service portal",
      "Signed webhooks and event log",
      "Email support"
    ]
  },
  {
    name: "Growth",
    price: "1.0%",
    cadence: "of recurring revenue, after Starter limits",
    blurb: "Built for teams scaling past their first thousand subscriptions.",
    highlighted: true,
    cta: { label: "Open the console", to: "/merchant" },
    features: [
      "Everything in Starter",
      "Smart retries and dunning policies",
      "Recovery queue and bulk actions",
      "Multi-environment (test + live)",
      "RBAC across ops and finance",
      "Priority support, < 4 h response"
    ]
  },
  {
    name: "Scale",
    price: "Custom",
    cadence: "for marketplaces, platforms, and enterprises",
    blurb: "Multi-tenant operators with sub-account billing and dedicated support.",
    cta: { label: "Talk to sales", to: "/contact" },
    features: [
      "Everything in Growth",
      "Sub-account billing and isolation",
      "Dedicated environment switcher",
      "SAML SSO and provisioning",
      "Custom retention and audit retention",
      "Dedicated support engineer"
    ]
  }
];

export function PricingPage() {
  return (
    <>
      <PageHero
        eyebrow="Pricing"
        crumbs={[
          { label: "Company" },
          { label: "Pricing" }
        ]}
        title={
          <>
            Pricing that grows with you —{" "}
            <span className="lp-hero__title-accent">never penalizes you.</span>
          </>
        }
        lede="Start free, pay only on revenue you successfully bill, and switch to custom terms once you outgrow our defaults. No per-seat tax, no setup fees."
        primaryCta={{ label: "Open the console", to: "/merchant" }}
        secondaryCta={{ label: "Talk to sales", to: "/contact" }}
        badges={["No setup fees", "Pay on success", "Cancel anytime"]}
      />

      <ContentSection>
        <motion.div className="lp-pricing" variants={stagger} {...inView}>
          {tiers.map((tier) => (
            <motion.article
              key={tier.name}
              className={`lp-pricing__card${tier.highlighted ? " lp-pricing__card--featured" : ""}`}
              variants={fadeUp}
            >
              <header className="lp-pricing__head">
                <div className="lp-pricing__name-row">
                  <h3>{tier.name}</h3>
                  {tier.highlighted ? <Badge tone="teal">Most teams</Badge> : null}
                </div>
                <strong className="lp-pricing__price lp-num">{tier.price}</strong>
                <span className="lp-pricing__cadence">{tier.cadence}</span>
                <p className="lp-pricing__blurb">{tier.blurb}</p>
              </header>
              <ul className="lp-pricing__features">
                {tier.features.map((f) => (
                  <li key={f}>
                    <Check size={16} aria-hidden="true" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <div className="lp-pricing__cta">
                {tier.cta.to.startsWith("/merchant") ? (
                  <a href={tier.cta.to}>
                    <Button
                      variant={tier.highlighted ? "primary" : "secondary"}
                      icon={<ArrowRight size={16} />}
                    >
                      {tier.cta.label}
                    </Button>
                  </a>
                ) : (
                  <Link to={tier.cta.to}>
                    <Button
                      variant={tier.highlighted ? "primary" : "secondary"}
                      icon={<ArrowRight size={16} />}
                    >
                      {tier.cta.label}
                    </Button>
                  </Link>
                )}
              </div>
            </motion.article>
          ))}
        </motion.div>
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="What's always included"
        title="Foundations are not a paid add-on."
      >
        <BulletList
          items={[
            "Signed webhooks with replay tooling on every plan, including Starter.",
            "Idempotency keys and audit trail on every write across all tiers.",
            "Tokenized-card renewals — raw card data never enters SubPilot.",
            "Self-service customer portal with branded styling.",
            "Test and live environments with strict isolation."
          ]}
        />
      </ContentSection>

      <CtaBand
        title="Bring your billing surface up to your product surface."
        primary={{ label: "Open the console", to: "/merchant" }}
        secondary={{ label: "Contact sales", to: "/contact" }}
      />
    </>
  );
}
