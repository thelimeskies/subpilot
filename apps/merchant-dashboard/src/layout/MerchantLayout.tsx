import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { SegmentedControl } from "@subpilot/ui";
import {
  Activity,
  Boxes,
  ChevronDown,
  Code2,
  CreditCard,
  ExternalLink,
  Gauge,
  ListRestart,
  LogOut,
  Menu as MenuIcon,
  ReceiptText,
  Search,
  Settings,
  ShieldCheck,
  Users,
  UsersRound,
  X
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";
import { usePermissions, type Capability } from "../auth/AuthContext";
import { getActiveEnvironmentMode, setActiveEnvironmentMode, type EnvironmentMode } from "../api/client";
import { GlobalSearch } from "../components/GlobalSearch";
import { NotificationsBell } from "../components/NotificationsBell";

interface NavEntry {
  to: string;
  label: string;
  icon: ReactNode;
  end?: boolean;
  section: "ops" | "account";
  /**
   * Capabilities required to *see* the link. If any of the listed
   * capabilities is held by the current user, the link is rendered.
   * Omit to keep the link visible for all signed-in users.
   */
  requires?: Capability[];
}

const navItems: NavEntry[] = [
  { to: "/", label: "Overview", icon: <Gauge size={16} aria-hidden="true" />, end: true, section: "ops" },
  { to: "/plans", label: "Plans", icon: <Boxes size={16} aria-hidden="true" />, section: "ops",
    // Plans tab is only meaningful to roles that can edit them or create subs.
    requires: ["edit_plan", "create_subscription"] },
  { to: "/subscriptions", label: "Subscriptions", icon: <UsersRound size={16} aria-hidden="true" />, section: "ops" },
  { to: "/invoices", label: "Invoices", icon: <ReceiptText size={16} aria-hidden="true" />, section: "ops" },
  { to: "/payments", label: "Payments", icon: <CreditCard size={16} aria-hidden="true" />, section: "ops" },
  { to: "/customers", label: "Customers", icon: <Users size={16} aria-hidden="true" />, section: "ops",
    requires: ["view_customers"] },
  { to: "/recovery", label: "Recovery", icon: <ListRestart size={16} aria-hidden="true" />, section: "ops",
    requires: ["retry_invoice", "manage_dunning_policies", "mark_uncollectible"] },
  { to: "/developers", label: "Developers", icon: <Code2 size={16} aria-hidden="true" />, section: "ops",
    // Devs / Owners only — Finance/Support/Read-only don't manage keys/webhooks.
    requires: ["manage_api_keys", "manage_webhook_endpoints", "replay_webhooks", "view_event_logs"] },
  { to: "/team", label: "Team", icon: <Users size={16} aria-hidden="true" />, section: "account" },
  { to: "/settings", label: "Settings", icon: <Settings size={16} aria-hidden="true" />, section: "account" },
  { to: "/portal-preview", label: "Portal preview", icon: <ExternalLink size={16} aria-hidden="true" />, section: "account" }
];

const breadcrumbMap: Record<string, string> = {
  "/": "Overview",
  "/plans": "Plans",
  "/subscriptions": "Subscriptions",
  "/invoices": "Invoices",
  "/payments": "Payments",
  "/customers": "Customers",
  "/recovery": "Recovery",
  "/developers": "Developers",
  "/team": "Team",
  "/settings": "Settings",
  "/portal-preview": "Portal preview"
};

export function MerchantLayout() {
  const { user, signOut } = useAuth();
  const { canAny } = usePermissions();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [searchOpen, setSearchOpen] = useState(false);
  const [navOpen, setNavOpen] = useState(false);
  const [environmentMode, setEnvironmentMode] = useState<EnvironmentMode>(() => getActiveEnvironmentMode());
  const menuRef = useRef<HTMLDivElement | null>(null);

  // Filter the static nav definition through the user's capability set so
  // links that wouldn't render any actionable content for this role are
  // hidden up front (they'd otherwise just lead to an empty page).
  const visibleNav = navItems.filter((item) => !item.requires || canAny(...item.requires));

  // Close the mobile drawer whenever the route changes.
  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!menuOpen) return;
    function onPointerDown(event: PointerEvent) {
      if (menuRef.current && !menuRef.current.contains(event.target as Node)) {
        setMenuOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setMenuOpen(false);
    }
    document.addEventListener("pointerdown", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [menuOpen]);

  // Cmd/Ctrl+K toggles the global search modal. Slash also opens it when no
  // input is focused — same shortcut conventions as Linear / GitHub.
  useEffect(() => {
    function onKey(event: KeyboardEvent) {
      const isMod = event.metaKey || event.ctrlKey;
      if (isMod && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setSearchOpen((v) => !v);
        return;
      }
      if (
        event.key === "/" &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey &&
        document.activeElement?.tagName !== "INPUT" &&
        document.activeElement?.tagName !== "TEXTAREA"
      ) {
        event.preventDefault();
        setSearchOpen(true);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  const segment = `/${location.pathname.split("/").filter(Boolean)[0] ?? ""}`;
  const crumb = breadcrumbMap[segment] ?? breadcrumbMap[location.pathname] ?? "Overview";

  function handleSignOut() {
    signOut();
    setMenuOpen(false);
    navigate("/sign-in", { replace: true });
  }

  function handleEnvironmentChange(next: string) {
    const mode = next === "live" ? "live" : "test";
    if (mode === environmentMode) return;
    setActiveEnvironmentMode(mode);
    setEnvironmentMode(mode);
    window.location.reload();
  }

  return (
    <div className={`mer-shell${navOpen ? " is-nav-open" : ""}`}>
      {navOpen ? (
        <button
          type="button"
          className="mer-shell__scrim"
          aria-label="Close navigation"
          onClick={() => setNavOpen(false)}
        />
      ) : null}

      <aside className="mer-sidebar" aria-label="Merchant navigation">
        <div className="mer-brand">
          <span className="mer-brand__mark" aria-hidden="true">S</span>
          <span className="mer-brand__text">
            <strong>SubPilot</strong>
            <small>{user?.orgName ?? "Merchant workspace"}</small>
          </span>
          <button
            type="button"
            className="mer-icon-btn mer-sidebar__close"
            aria-label="Close navigation"
            onClick={() => setNavOpen(false)}
          >
            <X size={16} aria-hidden="true" />
          </button>
        </div>

        <nav className="mer-nav" aria-label="Primary">
          <span className="mer-nav__label">Operations</span>
          {visibleNav.filter((i) => i.section === "ops").map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `mer-nav__item${isActive ? " is-active" : ""}`}
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
          <span className="mer-nav__label">Workspace</span>
          {visibleNav.filter((i) => i.section === "account").map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `mer-nav__item${isActive ? " is-active" : ""}`}
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="mer-sidebar__health" role="status">
          <ShieldCheck size={16} aria-hidden="true" />
          <span>
            <strong>{user?.mfaEnabled ? "MFA enforced" : "MFA recommended"}</strong>
            <small>Tokenized cards · webhooks signed</small>
          </span>
        </div>
      </aside>

      <div className="mer-main">
        <header className="mer-topbar">
          <button
            type="button"
            className="mer-icon-btn mer-topbar__menu"
            aria-label="Open navigation"
            aria-expanded={navOpen}
            onClick={() => setNavOpen((v) => !v)}
          >
            <MenuIcon size={18} aria-hidden="true" />
          </button>

          <div className="mer-topbar__crumbs">
            <span>{user?.orgName ?? "Workspace"}</span>
            <em aria-hidden="true">/</em>
            <strong>{crumb}</strong>
          </div>

          <button
            type="button"
            className="mer-topbar__search"
            onClick={() => setSearchOpen(true)}
            aria-label="Open search (Ctrl/Cmd + K)"
          >
            <Search size={16} aria-hidden="true" />
            <span>Search subscriptions, invoices, customers…</span>
            <kbd>⌘K</kbd>
          </button>

          <div className="mer-topbar__actions">
            <div className="mer-environment-switch">
              <SegmentedControl
                label="Workspace environment"
                value={environmentMode}
                onChange={handleEnvironmentChange}
                items={[
                  { label: "Test", value: "test" },
                  { label: "Live", value: "live" }
                ]}
              />
            </div>
            <button type="button" className="mer-icon-btn" aria-label="Activity">
              <Activity size={18} aria-hidden="true" />
            </button>
            <NotificationsBell />

            <div className="mer-profile" ref={menuRef}>
              <button
                type="button"
                className="mer-profile__trigger"
                onClick={() => setMenuOpen((open) => !open)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
                aria-label="Profile menu"
              >
                <span className="mer-profile__avatar" aria-hidden="true">{user?.initials ?? "SP"}</span>
                <span className="mer-profile__meta">
                  <strong>{user?.name ?? "Operator"}</strong>
                  <small>{user?.role ?? "Member"}</small>
                </span>
                <ChevronDown size={16} aria-hidden="true" />
              </button>
              {menuOpen ? (
                <div className="mer-profile__menu" role="menu">
                  <div className="mer-profile__header">
                    <strong>{user?.name}</strong>
                    <small>{user?.email}</small>
                  </div>
                  <button
                    type="button"
                    role="menuitem"
                    className="mer-profile__item"
                    onClick={() => {
                      setMenuOpen(false);
                      navigate("/settings");
                    }}
                  >
                    <Settings size={15} aria-hidden="true" />
                    <span>Workspace settings</span>
                  </button>
                  <button type="button" role="menuitem" className="mer-profile__item" onClick={handleSignOut}>
                    <LogOut size={15} aria-hidden="true" />
                    <span>Sign out</span>
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>

        <main className="mer-content">
          <Outlet />
        </main>
      </div>

      <GlobalSearch open={searchOpen} onClose={() => setSearchOpen(false)} />
    </div>
  );
}
