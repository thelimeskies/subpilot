import { clsx } from "clsx";
import "./components.css";

export interface TabItem {
  label: string;
  value: string;
  count?: number;
}

export function Tabs({
  items,
  value,
  onChange
}: {
  items: TabItem[];
  value: string;
  onChange: (value: string) => void;
}) {
  return (
    <div className="sp-tabs" role="tablist">
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          role="tab"
          aria-selected={item.value === value}
          className={clsx("sp-tab", item.value === value && "sp-tab--active")}
          onClick={() => onChange(item.value)}
        >
          {item.label}
          {typeof item.count === "number" ? <span>{item.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
