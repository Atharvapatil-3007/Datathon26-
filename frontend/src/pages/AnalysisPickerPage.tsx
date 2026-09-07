import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import clsx from "clsx";
import { Card } from "@/components/ui/Card";
import { ErrorBanner, LoadingState } from "@/components/ui/States";
import { api, ApiError } from "@/lib/api";
import type { AnalysisMode, AnalysisOption, DatasetSummary } from "@/lib/types";

/**
 * Post-Phase-2 landing screen: three big cards, exactly one gets selected.
 * When the user picks a mode we navigate to that mode's dedicated page
 * (which handles secondary/competitor picking as needed).
 */
export default function AnalysisPickerPage() {
  const { datasetId = "" } = useParams();
  const navigate = useNavigate();

  const [dataset, setDataset] = useState<DatasetSummary | null>(null);
  const [options, setOptions] = useState<AnalysisOption[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!datasetId) return;
    const ctrl = new AbortController();
    (async () => {
      try {
        const [ds, opts] = await Promise.all([
          api.getDataset(datasetId, ctrl.signal),
          api.getAnalysisOptions(ctrl.signal),
        ]);
        setDataset(ds);
        setOptions(opts.modes);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError(err instanceof ApiError ? err.message : (err as Error).message);
      }
    })();
    return () => ctrl.abort();
  }, [datasetId]);

  function pick(mode: AnalysisMode) {
    if (mode === "self_analysis") {
      navigate(`/datasets/${datasetId}/analysis/self`);
    } else if (mode === "merger_partnership_analysis") {
      navigate(`/datasets/${datasetId}/analysis/merger`);
    } else if (mode === "competitor_market_benchmark") {
      navigate(`/datasets/${datasetId}/analysis/benchmark`);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <Link
          to={`/datasets/${datasetId}`}
          className="text-xs text-ink-muted hover:text-ink"
        >
          ← Back to dashboard
        </Link>
        <h1 className="text-2xl font-semibold tracking-tight mt-1">
          What do you want to analyze?
        </h1>
        <p className="text-sm text-ink-muted mt-1">
          {dataset
            ? `Financial profile ready for ${dataset.original_filename}. Pick one of three analysis pipelines.`
            : "Pick one of three analysis pipelines."}
        </p>
      </div>

      {error && <ErrorBanner title="Couldn't load options" detail={error} />}
      {!options && !error && <LoadingState message="Preparing analysis modes…" />}

      {options && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {options.map((opt) => (
            <ModeCard key={opt.mode} option={opt} onClick={() => pick(opt.mode)} />
          ))}
        </div>
      )}

      {options && (
        <Card
          title="How this works"
          subtitle="Only the selected pipeline runs. Nothing is auto-executed."
        >
          <ul className="text-sm text-ink-muted space-y-2 leading-relaxed">
            <li>
              Metrics are labeled <em>reported</em>, <em>calculated</em>,{" "}
              <em>estimated</em>, or <em>scenario</em> so you always know what
              came from data and what came from a model.
            </li>
            <li>
              Merger figures are hypothetical combinations of two standalone
              datasets — never presented as forecasts.
            </li>
            <li>
              Benchmark analysis flags gaps and suggests investigation areas but
              never claims to know a competitor's strategy.
            </li>
          </ul>
        </Card>
      )}
    </div>
  );
}

function ModeCard({
  option,
  onClick,
}: {
  option: AnalysisOption;
  onClick: () => void;
}) {
  const icon =
    option.mode === "self_analysis"
      ? "self"
      : option.mode === "merger_partnership_analysis"
        ? "merger"
        : "bench";
  return (
    <button
      onClick={onClick}
      className={clsx(
        "text-left p-6 rounded-xl bg-bg-card border border-line shadow-card",
        "hover:border-brand-muted hover:bg-bg-hover/40 transition-colors group",
      )}
    >
      <div className="flex items-center justify-center h-12 w-12 rounded-lg bg-brand-soft border border-brand-muted text-brand mb-4">
        <ModeIcon kind={icon} />
      </div>
      <div className="text-sm font-semibold text-ink group-hover:text-brand transition-colors">
        {option.title}
      </div>
      <p className="text-xs text-ink-muted mt-2 leading-relaxed">
        {option.description}
      </p>
      <div className="mt-4 text-[11px] text-ink-faint font-mono">
        {option.requires.length === 1
          ? "Uses this dataset"
          : `Requires ${option.requires.length} datasets`}
      </div>
    </button>
  );
}

function ModeIcon({ kind }: { kind: "self" | "merger" | "bench" }) {
  if (kind === "self") {
    return (
      <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
        <path
          d="M4 20V4M4 20h16M8 16V9M12 16V6M16 16v-3M20 16v-5"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
        />
      </svg>
    );
  }
  if (kind === "merger") {
    return (
      <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
        <circle cx="8" cy="12" r="4" stroke="currentColor" strokeWidth="1.5" />
        <circle cx="16" cy="12" r="4" stroke="currentColor" strokeWidth="1.5" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
      <path
        d="M4 20h4v-8H4v8Zm6 0h4V4h-4v16Zm6 0h4v-12h-4v12Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    </svg>
  );
}
