import type { ReactNode } from "react";
import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import { clsx } from "clsx";
import "./components.css";

export type AlertTone = "success" | "warning" | "danger" | "info";

const icons: Record<AlertTone, ReactNode> = {
  success: <CheckCircle2 size={20} />,
  warning: <AlertTriangle size={20} />,
  danger: <XCircle size={20} />,
  info: <Info size={20} />
};

export function Alert({
  tone = "info",
  title,
  children
}: {
  tone?: AlertTone;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className={clsx("sp-alert", `sp-alert--${tone}`)} role={tone === "danger" ? "alert" : "status"}>
      <span>{icons[tone]}</span>
      <div>
        <strong>{title}</strong>
        <p>{children}</p>
      </div>
    </div>
  );
}

export function Toast({
  tone = "success",
  title,
  description
}: {
  tone?: AlertTone;
  title: string;
  description: string;
}) {
  return (
    <div className={clsx("sp-toast", `sp-toast--${tone}`)} role="status">
      <span>{icons[tone]}</span>
      <div>
        <strong>{title}</strong>
        <p>{description}</p>
      </div>
    </div>
  );
}
