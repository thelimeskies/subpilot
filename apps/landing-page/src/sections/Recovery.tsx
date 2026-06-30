import { motion } from "framer-motion";
import { Badge } from "@subpilot/ui";
import { CreditCard, Mail, RefreshCw, ShieldAlert, ShieldCheck } from "lucide-react";
import { fadeUp, slideInLeft, stagger, inView } from "../lib/motion";
import { dunningSteps } from "../lib/data";

const ICONS = {
  danger: ShieldAlert,
  warning: RefreshCw,
  info: Mail,
  success: ShieldCheck
} as const;

export function Recovery() {
  return (
    <section className="lp-section lp-section--soft" id="recovery">
      <div className="lp-container lp-recovery">
        <motion.div className="lp-recovery__copy" variants={slideInLeft} {...inView}>
          <span className="lp-kicker">Dunning and recovery</span>
          <h2 className="lp-section__title lp-section__title--left">
            Failed renewals get a real recovery path, not a stale retry loop.
          </h2>
          <p className="lp-section__lede lp-section__lede--left">
            SubPilot orchestrates smart retries, customer-facing recovery, and final-action policy
            from one place. Merchants see exactly what is at risk and what is being recovered.
          </p>

          <motion.div className="lp-stat" variants={fadeUp} {...inView}>
            <span className="lp-stat__label">Recovered in test cohort</span>
            <strong className="lp-stat__value lp-num">62%</strong>
            <span className="lp-stat__delta">of failed invoices, no manual intervention</span>
          </motion.div>
        </motion.div>

        <motion.ol className="lp-timeline" variants={stagger} {...inView}>
          {dunningSteps.map((step) => {
            const Icon = ICONS[step.tone];
            return (
              <motion.li key={step.day} className="lp-timeline__item" variants={fadeUp}>
                <div className="lp-timeline__marker" data-tone={step.tone}>
                  <Icon size={14} />
                </div>
                <div className="lp-timeline__body">
                  <div className="lp-timeline__head">
                    <span className="lp-mono">{step.day}</span>
                    <Badge tone={step.tone === "info" ? "info" : step.tone === "danger" ? "danger" : step.tone === "warning" ? "warning" : "success"}>
                      {step.label}
                    </Badge>
                  </div>
                  <p>{step.detail}</p>
                </div>
              </motion.li>
            );
          })}
        </motion.ol>

        <motion.aside className="lp-recovery__portal" variants={fadeUp} {...inView}>
          <div className="lp-recovery__portal-head">
            <CreditCard size={18} />
            <strong>Customer portal session</strong>
            <Badge tone="warning">Card update required</Badge>
          </div>
          <div className="lp-recovery__portal-body">
            <div className="lp-recovery__field">
              <span>Subscription</span>
              <strong>Pro Monthly · NGN 18,000</strong>
            </div>
            <div className="lp-recovery__field">
              <span>Reason</span>
              <strong>Issuer declined renewal</strong>
            </div>
            <button type="button" className="lp-recovery__cta">
              Update payment method
            </button>
            <span className="lp-recovery__hint">Secure session expires in 24 hours.</span>
          </div>
        </motion.aside>
      </div>
    </section>
  );
}
