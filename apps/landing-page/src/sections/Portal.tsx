import { motion } from "framer-motion";
import { Badge } from "@subpilot/ui";
import { CheckCircle2, Smartphone } from "lucide-react";
import { fadeUp, slideInLeft, slideInRight, inView } from "../lib/motion";

const bullets = [
  "Update payment method without contacting support",
  "Pause and resume subscriptions on the customer's terms",
  "Cancellation preview shows proration before confirmation"
];

export function Portal() {
  return (
    <section className="lp-section lp-portal" id="customers">
      <div className="lp-container lp-portal__inner">
        <motion.div className="lp-portal__copy" variants={slideInLeft} {...inView}>
          <span className="lp-kicker">Customer portal</span>
          <h2 className="lp-section__title lp-section__title--left">
            Customers resolve billing issues themselves.
          </h2>
          <p className="lp-section__lede lp-section__lede--left">
            Embeddable, brandable portal sessions for the moments that drive support tickets:
            updating a card, pausing during travel, or previewing the cost of a downgrade.
          </p>
          <ul className="lp-portal__bullets">
            {bullets.map((bullet) => (
              <li key={bullet}>
                <CheckCircle2 size={18} />
                <span>{bullet}</span>
              </li>
            ))}
          </ul>
        </motion.div>

        <motion.div className="lp-portal__visual" variants={slideInRight} {...inView}>
          <div className="lp-portal__desktop">
            <img src="/mockups/customer-portal.svg" alt="SubPilot customer portal on desktop" />
          </div>
          <motion.div
            className="lp-portal__phone"
            initial={{ opacity: 0, y: 24, rotate: 4 }}
            whileInView={{ opacity: 1, y: 0, rotate: 4 }}
            viewport={{ once: true }}
            transition={{ duration: 0.6, delay: 0.2 }}
          >
            <div className="lp-portal__phone-head">
              <Smartphone size={14} />
              <span>portal.subpilot.dev</span>
            </div>
            <div className="lp-portal__phone-body">
              <Badge tone="warning">Card update required</Badge>
              <strong>Pro Monthly</strong>
              <span className="lp-num">NGN 18,000 · renews 19 Jul</span>
              <button type="button">Update card</button>
              <button type="button" className="lp-portal__phone-secondary">
                Pause subscription
              </button>
            </div>
          </motion.div>
        </motion.div>
      </div>
    </section>
  );
}
