import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import clsx from "clsx";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { InlineDatasetInput } from "@/components/InlineDatasetInput";
import { ErrorBanner, InfoBanner, ProgressLoader } from "@/components/ui/States";
import { MergerAnalysisView } from "@/components/analysis/MergerAnalysisView";
import { api, ApiError } from "@/lib/api";
import { rememberAnalysis, rememberDataset } from "@/lib/assistantContext";
import type { AnalysisResult, DatasetSummary } from "@/lib/types";

const DEAL_TYPES = [
  {
    value: "merger",
    label: "Merger",
    hint: "Two organisations combine as equals",
  },
  {
    value: "acquisition",
    label: "Acquisition",
    hint: "One company absorbs another",
  },
  {
    value: "partnership",
    label: "Strategic Partnership",
    hint: "Joint operations, separate entities",
  },
] as const;

export default function MergerAnalysisPage() {
  const { datasetId = "" } = useParams();

  const [dataset, setDataset] = useState<DatasetSummary | null>(null);
  const [secondary, setSecondary] = useState<DatasetSummary | null>(null);
  const [dealType, setDealType] = useState<string>("merger");
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  useEffect(() => {
    if (!datasetId) return;
    const ctrl = new AbortController();
    api
      .getDataset(datasetId, ctrl.signal)
      .then((ds) => {
        setDataset(ds);
        rememberDataset(ds.id, ds.original_filename);
      })
      .catch(() => undefined);
    return () => ctrl.abort();
  }, [datasetId]);

  async function run() {
    if (!secondary) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.runMergerAnalysis({
        primary_dataset_id: datasetId,
        secondary_dataset_id: secondary.id,
        deal_type: dealType,
        primary_display_name: dataset?.original_filename,
        secondary_display_name: secondary.original_filename,
      });
      setResult(r);
      rememberAnalysis("merger_partnership_analysis", r);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[
          { label: "Datasets", to: "/datasets" },
          {
            label: dataset?.original_filename ?? "Dataset",
            to: `/datasets/${datasetId}`,
          },
          { label: "Analysis", to: `/datasets/${datasetId}/analysis` },
          { label: "Merger / partnership" },
        ]}
        eyebrow="Phase 3 · Merger analysis"
        title="Merger & partnership analysis"
        subtitle={
          dataset
            ? `${dataset.original_filename} combined with another company — projected as a hypothetical scenario, not a forecast.`
            : "Combine two standalone datasets into a hypothetical scenario."
        }
      />

      {!result && !running && (
        <Card
          eyebrow="Configuration"
          title="Configure the combination"
          subtitle="Upload or pick the second company's dataset. It will run through the same validation + profiling pipeline before combining."
        >
          <div className="space-y-6">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <YourCompanyCard dataset={dataset} />
              <InlineDatasetInput
                label="Other Company Dataset"
                hint="Required"
                excludeId={datasetId}
                selected={secondary}
                onSelect={setSecondary}
              />
            </div>
            <div>
              <div className="label mb-2">Deal type</div>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-2">
                {DEAL_TYPES.map((dt) => (
                  <button
                    key={dt.value}
                    onClick={() => setDealType(dt.value)}
                    className={clsx(
                      "text-left rounded-lg border px-3.5 py-3 transition-colors",
                      dealType === dt.value
                        ? "border-brand-muted bg-brand-soft/60 shadow-insetTop"
                        : "border-line bg-bg-soft/40 hover:border-brand-muted/40 hover:bg-bg-hover",
                    )}
                  >
                    <div className="text-sm font-medium text-ink">{dt.label}</div>
                    <div className="text-[11px] text-ink-muted mt-0.5">
                      {dt.hint}
                    </div>
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-end gap-2">
              <Button
                variant="primary"
                onClick={run}
                disabled={!secondary}
                loading={running}
              >
                Run merger analysis →
              </Button>
            </div>
          </div>
        </Card>
      )}

      {error && <ErrorBanner title="Analysis failed" detail={error} />}

      {running && (
        <>
          <Card>
            <ProgressLoader
              title="Combining financials"
              done={["Datasets validated", "Metrics extracted"]}
              current="Computing synergies and combined scenario"
              upcoming={["Score financial health", "Assess risks", "Generate insights"]}
            />
          </Card>
          <InfoBanner>
            Combined values are hypothetical scenarios, not forecasts. Every
            derived metric is labeled with its provenance.
          </InfoBanner>
        </>
      )}

      {result && (
        <MergerAnalysisView result={result} onReset={() => setResult(null)} />
      )}
    </div>
  );
}

/** Read-only summary of the primary dataset — it's already been ingested. */
function YourCompanyCard({ dataset }: { dataset: DatasetSummary | null }) {
  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <div className="label">Your Company Dataset</div>
        <div className="text-[11px] text-good">Ready</div>
      </div>
      <div className="rounded-lg border border-good/40 bg-good/5 px-4 py-3">
        <div className="flex items-center gap-2">
          <span className="inline-flex h-4 w-4 items-center justify-center rounded-full bg-good/20 text-good text-[10px]">
            ✓
          </span>
          <div className="text-sm font-medium text-ink truncate">
            {dataset?.original_filename ?? "Loading…"}
          </div>
        </div>
        <div className="text-[11px] text-ink-muted mt-1.5">
          Already validated and profiled through Phase 1 + Phase 2.
        </div>
      </div>
    </div>
  );
}
