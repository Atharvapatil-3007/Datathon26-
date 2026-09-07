import { PropsWithChildren, ReactNode } from "react";
import clsx from "clsx";

/* -------------------------------------------------------------------------
 * Loading states
 * ------------------------------------------------------------------------- */
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
        "flex items-center justify-center gap-3 py-10 text-sm text-ink-muted",
        className,
      )}
      role="status"
      aria-live="polite"
    >
      <span className="relative flex h-2.5 w-2.5">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand opacity-70" />
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-brand" />
      </span>
      <span>{message}</span>
    </div>
  );
}

/** Loading state that shows a progression checklist of completed subtasks. */
export function ProgressLoader({
  title = "Working…",
  done,
  current,
  upcoming = [],
}: {
  title?: string;
  done: string[];
  current?: string;
  upcoming?: string[];
}) {
  return (
    <div className="rounded-xl border border-line bg-bg-soft/50 p-5">
      <div className="flex items-center gap-3 mb-4">
        <span className="relative flex h-2.5 w-2.5">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-brand opacity-70" />
          <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-brand" />
        </span>
        <span className="text-sm font-medium text-ink">{title}</span>
      </div>
      <ol className="space-y-2 text-sm">
        {done.map((d) => (
          <li key={d} className="flex items-center gap-2 text-ink-muted">
            <span className="h-5 w-5 inline-flex items-center justify-center rounded-full bg-good/15 text-good text-[11px]">
              ✓
            </span>
            <span className="text-ink">{d}</span>
          </li>
        ))}
        {current && (
          <li className="flex items-center gap-2">
            <span className="h-5 w-5 inline-flex items-center justify-center rounded-full border border-brand-muted bg-brand-soft text-brand text-[11px] animate-pulseSoft">
              ●
            </span>
            <span className="text-ink">{current}</span>
          </li>
        )}
        {upcoming.map((u) => (
          <li key={u} className="flex items-center gap-2 text-ink-faint">
            <span className="h-5 w-5 inline-flex items-center justify-center rounded-full bg-bg-hover text-ink-faint text-[11px]">
              •
            </span>
            <span>{u}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Empty state
 * ------------------------------------------------------------------------- */
export function EmptyState({
  title,
  hint,
  action,
  icon,
  className,
}: {
  title: string;
  hint?: ReactNode;
  action?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "flex flex-col items-center justify-center text-center py-12 px-6",
        className,
      )}
    >
      <div className="h-12 w-12 rounded-xl bg-bg-hover border border-line flex items-center justify-center text-ink-faint mb-4">
        {icon ?? (
          <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
            <path
              d="M4 6h16M4 12h16M4 18h10"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
            />
          </svg>
        )}
      </div>
      <p className="text-sm font-medium text-ink">{title}</p>
      {hint && (
        <p className="text-xs text-ink-muted mt-1.5 max-w-sm leading-relaxed">
          {hint}
        </p>
      )}
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Banners
 * ------------------------------------------------------------------------- */
export function ErrorBanner({
  title,
  detail,
  onDismiss,
  onRetry,
  className,
}: {
  title: string;
  detail?: ReactNode;
  onDismiss?: () => void;
  onRetry?: () => void;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "rounded-lg border border-bad/40 bg-bad/10 px-4 py-3 text-sm text-ink flex items-start justify-between gap-3",
        className,
      )}
      role="alert"
    >
      <div className="flex items-start gap-3 min-w-0">
        <span
          className="mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-bad/20 text-bad text-[11px] font-semibold"
          aria-hidden
        >
          !
        </span>
        <div className="min-w-0">
          <p className="font-medium text-bad">{title}</p>
          {detail && (
            <p className="text-ink-muted mt-1 break-words leading-relaxed">
              {detail}
            </p>
          )}
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        {onRetry && (
          <button
            onClick={onRetry}
            className="text-xs text-bad hover:text-bad/80 border border-bad/40 rounded px-2 py-1 hover:bg-bad/10"
          >
            Try again
          </button>
        )}
        {onDismiss && (
          <button
            onClick={onDismiss}
            className="text-ink-faint hover:text-ink text-xs px-2 py-0.5 rounded hover:bg-bad/10"
          >
            Dismiss
          </button>
        )}
      </div>
    </div>
  );
}

export function InfoBanner({ children }: PropsWithChildren) {
  return (
    <div
      className="rounded-lg border border-brand-muted/40 bg-brand-soft/30 px-4 py-3 text-sm text-ink flex items-start gap-3"
      role="status"
    >
      <span
        className="mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-brand-soft border border-brand-muted text-brand text-[11px] font-semibold"
        aria-hidden
      >
        i
      </span>
      <div className="min-w-0 flex-1 leading-relaxed text-ink-muted">
        {children}
      </div>
    </div>
  );
}

export function WarningBanner({ children }: PropsWithChildren) {
  return (
    <div
      className="rounded-lg border border-warn/40 bg-warn/5 px-4 py-3 text-sm text-ink flex items-start gap-3"
      role="status"
    >
      <span
        className="mt-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-warn/15 text-warn text-[11px] font-semibold"
        aria-hidden
      >
        ⚠
      </span>
      <div className="min-w-0 flex-1 leading-relaxed text-ink-muted">
        {children}
      </div>
    </div>
  );
}
