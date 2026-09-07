import clsx from "clsx";
import { Card } from "@/components/ui/Card";
import { PriorityBadge, MetricStatusBadge } from "@/components/ui/StatusBadges";
import {
  formatMetricValue,
  ConfidenceFooter,
  HealthCard,
  InsightsCard,
  Section,
} from "./_shared";
import type {
  AnalysisResult,
  RiskItem,
  SynergyItem,
} from "@/lib/types";

const COMPARE_ORDER = [
  "revenue",
  "net_profit",
  "operating_profit",
  "ebitda",
  "assets",
  "liabilities",
  "equity",
  "debt",
  "cash",
  "customers",
  "gross_margin",
  "operating_margin",
  "net_margin",
  "roa",
  "roe",
  "debt_to_equity",
  "current_ratio",
];

export function MergerAnalysisView({
  result,
  onReset,
}: {
  result: AnalysisResult;
  onReset: () => void;
}) {
  const primary = new Map(
    (result.primary_entity?.metrics ?? []).map((m) => [m.metric_id, m]),
  );
  const secondary = new Map(
    (result.secondary_entity?.metrics ?? []).map((m) => [m.metric_id, m]),
  );
  const combined = new Map(
    [
      ...(result.combined_scenario?.metrics ?? []),
      ...result.ratios,
    ].map((m) => [m.metric_id, m]),
  );

  const rows = COMPARE_ORDER.map((id) => ({
    id,
    p: primary.get(id),
    s: secondary.get(id),
    c: combined.get(id),
  })).filter((r) => r.p || r.s || r.c);

  const attractiveness = result.warnings
    .map((w) => w.match(/Combination Attractiveness Score:\s*([\d.]+)/))
    .find(Boolean)?.[1];

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
        {attractiveness && (
          <div className="mt-4 flex items-center gap-3">
            <div className="rounded-lg border border-brand-muted bg-brand-soft/40 px-4 py-3">
              <div className="label">Combination Attractiveness</div>
              <div className="mt-0.5 text-2xl font-semibold text-brand">
                {parseFloat(attractiveness).toFixed(1)}
                <span className="text-sm text-ink-muted"> / 100</span>
              </div>
            </div>
            <p className="text-xs text-ink-faint max-w-md">
              Analytical support based on standalone data — not a forecast, not advice.
            </p>
          </div>
        )}
      </Section>

      {result.combined_scenario && (
        <Card
          title={result.combined_scenario.label}
          subtitle={`${result.primary_entity?.display_name} + ${result.secondary_entity?.display_name}`}
          bodyClassName="p-0"
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-bg-soft/60 border-b border-line">
                <tr className="text-left text-[11px] uppercase tracking-wider text-ink-faint">
                  <th className="px-4 py-2 font-medium">Metric</th>
                  <th className="px-4 py-2 font-medium">Primary</th>
                  <th className="px-4 py-2 font-medium">Secondary</th>
                  <th className="px-4 py-2 font-medium">Combined</th>
                  <th className="px-4 py-2 font-medium">Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map(({ id, p, s, c }) => {
                  const anchor = c ?? p ?? s;
                  if (!anchor) return null;
                  return (
                    <tr key={id}>
                      <td className="px-4 py-2.5 text-ink font-medium">
                        {anchor.display_name}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-ink-muted">
                        {p ? formatMetricValue(p.value, p.unit) : "—"}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-ink-muted">
                        {s ? formatMetricValue(s.value, s.unit) : "—"}
                      </td>
                      <td className="px-4 py-2.5 font-mono text-ink font-semibold">
                        {c ? formatMetricValue(c.value, c.unit) : "—"}
                      </td>
                      <td className="px-4 py-2.5">
                        {c && <MetricStatusBadge value={c.status} />}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {result.combined_scenario.caveats.length > 0 && (
            <div className="px-5 py-3 border-t border-line bg-bg-soft/30">
              <div className="label mb-2">Caveats</div>
              <ul className="space-y-1 text-xs text-ink-muted">
                {result.combined_scenario.caveats.map((c) => (
                  <li key={c}>• {c}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}

      {result.financial_health && (
        <HealthCard health={result.financial_health} title="Combined financial health" />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SynergiesCard synergies={result.synergies} />
        <RisksCard risks={result.risks} />
      </div>

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
// Synergies + Risks cards
// ---------------------------------------------------------------------------
function SynergiesCard({ synergies }: { synergies: SynergyItem[] }) {
  const revenue = synergies.filter((s) => s.kind === "revenue");
  const cost = synergies.filter((s) => s.kind === "cost");

  return (
    <Card title="Potential synergies" subtitle="Only fired when the underlying data supports them.">
      {synergies.length === 0 ? (
        <p className="text-sm text-ink-muted">
          No quantifiable synergies could be identified.
        </p>
      ) : (
        <div className="space-y-4">
          {revenue.length > 0 && (
            <SynergyList title="Revenue synergies" items={revenue} tone="good" />
          )}
          {cost.length > 0 && (
            <SynergyList title="Cost synergies" items={cost} tone="info" />
          )}
        </div>
      )}
    </Card>
  );
}

function SynergyList({
  title,
  items,
  tone,
}: {
  title: string;
  items: SynergyItem[];
  tone: "good" | "info";
}) {
  const toneCls = tone === "good" ? "text-good" : "text-brand";
  return (
    <div>
      <div className={clsx("label mb-2", toneCls)}>{title}</div>
      <ul className="space-y-2">
        {items.map((s) => (
          <li
            key={s.title}
            className="rounded-md border border-line bg-bg-soft/40 p-3 text-sm"
          >
            <div className="flex items-center justify-between gap-3">
              <span className="font-medium text-ink">{s.title}</span>
              {s.magnitude_hint && (
                <span className="text-[11px] text-ink-faint capitalize font-mono">
                  {s.magnitude_hint.replace(/_/g, " ")}
                </span>
              )}
            </div>
            <p className="text-xs text-ink-muted mt-1 leading-snug">{s.description}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RisksCard({ risks }: { risks: RiskItem[] }) {
  return (
    <Card title="Risks" subtitle="Data-supported concerns plus general considerations.">
      {risks.length === 0 ? (
        <p className="text-sm text-ink-muted">No material risks flagged.</p>
      ) : (
        <ul className="space-y-2">
          {risks.map((r) => (
            <li
              key={r.title}
              className="rounded-md border border-line bg-bg-soft/40 p-3 text-sm"
            >
              <div className="flex items-center justify-between gap-3">
                <span className="font-medium text-ink">{r.title}</span>
                <PriorityBadge value={r.severity} />
              </div>
              <p className="text-xs text-ink-muted mt-1 leading-snug">{r.description}</p>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
