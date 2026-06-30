import { useEffect, useMemo, useState } from "react";

/**
 * Drive a paginated slice of an array with bounded page state.
 *
 * - Resets to page 1 whenever the row count drops below the current page
 *   (e.g., the user filtered the dataset down).
 * - Returns a memoized slice plus a stable `totalLabel` like
 *   "Showing 11–20 of 47 payments".
 */
export function usePagination<T>(rows: T[], pageSize = 10, noun = "rows") {
  const [page, setPage] = useState(1);
  const total = rows.length;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  // Clamp page when the underlying rows shrink (e.g. filter applied).
  useEffect(() => {
    if (page > pageCount) setPage(1);
  }, [page, pageCount]);

  const slice = useMemo(() => {
    const start = (page - 1) * pageSize;
    return rows.slice(start, start + pageSize);
  }, [rows, page, pageSize]);

  const start = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);
  const totalLabel =
    total === 0
      ? `No ${noun} to show`
      : `Showing ${start.toLocaleString()}–${end.toLocaleString()} of ${total.toLocaleString()} ${noun}`;

  return { page, setPage, pageCount, slice, totalLabel, total };
}
