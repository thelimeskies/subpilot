import { motion } from "framer-motion";
import { Button } from "@subpilot/ui";
import { ArrowRight, BookOpen } from "lucide-react";
import { fadeUp, inView } from "../lib/motion";
import { merchantAppUrl } from "../lib/urls";

export function CTA() {
  return (
    <section className="lp-section lp-cta" id="cta">
      <div className="lp-container">
        <motion.div className="lp-cta__panel" variants={fadeUp} {...inView}>
          <div className="lp-cta__bg" aria-hidden="true" />
          <div className="lp-cta__content">
            <span className="lp-kicker lp-kicker--mint">Ready when you are</span>
            <h2>Recurring billing without recurring rebuilds.</h2>
            <p>
              Open the merchant console to see SubPilot operate end-to-end, from plan creation to a
              recovered renewal and a signed webhook delivered downstream.
            </p>
            <div className="lp-cta__actions">
              <a href={merchantAppUrl}>
                <Button icon={<ArrowRight size={16} />}>Open the merchant console</Button>
              </a>
              <a href="#developers">
                <Button variant="secondary" icon={<BookOpen size={16} />}>
                  Browse the API
                </Button>
              </a>
            </div>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
