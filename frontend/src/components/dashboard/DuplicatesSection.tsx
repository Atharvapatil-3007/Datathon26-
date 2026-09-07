import { SectionProps, SectionShell, Kpi } from "./_shared";
import { fmtInt, fmtPercent } from "@/lib/format";

export function DuplicatesSection({ profile }: SectionProps) {
  const { duplicates } = profile;

  return (
    <SectionShell
      title="Duplicates"
      subtitle="Full-row duplicates and repeated identifier values."
      status={duplicates.status}
      reason={duplicates.reason}
    >
      <div className="grid grid-cols-3 gap-4">
        <Kpi label="Duplicate rows" value={fmtInt(duplicates.duplicate_rows)} />
        <Kpi label="Duplicate ratio" value={fmtPercent(duplicates.duplicate_ratio)} />
        <Kpi label="Unique rows" value={fmtInt(duplicates.unique_rows)} />
      </div>

      {duplicates.duplicate_ids.length > 0 && (
        <div className="mt-5">
          <div className="label mb-2">Repeated identifier values</div>
          <div className="space-y-3">
            {duplicates.duplicate_ids.map((rep) => (
              <div key={rep.column} className="rounded-lg border border-line bg-bg-soft/40 p-3">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm font-medium text-ink">{rep.column}</span>
                  <span className="text-xs text-ink-muted">
                    {fmtInt(rep.duplicate_value_count)} value(s) duplicated —{" "}
                    {fmtInt(rep.duplicate_row_count)} extra rows
                  </span>
                </div>
                {rep.examples.length > 0 && (
                  <div className="flex flex-wrap gap-1.5">
                    {rep.examples.map((ex, i) => (
                      <span
                        key={`${rep.column}-${i}`}
                        className="inline-flex items-center gap-1 rounded-md border border-line bg-bg-hover px-2 py-0.5 text-[11px] font-mono text-ink-muted"
                      >
                        <span className="text-ink">{String(ex.value)}</span>
                        <span className="text-ink-faint">×{ex.count}</span>
                      </span>
                    ))}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </SectionShell>
  );
}
