import type { ReactNode } from "react";
import { clsx } from "clsx";
import "./components.css";

export interface NavItem {
  label: string;
  icon: ReactNode;
  active?: boolean;
}

export function AppShell({
  productLabel,
  productMeta,
  navItems,
  title,
  eyebrow,
  description,
  actions,
  children
}: {
  productLabel: string;
  productMeta: string;
  navItems: NavItem[];
  title: string;
  eyebrow: string;
  description?: string;
  actions?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="sp-app">
      <div className="sp-page">
        <aside className="sp-sidebar">
          <div className="sp-logo">
            <span className="sp-logo-mark">S</span>
            <span className="sp-logo-text">
              <span className="sp-logo-title">{productLabel}</span>
              <span className="sp-logo-subtitle">{productMeta}</span>
            </span>
          </div>
          <nav className="sp-nav" aria-label="Primary navigation">
            {navItems.map((item) => (
              <span key={item.label} className={clsx("sp-nav-item")} data-active={item.active ? "true" : "false"}>
                {item.icon}
                {item.label}
              </span>
            ))}
          </nav>
        </aside>
        <main className="sp-main">
          <header className="sp-topbar">
            <div className="sp-title-block">
              <span className="sp-kicker">{eyebrow}</span>
              <h1 className="sp-title">{title}</h1>
              {description ? <p className="sp-subtitle">{description}</p> : null}
            </div>
            {actions ? <div>{actions}</div> : null}
          </header>
          {children}
        </main>
      </div>
    </div>
  );
}
