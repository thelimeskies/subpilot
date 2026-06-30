import { Check, X } from "lucide-react";
import type { PasswordEvaluation } from "../auth/AuthContext";

const toneByScore: Record<PasswordEvaluation["score"], string> = {
  0: "mer-strength--empty",
  1: "mer-strength--weak",
  2: "mer-strength--weak",
  3: "mer-strength--fair",
  4: "mer-strength--strong"
};

export function PasswordStrengthMeter({ evaluation }: { evaluation: PasswordEvaluation }) {
  const filled = evaluation.score;
  const toneClass = toneByScore[filled] ?? "mer-strength--empty";
  return (
    <div className={`mer-strength ${toneClass}`} aria-live="polite">
      <div className="mer-strength__bars" aria-hidden="true">
        {[1, 2, 3, 4].map((i) => (
          <span key={i} className={`mer-strength__bar${i <= filled ? " is-on" : ""}`} />
        ))}
      </div>
      <div className="mer-strength__label">
        <span>{evaluation.label}</span>
      </div>
      <ul className="mer-strength__rules">
        {evaluation.issues.map((issue) => (
          <li key={issue.id} className={issue.ok ? "is-ok" : "is-pending"}>
            {issue.ok ? <Check size={12} aria-hidden="true" /> : <X size={12} aria-hidden="true" />}
            <span>{issue.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
