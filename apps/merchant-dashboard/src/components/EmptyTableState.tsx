import type { ReactNode } from "react";
import { Inbox } from "lucide-react";

/**
 * EmptyTableState — wraps DataTable's emptyText slot with a consistent
 * illustration, title, helper copy, and an optional action button. Intended
 * for "no rows yet" or "filters returned zero rows" states across every list
 * page in the merchant dashboard.
 */
export function EmptyTableState({
  icon,
  title,
  description,
  action
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mer-empty-table" role="status">
      <div className="mer-empty-table__icon" aria-hidden="true">
        {icon ?? <Inbox size={24} />}
      </div>
      <strong>{title}</strong>
      {description ? <p>{description}</p> : null}
      {action ? <div className="mer-empty-table__action">{action}</div> : null}
    </div>
  );
}
