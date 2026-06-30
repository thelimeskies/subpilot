import type { ButtonHTMLAttributes, ReactNode } from "react";
import { clsx } from "clsx";
import "./components.css";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  icon?: ReactNode;
}

export function Button({ className, variant = "primary", icon, children, ...props }: ButtonProps) {
  return (
    <button className={clsx("sp-button", `sp-button--${variant}`, className)} {...props}>
      {icon ? <span className="sp-button__icon">{icon}</span> : null}
      <span>{children}</span>
    </button>
  );
}
