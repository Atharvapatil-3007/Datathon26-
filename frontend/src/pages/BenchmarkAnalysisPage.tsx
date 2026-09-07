import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { InlineDatasetInput } from "@/components/InlineDatasetInput";
import { ErrorBanner, LoadingState } from "@/components/ui/States";
import { BenchmarkAnalysisView } from "@/components/analysis/BenchmarkAnalysisView";
import { api, ApiError } from "@/lib/api";
import type { AnalysisResult, DatasetSummary } from "@/lib/types";

export default function BenchmarkAnalysisPage() {
  const { datasetId = "" } = useParams();
  const [dataset, setDataset] = useState<DatasetSummary | null>(null);
  const [competitor, setCompetitor] = useState<DatasetSummary | null>(null);
  const [market, setMarket] = useState<DatasetSummary | null>(null);
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
    if (!competitor) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const r = await api.runBenchmarkAnalysis({
        primary_dataset_id: datasetId,
        competitor_dataset_id: competitor.id,
        market_dataset_id: market?.id,
        primary_display_name: dataset?.original_filename,
        competitor_display_name: competitor.original_filename,
        market_display_name: market?.original_filename,
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
          Competitor & Market Benchmarking
        </h1>
        <p className="text-sm text-ink-muted mt-1">
          Compare {dataset?.original_filename ?? "your company"} against a competitor
          and optionally an industry / market reference.
        </p>
      </div>

      {!result && (
        <Card
          title="Configuration"
          subtitle="Upload or pick the competitor's dataset. A market/industry benchmark is optional but enriches the comparison."
        >
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <YourCompanyCard dataset={dataset} />
            <InlineDatasetInput
              label="Competitor Dataset"
              hint="Required"
              excludeId={datasetId}
              selected={competitor}
              onSelect={setCompetitor}
            />
            <InlineDatasetInput
              label="Market / Industry Benchmark"
              hint="Optional"
              excludeId={datasetId}
              selected={market}
              onSelect={setMarket}
              optional
            />
          </div>
          <div className="mt-5 flex items-center justify-end gap-2">
            <button
              className="btn-primary"
              onClick={run}
              disabled={!competitor || running}
            >
              {running ? "Running…" : "Run benchmark analysis"}
            </button>
          </div>
        </Card>
      )}

      {error && <ErrorBanner title="Analysis failed" detail={error} />}

      {running && (
        <Card>
          <LoadingState message="Comparing metrics and computing gaps…" />
        </Card>
      )}

      {result && <BenchmarkAnalysisView result={result} onReset={() => setResult(null)} />}
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
