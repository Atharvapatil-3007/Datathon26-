/**
 * Rule-based Q&A engine for the AI Assistant.
 *
 * We deliberately do NOT call an LLM. Instead, we pattern-match natural
 * questions against a set of intents, then read structured data from the
 * cached AnalysisResult to compose a truthful, evidence-backed answer.
 *
 * Every answer includes:
 *   - text: a short natural-language sentence
 *   - evidence: literal values pulled from the analysis
 *   - source: which pipeline the answer draws from
 *   - confidence: derived from AnalysisResult.confidence when available
 *   - status:    the MetricStatus of the underlying value (when applicable)
 */

import type {
  AnalysisMode,
  AnalysisResult,
  ComparisonRow,
  GapItem,
  LabeledMetric,
  MetricStatus,
} from "./types";
import { fmtCompactCurrency, fmtDecimal, fmtInt } from "./format";

export interface AnswerLine {
  label: string;
  value: string;
}

export interface AssistantAnswer {
  text: string;
  evidence: AnswerLine[];
  source: string;
  confidence: "High" | "Medium" | "Low";
  status?: MetricStatus;
}

/* -------------------------------------------------------------------------
 * Suggested questions — vary by mode
 * ------------------------------------------------------------------------- */
export function suggestedQuestions(mode: AnalysisMode | null): string[] {
  if (mode === "merger_partnership_analysis") {
    return [
      "How attractive is this combination?",
      "What synergies did you identify?",
      "What are the biggest combination risks?",
      "How do the two companies compare on revenue?",
      "What is the combined financial health score?",
    ];
  }
  if (mode === "competitor_market_benchmark") {
    return [
      "Where am I behind the competitor?",
      "Where am I ahead of the competitor?",
      "What is my biggest gap?",
      "How do I reach the benchmark?",
      "What is my head-to-head record?",
    ];
  }
  // Self-analysis (default)
  return [
    "How is my financial health?",
    "How did revenue change?",
    "What are my biggest risks?",
    "What opportunities did you find?",
    "What are the top recommendations?",
    "How profitable am I?",
  ];
}

/* -------------------------------------------------------------------------
 * Answer engine
 * ------------------------------------------------------------------------- */
export function answerQuestion(
  question: string,
  result: AnalysisResult | null,
  mode: AnalysisMode | null,
): AssistantAnswer {
  if (!result) {
    return {
      text:
        "I don't have any analysis loaded yet. Run a self, merger or benchmark analysis first — I'll then be able to answer questions using its results.",
      evidence: [],
      source: "No context",
      confidence: "Low",
    };
  }

  const q = question.toLowerCase();
  const conf = confidenceLabel(result);

  // ---- Health ----
  if (matches(q, ["health", "healthy", "financial health", "grade", "score"])) {
    return healthAnswer(result, conf);
  }

  // ---- Revenue / trends ----
  if (matches(q, ["revenue", "sales", "turnover", "top line"])) {
    return metricTrendAnswer(result, "revenue", conf, mode);
  }
  if (matches(q, ["profit", "net income", "net profit"])) {
    return metricTrendAnswer(result, "net_profit", conf, mode);
  }
  if (matches(q, ["margin"])) {
    return metricTrendAnswer(result, "net_margin", conf, mode);
  }
  if (matches(q, ["cash"])) {
    return metricTrendAnswer(result, "cash", conf, mode);
  }
  if (matches(q, ["debt", "leverage"])) {
    return metricTrendAnswer(result, "debt", conf, mode);
  }

  // ---- Risks / opportunities / recommendations ----
  if (matches(q, ["risk", "risks", "concern", "concerns", "danger"])) {
    return risksAnswer(result, conf);
  }
  if (matches(q, ["opportunity", "opportunities"])) {
    return opportunitiesAnswer(result, conf);
  }
  if (matches(q, ["recommend", "action", "what should", "next step"])) {
    return recommendationsAnswer(result, conf);
  }

  // ---- Benchmarking specific ----
  if (matches(q, ["ahead", "leading", "outperform"])) {
    return comparisonSideAnswer(result, "ahead", conf);
  }
  if (matches(q, ["behind", "lagging", "underperform", "gap"])) {
    return comparisonSideAnswer(result, "behind", conf);
  }
  if (matches(q, ["biggest gap", "top gap", "priority gap"])) {
    return topGapAnswer(result, conf);
  }
  if (matches(q, ["reach the benchmark", "close the gap", "how do i improve"])) {
    return reachBenchmarkAnswer(result, conf);
  }
  if (matches(q, ["head-to-head", "head to head", "record", "score card"])) {
    return headToHeadAnswer(result, conf);
  }

  // ---- Merger specific ----
  if (
    matches(q, ["synerg", "value creation", "combined benefit"])
  ) {
    return synergiesAnswer(result, conf);
  }
  if (matches(q, ["attractive", "attractiveness", "worth", "should we"])) {
    return attractivenessAnswer(result, conf);
  }
  if (matches(q, ["combined", "combination", "merged"])) {
    return combinedAnswer(result, conf);
  }

  // ---- Generic fallback: use summary_text ----
  return {
    text: result.summary_text,
    evidence: buildTopMetricEvidence(result.metrics, 3),
    source: modeSource(mode),
    confidence: conf,
  };
}

/* -------------------------------------------------------------------------
 * Intent handlers
 * ------------------------------------------------------------------------- */
function healthAnswer(r: AnalysisResult, conf: AssistantAnswer["confidence"]): AssistantAnswer {
  const h = r.financial_health;
  if (!h) {
    return {
      text: "No financial health score could be computed for this dataset.",
      evidence: [],
      source: "Financial health scorer",
      confidence: "Low",
    };
  }
  const top = Object.entries(h.dimensions)
    .sort((a, b) => (b[1] as number) - (a[1] as number))
    .slice(0, 3);
  return {
    text: `Overall financial health is ${fmtDecimal(h.overall_score, 1)} / 100 (grade ${h.grade}). ${h.notes[0] ?? ""}`,
    evidence: [
      { label: "Overall score", value: `${fmtDecimal(h.overall_score, 1)} / 100` },
      { label: "Grade", value: h.grade },
      ...top.map(([name, value]) => ({
        label: cap(name),
        value: `${fmtDecimal(value as number, 1)} / 100`,
      })),
    ],
    source: "Financial health scorer",
    confidence: conf,
    status: "calculated",
  };
}

function metricTrendAnswer(
  r: AnalysisResult,
  metricId: string,
  conf: AssistantAnswer["confidence"],
  _mode: AnalysisMode | null,
): AssistantAnswer {
  const m = findMetric(r, metricId);
  if (!m || m.value === null) {
    return {
      text: `${prettifyMetricId(metricId)} isn't available for this dataset.`,
      evidence: availableMetricsEvidence(r),
      source: "Metric extractor",
      confidence: "Low",
    };
  }
  const series = seriesToArray(m.period_series);
  if (series.length < 2) {
    return {
      text: `${m.display_name} is ${formatValue(m)} (${m.status}). Only one period available — no trend to report.`,
      evidence: [
        { label: m.display_name, value: formatValue(m) },
        { label: "Status", value: m.status },
      ],
      source: sourceLabel(m),
      confidence: conf,
      status: m.status,
    };
  }
  const first = series[0];
  const last = series[series.length - 1];
  const prev = series[series.length - 2];
  const yoy = ((last.value - prev.value) / Math.abs(prev.value || 1)) * 100;
  const totalChange = ((last.value - first.value) / Math.abs(first.value || 1)) * 100;
  const direction = yoy >= 0 ? "increased" : "declined";
  return {
    text:
      `${m.display_name} ${direction} by ${Math.abs(yoy).toFixed(1)}% ` +
      `from ${prev.period} to ${last.period}. ` +
      `Over the full window (${first.period} → ${last.period}) the change is ${totalChange >= 0 ? "+" : ""}${totalChange.toFixed(1)}%.`,
    evidence: [
      { label: prev.period, value: formatUnit(prev.value, m.unit) },
      { label: last.period, value: formatUnit(last.value, m.unit) },
      { label: "YoY change", value: `${yoy >= 0 ? "+" : ""}${yoy.toFixed(1)}%` },
      {
        label: "Full window",
        value: `${totalChange >= 0 ? "+" : ""}${totalChange.toFixed(1)}%`,
      },
    ],
    source: sourceLabel(m),
    confidence: conf,
    status: m.status,
  };
}

function risksAnswer(r: AnalysisResult, conf: AssistantAnswer["confidence"]): AssistantAnswer {
  if (r.risks.length === 0) {
    return {
      text: "No material risks were surfaced from the current data.",
      evidence: [],
      source: "Risk analyzer",
      confidence: conf,
    };
  }
  const top = r.risks.slice(0, 3);
  return {
    text:
      `${r.risks.length} risk${r.risks.length > 1 ? "s" : ""} identified. Highest severity: ` +
      top[0].title.toLowerCase() + ".",
    evidence: top.map((rk) => ({
      label: rk.severity.toUpperCase(),
      value: rk.title,
    })),
    source: "Risk analyzer",
    confidence: conf,
  };
}

function opportunitiesAnswer(
  r: AnalysisResult,
  conf: AssistantAnswer["confidence"],
): AssistantAnswer {
  if (r.opportunities.length === 0) {
    return {
      text: "No specific opportunities were flagged from the current data.",
      evidence: [],
      source: "Insight engine",
      confidence: conf,
    };
  }
  return {
    text: `${r.opportunities.length} opportunit${r.opportunities.length > 1 ? "ies" : "y"} identified.`,
    evidence: r.opportunities.slice(0, 4).map((o) => ({ label: "Opportunity", value: o })),
    source: "Insight engine",
    confidence: conf,
  };
}

function recommendationsAnswer(
  r: AnalysisResult,
  conf: AssistantAnswer["confidence"],
): AssistantAnswer {
  if (r.recommendations.length === 0) {
    return {
      text: "No recommendations were generated for this dataset.",
      evidence: [],
      source: "Insight engine",
      confidence: conf,
    };
  }
  const top = r.recommendations.slice(0, 4);
  return {
    text: `Top recommendation${top.length > 1 ? "s" : ""}: ${top[0].text}`,
    evidence: top.map((rec, i) => ({
      label: `#${i + 1} · ${rec.priority.toUpperCase()}`,
      value: rec.text,
    })),
    source: "Insight engine",
    confidence: conf,
  };
}

function comparisonSideAnswer(
  r: AnalysisResult,
  side: "ahead" | "behind",
  conf: AssistantAnswer["confidence"],
): AssistantAnswer {
  const rows = r.comparisons.filter((c) => c.status === side);
  if (rows.length === 0) {
    return {
      text: `Nothing where you are ${side} in the current comparison.`,
      evidence: [],
      source: "Benchmark comparator",
      confidence: conf,
    };
  }
  return {
    text: `You are ${side} on ${rows.length} metric${rows.length > 1 ? "s" : ""}.`,
    evidence: rows.slice(0, 5).map((rr) => ({
      label: rr.display_name,
      value:
        rr.percentage_gap === null
          ? "—"
          : `${rr.percentage_gap >= 0 ? "+" : ""}${rr.percentage_gap.toFixed(1)}%`,
    })),
    source: "Benchmark comparator",
    confidence: conf,
  };
}

function topGapAnswer(
  r: AnalysisResult,
  conf: AssistantAnswer["confidence"],
): AssistantAnswer {
  const top = topGaps(r.gaps, 3);
  if (top.length === 0) {
    return {
      text: "No behind-benchmark gaps identified — you are at or above parity across compared metrics.",
      evidence: [],
      source: "Gap analyzer",
      confidence: conf,
    };
  }
  const first = top[0];
  return {
    text:
      `Biggest gap: ${first.display_name} — currently ${formatUnit(first.current_value, first.unit)} ` +
      `vs benchmark ${formatUnit(first.long_term_target, first.unit)} ` +
      `(${first.percentage_gap !== null ? first.percentage_gap.toFixed(1) + "%" : ""} priority ${first.priority}).`,
    evidence: top.map((g) => ({
      label: g.display_name,
      value:
        (g.percentage_gap !== null ? `${g.percentage_gap.toFixed(1)}% gap · ` : "") +
        g.priority.toUpperCase(),
    })),
    source: "Gap analyzer",
    confidence: conf,
  };
}

function reachBenchmarkAnswer(
  r: AnalysisResult,
  conf: AssistantAnswer["confidence"],
): AssistantAnswer {
  const g = r.gaps[0];
  if (!g) {
    return {
      text: "No gaps to close — primary is at or above benchmark on every metric.",
      evidence: [],
      source: "Gap analyzer",
      confidence: conf,
    };
  }
  return {
    text:
      `Focus on ${g.display_name}. Move from ${formatUnit(g.current_value, g.unit)} → ` +
      `${formatUnit(g.near_term_target, g.unit)} (near-term) → ` +
      `${formatUnit(g.long_term_target, g.unit)} (benchmark).`,
    evidence: [
      { label: "Current", value: formatUnit(g.current_value, g.unit) },
      { label: "Near-term target", value: formatUnit(g.near_term_target, g.unit) },
      { label: "Benchmark", value: formatUnit(g.long_term_target, g.unit) },
      ...(g.required_improvement
        ? [{ label: "Required", value: g.required_improvement }]
        : []),
    ],
    source: "Gap analyzer",
    confidence: conf,
  };
}

function headToHeadAnswer(
  r: AnalysisResult,
  conf: AssistantAnswer["confidence"],
): AssistantAnswer {
  const ahead = r.comparisons.filter((c) => c.status === "ahead").length;
  const behind = r.comparisons.filter((c) => c.status === "behind").length;
  const level = r.comparisons.filter((c) => c.status === "level").length;
  return {
    text: `Head-to-head record: ${ahead} ahead, ${behind} behind, ${level} at parity across ${r.comparisons.length} comparable metrics.`,
    evidence: [
      { label: "Ahead", value: String(ahead) },
      { label: "Behind", value: String(behind) },
      { label: "At parity", value: String(level) },
    ],
    source: "Benchmark comparator",
    confidence: conf,
  };
}

function synergiesAnswer(
  r: AnalysisResult,
  conf: AssistantAnswer["confidence"],
): AssistantAnswer {
  if (r.synergies.length === 0) {
    return {
      text: "No quantifiable synergies could be identified from the combined data.",
      evidence: [],
      source: "Merger analyzer",
      confidence: conf,
    };
  }
  const top = r.synergies.slice(0, 4);
  return {
    text: `${r.synergies.length} potential synergies identified.`,
    evidence: top.map((s) => ({
      label: cap(s.kind) + (s.magnitude_hint ? ` · ${s.magnitude_hint.replace(/_/g, " ")}` : ""),
      value: s.title,
    })),
    source: "Merger analyzer",
    confidence: conf,
  };
}

function attractivenessAnswer(
  r: AnalysisResult,
  conf: AssistantAnswer["confidence"],
): AssistantAnswer {
  const match = r.warnings
    .map((w) => w.match(/Combination Attractiveness Score:\s*([\d.]+)/))
    .find(Boolean)?.[1];
  if (!match) {
    return {
      text: "No combination attractiveness score was produced for this scenario.",
      evidence: [],
      source: "Merger analyzer",
      confidence: conf,
    };
  }
  const score = parseFloat(match);
  return {
    text: `The combination attractiveness score is ${score.toFixed(1)} / 100. ${
      score >= 70 ? "Strong analytical support." : score >= 50 ? "Moderate case with real risks." : "Weak analytical support."
    }`,
    evidence: [
      { label: "Score", value: `${score.toFixed(1)} / 100` },
      { label: "Interpretation", value: score >= 70 ? "Strong" : score >= 50 ? "Moderate" : "Weak" },
    ],
    source: "Merger analyzer",
    confidence: conf,
    status: "scenario",
  };
}

function combinedAnswer(
  r: AnalysisResult,
  conf: AssistantAnswer["confidence"],
): AssistantAnswer {
  if (!r.combined_scenario) {
    return {
      text: "No combined scenario is available in this analysis.",
      evidence: [],
      source: "Merger analyzer",
      confidence: conf,
    };
  }
  const top = r.combined_scenario.metrics
    .filter((m) => m.value !== null)
    .slice(0, 4);
  return {
    text: `${r.combined_scenario.label} — headline combined figures below. All values are scenario-based, not forecasts.`,
    evidence: top.map((m) => ({
      label: m.display_name,
      value: formatValue(m),
    })),
    source: "Merger analyzer",
    confidence: conf,
    status: "scenario",
  };
}

/* -------------------------------------------------------------------------
 * Utilities
 * ------------------------------------------------------------------------- */
function matches(q: string, keywords: string[]): boolean {
  return keywords.some((k) => q.includes(k));
}

function findMetric(r: AnalysisResult, id: string): LabeledMetric | undefined {
  return (
    r.metrics.find((m) => m.metric_id === id) ??
    r.ratios.find((m) => m.metric_id === id)
  );
}

function seriesToArray(
  series: Record<string, number> | null,
): { period: string; value: number }[] {
  if (!series) return [];
  return Object.entries(series)
    .filter(([_, v]) => Number.isFinite(v))
    .map(([k, v]) => ({ period: k, value: Number(v) }))
    .sort((a, b) => a.period.localeCompare(b.period));
}

function formatValue(m: LabeledMetric): string {
  return formatUnit(m.value, m.unit);
}

function formatUnit(
  value: number | null | undefined,
  unit: LabeledMetric["unit"],
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

function buildTopMetricEvidence(metrics: LabeledMetric[], n: number): AnswerLine[] {
  return metrics
    .filter((m) => m.value !== null && m.status !== "unavailable")
    .slice(0, n)
    .map((m) => ({ label: m.display_name, value: formatValue(m) }));
}

function availableMetricsEvidence(r: AnalysisResult): AnswerLine[] {
  return r.metrics
    .filter((m) => m.value !== null)
    .slice(0, 5)
    .map((m) => ({ label: "Available", value: m.display_name }));
}

function topGaps(gaps: GapItem[], n: number): GapItem[] {
  const priorityRank = { high: 0, medium: 1, low: 2 } as const;
  return [...gaps]
    .sort((a, b) => {
      const p = priorityRank[a.priority] - priorityRank[b.priority];
      if (p !== 0) return p;
      return Math.abs(b.percentage_gap ?? 0) - Math.abs(a.percentage_gap ?? 0);
    })
    .slice(0, n);
}

function sourceLabel(m: LabeledMetric): string {
  return m.status === "reported"
    ? "Reported in dataset"
    : m.status === "calculated"
      ? "Derived from dataset"
      : m.status === "estimated"
        ? "Estimated"
        : m.status === "scenario"
          ? "Scenario"
          : "Unavailable";
}

function confidenceLabel(r: AnalysisResult): AssistantAnswer["confidence"] {
  const c = r.confidence?.overall ?? 0;
  if (c >= 0.75) return "High";
  if (c >= 0.5) return "Medium";
  return "Low";
}

function modeSource(mode: AnalysisMode | null): string {
  if (mode === "merger_partnership_analysis") return "Merger analyzer";
  if (mode === "competitor_market_benchmark") return "Benchmark analyzer";
  return "Self analyzer";
}

function prettifyMetricId(id: string): string {
  return id
    .split("_")
    .map((s) => s.charAt(0).toUpperCase() + s.slice(1))
    .join(" ");
}

function cap(s: string): string {
  if (!s) return s;
  return s.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Comparison row + gap item types re-exported for callers that need them.
export type { ComparisonRow };
