import { PropsWithChildren, ReactNode } from "react";
import clsx from "clsx";

interface CardProps extends PropsWithChildren {
  title?: ReactNode;
  subtitle?: ReactNode;
  action?: ReactNode;
  eyebrow?: string;
  className?: string;
  bodyClassName?: string;
  /** Enable hover-lift interaction. */
  hover?: boolean;
  /** Use the raised elevation variant. */
  raised?: boolean;
}

export function Card({
  title,
  subtitle,
  action,
  eyebrow,
  children,
  className,
  bodyClassName,
  hover,
  raised,
}: CardProps) {
  return (
    <section
      className={clsx(
        raised ? "card-raised" : "card",
        hover && "card-hover",
        className,
      )}
    >
      {(title || action || eyebrow) && (
        <header className="flex items-start justify-between gap-4 px-5 pt-5 pb-3">
          <div className="min-w-0">
            {eyebrow && <div className="eyebrow mb-1.5">{eyebrow}</div>}
            {title && <h2 className="section-title">{title}</h2>}
            {subtitle && <p className="section-subtitle">{subtitle}</p>}
          </div>
          {action && <div className="shrink-0">{action}</div>}
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
