import { motion } from "framer-motion";
import { fadeUp, stagger, inView } from "../lib/motion";
import { pillars } from "../lib/data";

export function Pillars() {
  return (
    <section className="lp-section" id="product">
      <div className="lp-container">
        <motion.div className="lp-section__head" variants={fadeUp} {...inView}>
          <span className="lp-kicker">Product system</span>
          <h2 className="lp-section__title">
            One subscription layer for merchants and product teams
          </h2>
          <p className="lp-section__lede">
            SubPilot wraps payment primitives in the missing operating system: plans, billing
            cycles, subscription states, invoices, dunning, customer recovery, and signed events.
          </p>
        </motion.div>

        <motion.div className="lp-pillars" variants={stagger} {...inView}>
          {pillars.map((pillar) => (
            <motion.article key={pillar.title} className="lp-pillar" variants={fadeUp}>
              <span className="lp-pillar__icon" aria-hidden="true">
                <pillar.icon size={20} />
              </span>
              <h3 className="lp-pillar__title">{pillar.title}</h3>
              <p className="lp-pillar__body">{pillar.body}</p>
              <span className="lp-pillar__proof lp-mono">{pillar.proof}</span>
            </motion.article>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
