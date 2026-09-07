import { PropsWithChildren, ReactNode } from "react";
import clsx from "clsx";

export function LoadingState({
  message = "Loading…",
  className,
}: {
  message?: string;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "flex items-center justify-center gap-3 py-8 text-sm text-ink-muted",
        className,
      )}
    >
      <span className="relative flex h-2.5 w-2.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand opacity-70" />
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-brand" />
      </span>
      <span>{message}</span>
    </div>
  );
}

export function EmptyState({
  title,
  hint,
  action,
}: {
  title: string;
  hint?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center text-center py-12 px-6">
      <div className="h-10 w-10 rounded-full bg-bg-hover border border-line flex items-center justify-center text-ink-faint mb-3">
        <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
          <path
            d="M4 6h16M4 12h16M4 18h10"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
          />
        </svg>
      </div>
      <p className="text-sm font-medium text-ink">{title}</p>
      {hint && <p className="text-xs text-ink-muted mt-1 max-w-sm">{hint}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorBanner({
  title,
  detail,
  onDismiss,
}: {
  title: string;
  detail?: ReactNode;
  onDismiss?: () => void;
}) {
  return (
    <div className="rounded-lg border border-bad/50 bg-bad/10 px-4 py-3 text-sm text-ink flex items-start justify-between gap-3">
      <div className="min-w-0">
        <p className="font-medium text-bad">{title}</p>
        {detail && <p className="text-ink-muted mt-1 break-words">{detail}</p>}
      </div>
      {onDismiss && (
        <button
          onClick={onDismiss}
          className="text-ink-faint hover:text-ink text-xs px-2 py-0.5 rounded hover:bg-bad/10"
        >
          Dismiss
        </button>
      )}
    </div>
  );
}

export function InfoBanner({ children }: PropsWithChildren) {
  return (
    <div className="rounded-lg border border-brand-muted/50 bg-brand-soft/40 px-4 py-3 text-sm text-ink">
      {children}
    </div>
  );
}
