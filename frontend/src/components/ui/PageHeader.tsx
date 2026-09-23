import { ReactNode } from "react";
import { Link } from "react-router-dom";
import clsx from "clsx";

export interface Crumb {
  label: ReactNode;
  to?: string;
}

function HeaderGlyph({ title }: { title: ReactNode }) {
  const text = String(title).toLowerCase();
  const path = text.includes("upload")
    ? "M12 16V4m0 0L8 8m4-4 4 4M5 15v3a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-3"
    : text.includes("assistant")
      ? "M8 10h8M8 14h5M12 3a8 8 0 0 0-8 8c0 2.1.8 4 2.2 5.4L5 20l3.7-1.2A8 8 0 1 0 12 3Z"
      : text.includes("analysis") || text.includes("benchmark") || text.includes("merger")
        ? "M5 19V9m4 10V5m5 14v-7m5 7V3"
        : "M4 6h16M4 12h16M4 18h10";

  return (
    <span className="page-header-glyph" aria-hidden>
      <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
        <path d={path} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
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
          <div className="flex items-center gap-2.5 min-w-0">
            <HeaderGlyph title={title} />
            <h1 className="heading-1 text-balance truncate">{title}</h1>
          </div>
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
