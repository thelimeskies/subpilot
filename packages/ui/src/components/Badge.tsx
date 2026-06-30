import type { ReactNode } from "react";
import { clsx } from "clsx";
import "./components.css";

export type BadgeTone = "neutral" | "success" | "warning" | "danger" | "info" | "teal";

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: BadgeTone }) {
  return <span className={clsx("sp-badge", `sp-badge--${tone}`)}>{children}</span>;
}
