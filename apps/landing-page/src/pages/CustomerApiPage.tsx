import { useState } from "react";
import { motion } from "framer-motion";
import {
  BadgeCheck,
  Copy,
  CreditCard,
  ExternalLink,
  KeyRound,
  LockKeyhole,
  PackageCheck,
  ReceiptText,
  RefreshCcw,
  ShieldCheck,
  UserPlus
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import {
  PageHero,
  ContentSection,
  FeatureGrid,
  CtaBand
} from "../components/PageBuilders";
import { fadeUp, inView, stagger } from "../lib/motion";
import { customerPortalUrl } from "../lib/urls";

type SnippetKey = "python" | "curl" | "portal";

const snippets: Record<SnippetKey, string> = {
  python: `from subpilot import SubPilot

client = SubPilot(api_key="nse_test_...")

customer = client.customers.create(
    email="ada@example.com",
    name="Ada Okafor",
    external_id="user_123",
)

session = client.portal_sessions.create(
    customer_id=customer["id"],
    allowed_actions=[
        "view_subscriptions",
        "view_invoices",
        "update_payment_method",
        "pay_invoice",
    ],
    ttl_minutes=60,
)

return {"portal_token": session["token"]}`,
  curl: `curl -X POST https://api.subpilot.dev/api/v1/customers/ \\
  -H "Authorization: Bearer nse_test_..." \\
  -H "Content-Type: application/json" \\
  -d '{
    "email": "ada@example.com",
    "name": "Ada Okafor",
    "external_id": "user_123"
  }'`,
  portal: `import { SubPilotPortal } from "@subpilot/portal-js";
import "@subpilot/portal-js/styles.css";

export function BillingPortal({ portalToken }) {
  return (
    <SubPilotPortal
      publishableKey="pk_test_..."
      token={portalToken}
      apiBaseUrl="https://api.subpilot.dev/api/v1"
      displayMode="modal"
      open
      showCloseButton
    />
  );
}`
};

const customerEndpoints = [
  ["POST", "/customers/", "Create a customer", "Email, name, phone, external ID, and metadata."],
  ["GET", "/customers/", "List customers", "Tenant-scoped list for support, billing, and CRM sync."],
  ["GET", "/customers/{id}/", "Retrieve customer", "Customer profile and current status."],
  ["PATCH", "/customers/{id}/", "Update customer", "Patch contact data, external ID, status, or metadata."],
  ["POST", "/customers/{id}/archive/", "Archive customer", "Pause active access and mark customer archived."],
  ["POST", "/customers/{id}/reactivate/", "Reactivate customer", "Restore an archived customer to active."],
  ["POST", "/customers/{id}/merge/", "Merge customers", "Move subscriptions, invoices, sessions, and payment methods."],
  ["GET", "/customers/{id}/payment-methods/", "List methods", "Masked tokenized payment methods for one customer."],
  ["POST", "/customers/{id}/payment-methods/", "Attach method", "Attach tokenized card reference; never raw card data."],
  ["GET", "/customers/{id}/portal-sessions/", "List sessions", "Audit/debug customer portal sessions."],
  ["POST", "/customers/{id}/portal-sessions/", "Create portal session", "Short-lived customer self-service token and hosted URL."]
];

const portalEndpoints = [
  ["GET", "/portal/context", "Load embedded portal", "Customer, merchant branding, subscriptions, invoices, methods."],
  ["GET", "/portal/invoices", "List invoices", "Customer-scoped invoice history."],
  ["POST", "/portal/invoices/{id}/pay", "Pay invoice", "Charge default payment method for one invoice."],
  ["GET", "/portal/payment-methods", "List methods", "Customer-scoped masked cards."],
  ["POST", "/portal/payment-methods", "Attach card", "Attach a tokenized card from customer portal."],
  ["POST", "/portal/payment-methods/{id}/set-default", "Set default", "Make a card the default payment method."],
  ["POST", "/portal/subscriptions/{id}/cancel", "Cancel subscription", "Cancel now or at period end, based on policy."]
];

const objectCards: Array<{ icon: LucideIcon; title: string; body: string }> = [
  { icon: UserPlus, title: "Customer", body: "Email, phone, external ID, metadata, active/archive state." },
  { icon: CreditCard, title: "Payment method", body: "Provider, token reference, brand, last4, expiry, default flag." },
  { icon: ReceiptText, title: "Portal session", body: "Allowed actions, return URL, expiry, hosted URL, plaintext token at creation." },
  { icon: ExternalLink, title: "Hosted URL", body: "A ready-to-send `/session/{token}` URL for customers who do not use your app." }
];

export function CustomerApiPage() {
  const [activeSnippet, setActiveSnippet] = useState<SnippetKey>("python");

  return (
    <>
      <PageHero
        eyebrow="Customer API"
        crumbs={[
          { label: "Developers", to: "/developers" },
          { label: "Customer API" }
        ]}
        title={
          <>
            Customers, cards, and billing portals —{" "}
            <span className="lp-hero__title-accent">documented end to end.</span>
          </>
        }
        lede="Create customers, attach tokenized payment methods, issue scoped portal sessions, and let customers pay invoices or update cards without exposing secret API keys in the browser."
        primaryCta={{ label: "Open API reference", to: "/developers/api" }}
        secondaryCta={{ label: "Open customer portal", to: customerPortalUrl }}
        badges={["Customers", "Payment methods", "Portal sessions", "Python SDK"]}
      />

      <ContentSection
        tone="ink"
        kicker="Integration path"
        title="The customer flow has a clean trust boundary."
        lede="Your backend creates customers and portal sessions with a secret API key. Your frontend renders the portal with a publishable key and a short-lived portal token."
      >
        <motion.div className="lp-api-flow" variants={stagger} {...inView}>
          {[
            ["1", "Create or sync customer", "POST /customers/ with email, external ID, and metadata."],
            ["2", "Attach billing state", "Create subscriptions, invoices, and tokenized payment methods."],
            ["3", "Create portal token", "POST /customers/{id}/portal-sessions/ from your backend."],
            ["4", "Render portal", "Use @subpilot/portal-js or the hosted /session/{token} link."]
          ].map(([step, title, body]) => (
            <motion.article key={step} className="lp-api-flow__step" variants={fadeUp}>
              <span>{step}</span>
              <strong>{title}</strong>
              <p>{body}</p>
            </motion.article>
          ))}
        </motion.div>
      </ContentSection>

      <ContentSection
        kicker="Customer resources"
        title="Every customer operation your billing product needs."
        lede="The customer API is deliberately small: profile, lifecycle, merge, masked payment methods, and secure portal sessions."
      >
        <EndpointTable rows={customerEndpoints} />
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="Portal API"
        title="Customer-scoped endpoints for the embedded portal."
        lede="Portal endpoints are authenticated with the `Authorization: Portal portal_...` scheme and optionally bound to the publishable key sent by the SDK."
      >
        <EndpointTable rows={portalEndpoints} />
      </ContentSection>

      <ContentSection
        kicker="Auth model"
        title="Secret keys stay server-side. Publishable keys stay browser-side."
      >
        <FeatureGrid
          items={[
            {
              icon: LockKeyhole,
              title: "Secret API key",
              body: "Use `nse_test_...` or `nse_live_...` on your backend to create customers, subscriptions, invoices, and portal sessions.",
              proof: "Authorization: Bearer nse_..."
            },
            {
              icon: KeyRound,
              title: "Publishable key",
              body: "Use `pk_test_...` or `pk_live_...` in frontend code. It identifies the merchant environment but cannot create resources.",
              proof: "X-SubPilot-Publishable-Key"
            },
            {
              icon: ShieldCheck,
              title: "Portal token",
              body: "Use `portal_...` for one customer session. It is scoped by `allowed_actions` and expires after the configured TTL.",
              proof: "Authorization: Portal portal_..."
            }
          ]}
        />
      </ContentSection>

      <ContentSection
        tone="ink"
        kicker="Examples"
        title="Copy the customer flow in your stack."
        lede="Start with Python on the backend, cURL for raw requests, or the React portal package on the frontend."
      >
        <motion.div className="lp-api-snippet" variants={fadeUp} {...inView}>
          <div className="lp-dev__tabs" role="tablist" aria-label="Customer API example">
            {(["python", "curl", "portal"] as SnippetKey[]).map((key) => (
              <button
                key={key}
                type="button"
                role="tab"
                aria-selected={activeSnippet === key}
                className="lp-dev__tab"
                data-active={activeSnippet === key}
                onClick={() => setActiveSnippet(key)}
              >
                {key === "python" ? "Python SDK" : key === "curl" ? "cURL" : "React portal"}
              </button>
            ))}
            <button
              type="button"
              className="lp-dev__copy"
              onClick={() => navigator.clipboard?.writeText(snippets[activeSnippet])}
              aria-label="Copy customer API example"
            >
              <Copy size={14} />
            </button>
          </div>
          <pre className="lp-dev__pre">
            <code>{snippets[activeSnippet]}</code>
          </pre>
        </motion.div>
      </ContentSection>

      <ContentSection
        kicker="Python package"
        title="A backend SDK for the customer and portal flow."
      >
        <FeatureGrid
          items={[
            {
              icon: PackageCheck,
              title: "Typed resource helpers",
              body: "Customers, payment methods, portal sessions, subscriptions, invoices, and publishable keys are exposed as resource clients.",
              proof: "packages/subpilot-python"
            },
            {
              icon: RefreshCcw,
              title: "Idempotency support",
              body: "Every mutating method accepts an idempotency key so retries do not duplicate customer or billing records.",
              proof: "Idempotency-Key"
            },
            {
              icon: BadgeCheck,
              title: "Runnable examples",
              body: "Example scripts show customer creation, portal-session creation, and CLI-style local usage.",
              proof: "examples/customer_portal.py"
            }
          ]}
        />
      </ContentSection>

      <ContentSection
        tone="wash"
        kicker="Objects"
        title="The main customer objects are predictable."
      >
        <motion.div className="lp-object-grid" variants={stagger} {...inView}>
          {objectCards.map(({ icon: Icon, title, body }) => {
            return (
              <motion.article key={title} className="lp-object-card" variants={fadeUp}>
                <Icon size={18} aria-hidden="true" />
                <strong>{title}</strong>
                <p>{body}</p>
              </motion.article>
            );
          })}
        </motion.div>
      </ContentSection>

      <CtaBand
        title="Build your customer billing surface."
        body="Use the Python package on your backend and the portal package in your frontend."
        primary={{ label: "Open API reference", to: "/developers/api" }}
        secondary={{ label: "Portal SDK docs", to: "/portal" }}
      />
    </>
  );
}

function EndpointTable({ rows }: { rows: string[][] }) {
  return (
    <motion.div className="lp-endpoint-table" variants={fadeUp} {...inView}>
      {rows.map(([method, path, title, body]) => (
        <article key={`${method}-${path}`}>
          <span data-method={method}>{method}</span>
          <code>{path}</code>
          <div>
            <strong>{title}</strong>
            <p>{body}</p>
          </div>
        </article>
      ))}
    </motion.div>
  );
}
