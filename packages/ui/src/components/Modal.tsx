import type { ReactNode } from "react";
import { X } from "lucide-react";
import { Button } from "./Button";
import "./components.css";

export function Modal({
  open,
  title,
  description,
  children,
  footer,
  onClose
}: {
  open: boolean;
  title: string;
  description?: string;
  children: ReactNode;
  footer?: ReactNode;
  onClose: () => void;
}) {
  if (!open) return null;

  return (
    <div className="sp-overlay" role="presentation">
      <section className="sp-modal" role="dialog" aria-modal="true" aria-labelledby="sp-modal-title">
        <header className="sp-dialog-header">
          <div>
            <h2 id="sp-modal-title">{title}</h2>
            {description ? <p>{description}</p> : null}
          </div>
          <Button variant="ghost" aria-label="Close modal" icon={<X size={18} />} onClick={onClose}>
            Close
          </Button>
        </header>
        <div className="sp-dialog-body">{children}</div>
        {footer ? <footer className="sp-dialog-footer">{footer}</footer> : null}
      </section>
    </div>
  );
}
