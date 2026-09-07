import { SectionProps, SectionShell, Bar } from "./_shared";
import { fmtDecimal, fmtInt, fmtPercent } from "@/lib/format";

export function OutliersSection({ profile }: SectionProps) {
  const numericCols = profile.column_profiles.filter(
    (c) => c.column_class === "numerical" && c.outliers,
  );

  if (numericCols.length === 0) {
    return (
      <SectionShell
        title="Potential outliers"
        subtitle="IQR-based flags. Phase 2 only reports — it never modifies the data."
      >
        <p className="text-sm text-ink-muted">
          No numerical columns available for outlier analysis.
        </p>
      </SectionShell>
    );
  }

  const rows = [...numericCols].sort(
    (a, b) => (b.outliers?.count ?? 0) - (a.outliers?.count ?? 0),
  );

  return (
    <SectionShell
      title="Potential outliers"
      subtitle="IQR-based flags. Phase 2 only reports — it never modifies the data."
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft/60 border-b border-line">
            <tr className="text-left text-[11px] uppercase tracking-wider text-ink-faint">
              <th className="px-4 py-2 font-medium">Column</th>
              <th className="px-4 py-2 font-medium">Potential outliers</th>
              <th className="px-4 py-2 font-medium">Ratio</th>
              <th className="px-4 py-2 font-medium">Lower bound</th>
              <th className="px-4 py-2 font-medium">Upper bound</th>
              <th className="px-4 py-2 font-medium">IQR</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((col) => {
              const o = col.outliers!;
              return (
                <tr key={col.name}>
                  <td className="px-4 py-2.5">
                    <div className="text-ink font-medium">{col.name}</div>
                    {o.reason && (
                      <div className="text-[11px] text-ink-faint capitalize">
                        {o.reason.replace(/_/g, " ")}
                      </div>
                    )}
                  </td>
                  <td className="px-4 py-2.5 text-ink">{fmtInt(o.count)}</td>
                  <td className="px-4 py-2.5 min-w-[160px]">
                    <div className="text-ink-muted">{fmtPercent(o.ratio)}</div>
                    <div className="mt-1">
                      <Bar
                        ratio={Math.min(1, o.ratio)}
                        tone={o.ratio > 0.05 ? "bad" : "warn"}
                      />
                    </div>
                  </td>
                  <td className="px-4 py-2.5 font-mono text-ink-muted">
                    {o.lower_bound === null || o.lower_bound === undefined
                      ? "—"
                      : fmtDecimal(o.lower_bound)}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-ink-muted">
                    {o.upper_bound === null || o.upper_bound === undefined
                      ? "—"
                      : fmtDecimal(o.upper_bound)}
                  </td>
                  <td className="px-4 py-2.5 font-mono text-ink-muted">
                    {o.iqr === undefined ? "—" : fmtDecimal(o.iqr)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </SectionShell>
  );
}
