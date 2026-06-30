import { motion } from "framer-motion";
import { fadeUp, stagger, inView } from "../lib/motion";
import { segments } from "../lib/data";

export function BuiltFor() {
  return (
    <section className="lp-section" id="built-for">
      <div className="lp-container">
        <motion.div className="lp-section__head" variants={fadeUp} {...inView}>
          <span className="lp-kicker">Built for</span>
          <h2 className="lp-section__title">Teams that need recurring revenue without the rebuild.</h2>
        </motion.div>

        <motion.div className="lp-segments" variants={stagger} {...inView}>
          {segments.map((segment) => (
            <motion.article key={segment.title} className="lp-segment" variants={fadeUp}>
              <span className="lp-segment__icon" aria-hidden="true">
                <segment.icon size={20} />
              </span>
              <h3>{segment.title}</h3>
              <p>{segment.body}</p>
            </motion.article>
          ))}
        </motion.div>
      </div>
    </section>
  );
}
