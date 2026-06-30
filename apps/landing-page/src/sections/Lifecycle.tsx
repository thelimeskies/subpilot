import { useState } from "react";
import { motion } from "framer-motion";
import { fadeUp, inView } from "../lib/motion";
import { lifecycleNodes, type LifecycleNode } from "../lib/data";

export function Lifecycle() {
  const [active, setActive] = useState<LifecycleNode>(lifecycleNodes[3]); // active by default

  return (
    <section className="lp-lifecycle" id="lifecycle">
      <div className="lp-container">
        <motion.div className="lp-section__head lp-section__head--ink" variants={fadeUp} {...inView}>
          <span className="lp-kicker lp-kicker--mint">Differentiator</span>
          <h2 className="lp-section__title">State is the UI.</h2>
          <p className="lp-section__lede">
            Every subscription moves through ten explicit states. Transitions are auditable,
            idempotent, and reversible where it makes sense. The console, the API, and the webhook
            payload all describe the same machine.
          </p>
        </motion.div>

        <div className="lp-lifecycle__rail" role="list">
          {lifecycleNodes.map((node, i) => (
            <motion.button
              key={node.id}
              type="button"
              role="listitem"
              className="lp-lifecycle__node"
              data-tone={node.tone}
              data-active={node.id === active.id}
              onMouseEnter={() => setActive(node)}
              onFocus={() => setActive(node)}
              onClick={() => setActive(node)}
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.4, delay: i * 0.04 }}
              aria-pressed={node.id === active.id}
            >
              <span className="lp-lifecycle__dot" aria-hidden="true" />
              <span className="lp-lifecycle__label">{node.label}</span>
            </motion.button>
          ))}
        </div>

        <motion.div
          key={active.id}
          className="lp-lifecycle__detail"
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.35 }}
        >
          <span className="lp-mono">subscription.status = {active.id}</span>
          <p>{active.description}</p>
        </motion.div>

        <div className="lp-lifecycle__legend">
          <Legend tone="info" label="Pending or in trial" />
          <Legend tone="success" label="Active and paid" />
          <Legend tone="warning" label="Recoverable failure" />
          <Legend tone="danger" label="Blocked" />
          <Legend tone="neutral" label="Terminal or paused" />
        </div>
      </div>
    </section>
  );
}

function Legend({ tone, label }: { tone: string; label: string }) {
  return (
    <span className="lp-legend">
      <span className="lp-legend__dot" data-tone={tone} aria-hidden="true" />
      {label}
    </span>
  );
}
