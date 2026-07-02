import { Link } from "react-router-dom";

interface FooterLink {
  label: string;
  to: string;
  external?: boolean;
}

const groups: { title: string; links: FooterLink[] }[] = [
  {
    title: "Product",
    links: [
      { label: "Plans and cycles", to: "/plans" },
      { label: "Lifecycle", to: "/lifecycle" },
      { label: "Recovery", to: "/recovery" },
      { label: "Customer portal", to: "/portal" }
    ]
  },
  {
    title: "Developers",
    links: [
      { label: "API reference", to: "/developers/api" },
      { label: "Customer API", to: "/developers/customers" },
      { label: "Overview", to: "/developers" },
      { label: "Webhooks", to: "/developers/webhooks" },
      { label: "Idempotency", to: "/developers/idempotency" }
    ]
  },
  {
    title: "Company",
    links: [
      { label: "About", to: "/about" },
      { label: "Pricing", to: "/pricing" },
      { label: "Security", to: "/security" },
      { label: "Contact", to: "/contact" }
    ]
  }
];

export function Footer() {
  return (
    <footer className="lp-footer">
      <div className="lp-container lp-footer__inner">
        <div className="lp-footer__brand">
          <Link to="/" aria-label="SubPilot home">
            <img src="/logos/subpilot-logo-horizontal-dark.svg" alt="SubPilot" height={28} />
          </Link>
          <p>
            An independent subscription operations platform. Plans, renewals, recovery, and signed
            webhooks in one place.
          </p>
        </div>

        <div className="lp-footer__groups">
          {groups.map((group) => (
            <div key={group.title} className="lp-footer__group">
              <h4>{group.title}</h4>
              <ul>
                {group.links.map((link) => (
                  <li key={link.label}>
                    {link.external ? (
                      <a href={link.to} target="_blank" rel="noreferrer">
                        {link.label}
                      </a>
                    ) : (
                      <Link to={link.to}>{link.label}</Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>

      <div className="lp-container lp-footer__base">
        <span>© {new Date().getFullYear()} SubPilot. All rights reserved.</span>
        <span className="lp-footer__note">Subscription operations, end to end.</span>
      </div>
    </footer>
  );
}
