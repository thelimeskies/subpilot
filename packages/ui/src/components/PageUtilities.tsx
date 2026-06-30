import type { ReactNode } from "react";
import "./components.css";

export function Breadcrumbs({ items }: { items: string[] }) {
  return (
    <nav className="sp-breadcrumbs" aria-label="Breadcrumb">
      {items.map((item, index) => (
        <span key={`${item}-${index}`}>
          {item}
          {index < items.length - 1 ? <em>/</em> : null}
        </span>
      ))}
    </nav>
  );
}

export function Timeline({
  items
}: {
  items: Array<{ title: string; meta: string; body?: ReactNode }>;
}) {
  return (
    <ol className="sp-timeline">
      {items.map((item) => (
        <li key={`${item.title}-${item.meta}`}>
          <span />
          <div>
            <strong>{item.title}</strong>
            <small>{item.meta}</small>
            {item.body ? <p>{item.body}</p> : null}
          </div>
        </li>
      ))}
    </ol>
  );
}
