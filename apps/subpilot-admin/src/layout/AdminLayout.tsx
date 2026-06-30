import { useEffect, useRef, useState, type ReactNode } from "react";
import { NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import {
  Activity,
  Bell,
  BarChart3,
  Building2,
  ChevronDown,
  CreditCard,
  Gauge,
  KeyRound,
  LifeBuoy,
  LogOut,
  Search,
  Settings,
  ShieldCheck,
  Users,
  Webhook
} from "lucide-react";
import { useAuth } from "../auth/AuthContext";

interface NavEntry {
  to: string;
  label: string;
  icon: ReactNode;
  end?: boolean;
  section: "ops" | "account";
}

const navItems: NavEntry[] = [
  { to: "/", label: "Overview", icon: <Gauge size={16} aria-hidden="true" />, end: true, section: "ops" },
  { to: "/analytics", label: "Analytics", icon: <BarChart3 size={16} aria-hidden="true" />, section: "ops" },
  { to: "/merchants", label: "Merchants", icon: <Building2 size={16} aria-hidden="true" />, section: "ops" },
  { to: "/payments", label: "Payments", icon: <CreditCard size={16} aria-hidden="true" />, section: "ops" },
  { to: "/webhooks", label: "Webhooks", icon: <Webhook size={16} aria-hidden="true" />, section: "ops" },
  { to: "/api-keys", label: "API keys", icon: <KeyRound size={16} aria-hidden="true" />, section: "ops" },
  { to: "/support", label: "Support", icon: <LifeBuoy size={16} aria-hidden="true" />, section: "account" },
  { to: "/team", label: "Team", icon: <Users size={16} aria-hidden="true" />, section: "account" },
  { to: "/settings", label: "Settings", icon: <Settings size={16} aria-hidden="true" />, section: "account" }
];

const breadcrumbMap: Record<string, string> = {
  "/": "Overview",
  "/analytics": "Analytics",
  "/merchants": "Merchants",
  "/payments": "Payments",
  "/webhooks": "Webhooks",
  "/api-keys": "API keys",
  "/support": "Support",
  "/team": "Team",
  "/settings": "Settings"
};

export function AdminLayout() {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement | null>(null);

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

  const segment = `/${location.pathname.split("/").filter(Boolean)[0] ?? ""}`;
  const crumb = breadcrumbMap[segment] ?? breadcrumbMap[location.pathname] ?? "Overview";

  function handleSignOut() {
    void signOut();
    setMenuOpen(false);
    navigate("/sign-in", { replace: true });
  }

  return (
    <div className="adm-shell">
      <aside className="adm-sidebar" aria-label="Admin navigation">
        <div className="adm-brand">
          <span className="adm-brand__mark" aria-hidden="true">S</span>
          <span className="adm-brand__text">
            <strong>SubPilot</strong>
            <small>Platform admin</small>
          </span>
        </div>

        <nav className="adm-nav" aria-label="Primary">
          <span className="adm-nav__label">Operations</span>
          {navItems.filter((i) => i.section === "ops").map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `adm-nav__item${isActive ? " is-active" : ""}`}
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
          <span className="adm-nav__label">Account</span>
          {navItems.filter((i) => i.section === "account").map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) => `adm-nav__item${isActive ? " is-active" : ""}`}
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="adm-sidebar__health" role="status">
          <ShieldCheck size={16} aria-hidden="true" />
          <span>
            <strong>Adapter healthy</strong>
            <small>Webhook sigs verified</small>
          </span>
        </div>
      </aside>

      <div className="adm-main">
        <header className="adm-topbar">
          <div className="adm-topbar__crumbs">
            <span>SubPilot</span>
            <em aria-hidden="true">/</em>
            <strong>{crumb}</strong>
          </div>

          <label className="adm-topbar__search">
            <Search size={16} aria-hidden="true" />
            <input type="search" placeholder="Search merchants, events, tickets…" aria-label="Search" />
          </label>

          <div className="adm-topbar__actions">
            <button type="button" className="adm-icon-btn" aria-label="Activity">
              <Activity size={18} aria-hidden="true" />
            </button>
            <button type="button" className="adm-icon-btn" aria-label="Notifications">
              <Bell size={18} aria-hidden="true" />
              <span className="adm-icon-btn__dot" aria-hidden="true" />
            </button>

            <div className="adm-profile" ref={menuRef}>
              <button
                type="button"
                className="adm-profile__trigger"
                onClick={() => setMenuOpen((open) => !open)}
                aria-haspopup="menu"
                aria-expanded={menuOpen}
              >
                <span className="adm-profile__avatar" aria-hidden="true">{user?.initials ?? "SP"}</span>
                <span className="adm-profile__meta">
                  <strong>{user?.name ?? "Operator"}</strong>
                  <small>{user?.role ?? "Admin"}</small>
                </span>
                <ChevronDown size={16} aria-hidden="true" />
              </button>
              {menuOpen ? (
                <div className="adm-profile__menu" role="menu">
                  <div className="adm-profile__header">
                    <strong>{user?.name}</strong>
                    <small>{user?.email}</small>
                  </div>
                  <button type="button" role="menuitem" className="adm-profile__item" onClick={() => navigate("/settings")}>
                    <Settings size={15} aria-hidden="true" />
                    <span>Account settings</span>
                  </button>
                  <button type="button" role="menuitem" className="adm-profile__item" onClick={handleSignOut}>
                    <LogOut size={15} aria-hidden="true" />
                    <span>Sign out</span>
                  </button>
                </div>
              ) : null}
            </div>
          </div>
        </header>

        <main className="adm-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
