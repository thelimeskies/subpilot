import { CreditCard, PauseCircle, Receipt, RefreshCw, ShieldCheck, UserRoundCog } from "lucide-react";
import {
  PageHero,
  ContentSection,
  FeatureGrid,
  BulletList,
  CtaBand
} from "../components/PageBuilders";

export function PortalPage() {
  return (
    <>
      <PageHero
        eyebrow="Customer self-service portal"
        crumbs={[
          { label: "Product", to: "/" },
          { label: "Customer portal" }
        ]}
        title={
          <>
            Let customers help themselves —{" "}
            <span className="lp-hero__title-accent">securely.</span>
          </>
        }
        lede="An embeddable portal session for card update, pause, resume, and cancellation with proration preview. Co-branded, mobile-first, and fully scoped."
        primaryCta={{ label: "Try the demo", to: "/merchant" }}
        secondaryCta={{ label: "Read the API", to: "/developers" }}
        badges={["Tokenized cards", "Scoped sessions", "No raw card data"]}
      />

      <ContentSection
        kicker="What customers can do"
        title="Self-service that protects retention without breaking trust."
      >
        <FeatureGrid
          items={[
            {
              icon: CreditCard,
              title: "Update card on file",
              body: "Customers replace a failing card via tokenized checkout. SubPilot stores only the new token reference.",
              proof: "session → token"
            },
            {
              icon: PauseCircle,
              title: "Pause and resume",
              body: "Soft-pause keeps the subscription alive without charging. Resume restores billing on the next anchor.",
              proof: "active → paused → active"
            },
            {
              icon: RefreshCw,
              title: "Switch plans with proration",
              body: "Upgrade or downgrade with a clear preview of credits, debits, and the next invoice — before confirming.",
              proof: "preview → confirm"
            },
            {
              icon: Receipt,
              title: "View receipts",
              body: "All historical invoices and payment receipts in one place, downloadable PDFs included.",
              proof: "open → paid"
            },
            {
              icon: UserRoundCog,
              title: "Cancel cleanly",
              body: "Cancel-at-period-end keeps access until the cycle closes. Reasons are captured for retention insight.",
              proof: "active → canceling"
            },
            {
              icon: ShieldCheck,
              title: "Scoped sessions",
              body: "Each portal URL is a short-lived signed session bound to a single customer and merchant — never shareable.",
              proof: "signed · expiring"
            }
          ]}
        />
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="How it embeds"
        title="Drop into your product or open as a hosted page."
        lede="Decide where the portal lives. Both modes share the same underlying session contract and audit trail."
      >
        <BulletList
          items={[
            "Hosted: open portal.subpilot.dev with a signed session token — no front-end code required.",
            "Embedded: drop into your own app via iframe or SDK with full theming and custom return URLs.",
            "Co-branded: pull merchant logo, colors, and support links from your tenant configuration.",
            "Mobile-first: every screen is responsive and tested for one-handed use on small devices.",
            "Translated-ready: copy is structured for localization without re-architecting layouts."
          ]}
        />
      </ContentSection>

      <CtaBand
        title="Reduce support tickets, increase retention."
        body="Self-service is the cheapest recovery you have."
        primary={{ label: "Open the portal demo", to: "/merchant" }}
        secondary={{ label: "Webhooks reference", to: "/developers/webhooks" }}
      />
    </>
  );
}
