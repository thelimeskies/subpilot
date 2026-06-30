import { useState } from "react";
import { motion } from "framer-motion";
import { Mail, MessageSquare, Send, Sparkles } from "lucide-react";
import { Button, Badge } from "@subpilot/ui";
import {
  PageHero,
  ContentSection,
  CtaBand
} from "../components/PageBuilders";
import { fadeUp, stagger, inView } from "../lib/motion";

const channels = [
  {
    icon: Mail,
    title: "Sales",
    detail: "sales@subpilot.dev",
    note: "For pricing, demos, and tailored multi-tenant rollouts."
  },
  {
    icon: MessageSquare,
    title: "Support",
    detail: "support@subpilot.dev",
    note: "Existing customers — first reply within four hours on Growth and Scale."
  },
  {
    icon: Sparkles,
    title: "Security",
    detail: "security@subpilot.dev",
    note: "Responsible disclosure, vendor reviews, and architecture questions."
  }
];

const topics = [
  "I'm exploring SubPilot",
  "I'd like a demo",
  "I want to migrate from another tool",
  "I'm an existing customer",
  "Security and compliance question"
];

export function ContactPage() {
  const [submitted, setSubmitted] = useState(false);

  return (
    <>
      <PageHero
        eyebrow="Contact"
        crumbs={[
          { label: "Company" },
          { label: "Contact" }
        ]}
        title={
          <>
            Talk to a human —{" "}
            <span className="lp-hero__title-accent">about real billing problems.</span>
          </>
        }
        lede="Tell us about your subscription challenge. We'll respond within one business day with concrete next steps — not a generic deck."
        badges={["1-business-day response", "No bots", "Real engineers"]}
      />

      <ContentSection>
        <div className="lp-contact">
          <motion.aside className="lp-contact__channels" variants={stagger} {...inView}>
            {channels.map((c) => {
              const Icon = c.icon;
              return (
                <motion.article key={c.title} className="lp-contact__channel" variants={fadeUp}>
                  <span className="lp-contact__channel-icon">
                    <Icon size={18} />
                  </span>
                  <h3>{c.title}</h3>
                  <a href={`mailto:${c.detail}`} className="lp-contact__channel-link lp-mono">
                    {c.detail}
                  </a>
                  <p>{c.note}</p>
                </motion.article>
              );
            })}
          </motion.aside>

          <motion.form
            className="lp-contact__form"
            variants={fadeUp}
            {...inView}
            onSubmit={(e) => {
              e.preventDefault();
              setSubmitted(true);
            }}
          >
            <header>
              <h2>Send a message</h2>
              <p>We read every note that lands here.</p>
            </header>

            <label className="lp-field">
              <span>Full name</span>
              <input type="text" name="name" required placeholder="Ada Okafor" />
            </label>

            <label className="lp-field">
              <span>Work email</span>
              <input type="email" name="email" required placeholder="ada@company.com" />
            </label>

            <label className="lp-field">
              <span>Company</span>
              <input type="text" name="company" placeholder="Acme Learning" />
            </label>

            <fieldset className="lp-field">
              <legend>What brings you here?</legend>
              <div className="lp-contact__topics">
                {topics.map((t, i) => (
                  <label key={t} className="lp-contact__topic">
                    <input type="radio" name="topic" value={t} defaultChecked={i === 0} />
                    <span>{t}</span>
                  </label>
                ))}
              </div>
            </fieldset>

            <label className="lp-field">
              <span>Tell us more</span>
              <textarea
                name="message"
                rows={5}
                placeholder="Subscriptions, recovery, multi-tenant questions — share the context."
                required
              />
            </label>

            <div className="lp-contact__submit">
              {submitted ? (
                <Badge tone="success">Message received — we'll be in touch.</Badge>
              ) : null}
              <Button type="submit" icon={<Send size={16} />}>
                Send message
              </Button>
            </div>
          </motion.form>
        </div>
      </ContentSection>

      <CtaBand
        title="Prefer to start in the console?"
        body="You can always come back to us once you've kicked the tires."
        primary={{ label: "Open the console", to: "/merchant" }}
        secondary={{ label: "Read the docs", to: "/developers" }}
      />
    </>
  );
}
