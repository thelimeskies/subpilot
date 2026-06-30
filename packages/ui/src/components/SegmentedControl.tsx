import { clsx } from "clsx";
import "./components.css";

export interface SegmentItem {
  label: string;
  value: string;
}

export function SegmentedControl({
  items,
  value,
  onChange,
  label
}: {
  items: SegmentItem[];
  value: string;
  onChange: (value: string) => void;
  label: string;
}) {
  return (
    <div className="sp-segmented" role="radiogroup" aria-label={label}>
      {items.map((item) => (
        <button
          key={item.value}
          type="button"
          role="radio"
          aria-checked={item.value === value}
          className={clsx("sp-segment", item.value === value && "sp-segment--active")}
          onClick={() => onChange(item.value)}
        >
          {item.label}
        </button>
      ))}
    </div>
  );
}
