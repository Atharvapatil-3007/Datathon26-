import { ReactNode } from "react";
import clsx from "clsx";
import { Card } from "@/components/ui/Card";
import {
  MetricStatusBadge,
  PriorityBadge,
} from "@/components/ui/StatusBadges";
import { ScoreRing, scoreLabel } from "@/components/ui/ScoreRing";
import { InsightCard } from "@/components/ui/InsightCard";
import {
  fmtCompactCurrency,
  fmtDecimal,
  fmtInt,
  fmtPercent,
} from "@/lib/format";
import type {
  AnalysisHealthScore,
  AnalysisInsight,
  AnalysisPriority,
  LabeledMetric,
  MetricUnit,
} from "@/lib/types";

/* -------------------------------------------------------------------------
 * Metric value formatting (unit-aware)
 * ------------------------------------------------------------------------- */
export function formatMetricValue(
  value: number | null | undefined,
  unit: MetricUnit,
): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  switch (unit) {
    case "percent":
      return `${fmtDecimal(value, 2)}%`;
    case "ratio":
      return `${fmtDecimal(value, 2)}x`;
    case "count":
      return fmtInt(value);
    case "days":
      return `${fmtInt(value)}d`;
    case "currency":
      return fmtCompactCurrency(value);
    default:
      return fmtDecimal(value, 2);
  }
}

/* -------------------------------------------------------------------------
 * MetricTile — dense KPI tile
 * ------------------------------------------------------------------------- */
export function MetricTile({
  metric,
  compact = false,
  emphasise,
}: {
  metric: LabeledMetric;
  compact?: boolean;
  emphasise?: boolean;
}) {
  return (
    <div
      className={clsx(
        "rounded-xl border p-4 transition-colors",
        emphasise
          ? "border-brand-muted/70 bg-brand-soft/40"
          : "border-line bg-bg-card hover:border-brand-muted/40 hover:bg-bg-hover/40",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="label truncate">{metric.display_name}</div>
        <MetricStatusBadge value={metric.status} />
      </div>
      <div
        className={clsx(
          "mt-1.5 font-semibold tracking-tight text-ink tabular-nums",
          compact ? "text-lg" : "text-2xl",
        )}
      >
        {formatMetricValue(metric.value, metric.unit)}
      </div>
      {metric.notes.length > 0 && !compact && (
        <div className="text-[11px] text-ink-faint mt-1 line-clamp-2 leading-snug">
          {metric.notes[0]}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * HealthCard — score ring + dimensions with expandable notes
 * ------------------------------------------------------------------------- */
export function HealthCard({
  health,
  title = "Financial Health",
  subtitle,
}: {
  health: AnalysisHealthScore;
  title?: string;
  subtitle?: string;
}) {
  return (
    <Card
      eyebrow="Executive score"
      title={title}
      subtitle={
        subtitle ??
        "Composite health from profitability, liquidity, growth, leverage and efficiency."
      }
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-center">
        <div className="flex flex-col items-center gap-3">
          <ScoreRing
            score={health.overall_score}
            grade={health.grade}
            size="lg"
            label="/ 100"
          />
          <div className="rounded-full border border-line bg-bg-soft/60 px-3 py-1 text-xs text-ink-muted">
            {scoreLabel(health.overall_score)}
          </div>
        </div>
        <div className="md:col-span-2 space-y-3">
          {Object.entries(health.dimensions).map(([name, value]) => (
            <DimensionBar key={name} name={name} value={value} />
          ))}
          {Object.keys(health.dimensions).length === 0 && (
            <p className="text-sm text-ink-muted">
              No dimensions could be scored from the available data.
            </p>
          )}
        </div>
      </div>

      {health.notes.length > 0 && (
        <details className="mt-5 group">
          <summary className="cursor-pointer inline-flex items-center gap-1.5 text-xs text-brand hover:text-brand-strong">
            <span className="group-open:rotate-90 transition-transform" aria-hidden>
              ▶
            </span>
            Why this score?
          </summary>
          <ul className="mt-3 space-y-1 text-xs text-ink-muted">
            {health.notes.map((n) => (
              <li key={n} className="flex items-start gap-2">
                <span className="text-warn mt-0.5">·</span>
                <span>{n}</span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </Card>
  );
}

function DimensionBar({ name, value }: { name: string; value: number }) {
  const tone =
    value >= 90 ? "bg-good" : value >= 70 ? "bg-brand" : value >= 60 ? "bg-warn" : "bg-bad";
  const toneText =
    value >= 90
      ? "text-good"
      : value >= 70
        ? "text-brand"
        : value >= 60
          ? "text-warn"
          : "text-bad";
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-ink capitalize">{name}</span>
        <span className={clsx("font-mono tabular-nums font-medium", toneText)}>
          {fmtDecimal(value, 1)}
        </span>
      </div>
      <div className="mt-1.5 h-1.5 rounded-full bg-bg-hover overflow-hidden">
        <div
          className={clsx("h-full rounded-full transition-all duration-500", tone)}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * RatiosTable
 * ------------------------------------------------------------------------- */
export function RatiosTable({
  ratios,
  title = "Ratios",
  subtitle,
}: {
  ratios: LabeledMetric[];
  title?: string;
  subtitle?: string;
}) {
  const rows = ratios.filter((r) => r.status !== "unavailable" && r.value !== null);
  if (rows.length === 0) {
    return (
      <Card title={title} subtitle={subtitle}>
        <p className="text-sm text-ink-muted">
          No ratios could be computed from the available metrics.
        </p>
      </Card>
    );
  }
  return (
    <Card title={title} subtitle={subtitle} bodyClassName="p-0">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft/70 border-b border-line">
            <tr className="text-left text-[11px] uppercase tracking-[0.08em] text-ink-faint">
              <th className="px-4 py-2.5 font-medium">Ratio</th>
              <th className="px-4 py-2.5 font-medium text-right">Value</th>
              <th className="px-4 py-2.5 font-medium">Status</th>
              <th className="px-4 py-2.5 font-medium">Formula</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => (
              <tr key={r.metric_id}>
                <td className="px-4 py-2.5 text-ink font-medium">
                  {r.display_name}
                </td>
                <td className="px-4 py-2.5 num text-ink">
                  {formatMetricValue(r.value, r.unit)}
                </td>
                <td className="px-4 py-2.5">
                  <MetricStatusBadge value={r.status} />
                </td>
                <td className="px-4 py-2.5 text-[11px] text-ink-muted font-mono">
                  {r.notes[0] ?? ""}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------------------
 * InsightsCard — grouped observation / analysis / recommendation
 * ------------------------------------------------------------------------- */
export function InsightsCard({
  insights,
  recommendations,
}: {
  insights: AnalysisInsight[];
  recommendations: AnalysisInsight[];
}) {
  const observations = insights.filter((i) => i.kind === "observation");
  const analyses = insights.filter((i) => i.kind === "analysis");

  if (
    observations.length === 0 &&
    analyses.length === 0 &&
    recommendations.length === 0
  ) {
    return (
      <Card eyebrow="Insight engine" title="Insights & recommendations">
        <p className="text-sm text-ink-muted">
          The insight engine had nothing material to flag for this dataset.
        </p>
      </Card>
    );
  }

  return (
    <Card
      eyebrow="Insight engine"
      title="Insights & recommendations"
      subtitle="What the data shows, what it implies, and what to look at next."
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <InsightColumn
          heading="Observations"
          hint="What the data directly shows."
          items={observations}
          kind="observation"
        />
        <InsightColumn
          heading="Analysis"
          hint="What the numbers imply."
          items={analyses}
          kind="analysis"
        />
        <InsightColumn
          heading="Recommendations"
          hint="What to investigate or improve."
          items={recommendations}
          kind="recommendation"
        />
      </div>
    </Card>
  );
}

function InsightColumn({
  heading,
  hint,
  items,
  kind,
}: {
  heading: string;
  hint: string;
  items: AnalysisInsight[];
  kind: "observation" | "analysis" | "recommendation";
}) {
  return (
    <div>
      <div className="mb-3">
        <div className="text-sm font-semibold text-ink">{heading}</div>
        <div className="text-[11px] text-ink-faint mt-0.5">{hint}</div>
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-ink-faint">Nothing to flag.</p>
      ) : (
        <div className="space-y-2">
          {items.map((i, idx) => (
            <InsightCard
              key={`${i.text}-${idx}`}
              kind={kind}
              title={i.text}
              priority={i.priority}
            />
          ))}
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * SwotBoard — strengths / weaknesses / opportunities / risks
 * ------------------------------------------------------------------------- */
export function SwotBoard({
  strengths,
  weaknesses,
  opportunities,
  risks,
}: {
  strengths: string[];
  weaknesses: string[];
  opportunities: string[];
  risks: string[];
}) {
  return (
    <Card
      eyebrow="Perspective"
      title="Strengths, weaknesses, opportunities & risks"
      subtitle="A quick strategic scan surfaced from the underlying metrics."
    >
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <SwotList title="Strengths" items={strengths} tone="good" />
        <SwotList title="Weaknesses" items={weaknesses} tone="warn" />
        <SwotList title="Opportunities" items={opportunities} tone="info" />
        <SwotList title="Risks" items={risks} tone="bad" />
      </div>
    </Card>
  );
}

function SwotList({
  title,
  items,
  tone,
}: {
  title: string;
  items: string[];
  tone: "good" | "warn" | "info" | "bad";
}) {
  const toneMap = {
    good: { text: "text-good", ring: "border-good/30", bg: "bg-good/5" },
    warn: { text: "text-warn", ring: "border-warn/30", bg: "bg-warn/5" },
    info: { text: "text-info", ring: "border-info/30", bg: "bg-info/5" },
    bad: { text: "text-bad", ring: "border-bad/30", bg: "bg-bad/5" },
  } as const;
  const t = toneMap[tone];
  return (
    <div className={clsx("rounded-xl border p-4", t.ring, t.bg)}>
      <div
        className={clsx(
          "text-[11px] uppercase tracking-[0.14em] font-semibold mb-2",
          t.text,
        )}
      >
        {title}
      </div>
      {items.length === 0 ? (
        <p className="text-xs text-ink-faint">None identified.</p>
      ) : (
        <ul className="space-y-1.5 text-sm text-ink-muted">
          {items.map((s, i) => (
            <li key={`${s}-${i}`} className="flex items-start gap-2 leading-snug">
              <span
                className={clsx(
                  "mt-1 h-1 w-1 rounded-full shrink-0 bg-current",
                  t.text,
                )}
              />
              <span>{s}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * ConfidenceFooter
 * ------------------------------------------------------------------------- */
export function ConfidenceFooter({
  overall,
  coverage,
  notes,
}: {
  overall: number;
  coverage: number;
  notes: string[];
}) {
  return (
    <Card eyebrow="Trust" title="Confidence in this analysis">
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div className="rounded-lg border border-line bg-bg-soft/40 p-3">
          <div className="label">Overall</div>
          <div className="mt-1 font-mono text-lg text-ink tabular-nums">
            {fmtPercent(overall)}
          </div>
        </div>
        <div className="rounded-lg border border-line bg-bg-soft/40 p-3">
          <div className="label">Metric coverage</div>
          <div className="mt-1 font-mono text-lg text-ink tabular-nums">
            {fmtPercent(coverage)}
          </div>
        </div>
      </div>
      {notes.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs text-ink-muted">
          {notes.map((n) => (
            <li key={n} className="flex items-start gap-2">
              <span className="text-ink-faint mt-0.5">·</span>
              <span>{n}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

/* -------------------------------------------------------------------------
 * Section — thin Card passthrough kept for compatibility
 * ------------------------------------------------------------------------- */
export function Section({
  title,
  subtitle,
  action,
  eyebrow,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  eyebrow?: string;
  children: ReactNode;
}) {
  return (
    <Card title={title} subtitle={subtitle} action={action} eyebrow={eyebrow}>
      {children}
    </Card>
  );
}

/* -------------------------------------------------------------------------
 * PriorityChip — kept as convenience export
 * ------------------------------------------------------------------------- */
export function PriorityChip({ value }: { value: AnalysisPriority }) {
  return <PriorityBadge value={value} />;
}
