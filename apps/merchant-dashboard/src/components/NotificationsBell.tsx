import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bell } from "lucide-react";
import { useOptionalData } from "../data/store";
import { formatRelative } from "../data/selectors";

/**
 * NotificationsBell — topbar bell icon that opens a popover showing the last
 * 5 audit events. Acts as the "what's been happening here?" surface for
 * operators. Click an event row → navigate to /settings#audit for the full
 * log.
 */
export function NotificationsBell() {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const data = useOptionalData();
  const auditEvents = data?.auditEvents ?? [];

  const recent = useMemo(() => auditEvents.slice(0, 5), [auditEvents]);
  const hasUnseen = recent.length > 0;

  useEffect(() => {
    if (!open) return;
    function onPointer(event: PointerEvent) {
      if (wrapRef.current && !wrapRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  function viewAll() {
    setOpen(false);
    navigate("/settings#audit");
  }

  return (
    <div className="mer-bell" ref={wrapRef}>
      <button
        type="button"
        className="mer-icon-btn"
        aria-label="Notifications"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
      >
        <Bell size={18} aria-hidden="true" />
        {hasUnseen ? <span className="mer-icon-btn__dot" aria-hidden="true" /> : null}
      </button>
      {open ? (
        <div className="mer-bell__panel" role="menu" aria-label="Recent activity">
          <header className="mer-bell__header">
            <strong>Activity</strong>
            <small>Last {recent.length} event{recent.length === 1 ? "" : "s"}</small>
          </header>
          {recent.length === 0 ? (
            <p className="mer-bell__empty">Nothing has happened yet.</p>
          ) : (
            <ul className="mer-bell__list">
              {recent.map((event) => (
                <li key={event.id} className="mer-bell__item">
                  <strong>{event.action}</strong>
                  <small>
                    <span>{event.actor}</span>
                    {event.target ? <span> · {event.target}</span> : null}
                  </small>
                  <time dateTime={event.occurredAt}>{formatRelative(event.occurredAt)}</time>
                </li>
              ))}
            </ul>
          )}
          <button type="button" className="mer-bell__view-all" onClick={viewAll}>
            View full audit log
          </button>
        </div>
      ) : null}
    </div>
  );
}
