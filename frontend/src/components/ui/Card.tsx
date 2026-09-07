import { PropsWithChildren, ReactNode } from "react";
import clsx from "clsx";

interface CardProps extends PropsWithChildren {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  className?: string;
  bodyClassName?: string;
}

export function Card({
  title,
  subtitle,
  action,
  children,
  className,
  bodyClassName,
}: CardProps) {
  return (
    <section className={clsx("card", className)}>
      {(title || action) && (
        <header className="flex items-start justify-between gap-4 px-5 pt-5 pb-3">
          <div className="min-w-0">
            {title && <h2 className="text-sm font-semibold text-ink">{title}</h2>}
            {subtitle && (
              <p className="text-xs text-ink-muted mt-0.5">{subtitle}</p>
            )}
          </div>
          {action}
        </header>
      )}
      <div className={clsx("px-5 pb-5", bodyClassName)}>{children}</div>
    </section>
  );
}

export function CardGrid({ children, className }: PropsWithChildren<{ className?: string }>) {
  return (
    <div
      className={clsx(
        "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4",
        className,
      )}
    >
      {children}
    </div>
  );
}
