import { ReactNode } from "react";
import clsx from "clsx";

/**
 * Standalone section header for use above content that lives outside a Card
 * (e.g. hero rows, grid clusters). For header-within-card, prefer the Card
 * component's built-in title/subtitle props.
 */
export function SectionHeader({
  eyebrow,
  title,
  subtitle,
  action,
  className,
}: {
  eyebrow?: string;
  title: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={clsx("flex items-end justify-between gap-4", className)}>
      <div className="min-w-0">
        {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
        <h2 className="heading-2 text-balance">{title}</h2>
        {subtitle && (
          <p className="mt-1 text-sm text-ink-muted text-pretty max-w-2xl">
            {subtitle}
          </p>
        )}
      </div>
      {action && <div className="shrink-0">{action}</div>}
    </div>
  );
}
