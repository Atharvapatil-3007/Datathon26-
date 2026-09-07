import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorBanner, ProgressLoader } from "@/components/ui/States";
import { SelfAnalysisView } from "@/components/analysis/SelfAnalysisView";
import { api, ApiError } from "@/lib/api";
import { rememberAnalysis, rememberDataset } from "@/lib/assistantContext";
import type { AnalysisResult, DatasetSummary } from "@/lib/types";

export default function SelfAnalysisPage() {
  const { datasetId = "" } = useParams();
  const [dataset, setDataset] = useState<DatasetSummary | null>(null);
  const [result, setResult] = useState<AnalysisResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [phase, setPhase] = useState<"loading-dataset" | "analyzing" | "done">(
    "loading-dataset",
  );

  useEffect(() => {
    if (!datasetId) return;
    const ctrl = new AbortController();
    (async () => {
      try {
        setError(null);
        setPhase("loading-dataset");
        const ds = await api.getDataset(datasetId, ctrl.signal);
        setDataset(ds);
        rememberDataset(ds.id, ds.original_filename);

        setPhase("analyzing");
        const analysis = await api.runSelfAnalysis(
          datasetId,
          ds.original_filename,
          ctrl.signal,
        );
        setResult(analysis);
        rememberAnalysis("self_analysis", analysis);
        setPhase("done");
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError(err instanceof ApiError ? err.message : (err as Error).message);
      }
    })();
    return () => ctrl.abort();
  }, [datasetId]);

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
          { label: "Self analysis" },
        ]}
        eyebrow="Phase 3 · Self analysis"
        title="Financial intelligence"
        subtitle={
          dataset
            ? `Comprehensive analysis of ${dataset.original_filename}.`
            : "Building your financial intelligence report."
        }
      />

      {error && <ErrorBanner title="Analysis failed" detail={error} />}

      {!result && !error && (
        <Card>
          <ProgressLoader
            title="Building financial intelligence"
            done={
              phase === "analyzing"
                ? ["Dataset loaded"]
                : []
            }
            current={
              phase === "loading-dataset"
                ? "Loading dataset"
                : "Extracting metrics, computing ratios, scoring health"
            }
            upcoming={
              phase === "loading-dataset"
                ? [
                    "Extract financial metrics",
                    "Compute ratios",
                    "Score financial health",
                    "Generate insights",
                  ]
                : ["Score financial health", "Generate insights"]
            }
          />
        </Card>
      )}

      {result && <SelfAnalysisView result={result} />}
    </div>
  );
}
