import { CreditCard, FileLock, KeyRound, Network, ScrollText, ShieldCheck } from "lucide-react";
import {
  PageHero,
  ContentSection,
  FeatureGrid,
  BulletList,
  CtaBand
} from "../components/PageBuilders";

export function SecurityPage() {
  return (
    <>
      <PageHero
        eyebrow="Security and compliance"
        crumbs={[
          { label: "Company" },
          { label: "Security" }
        ]}
        title={
          <>
            Designed for billing —{" "}
            <span className="lp-hero__title-accent">designed for trust.</span>
          </>
        }
        lede="SubPilot never stores raw card data. Tenants are isolated, every write is audited, and every webhook is signed. Security is the default, not an upgrade."
        primaryCta={{ label: "Read webhooks", to: "/developers/webhooks" }}
        secondaryCta={{ label: "Contact security", to: "/contact" }}
        badges={["No raw card data", "Tenant isolation", "Signed events"]}
      />

      <ContentSection
        kicker="Cards and money"
        title="The places where mistakes are most expensive."
      >
        <FeatureGrid
          items={[
            {
              icon: CreditCard,
              title: "Tokenized cards only",
              body: "Cards are tokenized at checkout by your payment provider. SubPilot stores the token reference, never raw card data.",
              proof: "PCI-friendly by design"
            },
            {
              icon: ShieldCheck,
              title: "Webhook signatures",
              body: "Every webhook is signed with HMAC and a timestamp. Reject unsigned or stale deliveries automatically.",
              proof: "X-SubPilot-Signature"
            },
            {
              icon: KeyRound,
              title: "Idempotent writes",
              body: "Replays are safe by construction. Same key returns the same result for 24 hours.",
              proof: "same key → same result"
            },
            {
              icon: Network,
              title: "Tenant isolation",
              body: "Every read and write is scoped per merchant and environment. Test and Live live in strictly separate spaces.",
              proof: "merchant · environment"
            },
            {
              icon: FileLock,
              title: "Encryption everywhere",
              body: "TLS 1.2+ in transit. AES-256 at rest. Secret rotation on a fixed schedule with documented runbooks.",
              proof: "TLS 1.2+ · AES-256"
            },
            {
              icon: ScrollText,
              title: "Audit trail",
              body: "Every state change captures actor, reason, source event, and before/after diff. Exportable on request.",
              proof: "actor · reason · diff"
            }
          ]}
        />
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="Operational controls"
        title="The boring controls that prevent loud incidents."
      >
        <BulletList
          items={[
            "RBAC across ops, finance, support, and developer roles. Permissions are scoped per environment.",
            "Environment switcher prevents accidental writes against Live data from a Test session.",
            "Secrets management with rotation, scoped scopes, and least-privilege defaults.",
            "Replay tooling means incidents do not require destructive remediation steps.",
            "Customer portal sessions are short-lived, scoped, and signed — never shareable."
          ]}
        />
      </ContentSection>

      <ContentSection
        kicker="Disclosure"
        title="If you find something, tell us."
        lede="We treat responsible disclosures as a partnership. Email security@subpilot.dev with details and a way to reproduce. We will acknowledge within one business day."
      />

      <CtaBand
        title="Need a security review?"
        body="We share architecture diagrams, audit retention, and runbooks under NDA."
        primary={{ label: "Contact security", to: "/contact" }}
        secondary={{ label: "Read webhooks", to: "/developers/webhooks" }}
      />
    </>
  );
}
