import type { ReactNode } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { Button, Badge } from "@subpilot/ui";
import { ArrowRight, ChevronRight } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { fadeUp, stagger, inView } from "../lib/motion";

/* -------------------- PageHero -------------------- */

export interface Crumb {
  label: string;
  to?: string;
}

export interface PageHeroProps {
  eyebrow: string;
  title: ReactNode;
  lede: string;
  crumbs?: Crumb[];
  primaryCta?: { label: string; to: string; external?: boolean };
  secondaryCta?: { label: string; to: string; external?: boolean };
  badges?: string[];
}

export function PageHero({
  eyebrow,
  title,
  lede,
  crumbs,
  primaryCta,
  secondaryCta,
  badges
}: PageHeroProps) {
  return (
    <section className="lp-page-hero">
      <div className="lp-page-hero__bg" aria-hidden="true">
        <div className="lp-page-hero__grid" />
        <div className="lp-page-hero__glow" />
      </div>
      <div className="lp-container">
        {crumbs && crumbs.length > 0 ? (
          <nav className="lp-crumbs" aria-label="Breadcrumb">
            {crumbs.map((c, i) => (
              <span key={`${c.label}-${i}`} className="lp-crumbs__item">
                {c.to ? (
                  <Link to={c.to} className="lp-crumbs__link">
                    {c.label}
                  </Link>
                ) : (
                  <span className="lp-crumbs__current">{c.label}</span>
                )}
                {i < crumbs.length - 1 ? (
                  <ChevronRight size={12} className="lp-crumbs__sep" aria-hidden="true" />
                ) : null}
              </span>
            ))}
          </nav>
        ) : null}

        <motion.div className="lp-page-hero__inner" variants={stagger} initial="hidden" animate="show">
          <motion.span className="lp-kicker" variants={fadeUp}>
            {eyebrow}
          </motion.span>
          <motion.h1 className="lp-page-hero__title" variants={fadeUp}>
            {title}
          </motion.h1>
          <motion.p className="lp-page-hero__lede" variants={fadeUp}>
            {lede}
          </motion.p>

          {badges && badges.length > 0 ? (
            <motion.div className="lp-page-hero__badges" variants={fadeUp}>
              {badges.map((b) => (
                <Badge key={b} tone="teal">
                  {b}
                </Badge>
              ))}
            </motion.div>
          ) : null}

          {(primaryCta || secondaryCta) && (
            <motion.div className="lp-page-hero__actions" variants={fadeUp}>
              {primaryCta ? (
                <CtaLink to={primaryCta.to} external={primaryCta.external}>
                  <Button icon={<ArrowRight size={16} />}>{primaryCta.label}</Button>
                </CtaLink>
              ) : null}
              {secondaryCta ? (
                <CtaLink to={secondaryCta.to} external={secondaryCta.external}>
                  <Button variant="secondary">{secondaryCta.label}</Button>
                </CtaLink>
              ) : null}
            </motion.div>
          )}
        </motion.div>
      </div>
    </section>
  );
}

function CtaLink({
  to,
  external,
  children
}: {
  to: string;
  external?: boolean;
  children: ReactNode;
}) {
  if (external) {
    return (
      <a href={to} target="_blank" rel="noreferrer">
        {children}
      </a>
    );
  }
  if (to.startsWith("/merchant") || to.startsWith("/admin")) {
    return <a href={to}>{children}</a>;
  }
  return <Link to={to}>{children}</Link>;
}

/* -------------------- ContentSection -------------------- */

export interface ContentSectionProps {
  id?: string;
  kicker?: string;
  title?: ReactNode;
  lede?: string;
  tone?: "light" | "ink" | "wash";
  children?: ReactNode;
  align?: "left" | "center";
}

export function ContentSection({
  id,
  kicker,
  title,
  lede,
  tone = "light",
  children,
  align = "left"
}: ContentSectionProps) {
  return (
    <section
      id={id}
      className={`lp-section lp-section--${tone === "ink" ? "ink" : tone === "wash" ? "wash" : "light"}`}
    >
      <div className="lp-container">
        {(kicker || title || lede) && (
          <motion.header
            className={`lp-section__head${align === "center" ? " lp-section__head--center" : ""}${
              tone === "ink" ? " lp-section__head--ink" : ""
            }`}
            variants={fadeUp}
            {...inView}
          >
            {kicker ? (
              <span className={`lp-kicker${tone === "ink" ? " lp-kicker--mint" : ""}`}>{kicker}</span>
            ) : null}
            {title ? <h2 className="lp-section__title">{title}</h2> : null}
            {lede ? <p className="lp-section__lede">{lede}</p> : null}
          </motion.header>
        )}
        {children}
      </div>
    </section>
  );
}

/* -------------------- FeatureGrid -------------------- */

export interface FeatureItem {
  icon?: LucideIcon;
  title: string;
  body: string;
  proof?: string;
}

export function FeatureGrid({ items }: { items: FeatureItem[] }) {
  return (
    <motion.div className="lp-feature-grid" variants={stagger} {...inView}>
      {items.map((item) => {
        const Icon = item.icon;
        return (
          <motion.article key={item.title} className="lp-feature-card" variants={fadeUp}>
            {Icon ? (
              <span className="lp-feature-card__icon">
                <Icon size={18} strokeWidth={2} />
              </span>
            ) : null}
            <h3>{item.title}</h3>
            <p>{item.body}</p>
            {item.proof ? <span className="lp-feature-card__proof lp-mono">{item.proof}</span> : null}
          </motion.article>
        );
      })}
    </motion.div>
  );
}

/* -------------------- BulletList -------------------- */

export function BulletList({ items }: { items: string[] }) {
  return (
    <motion.ul className="lp-bullet-list" variants={stagger} {...inView}>
      {items.map((item) => (
        <motion.li key={item} variants={fadeUp}>
          <span className="lp-bullet-list__dot" aria-hidden="true" />
          <span>{item}</span>
        </motion.li>
      ))}
    </motion.ul>
  );
}

/* -------------------- StatGrid -------------------- */

export interface Stat {
  value: string;
  label: string;
  hint?: string;
}

export function StatGrid({ stats }: { stats: Stat[] }) {
  return (
    <motion.div className="lp-stat-grid" variants={stagger} {...inView}>
      {stats.map((s) => (
        <motion.div key={s.label} className="lp-stat-grid__cell" variants={fadeUp}>
          <strong className="lp-num">{s.value}</strong>
          <span>{s.label}</span>
          {s.hint ? <small>{s.hint}</small> : null}
        </motion.div>
      ))}
    </motion.div>
  );
}

/* -------------------- CtaBand -------------------- */

export interface CtaBandProps {
  title: string;
  body?: string;
  primary?: { label: string; to: string; external?: boolean };
  secondary?: { label: string; to: string; external?: boolean };
}

export function CtaBand({ title, body, primary, secondary }: CtaBandProps) {
  return (
    <section className="lp-cta-band">
      <div className="lp-container">
        <motion.div className="lp-cta-band__inner" variants={fadeUp} {...inView}>
          <div>
            <h2>{title}</h2>
            {body ? <p>{body}</p> : null}
          </div>
          <div className="lp-cta-band__actions">
            {primary ? (
              <CtaLink to={primary.to} external={primary.external}>
                <Button icon={<ArrowRight size={16} />}>{primary.label}</Button>
              </CtaLink>
            ) : null}
            {secondary ? (
              <CtaLink to={secondary.to} external={secondary.external}>
                <Button variant="ghost">{secondary.label}</Button>
              </CtaLink>
            ) : null}
          </div>
        </motion.div>
      </div>
    </section>
  );
}
