import { SectionProps, SectionShell, Kpi, CHART_TOOLTIP_STYLE } from "./_shared";
import { fmtInt, fmtPercent } from "@/lib/format";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

export function MissingSection({ profile }: SectionProps) {
  const { missing } = profile;
  const topOffenders = missing.per_column
    .filter((c) => c.missing_count > 0)
    .slice(0, 10)
    .map((c) => ({
      column: c.column,
      pct: Number((c.missing_ratio * 100).toFixed(2)),
      count: c.missing_count,
    }));

  return (
    <SectionShell
      title="Missing values"
      subtitle="Cell-level completeness across the dataset."
      status={missing.status}
      reason={missing.reason}
    >
      <div className="grid grid-cols-3 gap-4">
        <Kpi label="Missing cells" value={fmtInt(missing.total_missing)} />
        <Kpi label="Missing ratio" value={fmtPercent(missing.missing_ratio)} />
        <Kpi label="Columns affected" value={fmtInt(missing.columns_with_missing)} />
      </div>

      {topOffenders.length > 0 ? (
        <div className="mt-6">
          <div className="label mb-2">Top columns by missing values</div>
          <div className="h-64">
            <ResponsiveContainer>
              <BarChart data={topOffenders} layout="vertical" margin={{ left: 24, right: 24 }}>
                <CartesianGrid stroke="#243056" strokeDasharray="3 3" horizontal={false} />
                <XAxis type="number" tick={{ fill: "#8590aa", fontSize: 11 }} stroke="#243056" unit="%" />
                <YAxis
                  type="category"
                  dataKey="column"
                  tick={{ fill: "#e6ebf5", fontSize: 12 }}
                  stroke="#243056"
                  width={140}
                />
                <Tooltip
                  {...CHART_TOOLTIP_STYLE}
                  formatter={(value: number, _key, payload) => [
                    `${value}% (${(payload as any)?.payload?.count ?? "?"} rows)`,
                    "Missing",
                  ]}
                />
                <Bar dataKey="pct" fill="#facc15" radius={[0, 4, 4, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : (
        <p className="mt-6 text-sm text-ink-muted">
          No missing values detected — every cell is populated.
        </p>
      )}
    </SectionShell>
  );
}
