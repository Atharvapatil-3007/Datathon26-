import clsx from "clsx";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { PriorityBadge } from "@/components/ui/StatusBadges";
import {
  formatMetricValue,
  ConfidenceFooter,
  InsightsCard,
  SwotBoard,
} from "./_shared";
import type {
  AnalysisResult,
  ComparisonRow,
  GapItem,
} from "@/lib/types";

export function BenchmarkAnalysisView({
  result,
  onReset,
}: {
  result: AnalysisResult;
  onReset: () => void;
}) {
  const primaryName = result.primary_entity?.display_name ?? "Your company";
  const competitorName = result.secondary_entity?.display_name ?? "Competitor";
  const marketName = result.market_entity?.display_name;

  const aheadCount = result.comparisons.filter((c) => c.status === "ahead").length;
  const behindCount = result.comparisons.filter((c) => c.status === "behind").length;
  const levelCount = result.comparisons.filter((c) => c.status === "level").length;

  return (
    <div className="space-y-6">
      <Card
        eyebrow="Executive summary"
        title="Benchmark narrative"
        action={
          <Button size="sm" onClick={onReset}>
            Change inputs
          </Button>
        }
      >
        <p className="text-sm text-ink-muted leading-relaxed text-pretty">
          {result.summary_text}
        </p>
      </Card>

      {/* Head-to-head hero */}
      <BenchmarkHero
        primaryName={primaryName}
        competitorName={competitorName}
        marketName={marketName}
        ahead={aheadCount}
        behind={behindCount}
        level={levelCount}
      />

      <ComparisonTable
        rows={result.comparisons}
        primaryLabel={primaryName}
        secondaryLabel={competitorName}
        marketLabel={marketName}
      />

      <PriorityMatrix gaps={result.gaps} />

      <ReachTheBenchmark gaps={result.gaps.slice(0, 6)} />

      <SwotBoard
        strengths={result.strengths}
        weaknesses={result.weaknesses}
        opportunities={result.opportunities}
        risks={[]}
      />

      <InsightsCard
        insights={result.insights}
        recommendations={result.recommendations}
      />

      {result.confidence && (
        <ConfidenceFooter
          overall={result.confidence.overall}
          coverage={result.confidence.metric_coverage}
          notes={result.confidence.notes}
        />
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Benchmark hero — You vs Competitor vs Market
 * ------------------------------------------------------------------------- */
function BenchmarkHero({
  primaryName,
  competitorName,
  marketName,
  ahead,
  behind,
  level,
}: {
  primaryName: string;
  competitorName: string;
  marketName?: string;
  ahead: number;
  behind: number;
  level: number;
}) {
  return (
    <Card raised className="hero-bg" bodyClassName="p-0">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-px bg-line/60 rounded-xl overflow-hidden">
        <HeroTile tone="brand" label="Your company" name={primaryName} />
        <HeroTile tone="accent" label="Competitor" name={competitorName} />
        {marketName ? (
          <HeroTile tone="info" label="Market benchmark" name={marketName} />
        ) : (
          <div className="bg-bg-card px-4 py-4 flex flex-col justify-center">
            <div className="label">Market benchmark</div>
            <div className="mt-1 text-sm text-ink-faint">Not provided</div>
            <div className="text-[11px] text-ink-faint mt-1">
              Optional. Adds a third reference line to every metric.
            </div>
          </div>
        )}
      </div>
      <div className="px-5 py-4 border-t border-line bg-bg-soft/40 flex flex-wrap items-center gap-2 text-xs">
        <span className="text-ink-muted mr-1">Head-to-head score:</span>
        <span className="chip text-good">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-good" />
          {ahead} ahead
        </span>
        <span className="chip text-ink-muted">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-ink-muted" />
          {level} at parity
        </span>
        <span className="chip text-bad">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-bad" />
          {behind} behind
        </span>
      </div>
    </Card>
  );
}

function HeroTile({
  tone,
  label,
  name,
}: {
  tone: "brand" | "accent" | "info";
  label: string;
  name: string;
}) {
  const styles =
    tone === "brand"
      ? "text-brand"
      : tone === "accent"
        ? "text-accent"
        : "text-info";
  return (
    <div className="bg-bg-card px-4 py-4 flex flex-col justify-center">
      <div className="label">{label}</div>
      <div className={clsx("mt-1 text-lg font-semibold truncate", styles)}>
        {name}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Comparison table
 * ------------------------------------------------------------------------- */
function ComparisonTable({
  rows,
  primaryLabel,
  secondaryLabel,
  marketLabel,
}: {
  rows: ComparisonRow[];
  primaryLabel: string;
  secondaryLabel: string;
  marketLabel?: string;
}) {
  if (rows.length === 0) {
    return (
      <Card eyebrow="Comparison" title="Head-to-head comparison">
        <p className="text-sm text-ink-muted">
          No comparable metrics were found across the two datasets.
        </p>
      </Card>
    );
  }

  return (
    <Card
      eyebrow="Comparison"
      title="Head-to-head comparison"
      subtitle="Direction-aware — 'ahead' or 'behind' is metric-specific."
      bodyClassName="p-0"
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft/70 border-b border-line">
            <tr className="text-left text-[11px] uppercase tracking-[0.08em] text-ink-faint">
              <th className="px-4 py-2.5 font-medium">Metric</th>
              <th className="px-4 py-2.5 font-medium text-right">{primaryLabel}</th>
              <th className="px-4 py-2.5 font-medium text-right">{secondaryLabel}</th>
              {marketLabel && (
                <th className="px-4 py-2.5 font-medium text-right">{marketLabel}</th>
              )}
              <th className="px-4 py-2.5 font-medium text-right">Gap</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => (
              <tr key={r.metric_id}>
                <td className="px-4 py-2.5 text-ink font-medium">
                  {r.display_name}
                </td>
                <td className="px-4 py-2.5 num text-ink-muted">
                  {formatMetricValue(r.primary_value, r.unit)}
                </td>
                <td className="px-4 py-2.5 num text-ink-muted">
                  {formatMetricValue(r.secondary_value, r.unit)}
                </td>
                {marketLabel && (
                  <td className="px-4 py-2.5 num text-ink-faint">
                    {formatMetricValue(r.market_value, r.unit)}
                  </td>
                )}
                <td className="px-4 py-2.5 num text-ink-muted">
                  {r.percentage_gap === null
                    ? "—"
                    : `${r.percentage_gap >= 0 ? "+" : ""}${r.percentage_gap.toFixed(2)}%`}
                </td>
                <td className="px-4 py-2.5">
                  <StatusPill status={r.status} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function StatusPill({ status }: { status: ComparisonRow["status"] }) {
  const cls =
    status === "ahead"
      ? "text-good border-good/40 bg-good/10"
      : status === "behind"
        ? "text-bad border-bad/40 bg-bad/10"
        : status === "level"
          ? "text-ink-muted border-line bg-bg-hover"
          : "text-ink-faint border-line bg-bg-hover";
  const label =
    status === "ahead"
      ? "Ahead"
      : status === "behind"
        ? "Behind"
        : status === "level"
          ? "At benchmark"
          : "Review";
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium",
        cls,
      )}
    >
      {label}
    </span>
  );
}

/* -------------------------------------------------------------------------
 * Priority Gap Matrix — 2×2 quadrant + list
 * ------------------------------------------------------------------------- */
function PriorityMatrix({ gaps }: { gaps: GapItem[] }) {
  const behind = gaps.filter(
    (g) => g.percentage_gap !== null && g.priority !== "low",
  );
  const maxGap = behind.reduce(
    (m, g) => Math.max(m, Math.abs(g.percentage_gap ?? 0)),
    0,
  );

  if (gaps.length === 0) {
    return (
      <Card
        eyebrow="Where to focus"
        title="Priority gap matrix"
        subtitle="Impact × gap size. Nothing to close — primary is at or above parity."
      >
        <p className="text-sm text-ink-muted">
          No behind-benchmark gaps detected.
        </p>
      </Card>
    );
  }

  return (
    <Card
      eyebrow="Where to focus"
      title="Priority gap matrix"
      subtitle="High-impact metrics with large gaps deserve immediate attention. The quadrant clusters gaps by importance and distance from benchmark."
    >
      <div className="grid grid-cols-1 lg:grid-cols-[2fr_3fr] gap-6">
        {/* 2×2 quadrant visualization */}
        <div>
          <QuadrantChart gaps={gaps} maxGap={maxGap} />
        </div>

        {/* Categorized bucket list */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <PriorityBucket
            title="High priority"
            tone="bad"
            items={gaps.filter((g) => g.priority === "high")}
          />
          <PriorityBucket
            title="Medium priority"
            tone="warn"
            items={gaps.filter((g) => g.priority === "medium")}
          />
          <PriorityBucket
            title="Low priority"
            tone="info"
            items={gaps.filter((g) => g.priority === "low")}
          />
        </div>
      </div>
    </Card>
  );
}

function QuadrantChart({ gaps, maxGap }: { gaps: GapItem[]; maxGap: number }) {
  const size = 320;
  const pad = 24;
  const inner = size - pad * 2;
  const range = Math.max(maxGap, 1);

  const priorityToY = (p: GapItem["priority"]) =>
    p === "high" ? 0.85 : p === "medium" ? 0.5 : 0.2;

  return (
    <div className="relative rounded-xl border border-line bg-bg-soft/40 p-4">
      <div className="mb-2 flex items-center justify-between">
        <div>
          <div className="text-sm font-semibold text-ink">Impact × Gap</div>
          <div className="text-[11px] text-ink-faint">
            Each dot is a metric. Top-right = act now.
          </div>
        </div>
        <div className="flex items-center gap-2 text-[10px] text-ink-faint">
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-bad" /> High
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-warn" /> Medium
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="inline-block h-2 w-2 rounded-full bg-info" /> Low
          </span>
        </div>
      </div>

      <svg
        viewBox={`0 0 ${size} ${size}`}
        className="w-full h-auto max-w-[420px] mx-auto block"
        role="img"
        aria-label="Priority gap matrix"
      >
        {/* Quadrant backdrop */}
        <rect
          x={pad}
          y={pad}
          width={inner}
          height={inner}
          fill="url(#quadGrad)"
          rx="8"
        />
        <defs>
          <linearGradient id="quadGrad" x1="0" y1="1" x2="1" y2="0">
            <stop offset="0" stopColor="#0d1425" />
            <stop offset="1" stopColor="#182541" />
          </linearGradient>
        </defs>

        {/* Grid */}
        <line
          x1={pad}
          x2={size - pad}
          y1={pad + inner / 2}
          y2={pad + inner / 2}
          stroke="#1e2a4a"
          strokeDasharray="3 3"
        />
        <line
          x1={pad + inner / 2}
          x2={pad + inner / 2}
          y1={pad}
          y2={size - pad}
          stroke="#1e2a4a"
          strokeDasharray="3 3"
        />

        {/* Axis labels */}
        <text x={pad} y={pad - 6} fill="#94a3c4" fontSize="10">
          HIGH IMPACT
        </text>
        <text
          x={size - pad}
          y={size - 4}
          fill="#94a3c4"
          fontSize="10"
          textAnchor="end"
        >
          GAP →
        </text>

        {/* Quadrant labels */}
        <text
          x={pad + 8}
          y={pad + 18}
          fill="#5c6885"
          fontSize="10"
          fontWeight="600"
        >
          MAINTAIN
        </text>
        <text
          x={size - pad - 8}
          y={pad + 18}
          fill="#f87171"
          fontSize="10"
          fontWeight="600"
          textAnchor="end"
        >
          IMMEDIATE
        </text>
        <text
          x={pad + 8}
          y={size - pad - 8}
          fill="#5c6885"
          fontSize="10"
          fontWeight="600"
        >
          MONITOR
        </text>
        <text
          x={size - pad - 8}
          y={size - pad - 8}
          fill="#facc15"
          fontSize="10"
          fontWeight="600"
          textAnchor="end"
        >
          SECONDARY
        </text>

        {/* Data points */}
        {gaps.map((g) => {
          if (g.percentage_gap === null) return null;
          const relGap = Math.abs(g.percentage_gap) / range;
          const cx = pad + Math.min(1, relGap) * inner;
          const cy = pad + (1 - priorityToY(g.priority)) * inner;
          const fill =
            g.priority === "high"
              ? "#f87171"
              : g.priority === "medium"
                ? "#facc15"
                : "#38bdf8";
          return (
            <g key={g.metric_id}>
              <circle
                cx={cx}
                cy={cy}
                r={6}
                fill={fill}
                fillOpacity="0.85"
                stroke="#0d1425"
                strokeWidth="1.5"
              />
              <title>
                {g.display_name}: {g.percentage_gap.toFixed(1)}% gap · {g.priority} priority
              </title>
            </g>
          );
        })}
      </svg>
    </div>
  );
}

function PriorityBucket({
  title,
  tone,
  items,
}: {
  title: string;
  tone: "bad" | "warn" | "info";
  items: GapItem[];
}) {
  const toneCls =
    tone === "bad"
      ? "border-bad/40 bg-bad/5"
      : tone === "warn"
        ? "border-warn/40 bg-warn/5"
        : "border-info/30 bg-info/5";
  const textCls =
    tone === "bad" ? "text-bad" : tone === "warn" ? "text-warn" : "text-info";
  return (
    <div className={clsx("rounded-xl border p-3", toneCls)}>
      <div className="flex items-center justify-between mb-2">
        <span
          className={clsx(
            "text-[11px] uppercase tracking-[0.14em] font-semibold",
            textCls,
          )}
        >
          {title}
        </span>
        <span className="text-xs text-ink-faint">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-ink-faint">—</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((g) => (
            <li
              key={g.metric_id}
              className="text-sm text-ink flex items-center justify-between gap-2"
            >
              <span className="truncate">{g.display_name}</span>
              <span className="font-mono tabular-nums text-[11px] text-ink-muted">
                {g.percentage_gap !== null
                  ? `${g.percentage_gap.toFixed(1)}%`
                  : "—"}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Reach the benchmark
 * ------------------------------------------------------------------------- */
function ReachTheBenchmark({ gaps }: { gaps: GapItem[] }) {
  if (gaps.length === 0) return null;
  return (
    <Card
      eyebrow="Action plan"
      title="How do we close the gap?"
      subtitle="Near-term and long-term targets for the highest-priority metrics."
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {gaps.map((g) => (
          <GapCard key={g.metric_id} gap={g} />
        ))}
      </div>
    </Card>
  );
}

function GapCard({ gap }: { gap: GapItem }) {
  return (
    <div className="rounded-xl border border-line bg-bg-soft/40 p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-medium text-ink">{gap.display_name}</div>
          <div className="text-[11px] text-ink-faint">
            {gap.direction === "higher_better"
              ? "Higher is better"
              : gap.direction === "lower_better"
                ? "Lower is better"
                : "Neutral direction"}
          </div>
        </div>
        <PriorityBadge value={gap.priority} />
      </div>

      <div className="mt-4 space-y-2 text-sm">
        <StepRow label="Current" value={gap.current_value} unit={gap.unit} tone="bad" />
        <StepRow
          label="Near-term target"
          value={gap.near_term_target}
          unit={gap.unit}
          tone="warn"
        />
        <StepRow
          label="Benchmark"
          value={gap.long_term_target}
          unit={gap.unit}
          tone="good"
        />
      </div>

      {gap.required_improvement && (
        <div className="mt-3 rounded-md border border-line bg-bg-soft/60 px-3 py-2 text-xs text-ink-muted">
          <span className="text-brand font-medium">Required:</span>{" "}
          {gap.required_improvement}
        </div>
      )}
    </div>
  );
}

function StepRow({
  label,
  value,
  unit,
  tone,
}: {
  label: string;
  value: number | null;
  unit: GapItem["unit"];
  tone: "bad" | "warn" | "good";
}) {
  const toneCls =
    tone === "bad" ? "text-bad" : tone === "warn" ? "text-warn" : "text-good";
  const dotCls =
    tone === "bad" ? "bg-bad" : tone === "warn" ? "bg-warn" : "bg-good";
  return (
    <div className="flex items-center justify-between">
      <span className="flex items-center gap-2 text-ink-muted">
        <span className={clsx("inline-block h-2 w-2 rounded-full", dotCls)} />
        {label}
      </span>
      <span className={clsx("font-mono tabular-nums font-medium", toneCls)}>
        {formatMetricValue(value, unit)}
      </span>
    </div>
  );
}

/* Kept exported for any downstream consumer of this module. */
export type { GapItem };
