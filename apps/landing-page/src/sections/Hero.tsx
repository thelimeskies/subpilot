import { motion } from "framer-motion";
import { Badge, Button } from "@subpilot/ui";
import { ArrowRight, BookOpen, CheckCircle2, RefreshCw, Webhook } from "lucide-react";
import { fadeUp, slideInRight, stagger, inView } from "../lib/motion";

export function Hero() {
  return (
    <section className="lp-hero" id="top">
      <div className="lp-hero__bg" aria-hidden="true">
        <div className="lp-hero__grid" />
        <div className="lp-hero__glow lp-hero__glow--a" />
        <div className="lp-hero__glow lp-hero__glow--b" />
      </div>

      <div className="lp-container lp-hero__inner">
        <motion.div
          className="lp-hero__copy"
          variants={stagger}
          initial="hidden"
          animate="show"
        >
          <motion.div variants={fadeUp}>
            <Badge tone="teal">Recurring billing, fully operated</Badge>
          </motion.div>
          <motion.h1 variants={fadeUp} className="lp-hero__title">
            Subscription operations,
            <br />
            <span className="lp-hero__title-accent">guided from checkout to renewal.</span>
          </motion.h1>
          <motion.p variants={fadeUp} className="lp-hero__lede">
            SubPilot helps businesses launch and operate recurring billing without rebuilding
            subscription logic from scratch. Plans, billing cycles, proration, dunning, customer
            self-service, and signed developer webhooks in one place — so your team can ship product
            instead of patching billing.
          </motion.p>
          <motion.div variants={fadeUp} className="lp-hero__actions">
            <a href="/merchant">
              <Button icon={<ArrowRight size={16} />}>Open the console</Button>
            </a>
            <a href="#developers">
              <Button variant="secondary" icon={<BookOpen size={16} />}>
                Read the docs
              </Button>
            </a>
          </motion.div>
          <motion.ul variants={fadeUp} className="lp-hero__bullets">
            <li>
              <CheckCircle2 size={16} /> Ten-state subscription machine
            </li>
            <li>
              <CheckCircle2 size={16} /> Tokenized-card renewals, never raw cards
            </li>
            <li>
              <CheckCircle2 size={16} /> Recovery built in, not bolted on
            </li>
          </motion.ul>
        </motion.div>

        <motion.div
          className="lp-hero__scene"
          variants={slideInRight}
          {...inView}
        >
          <DashboardScene />
        </motion.div>
      </div>
    </section>
  );
}

function DashboardScene() {
  return (
    <div className="lp-scene" role="img" aria-label="Animated SubPilot console preview">
      <div className="lp-scene__chrome">
        <span />
        <span />
        <span />
        <strong>console.subpilot.dev</strong>
      </div>

      <div className="lp-scene__body">
        <header className="lp-scene__header">
          <div>
            <span className="lp-scene__eyebrow">Merchant workspace</span>
            <strong>Subscription operations</strong>
          </div>
          <Badge tone="teal">Live</Badge>
        </header>

        <motion.div
          className="lp-scene__metrics"
          variants={stagger}
          {...inView}
        >
          <Metric label="MRR" value="NGN 14,820,000" delta="+8.4%" tone="success" />
          <Metric label="At risk" value="NGN 840,000" delta="-2 invoices" tone="warning" />
          <Metric label="Recovered" value="NGN 510,000" delta="62% rate" tone="success" />
        </motion.div>

        <div className="lp-scene__split">
          <motion.div className="lp-scene__rows" variants={stagger} {...inView}>
            <Row name="Ada Okafor" plan="Pro Monthly" status="Active" tone="success" />
            <Row name="Chinedu Bello" plan="Pro Monthly" status="Past due" tone="warning" />
            <Row name="Ifeoma James" plan="Team Annual" status="Card update" tone="danger" />
            <Row name="Kemi Lawal" plan="Pro Monthly" status="Canceling" tone="neutral" />
            <Row name="Tunde Akin" plan="Starter" status="Trialing" tone="info" />
          </motion.div>

          <motion.div
            className="lp-scene__panel"
            initial={{ opacity: 0, y: 16 }}
            whileInView={{ opacity: 1, y: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.4 }}
          >
            <div className="lp-scene__panel-head">
              <RefreshCw size={16} />
              <strong>Recovery path</strong>
            </div>
            <ol className="lp-scene__steps">
              <li>Send portal link</li>
              <li>Customer updates card</li>
              <li>Retry tokenized charge</li>
              <li>Replay signed webhook</li>
            </ol>
          </motion.div>
        </div>

        <motion.div
          className="lp-scene__toast"
          initial={{ opacity: 0, y: 12, scale: 0.96 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 0.5, delay: 1.1 }}
        >
          <Webhook size={16} />
          <div>
            <strong>subscription.activated</strong>
            <span>delivered · 142 ms</span>
          </div>
          <Badge tone="success">200</Badge>
        </motion.div>
      </div>
    </div>
  );
}

function Metric({ label, value, delta, tone }: { label: string; value: string; delta: string; tone: "success" | "warning" }) {
  return (
    <motion.div className="lp-metric" variants={fadeUp}>
      <span className="lp-metric__label">{label}</span>
      <strong className="lp-metric__value lp-num">{value}</strong>
      <span className={`lp-metric__delta lp-metric__delta--${tone}`}>{delta}</span>
    </motion.div>
  );
}

function Row({ name, plan, status, tone }: { name: string; plan: string; status: string; tone: "success" | "warning" | "danger" | "neutral" | "info" }) {
  return (
    <motion.div className="lp-row" variants={fadeUp}>
      <div className="lp-row__main">
        <span className="lp-row__avatar" aria-hidden="true">
          {name.charAt(0)}
        </span>
        <div>
          <strong>{name}</strong>
          <span>{plan}</span>
        </div>
      </div>
      <Badge tone={tone}>{status}</Badge>
    </motion.div>
  );
}
