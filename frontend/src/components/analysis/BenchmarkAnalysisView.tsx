import clsx from "clsx";
import { Card } from "@/components/ui/Card";
import { PriorityBadge } from "@/components/ui/StatusBadges";
import {
  formatMetricValue,
  ConfidenceFooter,
  InsightsCard,
  Section,
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
  const primaryName = result.primary_entity?.display_name ?? "Primary";
  const competitorName = result.secondary_entity?.display_name ?? "Competitor";
  const marketName = result.market_entity?.display_name;

  return (
    <div className="space-y-6">
      <Section
        title="Executive summary"
        action={
          <button className="btn" onClick={onReset}>
            Change inputs
          </button>
        }
      >
        <p className="text-sm text-ink-muted leading-relaxed">{result.summary_text}</p>
      </Section>

      <ComparisonTable
        rows={result.comparisons}
        primaryLabel={primaryName}
        secondaryLabel={competitorName}
        marketLabel={marketName}
      />

      <PriorityMatrix gaps={result.gaps} />

      <ReachTheBenchmark gaps={result.gaps.slice(0, 5)} />

      <SwotBoard
        strengths={result.strengths}
        weaknesses={result.weaknesses}
        opportunities={result.opportunities}
        risks={[]}
      />

      <InsightsCard insights={result.insights} recommendations={result.recommendations} />

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

// ---------------------------------------------------------------------------
// Comparison table
// ---------------------------------------------------------------------------
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
      <Card title="Comparison">
        <p className="text-sm text-ink-muted">
          No comparable metrics were found across the two datasets.
        </p>
      </Card>
    );
  }

  return (
    <Card
      title="Head-to-head comparison"
      subtitle="Direction-aware — 'ahead' or 'behind' is metric-specific."
      bodyClassName="p-0"
    >
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft/60 border-b border-line">
            <tr className="text-left text-[11px] uppercase tracking-wider text-ink-faint">
              <th className="px-4 py-2 font-medium">Metric</th>
              <th className="px-4 py-2 font-medium">{primaryLabel}</th>
              <th className="px-4 py-2 font-medium">{secondaryLabel}</th>
              {marketLabel && (
                <th className="px-4 py-2 font-medium">{marketLabel}</th>
              )}
              <th className="px-4 py-2 font-medium">Gap</th>
              <th className="px-4 py-2 font-medium">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => (
              <tr key={r.metric_id}>
                <td className="px-4 py-2.5 text-ink font-medium">{r.display_name}</td>
                <td className="px-4 py-2.5 font-mono text-ink-muted">
                  {formatMetricValue(r.primary_value, r.unit)}
                </td>
                <td className="px-4 py-2.5 font-mono text-ink-muted">
                  {formatMetricValue(r.secondary_value, r.unit)}
                </td>
                {marketLabel && (
                  <td className="px-4 py-2.5 font-mono text-ink-faint">
                    {formatMetricValue(r.market_value, r.unit)}
                  </td>
                )}
                <td className="px-4 py-2.5 font-mono text-ink-muted">
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
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium capitalize",
        cls,
      )}
    >
      {status}
    </span>
  );
}

// ---------------------------------------------------------------------------
// Priority matrix (High / Medium / Low buckets)
// ---------------------------------------------------------------------------
function PriorityMatrix({ gaps }: { gaps: GapItem[] }) {
  const high = gaps.filter((g) => g.priority === "high");
  const medium = gaps.filter((g) => g.priority === "medium");
  const low = gaps.filter((g) => g.priority === "low");

  return (
    <Card
      title="Gap priority matrix"
      subtitle="High-priority gaps close the biggest competitive distance."
    >
      {gaps.length === 0 ? (
        <p className="text-sm text-ink-muted">
          No behind-benchmark gaps — primary is at or above parity.
        </p>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <PriorityBucket title="High priority" items={high} tone="bad" />
          <PriorityBucket title="Medium priority" items={medium} tone="warn" />
          <PriorityBucket title="Low priority" items={low} tone="info" />
        </div>
      )}
    </Card>
  );
}

function PriorityBucket({
  title,
  items,
  tone,
}: {
  title: string;
  items: GapItem[];
  tone: "bad" | "warn" | "info";
}) {
  const toneCls =
    tone === "bad"
      ? "border-bad/40 bg-bad/5"
      : tone === "warn"
      ? "border-warn/40 bg-warn/5"
      : "border-line bg-bg-soft/40";
  return (
    <div className={clsx("rounded-lg border p-3", toneCls)}>
      <div className="flex items-center justify-between mb-2">
        <span className="label">{title}</span>
        <span className="text-xs text-ink-faint">{items.length}</span>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-ink-faint">—</p>
      ) : (
        <ul className="space-y-1.5">
          {items.map((g) => (
            <li key={g.metric_id} className="text-sm text-ink flex items-center justify-between gap-2">
              <span className="truncate">{g.display_name}</span>
              <span className="font-mono text-[11px] text-ink-muted">
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

// ---------------------------------------------------------------------------
// "How do we reach the benchmark?" — top gap detail cards
// ---------------------------------------------------------------------------
function ReachTheBenchmark({ gaps }: { gaps: GapItem[] }) {
  if (gaps.length === 0) return null;
  return (
    <Card
      title="How do we close the gap?"
      subtitle="Top gaps with near-term and long-term targets."
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
    <div className="rounded-lg border border-line bg-bg-soft/40 p-4">
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
        <StepRow label="Near-term target" value={gap.near_term_target} unit={gap.unit} tone="warn" />
        <StepRow label="Benchmark" value={gap.long_term_target} unit={gap.unit} tone="good" />
      </div>

      {gap.required_improvement && (
        <p className="mt-3 text-xs text-ink-muted">{gap.required_improvement}</p>
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
  return (
    <div className="flex items-center justify-between">
      <span className="text-ink-muted">{label}</span>
      <span className={clsx("font-mono font-medium", toneCls)}>
        {formatMetricValue(value, unit)}
      </span>
    </div>
  );
}
