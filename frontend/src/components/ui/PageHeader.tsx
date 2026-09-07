import { ReactNode } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";

export interface Crumb {
  label: ReactNode;
  to?: string;
}

/**
 * Page hero used at the top of every route. Renders an optional breadcrumb
 * trail above a big title / subtitle pair and an optional actions block on
 * the right.
 */
export function PageHeader({
  eyebrow,
  crumbs,
  title,
  subtitle,
  actions,
  meta,
  className,
}: {
  eyebrow?: string;
  crumbs?: Crumb[];
  title: ReactNode;
  subtitle?: ReactNode;
  actions?: ReactNode;
  meta?: ReactNode;
  className?: string;
}) {
  return (
    <header className={clsx("space-y-3", className)}>
      {crumbs && crumbs.length > 0 && (
        <nav className="flex items-center gap-1.5 text-[11px] text-ink-faint" aria-label="Breadcrumb">
          {crumbs.map((c, i) => (
            <span key={i} className="inline-flex items-center gap-1.5">
              {i > 0 && <span className="text-ink-faint/70">/</span>}
              {c.to ? (
                <Link
                  to={c.to}
                  className="hover:text-ink transition-colors"
                >
                  {c.label}
                </Link>
              ) : (
                <span className="text-ink-muted">{c.label}</span>
              )}
            </span>
          ))}
        </nav>
      )}
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div className="min-w-0 flex-1">
          {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
          <h1 className="heading-1 text-balance truncate">{title}</h1>
          {subtitle && (
            <p className="mt-1.5 text-sm text-ink-muted text-pretty max-w-2xl">
              {subtitle}
            </p>
          )}
          {meta && <div className="mt-3">{meta}</div>}
        </div>
        {actions && <div className="flex items-center gap-2 shrink-0">{actions}</div>}
      </div>
    </header>
  );
}
