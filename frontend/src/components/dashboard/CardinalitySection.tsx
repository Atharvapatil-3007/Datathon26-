import clsx from "clsx";
import { SectionProps, SectionShell } from "./_shared";

export function CardinalitySection({ profile }: SectionProps) {
  const c = profile.cardinality;

  const buckets: Array<[string, string[], string]> = [
    ["Unique", c.unique, "text-brand border-brand-muted/60 bg-brand-soft/40"],
    ["High", c.high, "text-warn border-warn/40 bg-warn/10"],
    ["Medium", c.medium, "text-info border-info/40 bg-info/10"],
    ["Low", c.low, "text-good border-good/40 bg-good/10"],
  ];

  const total = c.unique.length + c.high.length + c.medium.length + c.low.length;

  return (
    <SectionShell
      title="Cardinality distribution"
      subtitle="How diverse each column's values are, bucketed for quick scanning."
      status={c.status}
      reason={c.reason}
    >
      {total === 0 ? (
        <p className="text-sm text-ink-muted">No columns to bucket.</p>
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
          {buckets.map(([label, cols, tone]) => (
            <div key={label} className="rounded-lg border border-line bg-bg-soft/40 p-3">
              <div className="flex items-center justify-between mb-2">
                <span className="label">{label}</span>
                <span
                  className={clsx(
                    "text-[11px] font-semibold px-1.5 rounded-md border",
                    tone,
                  )}
                >
                  {cols.length}
                </span>
              </div>
              <div className="flex flex-wrap gap-1">
                {cols.length === 0 ? (
                  <span className="text-xs text-ink-faint">—</span>
                ) : (
                  cols.map((name) => (
                    <span
                      key={name}
                      className="inline-flex text-[11px] font-mono text-ink-muted border border-line rounded-md px-1.5 py-0.5 bg-bg-hover"
                      title={name}
                    >
                      {name}
                    </span>
                  ))
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </SectionShell>
  );
}
