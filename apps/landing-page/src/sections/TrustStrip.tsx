import { trustChips } from "../lib/data";

export function TrustStrip() {
  return (
    <section className="lp-trust" aria-label="Recurring revenue capabilities">
      <div className="lp-container">
        <p className="lp-trust__lede">Built around the recurring revenue stack</p>
        <div className="lp-trust__track" role="list">
          {trustChips.map((chip) => (
            <span key={chip} className="lp-trust__chip" role="listitem">
              {chip}
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
