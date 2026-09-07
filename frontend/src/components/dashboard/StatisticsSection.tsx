import { useMemo, useState } from "react";
import { SectionProps, SectionShell } from "./_shared";
import { ColumnClassBadge } from "@/components/ui/Badges";
import { fmtDecimal, fmtInt } from "@/lib/format";
import type {
  BooleanStatistics,
  CategoricalStatistics,
  ColumnProfile,
  DatetimeStatistics,
  IdStatistics,
  NumericalStatistics,
  TextStatistics,
} from "@/lib/types";

export function StatisticsSection({ profile }: SectionProps) {
  const eligible = profile.column_profiles.filter(
    (c) =>
      c.column_class !== "unknown" &&
      Object.keys(c.statistics).length > 0,
  );

  const [selected, setSelected] = useState<string>(eligible[0]?.name ?? "");
  const column = useMemo(
    () => eligible.find((c) => c.name === selected) ?? eligible[0],
    [selected, eligible],
  );

  if (eligible.length === 0) {
    return (
      <SectionShell title="Statistics">
        <p className="text-sm text-ink-muted">
          No columns have statistics computed.
        </p>
      </SectionShell>
    );
  }

  return (
    <SectionShell
      title="Statistics"
      subtitle="Type-appropriate descriptive statistics for a single column."
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
        <div>
          <div className="flex items-center gap-2 mb-4">
            <ColumnClassBadge value={column.column_class} />
            <span className="text-sm font-medium text-ink">{column.name}</span>
            <span className="text-xs text-ink-faint font-mono">{column.dtype}</span>
          </div>
          <StatsRenderer column={column} />
        </div>
      )}
    </SectionShell>
  );
}

function StatsRenderer({ column }: { column: ColumnProfile }) {
  const s = column.statistics;
  switch (column.column_class) {
    case "numerical":
      return <NumericalStats s={s as NumericalStatistics} />;
    case "categorical":
      return <CategoricalStats s={s as CategoricalStatistics} />;
    case "text":
      return <TextStats s={s as TextStatistics} />;
    case "date":
    case "datetime":
      return <DatetimeStats s={s as DatetimeStatistics} />;
    case "boolean":
      return <BooleanStats s={s as BooleanStatistics} />;
    case "id":
      return <IdStats s={s as IdStatistics} />;
    default:
      return <pre className="text-xs text-ink-muted">{JSON.stringify(s, null, 2)}</pre>;
  }
}

function KV({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex items-baseline justify-between border-b border-line/70 py-1.5 text-sm">
      <span className="text-ink-muted">{label}</span>
      <span className="font-mono text-ink">{value}</span>
    </div>
  );
}

function NumericalStats({ s }: { s: NumericalStatistics }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-x-8">
      <div>
        <KV label="Count" value={fmtInt(s.count)} />
        <KV label="Mean" value={fmtDecimal(s.mean)} />
        <KV label="Median" value={fmtDecimal(s.median)} />
        <KV label="Std dev" value={fmtDecimal(s.std)} />
        <KV label="Sum" value={fmtDecimal(s.sum)} />
      </div>
      <div>
        <KV label="Min" value={fmtDecimal(s.min)} />
        <KV label="Q1" value={fmtDecimal(s.q1)} />
        <KV label="Q3" value={fmtDecimal(s.q3)} />
        <KV label="Max" value={fmtDecimal(s.max)} />
        <KV label="IQR" value={fmtDecimal(s.iqr)} />
      </div>
      {s.percentiles && (
        <div className="md:col-span-2 mt-3">
          <div className="label mb-2">Percentiles</div>
          <div className="grid grid-cols-5 gap-2">
            {(["p10", "p25", "p50", "p75", "p90"] as const).map((p) => (
              <div key={p} className="rounded-md border border-line bg-bg-soft/40 p-2 text-center">
                <div className="text-[11px] text-ink-faint">{p.toUpperCase()}</div>
                <div className="font-mono text-ink text-sm">{fmtDecimal(s.percentiles?.[p])}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function CategoricalStats({ s }: { s: CategoricalStatistics }) {
  return (
    <div className="max-w-md">
      <KV label="Count" value={fmtInt(s.count)} />
      <KV label="Unique categories" value={fmtInt(s.unique_count)} />
      <KV label="Mode" value={String(s.mode ?? "—")} />
      <KV label="Mode frequency" value={fmtInt(s.mode_frequency)} />
      <KV label="Mode ratio" value={s.mode_ratio ? `${((s.mode_ratio ?? 0) * 100).toFixed(2)}%` : "—"} />
    </div>
  );
}

function TextStats({ s }: { s: TextStatistics }) {
  return (
    <div className="max-w-md">
      <KV label="Count" value={fmtInt(s.count)} />
      <KV label="Unique" value={fmtInt(s.unique_count)} />
      <KV label="Avg length" value={fmtDecimal(s.avg_length, 2)} />
      <KV label="Min length" value={fmtInt(s.min_length)} />
      <KV label="Max length" value={fmtInt(s.max_length)} />
    </div>
  );
}

function DatetimeStats({ s }: { s: DatetimeStatistics }) {
  return (
    <div className="max-w-md">
      <KV label="Count" value={fmtInt(s.count)} />
      <KV label="Unique dates" value={fmtInt(s.unique_count)} />
      <KV label="Earliest" value={s.min ?? "—"} />
      <KV label="Latest" value={s.max ?? "—"} />
      <KV label="Range (days)" value={fmtInt(s.range_days)} />
    </div>
  );
}

function BooleanStats({ s }: { s: BooleanStatistics }) {
  return (
    <div className="max-w-md">
      <KV label="Count" value={fmtInt(s.count)} />
      <KV label="True" value={fmtInt(s.true_count)} />
      <KV label="False" value={fmtInt(s.false_count)} />
      <KV
        label="True ratio"
        value={s.true_ratio !== undefined ? `${((s.true_ratio ?? 0) * 100).toFixed(2)}%` : "—"}
      />
    </div>
  );
}

function IdStats({ s }: { s: IdStatistics }) {
  return (
    <div className="max-w-md">
      <KV label="Count" value={fmtInt(s.count)} />
      <KV label="Unique" value={fmtInt(s.unique_count)} />
      <KV label="Duplicates" value={fmtInt(s.duplicate_count)} />
      <KV
        label="Uniqueness"
        value={`${((s.uniqueness_ratio ?? 0) * 100).toFixed(2)}%`}
      />
    </div>
  );
}
