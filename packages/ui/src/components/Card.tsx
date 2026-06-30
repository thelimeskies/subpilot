import type { ReactNode } from "react";
import { clsx } from "clsx";
import "./components.css";

export function Card({
  children,
  className,
  tone = "surface"
}: {
  children: ReactNode;
  className?: string;
  tone?: "surface" | "mint" | "ink";
}) {
  return <section className={clsx("sp-card", `sp-card--${tone}`, className)}>{children}</section>;
}

export function CardHeader({
  title,
  description,
  action
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="sp-card-header">
      <div>
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {action ? <div>{action}</div> : null}
    </div>
  );
}
