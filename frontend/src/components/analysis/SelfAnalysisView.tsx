import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card } from "@/components/ui/Card";
import { MetricCard } from "@/components/ui/MetricCard";
import { InsightCard } from "@/components/ui/InsightCard";
import {
  ConfidenceFooter,
  HealthCard,
  InsightsCard,
  RatiosTable,
  SwotBoard,
  formatMetricValue,
} from "./_shared";
import { fmtCompactCurrency } from "@/lib/format";
import type { AnalysisResult, LabeledMetric } from "@/lib/types";

/**
 * Ranking priority for KPI-row selection. Metrics listed earlier are
 * preferred; anything not listed still gets shown but at a lower rank.
 */
const KPI_ORDER = [
  "revenue",
  "net_profit",
  "operating_profit",
  "ebitda",
  "net_margin",
  "operating_margin",
  "gross_margin",
  "cash",
  "debt",
  "equity",
  "assets",
  "customers",
  "deposits",
  "loans",
  "net_interest_income",
];

/**
 * Which metrics we'd like to render as trend charts if they have a
 * period_series (multi-period data).
 */
const TREND_CANDIDATES = ["revenue", "net_profit", "ebitda", "operating_profit"];

export function SelfAnalysisView({ result }: { result: AnalysisResult }) {
  const rankedMetrics = useMemo(
    () => [...result.metrics].sort((a, b) => rank(a.metric_id) - rank(b.metric_id)),
    [result.metrics],
  );

  const kpiMetrics = useMemo(
    () =>
      rankedMetrics
        .filter((m) => m.value !== null && m.status !== "unavailable")
        .slice(0, 6),
    [rankedMetrics],
  );

  const trendMetrics = useMemo(
    () =>
      rankedMetrics.filter(
        (m) =>
          TREND_CANDIDATES.includes(m.metric_id) &&
          m.period_series &&
          Object.keys(m.period_series).length > 1,
      ),
    [rankedMetrics],
  );

  const risks = result.risks;
  const strengths = result.strengths;
  const opportunities = result.opportunities;

  return (
    <div className="space-y-6">
      {/* Executive summary */}
      <Card eyebrow="Executive summary" title="Analytical narrative">
        <p className="text-sm text-ink-muted leading-relaxed text-pretty">
          {result.summary_text}
        </p>
        {result.warnings.length > 0 && (
          <ul className="mt-3 space-y-1 text-xs text-warn">
            {result.warnings.slice(0, 4).map((w) => (
              <li key={w}>⚠ {w}</li>
            ))}
          </ul>
        )}
      </Card>

      {/* KPI row */}
      {kpiMetrics.length > 0 && (
        <section>
          <div className="mb-3 flex items-baseline justify-between">
            <div>
              <div className="eyebrow">Financial overview</div>
              <h2 className="heading-2 mt-1">Key metrics</h2>
            </div>
            <div className="text-[11px] text-ink-faint">
              {kpiMetrics.length} of {rankedMetrics.length} shown
            </div>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
            {kpiMetrics.map((m, i) => (
              <ExecMetric key={m.metric_id} metric={m} emphasise={i === 0} />
            ))}
          </div>
        </section>
      )}

      {/* Trend charts */}
      {trendMetrics.length > 0 && (
        <section>
          <div className="mb-3">
            <div className="eyebrow">Performance trends</div>
            <h2 className="heading-2 mt-1">Multi-period view</h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {trendMetrics.slice(0, 4).map((m) => (
              <TrendCard key={m.metric_id} metric={m} />
            ))}
          </div>
        </section>
      )}

      {/* Financial health */}
      {result.financial_health && <HealthCard health={result.financial_health} />}

      {/* Risks & opportunities cards */}
      {(risks.length > 0 || opportunities.length > 0 || strengths.length > 0) && (
        <Card
          eyebrow="Strategic posture"
          title="Risks & opportunities"
          subtitle="Prioritised items surfaced from the data — supporting metrics link back to the raw values."
        >
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-3">
              <div className="text-[11px] uppercase tracking-[0.14em] text-bad font-semibold">
                Risks
              </div>
              {risks.length === 0 ? (
                <p className="text-xs text-ink-faint">No material risks flagged.</p>
              ) : (
                risks.slice(0, 4).map((r) => (
                  <InsightCard
                    key={r.title}
                    kind="risk"
                    title={r.title}
                    body={r.description}
                    priority={r.severity}
                  />
                ))
              )}
            </div>
            <div className="space-y-3">
              <div className="text-[11px] uppercase tracking-[0.14em] text-good font-semibold">
                Opportunities & strengths
              </div>
              {opportunities.length === 0 && strengths.length === 0 ? (
                <p className="text-xs text-ink-faint">
                  None identified in the current data.
                </p>
              ) : (
                <>
                  {opportunities.slice(0, 4).map((o) => (
                    <InsightCard
                      key={`opp-${o}`}
                      kind="opportunity"
                      title={o}
                    />
                  ))}
                  {strengths.slice(0, 3).map((s) => (
                    <InsightCard key={`str-${s}`} kind="observation" title={s} />
                  ))}
                </>
              )}
            </div>
          </div>
        </Card>
      )}

      {/* Ratios */}
      <RatiosTable
        ratios={result.ratios}
        title="Financial ratios"
        subtitle="Only ratios whose input metrics were present in the dataset are shown."
      />

      {/* SWOT */}
      <SwotBoard
        strengths={strengths}
        weaknesses={result.weaknesses}
        opportunities={opportunities}
        risks={risks.map((r) => r.title)}
      />

      {/* Insights & recommendations */}
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
 * Executive metric card — wraps MetricCard with period_series → change/spark
 * ------------------------------------------------------------------------- */
function ExecMetric({
  metric,
  emphasise,
}: {
  metric: LabeledMetric;
  emphasise?: boolean;
}) {
  const series = seriesToArray(metric.period_series);
  const change =
    series.length > 1
      ? ((series[series.length - 1].value - series[series.length - 2].value) /
          Math.abs(series[series.length - 2].value || 1)) *
        100
      : null;
  const comparisonLabel =
    series.length > 1
      ? `vs ${series[series.length - 2].period}`
      : undefined;

  return (
    <MetricCard
      label={metric.display_name}
      value={metric.value}
      unit={metric.unit}
      status={metric.status}
      changePct={change}
      comparisonLabel={comparisonLabel}
      trend={series.length > 1 ? series.map((p) => p.value) : undefined}
      hint={metric.notes[0]}
      emphasise={emphasise}
    />
  );
}

/* -------------------------------------------------------------------------
 * TrendCard — full area chart for a single labeled metric
 * ------------------------------------------------------------------------- */
function TrendCard({ metric }: { metric: LabeledMetric }) {
  const series = seriesToArray(metric.period_series).map((p) => ({
    period: p.period,
    value: p.value,
  }));
  const min = Math.min(...series.map((p) => p.value));
  const max = Math.max(...series.map((p) => p.value));
  const domain: [number, number] = [
    min - (max - min) * 0.1,
    max + (max - min) * 0.1,
  ];

  return (
    <Card>
      <div className="flex items-start justify-between gap-4">
        <div>
          <div className="label">{metric.display_name}</div>
          <div className="mt-1 text-2xl font-semibold text-ink tabular-nums">
            {formatMetricValue(metric.value, metric.unit)}
          </div>
        </div>
        <div className="text-[11px] text-ink-faint">
          {series[0]?.period} – {series[series.length - 1]?.period}
        </div>
      </div>
      <div className="mt-3 h-40">
        <ResponsiveContainer>
          <AreaChart data={series} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
            <defs>
              <linearGradient id={`grad-${metric.metric_id}`} x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor="#7aa8ff" stopOpacity={0.35} />
                <stop offset="100%" stopColor="#7aa8ff" stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke="#1e2a4a" strokeDasharray="3 3" vertical={false} />
            <XAxis dataKey="period" tick={{ fill: "#94a3c4", fontSize: 10 }} stroke="#1e2a4a" />
            <YAxis
              tick={{ fill: "#94a3c4", fontSize: 10 }}
              stroke="#1e2a4a"
              domain={domain}
              tickFormatter={(v) => shortNumber(v)}
              width={44}
            />
            <Tooltip
              contentStyle={{
                background: "#101a33",
                border: "1px solid #1e2a4a",
                borderRadius: 8,
                fontSize: 12,
                color: "#eef2ff",
              }}
              labelStyle={{ color: "#94a3c4" }}
              formatter={(v: number) => [formatMetricValue(v, metric.unit), metric.display_name]}
            />
            <Area
              type="monotone"
              dataKey="value"
              stroke="#7aa8ff"
              strokeWidth={2}
              fill={`url(#grad-${metric.metric_id})`}
              dot={{ r: 3, stroke: "#7aa8ff", fill: "#101a33", strokeWidth: 1.5 }}
              activeDot={{ r: 4 }}
            />
          </AreaChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------------------
 * Helpers
 * ------------------------------------------------------------------------- */
function rank(id: string): number {
  const i = KPI_ORDER.indexOf(id);
  return i === -1 ? 999 : i;
}

interface SeriesPoint {
  period: string;
  value: number;
}

function seriesToArray(series: Record<string, number> | null): SeriesPoint[] {
  if (!series) return [];
  const entries = Object.entries(series)
    .filter(([_, v]) => Number.isFinite(v))
    .map(([k, v]) => ({ period: k, value: Number(v) }));
  // Sort by period label (works for FY2024 / 2024 / 2024-01 / ISO dates).
  entries.sort((a, b) => a.period.localeCompare(b.period));
  return entries;
}

function shortNumber(v: number): string {
  return fmtCompactCurrency(v);
}
