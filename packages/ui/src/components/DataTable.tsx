import type { ReactNode } from "react";
import { clsx } from "clsx";
import "./components.css";

export interface DataTableColumn<T> {
  key: string;
  header: string;
  align?: "left" | "right";
  render: (row: T) => ReactNode;
}

export function DataTable<T>({
  columns,
  rows,
  getRowKey,
  emptyText = "No records found"
}: {
  columns: DataTableColumn<T>[];
  rows: T[];
  getRowKey: (row: T) => string;
  emptyText?: string;
}) {
  if (rows.length === 0) {
    return <div className="sp-empty-table">{emptyText}</div>;
  }

  return (
    <div className="sp-table-wrap">
      <table className="sp-table">
        <thead>
          <tr>
            {columns.map((column) => (
              <th key={column.key} className={clsx(column.align === "right" && "sp-align-right")}>
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={getRowKey(row)}>
              {columns.map((column) => (
                <td key={column.key} className={clsx(column.align === "right" && "sp-align-right")}>
                  {column.render(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
