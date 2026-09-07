import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { ErrorBanner, LoadingState } from "@/components/ui/States";
import { SelfAnalysisView } from "@/components/analysis/SelfAnalysisView";
import { api, ApiError } from "@/lib/api";
import type { AnalysisResult, DatasetSummary } from "@/lib/types";

export default function SelfAnalysisPage() {
  const { datasetId = "" } = useParams();
  const [dataset, setDataset] = useState<DatasetSummary | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!datasetId) return;
    const ctrl = new AbortController();
    (async () => {
      try {
        const ds = await api.getDataset(datasetId, ctrl.signal);
        setDataset(ds);
        const analysis = await api.runSelfAnalysis(
          datasetId,
          ds.original_filename,
          ctrl.signal,
        );
        setResult(analysis);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError(err instanceof ApiError ? err.message : (err as Error).message);
      }
    })();
    return () => ctrl.abort();
  }, [datasetId]);

  return (
    <div className="space-y-6">
      <Link
        to={`/datasets/${datasetId}/analysis`}
        className="text-xs text-ink-muted hover:text-ink"
      >
        ← Analysis modes
      </Link>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Self Financial Analysis</h1>
        <p className="text-sm text-ink-muted mt-1">
          {dataset ? dataset.original_filename : "Loading dataset…"}
        </p>
      </div>

      {error && <ErrorBanner title="Analysis failed" detail={error} />}
      {!result && !error && (
        <Card>
          <LoadingState message="Building your financial intelligence…" />
        </Card>
      )}
      {result && <SelfAnalysisView result={result} />}
    </div>
  );
}
