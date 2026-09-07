import clsx from "clsx";
import { Card } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { InsightCard } from "@/components/ui/InsightCard";
import { MetricStatusBadge } from "@/components/ui/StatusBadges";
import {
  formatMetricValue,
  ConfidenceFooter,
  HealthCard,
  InsightsCard,
} from "./_shared";
import type {
  AnalysisResult,
  LabeledMetric,
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

  const primaryName = result.primary_entity?.display_name ?? "Company A";
  const secondaryName = result.secondary_entity?.display_name ?? "Company B";

  return (
    <div className="space-y-6">
      {/* Executive summary */}
      <Card
        eyebrow="Executive summary"
        title="Combination narrative"
        action={
          <Button onClick={onReset} size="sm">
            Change inputs
          </Button>
        }
      >
        <p className="text-sm text-ink-muted leading-relaxed text-pretty">
          {result.summary_text}
        </p>
      </Card>

      {/* A + B → Combined hero */}
      <CombinationHero
        primaryName={primaryName}
        secondaryName={secondaryName}
        attractiveness={attractiveness}
        combinedLabel={result.combined_scenario?.label}
      />

      {/* Comparison table */}
      {result.combined_scenario && (
        <Card
          eyebrow="Scenario table"
          title={result.combined_scenario.label}
          subtitle={`Hypothetical combination of ${primaryName} + ${secondaryName}. Values labeled to preserve provenance.`}
          bodyClassName="p-0"
        >
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-bg-soft/70 border-b border-line">
                <tr className="text-left text-[11px] uppercase tracking-[0.08em] text-ink-faint">
                  <th className="px-4 py-2.5 font-medium">Metric</th>
                  <th className="px-4 py-2.5 font-medium text-right">{primaryName}</th>
                  <th className="px-4 py-2.5 font-medium text-right">{secondaryName}</th>
                  <th className="px-4 py-2.5 font-medium text-right">Combined</th>
                  <th className="px-4 py-2.5 font-medium">Status</th>
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
                      <td className="px-4 py-2.5 num text-ink-muted">
                        {p ? formatMetricValue(p.value, p.unit) : "—"}
                      </td>
                      <td className="px-4 py-2.5 num text-ink-muted">
                        {s ? formatMetricValue(s.value, s.unit) : "—"}
                      </td>
                      <td className="px-4 py-2.5 num text-ink font-semibold">
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
              <div className="label mb-2">Scenario caveats</div>
              <ul className="space-y-1 text-xs text-ink-muted">
                {result.combined_scenario.caveats.map((c) => (
                  <li key={c}>· {c}</li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      )}

      {result.financial_health && (
        <HealthCard
          health={result.financial_health}
          title="Combined financial health"
          subtitle="Scored against the same rubric used for self-analysis, applied to the scenario data."
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <SynergiesCard synergies={result.synergies} />
        <RisksCard risks={result.risks} />
      </div>

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
 * Combination hero
 * ------------------------------------------------------------------------- */
function CombinationHero({
  primaryName,
  secondaryName,
  attractiveness,
  combinedLabel,
}: {
  primaryName: string;
  secondaryName: string;
  attractiveness?: string;
  combinedLabel?: string;
}) {
  const score = attractiveness ? parseFloat(attractiveness) : null;
  return (
    <Card raised className="hero-bg">
      <div className="flex flex-col lg:flex-row items-stretch gap-5">
        {/* A + B → C visual */}
        <div className="flex-1 grid grid-cols-[1fr_auto_1fr] gap-3 items-center">
          <CompanyTag name={primaryName} tone="brand" />
          <div className="flex flex-col items-center gap-1">
            <span className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-brand-muted bg-brand-soft text-brand text-lg font-semibold">
              +
            </span>
          </div>
          <CompanyTag name={secondaryName} tone="accent" />
        </div>

        <div className="hidden lg:flex items-center">
          <span className="text-ink-faint text-xl">→</span>
        </div>

        {/* Combined + attractiveness */}
        <div className="flex-1 rounded-xl border border-brand-muted/50 bg-brand-soft/30 p-5">
          <div className="flex items-start justify-between gap-4">
            <div className="min-w-0">
              <div className="eyebrow">Combined scenario</div>
              <div className="mt-1 text-lg font-semibold text-ink text-balance">
                {combinedLabel ?? `${primaryName} + ${secondaryName}`}
              </div>
              <div className="mt-1.5 text-xs text-ink-muted">
                Hypothetical combination — not a forecast.
              </div>
            </div>
            {score !== null && (
              <div className="text-right">
                <div className="eyebrow">Attractiveness</div>
                <div className="mt-1 text-3xl font-semibold text-brand tabular-nums">
                  {score.toFixed(1)}
                  <span className="text-sm text-ink-muted"> / 100</span>
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </Card>
  );
}

function CompanyTag({ name, tone }: { name: string; tone: "brand" | "accent" }) {
  const styles =
    tone === "brand"
      ? "border-brand-muted/50 bg-brand-soft/40 text-brand"
      : "border-accent/40 bg-accent-soft/60 text-accent";
  return (
    <div
      className={clsx(
        "rounded-xl border p-4 min-h-[76px] flex flex-col justify-center",
        styles,
      )}
    >
      <div className="text-[10px] uppercase tracking-[0.14em] font-semibold opacity-80">
        Company
      </div>
      <div className="mt-1 text-sm font-semibold text-ink truncate">{name}</div>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Synergies + risks
 * ------------------------------------------------------------------------- */
function SynergiesCard({ synergies }: { synergies: SynergyItem[] }) {
  const revenue = synergies.filter((s) => s.kind === "revenue");
  const cost = synergies.filter((s) => s.kind === "cost");
  const other = synergies.filter(
    (s) => s.kind !== "revenue" && s.kind !== "cost",
  );

  return (
    <Card
      eyebrow="Value creation"
      title="Potential synergies"
      subtitle="Only fired when the underlying data supports them."
    >
      {synergies.length === 0 ? (
        <p className="text-sm text-ink-muted">
          No quantifiable synergies could be identified from the current data.
        </p>
      ) : (
        <div className="space-y-4">
          {revenue.length > 0 && <SynergyList title="Revenue synergies" items={revenue} />}
          {cost.length > 0 && <SynergyList title="Cost synergies" items={cost} />}
          {other.length > 0 && <SynergyList title="Other synergies" items={other} />}
        </div>
      )}
    </Card>
  );
}

function SynergyList({ title, items }: { title: string; items: SynergyItem[] }) {
  return (
    <div>
      <div className="text-[11px] uppercase tracking-[0.14em] text-good font-semibold mb-2">
        {title}
      </div>
      <div className="space-y-2">
        {items.map((s) => (
          <InsightCard
            key={s.title}
            kind="opportunity"
            title={
              <div className="flex items-center justify-between gap-3">
                <span>{s.title}</span>
                {s.magnitude_hint && (
                  <span className="text-[10px] text-ink-faint capitalize font-mono">
                    {s.magnitude_hint.replace(/_/g, " ")}
                  </span>
                )}
              </div>
            }
            body={s.description}
          />
        ))}
      </div>
    </div>
  );
}

function RisksCard({ risks }: { risks: AnalysisResult["risks"] }) {
  return (
    <Card
      eyebrow="What could go wrong"
      title="Combination risks"
      subtitle="Data-supported concerns plus general considerations."
    >
      {risks.length === 0 ? (
        <p className="text-sm text-ink-muted">No material risks flagged.</p>
      ) : (
        <div className="space-y-2">
          {risks.map((r) => (
            <InsightCard
              key={r.title}
              kind="risk"
              title={r.title}
              body={r.description}
              priority={r.severity}
            />
          ))}
        </div>
      )}
    </Card>
  );
}

// Kept exported for potential future use.
export type { LabeledMetric };
