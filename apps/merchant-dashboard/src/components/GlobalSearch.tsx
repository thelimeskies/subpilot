import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Modal } from "@subpilot/ui";
import { Boxes, CreditCard, ReceiptText, Search, Users, UsersRound } from "lucide-react";
import { useOptionalData } from "../data/store";
import { findCustomerById, findPlanById } from "../data/selectors";

interface SearchHit {
  type: "customer" | "subscription" | "invoice" | "plan";
  id: string;
  title: string;
  subtitle: string;
  to: string;
}

/**
 * GlobalSearch — Cmd/Ctrl+K spotlight modal that searches across customers,
 * subscriptions, invoices, and plans using the in-memory selectors. Result
 * click navigates to the entity's detail page.
 */
export function GlobalSearch({ open, onClose }: { open: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement | null>(null);
  const data = useOptionalData();
  const customers = data?.customers ?? [];
  const subscriptions = data?.subscriptions ?? [];
  const invoices = data?.invoices ?? [];
  const plans = data?.plans ?? [];

  useEffect(() => {
    if (open) {
      setQuery("");
      setActiveIndex(0);
      // Defer focus so the modal animation can mount first.
      const t = window.setTimeout(() => inputRef.current?.focus(), 30);
      return () => window.clearTimeout(t);
    }
    return undefined;
  }, [open]);

  const hits = useMemo<SearchHit[]>(() => {
    const trimmed = query.trim().toLowerCase();
    if (!trimmed) return [];
    const out: SearchHit[] = [];
    for (const c of customers) {
      if (out.length >= 6) break;
      if (
        c.name.toLowerCase().includes(trimmed) ||
        c.email.toLowerCase().includes(trimmed) ||
        c.id.toLowerCase().includes(trimmed)
      ) {
        out.push({
          type: "customer",
          id: c.id,
          title: c.name,
          subtitle: c.email,
          to: `/customers/${c.id}`
        });
      }
    }
    for (const s of subscriptions) {
      if (out.length >= 12) break;
      const plan = findPlanById(plans, s.planId);
      const customer = findCustomerById(customers, s.customerId);
      const blob = `${s.id} ${plan?.name ?? ""} ${customer?.name ?? ""}`.toLowerCase();
      if (blob.includes(trimmed)) {
        out.push({
          type: "subscription",
          id: s.id,
          title: `${plan?.name ?? "Plan"} · ${customer?.name ?? "Customer"}`,
          subtitle: `${s.id} · ${s.status}`,
          to: `/subscriptions/${s.id}`
        });
      }
    }
    for (const inv of invoices) {
      if (out.length >= 18) break;
      const customer = findCustomerById(customers, inv.customerId);
      const blob = `${inv.id} ${inv.number} ${customer?.name ?? ""}`.toLowerCase();
      if (blob.includes(trimmed)) {
        out.push({
          type: "invoice",
          id: inv.id,
          title: `Invoice ${inv.number}`,
          subtitle: `${customer?.name ?? "Customer"} · ${inv.status}`,
          to: `/invoices/${inv.id}`
        });
      }
    }
    for (const p of plans) {
      if (out.length >= 24) break;
      const blob = `${p.id} ${p.name} ${p.code}`.toLowerCase();
      if (blob.includes(trimmed)) {
        out.push({
          type: "plan",
          id: p.id,
          title: p.name,
          subtitle: `${p.code} · ${p.status}`,
          to: `/plans/${p.id}`
        });
      }
    }
    return out;
  }, [query, customers, subscriptions, invoices, plans]);

  useEffect(() => {
    setActiveIndex(0);
  }, [hits.length]);

  function go(hit: SearchHit) {
    onClose();
    navigate(hit.to);
  }

  function handleKeyDown(event: React.KeyboardEvent<HTMLInputElement>) {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((i) => Math.min(i + 1, Math.max(hits.length - 1, 0)));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((i) => Math.max(i - 1, 0));
    } else if (event.key === "Enter" && hits[activeIndex]) {
      event.preventDefault();
      go(hits[activeIndex]);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Search"
      description="Find customers, subscriptions, invoices, or plans."
    >
      <div className="mer-search-box">
        <Search size={16} aria-hidden="true" />
        <input
          ref={inputRef}
          type="search"
          placeholder="Type to search…"
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={handleKeyDown}
          aria-label="Search workspace"
          autoComplete="off"
        />
        <kbd>esc</kbd>
      </div>
      {query.trim() === "" ? (
        <p className="mer-search-hint">Try a customer name, invoice number, plan code, or subscription ID.</p>
      ) : hits.length === 0 ? (
        <p className="mer-search-hint">No results for “{query}”.</p>
      ) : (
        <ul className="mer-search-results" role="listbox" aria-label="Search results">
          {hits.map((hit, index) => (
            <li key={`${hit.type}-${hit.id}`}>
              <button
                type="button"
                role="option"
                aria-selected={index === activeIndex}
                className={`mer-search-result${index === activeIndex ? " is-active" : ""}`}
                onMouseEnter={() => setActiveIndex(index)}
                onClick={() => go(hit)}
              >
                <span className="mer-search-result__icon" aria-hidden="true">
                  {hit.type === "customer" ? <Users size={15} /> : null}
                  {hit.type === "subscription" ? <UsersRound size={15} /> : null}
                  {hit.type === "invoice" ? <ReceiptText size={15} /> : null}
                  {hit.type === "plan" ? <Boxes size={15} /> : null}
                </span>
                <span className="mer-search-result__body">
                  <strong>{hit.title}</strong>
                  <small>{hit.subtitle}</small>
                </span>
                <span className="mer-search-result__type" aria-hidden="true">
                  {hit.type}
                </span>
              </button>
            </li>
          ))}
        </ul>
      )}
      <p className="mer-search-footer">
        <CreditCard size={13} aria-hidden="true" />
        <span>
          Press <kbd>↑</kbd> <kbd>↓</kbd> to navigate, <kbd>↵</kbd> to open.
        </span>
      </p>
    </Modal>
  );
}
