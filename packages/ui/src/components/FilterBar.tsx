import { Search, SlidersHorizontal } from "lucide-react";
import { Button } from "./Button";
import { SelectInput, TextInput } from "./Form";
import "./components.css";

export interface FilterOption {
  label: string;
  value: string;
}

export function FilterBar({
  searchPlaceholder = "Search",
  filters,
  action
}: {
  searchPlaceholder?: string;
  filters: Array<{ label: string; options: FilterOption[] }>;
  action?: React.ReactNode;
}) {
  return (
    <div className="sp-filter-bar">
      <div className="sp-search">
        <Search size={18} />
        <TextInput aria-label="Search" placeholder={searchPlaceholder} />
      </div>
      {filters.map((filter) => (
        <SelectInput key={filter.label} aria-label={filter.label}>
          <option>{filter.label}</option>
          {filter.options.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </SelectInput>
      ))}
      <Button variant="secondary" icon={<SlidersHorizontal size={16} />}>
        More filters
      </Button>
      {action ? <div className="sp-filter-bar__action">{action}</div> : null}
    </div>
  );
}
