import { useEffect, useRef, useState } from "react";
import { motion, useScroll, useMotionValueEvent } from "framer-motion";
import { Link, NavLink, useLocation } from "react-router-dom";
import { Button } from "@subpilot/ui";
import { ArrowRight, ChevronDown, Menu, X } from "lucide-react";

interface SubLink {
  to: string;
  label: string;
  desc?: string;
}

interface NavGroup {
  label: string;
  links: SubLink[];
}

const groups: NavGroup[] = [
  {
    label: "Product",
    links: [
      { to: "/plans", label: "Plans and cycles", desc: "Catalog, prices, and cycles." },
      { to: "/lifecycle", label: "Lifecycle", desc: "Ten-state subscription machine." },
      { to: "/recovery", label: "Recovery", desc: "Smart retries and dunning." },
      { to: "/portal", label: "Customer portal", desc: "Self-service for your customers." }
    ]
  },
  {
    label: "Developers",
    links: [
      { to: "/developers", label: "Overview", desc: "APIs, SDKs, and quickstart." },
      { to: "/developers/customers", label: "Customer API", desc: "Customers, payment methods, and portal sessions." },
      { to: "/developers/api", label: "API reference", desc: "Live OpenAPI explorer." },
      { to: "/developers/webhooks", label: "Webhooks", desc: "Signed events and replay." },
      { to: "/developers/idempotency", label: "Idempotency", desc: "Safe retries by design." }
    ]
  },
  {
    label: "Company",
    links: [
      { to: "/about", label: "About", desc: "Why SubPilot exists." },
      { to: "/pricing", label: "Pricing", desc: "Free to start, pay on success." },
      { to: "/security", label: "Security", desc: "Trust boundaries and audit." },
      { to: "/contact", label: "Contact", desc: "Talk to a real human." }
    ]
  }
];

export function Nav() {
  const { scrollY } = useScroll();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);
  const [activeGroup, setActiveGroup] = useState<string | null>(null);
  const closeTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navRef = useRef<HTMLElement | null>(null);
  const location = useLocation();

  useMotionValueEvent(scrollY, "change", (v) => {
    setScrolled(v > 12);
  });

  useEffect(() => {
    if (open) document.body.style.overflow = "hidden";
    else document.body.style.overflow = "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  // Close mobile / dropdowns on route change
  useEffect(() => {
    setOpen(false);
    setActiveGroup(null);
  }, [location.pathname]);

  // Close dropdowns on outside click and on Escape
  useEffect(() => {
    if (!activeGroup) return;
    function onPointerDown(e: PointerEvent) {
      if (navRef.current && !navRef.current.contains(e.target as Node)) {
        setActiveGroup(null);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setActiveGroup(null);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [activeGroup]);

  function clearCloseTimer() {
    if (closeTimer.current) {
      clearTimeout(closeTimer.current);
      closeTimer.current = null;
    }
  }

  function openGroup(label: string) {
    clearCloseTimer();
    setActiveGroup(label);
  }

  function scheduleClose() {
    clearCloseTimer();
    closeTimer.current = setTimeout(() => setActiveGroup(null), 140);
  }

  return (
    <motion.header
      ref={navRef}
      className="lp-nav"
      data-scrolled={scrolled}
      initial={{ y: -24, opacity: 0 }}
      animate={{ y: 0, opacity: 1 }}
      transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
    >
      <div className="lp-container lp-nav__inner">
        <Link className="lp-nav__brand" to="/" aria-label="SubPilot home">
          <img src="/logos/subpilot-logo-horizontal.svg" alt="SubPilot" height={28} />
        </Link>

        <nav className="lp-nav__links" aria-label="Primary">
          {groups.map((group) => (
            <div
              key={group.label}
              className="lp-nav__group"
              data-open={activeGroup === group.label}
              onMouseEnter={() => openGroup(group.label)}
              onMouseLeave={scheduleClose}
            >
              <button
                type="button"
                className="lp-nav__group-trigger"
                aria-expanded={activeGroup === group.label}
                aria-haspopup="true"
                onClick={() =>
                  setActiveGroup((prev) => (prev === group.label ? null : group.label))
                }
                onFocus={() => openGroup(group.label)}
              >
                <span>{group.label}</span>
                <ChevronDown size={14} aria-hidden="true" />
              </button>
              {activeGroup === group.label ? (
                <motion.div
                  className="lp-nav__menu"
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.18 }}
                  onMouseEnter={clearCloseTimer}
                  onMouseLeave={scheduleClose}
                >
                  <ul>
                    {group.links.map((link) => (
                      <li key={link.to}>
                        <NavLink to={link.to} className="lp-nav__menu-item">
                          <strong>{link.label}</strong>
                          {link.desc ? <span>{link.desc}</span> : null}
                        </NavLink>
                      </li>
                    ))}
                  </ul>
                </motion.div>
              ) : null}
            </div>
          ))}
          <NavLink to="/pricing" className="lp-nav__direct">
            Pricing
          </NavLink>
        </nav>

        <div className="lp-nav__actions">
          <a href="/merchant" aria-label="Open the merchant console">
            <Button icon={<ArrowRight size={16} />}>Open the console</Button>
          </a>
        </div>

        <button
          type="button"
          className="lp-nav__toggle"
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </div>

      {open ? (
        <motion.div
          className="lp-nav__mobile"
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.25 }}
        >
          {groups.map((group) => (
            <div key={group.label} className="lp-nav__mobile-group">
              <span className="lp-nav__mobile-label">{group.label}</span>
              <ul>
                {group.links.map((link) => (
                  <li key={link.to}>
                    <NavLink to={link.to} onClick={() => setOpen(false)}>
                      {link.label}
                    </NavLink>
                  </li>
                ))}
              </ul>
            </div>
          ))}
          <a href="/merchant" onClick={() => setOpen(false)}>
            <Button icon={<ArrowRight size={16} />}>Open the console</Button>
          </a>
        </motion.div>
      ) : null}
    </motion.header>
  );
}
