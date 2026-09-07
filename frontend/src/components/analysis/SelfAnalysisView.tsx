import { Card } from "@/components/ui/Card";
import {
  ConfidenceFooter,
  HealthCard,
  InsightsCard,
  MetricTile,
  RatiosTable,
  Section,
  SwotBoard,
} from "./_shared";
import type { AnalysisResult } from "@/lib/types";

const CORE_ORDER = [
  "revenue",
  "net_profit",
  "operating_profit",
  "ebitda",
  "assets",
  "equity",
  "debt",
  "cash",
  "customers",
  "deposits",
  "loans",
  "net_interest_income",
];

export function SelfAnalysisView({ result }: { result: AnalysisResult }) {
  const metrics = result.metrics
    .filter((m) => m.value !== null && m.status !== "unavailable")
    .slice()
    .sort((a, b) => rank(a.metric_id) - rank(b.metric_id));

  return (
    <div className="space-y-6">
      <Section title="Executive summary">
        <p className="text-sm text-ink-muted leading-relaxed">{result.summary_text}</p>
        {result.warnings.length > 0 && (
          <ul className="mt-3 space-y-1 text-xs text-warn">
            {result.warnings.map((w) => (
              <li key={w}>⚠ {w}</li>
            ))}
          </ul>
        )}
      </Section>

      {result.financial_health && (
        <HealthCard health={result.financial_health} />
      )}

      <Card title="Key metrics" subtitle="Base financial metrics extracted from the dataset">
        {metrics.length === 0 ? (
          <p className="text-sm text-ink-muted">No canonical metrics identified.</p>
        ) : (
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
            {metrics.slice(0, 12).map((m) => (
              <MetricTile key={m.metric_id} metric={m} />
            ))}
          </div>
        )}
      </Card>

      <RatiosTable
        ratios={result.ratios}
        title="Ratios"
        subtitle="Only ratios whose inputs were present are shown."
      />

      <SwotBoard
        strengths={result.strengths}
        weaknesses={result.weaknesses}
        opportunities={result.opportunities}
        risks={result.warnings.filter((w) => !w.includes("Attractiveness"))}
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

function rank(id: string): number {
  const idx = CORE_ORDER.indexOf(id);
  return idx === -1 ? 999 : idx;
}
