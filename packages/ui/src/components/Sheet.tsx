import type { ReactNode } from "react";
import { X } from "lucide-react";
import { clsx } from "clsx";
import { Button } from "./Button";
import "./components.css";

export function Sheet({
  open,
  title,
  description,
  side = "right",
  children,
  footer,
  onClose
}: {
  open: boolean;
  title: string;
  description?: string;
  side?: "right" | "left";
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
}) {
  if (!open) return null;

  return (
    <div className="sp-overlay" role="presentation">
      <aside className={clsx("sp-sheet", `sp-sheet--${side}`)} role="dialog" aria-modal="true" aria-labelledby="sp-sheet-title">
        <header className="sp-dialog-header">
          <div>
            <h2 id="sp-sheet-title">{title}</h2>
            {description ? <p>{description}</p> : null}
          </div>
          <Button variant="ghost" aria-label="Close sheet" icon={<X size={18} />} onClick={onClose}>
            Close
          </Button>
        </header>
        <div className="sp-dialog-body">{children}</div>
        {footer ? <footer className="sp-dialog-footer">{footer}</footer> : null}
      </aside>
    </div>
  );
}
