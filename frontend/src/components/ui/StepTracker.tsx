import clsx from "clsx";

export interface Step {
  id: string;
  label: string;
  hint?: string;
}

/**
 * Progress bar for multi-stage flows (e.g. Upload → Validate → Profile →
 * Ready). The visual is a horizontal ladder with connectors that fill as
 * steps complete.
 */
export function StepTracker({
  steps,
  current,
  error,
  className,
}: {
  steps: Step[];
  /** Index of the currently-active step. */
  current: number;
  /** If true, the current step is rendered in the error state. */
  error?: boolean;
  className?: string;
}) {
  return (
    <ol
      className={clsx(
        "flex items-center gap-0 w-full",
        className,
      )}
      aria-label="Progress"
    >
      {steps.map((step, i) => {
        const state =
          i < current ? "done" : i === current ? (error ? "error" : "active") : "pending";
        const isLast = i === steps.length - 1;
        return (
          <li key={step.id} className="flex-1 flex items-center min-w-0">
            <div className="flex flex-col items-center gap-1.5 min-w-0">
              <div
                className={clsx(
                  "flex h-7 w-7 items-center justify-center rounded-full border text-[11px] font-medium",
                  state === "done" &&
                    "border-good/50 bg-good/15 text-good",
                  state === "active" &&
                    "border-brand-muted bg-brand-soft text-brand animate-pulseSoft",
                  state === "error" &&
                    "border-bad/60 bg-bad/15 text-bad",
                  state === "pending" &&
                    "border-line bg-bg-soft text-ink-faint",
                )}
                aria-current={state === "active" ? "step" : undefined}
              >
                {state === "done" ? "✓" : state === "error" ? "!" : i + 1}
              </div>
              <div className="text-center min-w-0 px-1">
                <div
                  className={clsx(
                    "text-[11px] font-medium truncate max-w-[9rem]",
                    state === "pending" ? "text-ink-faint" : "text-ink",
                  )}
                >
                  {step.label}
                </div>
                {step.hint && (
                  <div className="text-[10px] text-ink-faint truncate max-w-[9rem]">
                    {step.hint}
                  </div>
                )}
              </div>
            </div>
            {!isLast && (
              <div
                className={clsx(
                  "flex-1 h-px mx-2 self-start mt-[13px]",
                  i < current ? "bg-good/50" : "bg-line",
                )}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}
