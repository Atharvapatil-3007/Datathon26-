import { useMemo, useState } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { SectionProps, SectionShell, CHART_TOOLTIP_STYLE } from "./_shared";
import { ColumnClassBadge } from "@/components/ui/Badges";
import { fmtDecimal, fmtInt } from "@/lib/format";
import type {
  CategoricalDistribution,
  ColumnProfile,
  HistogramDistribution,
} from "@/lib/types";

export function DistributionsSection({ profile }: SectionProps) {
  const eligible = profile.column_profiles.filter(
    (c) =>
      (c.column_class === "numerical" ||
        c.column_class === "categorical" ||
        c.column_class === "boolean") &&
      Object.keys(c.distribution).length > 0,
  );

  const [selected, setSelected] = useState<string>(eligible[0]?.name ?? "");
  const column = useMemo(
    () => eligible.find((c) => c.name === selected) ?? eligible[0],
    [selected, eligible],
  );

  if (eligible.length === 0) {
    return (
      <SectionShell title="Distributions">
        <p className="text-sm text-ink-muted">
          No columns with distribution data (need at least one numerical, categorical, or boolean column).
        </p>
      </SectionShell>
    );
  }

  return (
    <SectionShell
      title="Distributions"
      subtitle="Histograms for numerical columns; frequency bars for categorical."
      action={
        <select
          value={column?.name ?? ""}
          onChange={(e) => setSelected(e.target.value)}
          className="bg-bg-soft border border-line rounded-md px-3 py-1.5 text-sm text-ink"
        >
          {eligible.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      }
    >
      {column && (
        <>
          <div className="flex items-center gap-2 mb-3">
            <ColumnClassBadge value={column.column_class} />
            <span className="text-sm font-medium text-ink">{column.name}</span>
            {"shape" in column.distribution && (column.distribution as HistogramDistribution).shape && (
              <span className="text-[11px] text-ink-faint capitalize">
                · {(column.distribution as HistogramDistribution).shape?.replace(/_/g, " ")}
              </span>
            )}
          </div>
          <DistChart column={column} />
        </>
      )}
    </SectionShell>
  );
}

function DistChart({ column }: { column: ColumnProfile }) {
  if (column.column_class === "numerical") {
    return <Histogram dist={column.distribution as HistogramDistribution} />;
  }
  return <FrequencyBars dist={column.distribution as CategoricalDistribution} />;
}

function Histogram({ dist }: { dist: HistogramDistribution }) {
  const data = (dist.counts ?? []).map((count, i) => {
    const lo = dist.bins?.[i] ?? 0;
    const hi = dist.bins?.[i + 1] ?? lo;
    return {
      label: `${fmtDecimal(lo, 2)}`,
      range: `${fmtDecimal(lo, 2)} – ${fmtDecimal(hi, 2)}`,
      count,
    };
  });

  return (
    <div className="h-72">
      <ResponsiveContainer>
        <BarChart data={data} margin={{ left: 4, right: 16, top: 4, bottom: 4 }}>
          <CartesianGrid stroke="#243056" strokeDasharray="3 3" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#8590aa", fontSize: 10 }} stroke="#243056" />
          <YAxis tick={{ fill: "#8590aa", fontSize: 11 }} stroke="#243056" />
          <Tooltip
            {...CHART_TOOLTIP_STYLE}
            formatter={(value: number) => [fmtInt(value), "Count"]}
            labelFormatter={(_lbl, payload) =>
              (payload?.[0]?.payload as any)?.range ?? _lbl
            }
          />
          <Bar dataKey="count" fill="#6ea8ff" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function FrequencyBars({ dist }: { dist: CategoricalDistribution }) {
  const data = (dist.top_values ?? []).map((v) => ({
    value: String(v.value ?? "—"),
    count: v.count,
    ratio: v.ratio,
  }));

  if (data.length === 0) {
    return <p className="text-sm text-ink-muted">No values to display.</p>;
  }

  return (
    <div className="h-72">
      <ResponsiveContainer>
        <BarChart
          data={data}
          layout="vertical"
          margin={{ left: 24, right: 24, top: 4, bottom: 4 }}
        >
          <CartesianGrid stroke="#243056" strokeDasharray="3 3" horizontal={false} />
          <XAxis type="number" tick={{ fill: "#8590aa", fontSize: 11 }} stroke="#243056" />
          <YAxis
            type="category"
            dataKey="value"
            tick={{ fill: "#e6ebf5", fontSize: 12 }}
            stroke="#243056"
            width={160}
          />
          <Tooltip
            {...CHART_TOOLTIP_STYLE}
            formatter={(value: number, _key, payload) => [
              `${fmtInt(value)} (${(((payload as any)?.payload?.ratio ?? 0) * 100).toFixed(1)}%)`,
              "Count",
            ]}
          />
          <Bar dataKey="count" fill="#4ade80" radius={[0, 4, 4, 0]} />
        </BarChart>
      </ResponsiveContainer>
      {dist.other_count > 0 && (
        <p className="mt-2 text-xs text-ink-faint">
          {fmtInt(dist.other_count)} additional value(s) not shown ({fmtInt(dist.unique_count)} unique total).
        </p>
      )}
    </div>
  );
}
