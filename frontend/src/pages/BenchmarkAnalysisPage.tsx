import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { InlineDatasetInput } from "@/components/InlineDatasetInput";
import { ErrorBanner, ProgressLoader } from "@/components/ui/States";
import { BenchmarkAnalysisView } from "@/components/analysis/BenchmarkAnalysisView";
import { api, ApiError } from "@/lib/api";
import { rememberAnalysis, rememberDataset } from "@/lib/assistantContext";
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
      rememberAnalysis("competitor_market_benchmark", r);
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
          { label: "Competitor benchmark" },
        ]}
        eyebrow="Phase 3 · Competitor & market benchmark"
        title="Competitor & market benchmarking"
        subtitle={
          dataset
            ? `Compare ${dataset.original_filename} against a competitor and an optional market/industry reference.`
            : "Compare your company against a competitor and market benchmark."
        }
      />

      {!result && !running && (
        <Card
          eyebrow="Configuration"
          title="Configure the comparison"
          subtitle="A competitor dataset is required. A market/industry benchmark is optional but enriches the comparison."
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
          <div className="mt-6 flex items-center justify-end gap-2">
            <Button
              variant="primary"
              onClick={run}
              disabled={!competitor}
              loading={running}
            >
              Run benchmark analysis →
            </Button>
          </div>
        </Card>
      )}

      {error && <ErrorBanner title="Analysis failed" detail={error} />}

      {running && (
        <Card>
          <ProgressLoader
            title="Comparing companies"
            done={["Datasets validated", "Aligning metric definitions"]}
            current="Computing gaps and priority matrix"
            upcoming={["Identify strengths & weaknesses", "Generate action plan"]}
          />
        </Card>
      )}

      {result && (
        <BenchmarkAnalysisView result={result} onReset={() => setResult(null)} />
      )}
    </div>
  );
}

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
