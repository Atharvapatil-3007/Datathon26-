import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { InlineDatasetInput } from "@/components/InlineDatasetInput";
import { ErrorBanner, InfoBanner, LoadingState } from "@/components/ui/States";
import { MergerAnalysisView } from "@/components/analysis/MergerAnalysisView";
import { api, ApiError } from "@/lib/api";
import type { AnalysisResult, DatasetSummary } from "@/lib/types";

const DEAL_TYPES = [
  { value: "merger", label: "Merger" },
  { value: "acquisition", label: "Acquisition" },
  { value: "partnership", label: "Strategic Partnership" },
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
    api.getDataset(datasetId, ctrl.signal).then(setDataset).catch(() => undefined);
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
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="space-y-6">
      <Link
        to={`/datasets/${datasetId}/analysis`}
        className="text-xs text-ink-muted hover:text-ink"
      >
        ← Analysis modes
      </Link>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">
          Merger / Partnership Analysis
        </h1>
        <p className="text-sm text-ink-muted mt-1">
          {dataset ? `${dataset.original_filename} combined with…` : "…"}
        </p>
      </div>

      {!result && (
        <Card
          title="Configuration"
          subtitle="Upload or pick the second company's dataset. It will be validated and profiled before combining."
        >
          <div className="space-y-5">
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
              <div className="flex flex-wrap gap-2">
                {DEAL_TYPES.map((dt) => (
                  <button
                    key={dt.value}
                    onClick={() => setDealType(dt.value)}
                    className={
                      "px-3 py-1.5 text-sm rounded-md border transition-colors " +
                      (dealType === dt.value
                        ? "border-brand text-brand bg-brand-soft/60"
                        : "border-line text-ink-muted hover:text-ink hover:bg-bg-hover")
                    }
                  >
                    {dt.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="flex items-center justify-end gap-2">
              <button
                className="btn-primary"
                onClick={run}
                disabled={!secondary || running}
              >
                {running ? "Running…" : "Run merger analysis"}
              </button>
            </div>
          </div>
        </Card>
      )}

      {error && <ErrorBanner title="Analysis failed" detail={error} />}

      {running && (
        <Card>
          <LoadingState message="Combining financials, computing synergies…" />
          <InfoBanner>
            Combined values are hypothetical scenarios, not forecasts.
          </InfoBanner>
        </Card>
      )}

      {result && <MergerAnalysisView result={result} onReset={() => setResult(null)} />}
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
        <div className="text-sm font-medium text-ink truncate">
          {dataset?.original_filename ?? "Loading…"}
        </div>
        <div className="text-[11px] text-ink-muted mt-0.5">
          Already validated and profiled through Phase 1 + Phase 2.
        </div>
      </div>
    </div>
  );
}
