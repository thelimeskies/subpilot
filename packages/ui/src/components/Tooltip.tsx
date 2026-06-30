import type { ReactNode } from "react";
import "./components.css";

export function Tooltip({
  label,
  children
}: {
  label: string;
  children: ReactNode;
}) {
  return (
    <span className="sp-tooltip">
      {children}
      <span className="sp-tooltip__bubble" role="tooltip">
        {label}
      </span>
    </span>
  );
}
