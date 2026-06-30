import { useState } from "react";
import { motion } from "framer-motion";
import { Badge } from "@subpilot/ui";
import { Copy, Terminal, Webhook } from "lucide-react";
import { fadeUp, inView } from "../lib/motion";
import { codeSamples, webhookEvent } from "../lib/data";

type Lang = "python" | "node" | "curl";

const tabs: { id: Lang; label: string }[] = [
  { id: "python", label: "Python" },
  { id: "node", label: "Node" },
  { id: "curl", label: "cURL" }
];

export function Developers() {
  const [lang, setLang] = useState<Lang>("python");

  return (
    <section className="lp-section lp-section--ink" id="developers">
      <div className="lp-container">
        <motion.div className="lp-section__head lp-section__head--ink" variants={fadeUp} {...inView}>
          <span className="lp-kicker lp-kicker--mint">Developers</span>
          <h2 className="lp-section__title">APIs, SDKs, and signed events you can trust.</h2>
          <p className="lp-section__lede">
            Create subscriptions, open portal sessions, retry invoices, and verify webhooks without
            handling raw card data or gateway secrets. Idempotency keys are first-class. Replay is one
            click.
          </p>
        </motion.div>

        <div className="lp-dev">
          <motion.div className="lp-dev__code" variants={fadeUp} {...inView}>
            <div className="lp-dev__tabs" role="tablist" aria-label="Code language">
              <Terminal size={14} className="lp-dev__tabs-icon" />
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  role="tab"
                  type="button"
                  aria-selected={lang === tab.id}
                  data-active={lang === tab.id}
                  className="lp-dev__tab"
                  onClick={() => setLang(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
              <button
                type="button"
                className="lp-dev__copy"
                onClick={() => navigator.clipboard?.writeText(codeSamples[lang])}
                aria-label="Copy code"
              >
                <Copy size={14} />
              </button>
            </div>
            <pre className="lp-dev__pre" aria-label={`${lang} example`}>
              <code>{codeSamples[lang]}</code>
            </pre>
          </motion.div>

          <motion.div className="lp-dev__event" variants={fadeUp} {...inView}>
            <div className="lp-dev__event-head">
              <Webhook size={16} />
              <strong>Webhook event</strong>
              <Badge tone="success">signed</Badge>
            </div>
            <pre className="lp-dev__pre lp-dev__pre--event" aria-label="Webhook payload">
              <code>{webhookEvent}</code>
            </pre>
            <ul className="lp-dev__points">
              <li>HMAC signature with rotating secrets</li>
              <li>Idempotency keys block double-charging</li>
              <li>Replay any event from the delivery log</li>
            </ul>
          </motion.div>
        </div>

        <motion.figure className="lp-dev__mockup" variants={fadeUp} {...inView}>
          <img src="/mockups/developer-console.svg" alt="SubPilot developer console" />
          <figcaption>Developer console: API keys, webhook endpoints, and signed delivery log.</figcaption>
        </motion.figure>
      </div>
    </section>
  );
}
