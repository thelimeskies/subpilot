import { motion } from "framer-motion";
import { useState } from "react";
import {
  BookOpen,
  Code2,
  KeyRound,
  Layers,
  RefreshCcw,
  ShieldCheck,
  Terminal,
  Webhook
} from "lucide-react";
import {
  PageHero,
  ContentSection,
  FeatureGrid,
  CtaBand
} from "../components/PageBuilders";
import { codeSamples } from "../lib/data";
import { fadeUp, inView } from "../lib/motion";

type Lang = "python" | "node" | "curl";

export function DevelopersPage() {
  const [lang, setLang] = useState<Lang>("node");

  return (
    <>
      <PageHero
        eyebrow="Developers"
        crumbs={[
          { label: "Developers", to: "/developers" },
          { label: "Overview" }
        ]}
        title={
          <>
            APIs, SDKs, and signed events —{" "}
            <span className="lp-hero__title-accent">you can trust.</span>
          </>
        }
        lede="Create subscriptions, open portal sessions, retry invoices, and verify webhooks without handling raw card data or gateway secrets. Idempotency keys are first-class. Replay is one click."
        primaryCta={{ label: "Customer API guide", to: "/developers/customers", external: false }}
        secondaryCta={{ label: "Browse API reference", to: "/developers/api" }}
        badges={["REST + JSON", "TypeScript SDK", "Signed webhooks"]}
      />

      <ContentSection
        tone="ink"
        kicker="Quickstart"
        title="From zero to a live subscription in three lines."
        lede="Pick a language and copy. The same idempotency key keeps retries safe forever."
      >
        <motion.div className="lp-dev__code lp-dev__code--page" variants={fadeUp} {...inView}>
          <div className="lp-dev__tabs" role="tablist" aria-label="Code language">
            <Terminal size={14} className="lp-dev__tabs-icon" />
            {(["node", "python", "curl"] as Lang[]).map((l) => (
              <button
                key={l}
                type="button"
                role="tab"
                aria-selected={lang === l}
                className="lp-dev__tab"
                data-active={lang === l}
                onClick={() => setLang(l)}
              >
                {l === "node" ? "Node" : l === "python" ? "Python" : "cURL"}
              </button>
            ))}
          </div>
          <pre className="lp-dev__pre">
            <code>{codeSamples[lang]}</code>
          </pre>
        </motion.div>
      </ContentSection>

      <ContentSection
        kicker="What you get"
        title="A small set of well-shaped resources."
      >
        <FeatureGrid
          items={[
            {
              icon: Layers,
              title: "Plans and prices",
              body: "Read your catalog, version prices safely, and surface them in your own checkout or app.",
              proof: "/v1/plans · /v1/prices"
            },
            {
              icon: RefreshCcw,
              title: "Subscriptions",
              body: "Create, change, pause, resume, and cancel with idempotent endpoints and proration previews.",
              proof: "/v1/subscriptions"
            },
            {
              icon: KeyRound,
              title: "Portal sessions",
              body: "Issue scoped, short-lived URLs that drop your customers into a self-service portal.",
              proof: "/customers/{id}/portal-sessions"
            },
            {
              icon: Webhook,
              title: "Events and webhooks",
              body: "Signed deliveries, replay tooling, and a delivery log developers can trust.",
              proof: "/v1/events"
            },
            {
              icon: ShieldCheck,
              title: "Auth and tenants",
              body: "API keys per environment, sub-account scoping, and clear separation of test and live.",
              proof: "Bearer · live/test"
            },
            {
              icon: BookOpen,
              title: "OpenAPI spec",
              body: "A canonical OpenAPI document that powers our SDKs — and you can generate yours from the same source.",
              proof: "openapi.yaml"
            }
          ]}
        />
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="SDKs"
        title="Pick the SDK that fits your stack."
      >
        <FeatureGrid
          items={[
            {
              icon: Code2,
              title: "@subpilot/node",
              body: "Typed client for Node and edge runtimes. First-class idempotency, retry helpers, and webhook verification.",
              proof: "npm install @subpilot/node"
            },
            {
              icon: Code2,
              title: "subpilot-python",
              body: "Pythonic client with typed responses, automatic pagination, and signed webhook helpers.",
              proof: "pip install subpilot"
            },
            {
              icon: Code2,
              title: "REST + cURL",
              body: "No SDK? No problem. Every endpoint is well-shaped JSON with idempotency and signing built in.",
              proof: "curl https://api.subpilot.kylodo.com"
            }
          ]}
        />
      </ContentSection>

      <CtaBand
        title="Ship recurring billing in an afternoon."
        body="Read the docs, grab an SDK, and wire your webhooks."
        primary={{ label: "Customer API guide", to: "/developers/customers" }}
        secondary={{ label: "Read webhooks", to: "/developers/webhooks" }}
      />
    </>
  );
}
