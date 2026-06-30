import { useState } from "react";
import { AnimatePresence, motion } from "framer-motion";
import { Plus } from "lucide-react";
import { fadeUp, inView } from "../lib/motion";
import { faqs } from "../lib/data";

export function FAQ() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section className="lp-section lp-section--soft" id="faq">
      <div className="lp-container lp-faq">
        <motion.div className="lp-section__head lp-section__head--left" variants={fadeUp} {...inView}>
          <span className="lp-kicker">Questions</span>
          <h2 className="lp-section__title lp-section__title--left">
            Things teams ask before going live.
          </h2>
        </motion.div>

        <div className="lp-faq__list">
          {faqs.map((item, i) => {
            const isOpen = open === i;
            return (
              <motion.div
                key={item.question}
                className="lp-faq__item"
                data-open={isOpen}
                initial={{ opacity: 0, y: 12 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true }}
                transition={{ duration: 0.4, delay: i * 0.04 }}
              >
                <button
                  type="button"
                  className="lp-faq__q"
                  aria-expanded={isOpen}
                  onClick={() => setOpen(isOpen ? null : i)}
                >
                  <span>{item.question}</span>
                  <motion.span
                    className="lp-faq__icon"
                    animate={{ rotate: isOpen ? 45 : 0 }}
                    transition={{ duration: 0.2 }}
                    aria-hidden="true"
                  >
                    <Plus size={18} />
                  </motion.span>
                </button>
                <AnimatePresence initial={false}>
                  {isOpen ? (
                    <motion.div
                      key="content"
                      className="lp-faq__a"
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.25 }}
                    >
                      <p>{item.answer}</p>
                    </motion.div>
                  ) : null}
                </AnimatePresence>
              </motion.div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
