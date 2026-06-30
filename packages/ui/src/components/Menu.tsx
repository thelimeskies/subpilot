import type { ReactNode } from "react";
import { MoreHorizontal } from "lucide-react";
import { Button } from "./Button";
import "./components.css";

export interface MenuItem {
  label: string;
  description?: string;
  icon?: ReactNode;
  destructive?: boolean;
}

export function Menu({
  label = "Actions",
  items
}: {
  label?: string;
  items: MenuItem[];
}) {
  return (
    <div className="sp-menu">
      <Button variant="secondary" icon={<MoreHorizontal size={16} />}>
        {label}
      </Button>
      <div className="sp-menu__content" role="menu">
        {items.map((item) => (
          <button key={item.label} type="button" className="sp-menu__item" data-destructive={item.destructive ? "true" : "false"} role="menuitem">
            {item.icon ? <span>{item.icon}</span> : null}
            <span>
              <strong>{item.label}</strong>
              {item.description ? <small>{item.description}</small> : null}
            </span>
          </button>
        ))}
      </div>
    </div>
  );
}
