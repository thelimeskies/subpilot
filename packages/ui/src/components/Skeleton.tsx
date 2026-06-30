import type { CSSProperties } from "react";
import { clsx } from "clsx";
import "./components.css";

export function Skeleton({ className, style }: { className?: string; style?: CSSProperties }) {
  return <span className={clsx("sp-skeleton", className)} style={style} aria-hidden="true" />;
}

export function SkeletonTable({ rows = 4 }: { rows?: number }) {
  return (
    <div className="sp-skeleton-table" aria-label="Loading table">
      {Array.from({ length: rows }).map((_, index) => (
        <div key={index}>
          <Skeleton />
          <Skeleton />
          <Skeleton />
          <Skeleton />
        </div>
      ))}
    </div>
  );
}
