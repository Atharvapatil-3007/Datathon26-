import { ReactNode, useState } from "react";
import clsx from "clsx";

export interface TabItem<TId extends string = string> {
  id: TId;
  label: ReactNode;
  hint?: ReactNode;
  icon?: ReactNode;
  disabled?: boolean;
}

/**
 * Underlined tab bar. Purely controlled — parent owns the active id.
 * Renders as a horizontally-scrollable pill row on very small screens.
 */
export function Tabs<TId extends string>({
  items,
  active,
  onChange,
  className,
}: {
  items: TabItem<TId>[];
  active: TId;
  onChange: (id: TId) => void;
  className?: string;
}) {
  return (
    <div
      role="tablist"
      aria-orientation="horizontal"
      className={clsx(
        "flex items-center gap-1 overflow-x-auto no-scrollbar border-b border-line",
        className,
      )}
    >
      {items.map((it) => {
        const isActive = it.id === active;
        return (
          <button
            key={it.id}
            role="tab"
            aria-selected={isActive}
            aria-controls={`tabpanel-${it.id}`}
            disabled={it.disabled}
            onClick={() => onChange(it.id)}
            className={clsx(
              "relative shrink-0 inline-flex items-center gap-2 px-3.5 py-2.5 text-sm transition-colors border-b-2 whitespace-nowrap -mb-px",
              isActive
                ? "border-brand text-ink"
                : "border-transparent text-ink-muted hover:text-ink",
              it.disabled && "opacity-50 cursor-not-allowed",
            )}
          >
            {it.icon && <span className="text-ink-muted">{it.icon}</span>}
            <span>{it.label}</span>
            {it.hint && (
              <span className="text-[10px] text-ink-faint font-mono">{it.hint}</span>
            )}
          </button>
        );
      })}
    </div>
  );
}

/**
 * Convenience hook for the common case of a self-contained tab set.
 */
export function useTabs<TId extends string>(items: TabItem<TId>[], initial?: TId) {
  const [active, setActive] = useState<TId>(initial ?? items[0].id);
  return { active, setActive };
}

/**
 * Panel wrapper — mostly for a11y (role="tabpanel").
 */
export function TabPanel({
  id,
  active,
  children,
  className,
}: {
  id: string;
  active: boolean;
  children: ReactNode;
  className?: string;
}) {
  if (!active) return null;
  return (
    <section
      role="tabpanel"
      id={`tabpanel-${id}`}
      aria-labelledby={`tab-${id}`}
      className={clsx("animate-fadeIn", className)}
    >
      {children}
    </section>
  );
}
