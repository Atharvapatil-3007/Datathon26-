import clsx from "clsx";
import { SectionProps, SectionShell } from "./_shared";
import { fmtDecimal } from "@/lib/format";

export function CorrelationsSection({ profile }: SectionProps) {
  const { correlations } = profile;

  return (
    <SectionShell
      title="Correlations"
      subtitle="Pearson correlations across numerical columns. Association only — not causation."
      status={correlations.status}
      reason={correlations.reason}
    >
      <div className="grid grid-cols-1 lg:grid-cols-5 gap-6">
        <div className="lg:col-span-3 overflow-x-auto">
          <Heatmap
            columns={correlations.columns}
            matrix={correlations.matrix}
          />
        </div>
        <div className="lg:col-span-2 space-y-4">
          <PairList
            title="Strongest positive"
            pairs={correlations.strong_positive.slice(0, 5)}
            emptyText="No strong positive correlations found (|r| ≥ 0.6)."
          />
          <PairList
            title="Strongest negative"
            pairs={correlations.strong_negative.slice(0, 5)}
            emptyText="No strong negative correlations found (|r| ≥ 0.6)."
          />
        </div>
      </div>
    </SectionShell>
  );
}

function Heatmap({
  columns,
  matrix,
}: {
  columns: string[];
  matrix: number[][];
}) {
  if (columns.length === 0) {
    return (
      <p className="text-sm text-ink-muted">
        Not enough numerical columns to build a heatmap.
      </p>
    );
  }
  return (
    <div className="inline-block">
      <table className="border-separate border-spacing-1">
        <thead>
          <tr>
            <th className="sticky left-0 bg-bg-card" />
            {columns.map((c) => (
              <th
                key={c}
                className="px-1 py-1 text-[10px] font-normal text-ink-muted whitespace-nowrap max-w-[80px] truncate"
                title={c}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {columns.map((rowName, i) => (
            <tr key={rowName}>
              <th
                className="pr-2 py-1 text-[10px] font-normal text-right text-ink-muted whitespace-nowrap max-w-[120px] truncate"
                title={rowName}
              >
                {rowName}
              </th>
              {columns.map((_, j) => (
                <Cell key={j} value={matrix?.[i]?.[j] ?? 0} isDiagonal={i === j} />
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="mt-4 flex items-center gap-3 text-[11px] text-ink-muted">
        <LegendSwatch color="rgb(248, 113, 113)" label="-1.0" />
        <LegendSwatch color="rgb(146, 146, 146)" label="0.0" />
        <LegendSwatch color="rgb(74, 222, 128)" label="+1.0" />
      </div>
    </div>
  );
}

function Cell({ value, isDiagonal }: { value: number; isDiagonal: boolean }) {
  const bg = correlationColor(value);
  return (
    <td
      className={clsx(
        "w-10 h-10 min-w-[2.5rem] text-[10px] font-mono text-center align-middle rounded",
        isDiagonal ? "text-ink-faint" : "text-black",
      )}
      style={{ backgroundColor: bg }}
      title={`r = ${value.toFixed(4)}`}
    >
      {isDiagonal ? "—" : value.toFixed(2)}
    </td>
  );
}

function LegendSwatch({ color, label }: { color: string; label: string }) {
  return (
    <div className="flex items-center gap-1.5">
      <span className="inline-block h-3 w-3 rounded" style={{ backgroundColor: color }} />
      <span>{label}</span>
    </div>
  );
}

function correlationColor(v: number): string {
  // Blend from red (-1) through neutral (0) to green (+1).
  const clamped = Math.max(-1, Math.min(1, v));
  const t = (clamped + 1) / 2; // 0..1
  const red = { r: 248, g: 113, b: 113 };
  const mid = { r: 130, g: 130, b: 138 };
  const green = { r: 74, g: 222, b: 128 };
  const mix = t < 0.5
    ? blend(red, mid, t * 2)
    : blend(mid, green, (t - 0.5) * 2);
  return `rgb(${mix.r}, ${mix.g}, ${mix.b})`;
}

function blend(
  a: { r: number; g: number; b: number },
  b: { r: number; g: number; b: number },
  t: number,
) {
  const inv = 1 - t;
  return {
    r: Math.round(a.r * inv + b.r * t),
    g: Math.round(a.g * inv + b.g * t),
    b: Math.round(a.b * inv + b.b * t),
  };
}

function PairList({
  title,
  pairs,
  emptyText,
}: {
  title: string;
  pairs: SectionProps["profile"]["correlations"]["strong_positive"];
  emptyText: string;
}) {
  return (
    <div>
      <div className="label mb-2">{title}</div>
      {pairs.length === 0 ? (
        <p className="text-xs text-ink-faint">{emptyText}</p>
      ) : (
        <ul className="space-y-1.5">
          {pairs.map((p) => (
            <li
              key={`${p.column_a}-${p.column_b}`}
              className="flex items-center justify-between text-sm rounded-md border border-line bg-bg-soft/40 px-3 py-1.5"
            >
              <div className="min-w-0">
                <div className="text-ink truncate">
                  {p.column_a} <span className="text-ink-faint">·</span> {p.column_b}
                </div>
                <div className="text-[11px] text-ink-faint capitalize">
                  {p.strength.replace(/_/g, " ")} {p.direction}
                </div>
              </div>
              <span
                className={clsx(
                  "font-mono text-sm",
                  p.direction === "positive" ? "text-good" : "text-bad",
                )}
              >
                {fmtDecimal(p.coefficient, 3)}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
