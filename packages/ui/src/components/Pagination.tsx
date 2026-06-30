import { ChevronLeft, ChevronRight } from "lucide-react";
import { Button } from "./Button";
import "./components.css";

export function Pagination({
  page,
  pageCount,
  totalLabel,
  onPageChange
}: {
  page: number;
  pageCount: number;
  totalLabel: string;
  onPageChange: (page: number) => void;
}) {
  return (
    <nav className="sp-pagination" aria-label="Pagination">
      <span>{totalLabel}</span>
      <div>
        <Button variant="secondary" icon={<ChevronLeft size={16} />} disabled={page <= 1} onClick={() => onPageChange(page - 1)}>
          Previous
        </Button>
        <strong>
          Page {page} of {pageCount}
        </strong>
        <Button variant="secondary" icon={<ChevronRight size={16} />} disabled={page >= pageCount} onClick={() => onPageChange(page + 1)}>
          Next
        </Button>
      </div>
    </nav>
  );
}
