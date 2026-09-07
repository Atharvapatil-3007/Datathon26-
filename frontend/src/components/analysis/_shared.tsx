import { ReactNode } from "react";
import clsx from "clsx";
import { Card } from "@/components/ui/Card";
import {
  MetricStatusBadge,
  PriorityBadge,
} from "@/components/ui/StatusBadges";
import { fmtDecimal, fmtInt, fmtPercent } from "@/lib/format";
import type {
  AnalysisHealthScore,
  AnalysisInsight,
  AnalysisPriority,
  LabeledMetric,
  MetricUnit,
} from "@/lib/types";

// ---------------------------------------------------------------------------
// Value formatting (unit-aware)
// ---------------------------------------------------------------------------
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
    default:
      return fmtDecimal(value, 2);
  }
}

// ---------------------------------------------------------------------------
// KPI tile with status badge — used across Self & Merger views.
// ---------------------------------------------------------------------------
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
        "rounded-lg border border-line bg-bg-soft/40 p-4",
        emphasise && "border-brand-muted bg-brand-soft/30",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="label truncate">{metric.display_name}</div>
        <MetricStatusBadge value={metric.status} />
      </div>
      <div className={clsx("mt-1 font-semibold tracking-tight text-ink", compact ? "text-lg" : "text-2xl")}>
        {formatMetricValue(metric.value, metric.unit)}
      </div>
      {metric.notes.length > 0 && !compact && (
        <div className="text-[11px] text-ink-faint mt-1 line-clamp-2">
          {metric.notes[0]}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Health ring + dimensions block.
// ---------------------------------------------------------------------------
export function HealthCard({
  health,
  title = "Financial Health",
}: {
  health: AnalysisHealthScore;
  title?: string;
}) {
  return (
    <Card title={title}>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center">
        <div className="flex flex-col items-center">
          <HealthRing score={health.overall_score} grade={health.grade} />
          <div className="mt-3 text-xs text-ink-muted">
            Grade <strong className="text-ink">{health.grade}</strong>
          </div>
        </div>
        <div className="space-y-3">
          {Object.entries(health.dimensions).map(([name, value]) => (
            <DimensionBar key={name} name={name} value={value} />
          ))}
          {Object.keys(health.dimensions).length === 0 && (
            <p className="text-sm text-ink-muted">No dimensions could be scored.</p>
          )}
        </div>
      </div>
      {health.notes.length > 0 && (
        <ul className="mt-4 space-y-1 text-xs text-ink-muted">
          {health.notes.map((n) => (
            <li key={n} className="flex items-start gap-2">
              <span className="text-warn">•</span>
              <span>{n}</span>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

function HealthRing({ score, grade }: { score: number; grade: string }) {
  const clamped = Math.max(0, Math.min(100, score));
  const color =
    score >= 90 ? "#4ade80" : score >= 80 ? "#38bdf8" : score >= 70 ? "#facc15" : score >= 60 ? "#f59e0b" : "#f87171";
  return (
    <div className="relative">
      <svg viewBox="0 0 120 120" className="w-36 h-36">
        <circle cx="60" cy="60" r="52" stroke="#243056" strokeWidth="10" fill="none" />
        <circle
          cx="60"
          cy="60"
          r="52"
          stroke={color}
          strokeWidth="10"
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${(clamped / 100) * 326.7} 326.7`}
          transform="rotate(-90 60 60)"
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center">
        <div className="text-3xl font-semibold text-ink">{fmtDecimal(score, 1)}</div>
        <div className="text-[11px] text-ink-muted">/ 100 · {grade}</div>
      </div>
    </div>
  );
}

function DimensionBar({ name, value }: { name: string; value: number }) {
  const tone =
    value >= 90 ? "bg-good" : value >= 70 ? "bg-brand" : value >= 60 ? "bg-warn" : "bg-bad";
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-ink capitalize">{name}</span>
        <span className="font-mono text-ink">{fmtDecimal(value, 1)}</span>
      </div>
      <div className="mt-1 h-1.5 rounded-full bg-bg-hover overflow-hidden">
        <div
          className={clsx("h-full rounded-full", tone)}
          style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
        />
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Ratios table (used in Self + Merger views)
// ---------------------------------------------------------------------------
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
          <thead className="bg-bg-soft/60 border-b border-line">
            <tr className="text-left text-[11px] uppercase tracking-wider text-ink-faint">
              <th className="px-4 py-2 font-medium">Ratio</th>
              <th className="px-4 py-2 font-medium">Value</th>
              <th className="px-4 py-2 font-medium">Status</th>
              <th className="px-4 py-2 font-medium">Formula</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((r) => (
              <tr key={r.metric_id}>
                <td className="px-4 py-2.5 text-ink font-medium">{r.display_name}</td>
                <td className="px-4 py-2.5 font-mono text-ink">
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

// ---------------------------------------------------------------------------
// Insights: OBSERVATION / ANALYSIS / RECOMMENDATION grouped
// ---------------------------------------------------------------------------
export function InsightsCard({
  insights,
  recommendations,
}: {
  insights: AnalysisInsight[];
  recommendations: AnalysisInsight[];
}) {
  const observations = insights.filter((i) => i.kind === "observation");
  const analyses = insights.filter((i) => i.kind === "analysis");

  return (
    <Card title="Insights">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <InsightColumn
          title="Observations"
          hint="What the data directly shows"
          items={observations}
          accent="text-ink-muted"
        />
        <InsightColumn
          title="Analysis"
          hint="What the numbers imply"
          items={analyses}
          accent="text-brand"
        />
        <InsightColumn
          title="Recommendations"
          hint="What to investigate or improve"
          items={recommendations}
          accent="text-good"
        />
      </div>
    </Card>
  );
}

function InsightColumn({
  title,
  hint,
  items,
  accent,
}: {
  title: string;
  hint: string;
  items: AnalysisInsight[];
  accent: string;
}) {
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between">
        <span className={clsx("label", accent)}>{title}</span>
        {items.some((i) => i.priority === "high") && (
          <PriorityBadge value="high" />
        )}
      </div>
      <p className="text-[11px] text-ink-faint mb-2">{hint}</p>
      {items.length === 0 ? (
        <p className="text-xs text-ink-faint">Nothing to flag.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((i, idx) => (
            <li key={`${i.text}-${idx}`} className="text-sm text-ink leading-snug">
              <span className={clsx(accent, "mr-1")}>•</span>
              <span className="text-ink-muted">{i.text}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Strengths / Weaknesses / Opportunities / Risks lists
// ---------------------------------------------------------------------------
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
    <Card title="Strengths, weaknesses, opportunities, risks">
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
    good: "text-good",
    warn: "text-warn",
    info: "text-brand",
    bad: "text-bad",
  } as const;
  return (
    <div className="rounded-lg border border-line bg-bg-soft/40 p-3">
      <div className={clsx("label mb-2", toneMap[tone])}>{title}</div>
      {items.length === 0 ? (
        <p className="text-xs text-ink-faint">None identified.</p>
      ) : (
        <ul className="space-y-1 text-sm text-ink-muted">
          {items.map((s, i) => (
            <li key={`${s}-${i}`} className="flex items-start gap-2">
              <span className={clsx("mt-0.5", toneMap[tone])}>•</span>
              <span>{s}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confidence footer
// ---------------------------------------------------------------------------
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
    <Card title="Confidence">
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="label">Overall</div>
          <div className="mt-1 font-mono text-lg text-ink">
            {fmtPercent(overall)}
          </div>
        </div>
        <div>
          <div className="label">Metric coverage</div>
          <div className="mt-1 font-mono text-lg text-ink">
            {fmtPercent(coverage)}
          </div>
        </div>
      </div>
      {notes.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs text-ink-muted">
          {notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Helper wrapper for common section
// ---------------------------------------------------------------------------
export function Section({
  title,
  subtitle,
  action,
  children,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <Card title={title} subtitle={subtitle} action={action}>
      {children}
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Priority chip
// ---------------------------------------------------------------------------
export function PriorityChip({ value }: { value: AnalysisPriority }) {
  return <PriorityBadge value={value} />;
}
