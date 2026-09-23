import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import clsx from "clsx";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorBanner, LoadingState } from "@/components/ui/States";
import { api, ApiError } from "@/lib/api";
import { rememberDataset } from "@/lib/assistantContext";
import type { AnalysisMode, AnalysisOption, DatasetSummary } from "@/lib/types";

type ModeKey = "self" | "merger" | "bench";

const MODE_META: Record<
  ModeKey,
  {
    icon: React.ReactNode;
    gradient: string;
    ring: string;
    accent: string;
    highlights: string[];
    cta: string;
  }
> = {
  self: {
    icon: <IconSelf />,
    gradient: "from-brand/25 via-brand/5 to-transparent",
    ring: "hover:border-brand-muted",
    accent: "text-brand",
    highlights: ["Health score", "Ratios & metrics", "Risks & opportunities"],
    cta: "Analyze this company",
  },
  merger: {
    icon: <IconMerger />,
    gradient: "from-accent/20 via-accent/5 to-transparent",
    ring: "hover:border-accent/60",
    accent: "text-accent",
    highlights: ["Combined scenarios", "Synergies", "Compatibility score"],
    cta: "Model a combination",
  },
  bench: {
    icon: <IconBench />,
    gradient: "from-info/20 via-info/5 to-transparent",
    ring: "hover:border-info/60",
    accent: "text-info",
    highlights: ["Head-to-head metrics", "Priority gap matrix", "Reach the benchmark"],
    cta: "Benchmark performance",
  },
};

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
        rememberDataset(ds.id, ds.original_filename);
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
    <div className="analytical-canvas space-y-8">
      <PageHeader
        crumbs={[
          { label: "Datasets", to: "/datasets" },
          {
            label: dataset?.original_filename ?? "Dataset",
            to: `/datasets/${datasetId}`,
          },
          { label: "Analysis" },
        ]}
        eyebrow="Phase 3 · Financial intelligence"
        title="Choose your analysis mode"
        subtitle={
          dataset
            ? `Ready to analyze ${dataset.original_filename}. Pick a pipeline — each runs deliberately, no auto-execution.`
            : "Pick one of three analysis pipelines to run against this dataset."
        }
      />

      {error && <ErrorBanner title="Couldn't load options" detail={error} />}
      {!options && !error && <LoadingState message="Preparing analysis pipelines…" />}

      {options && (
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
          {options.map((opt) => (
            <ModeCard key={opt.mode} option={opt} onClick={() => pick(opt.mode)} />
          ))}
        </div>
      )}

      {options && <TrustNotes />}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Individual mode card
 * ------------------------------------------------------------------------- */
function ModeCard({
  option,
  onClick,
}: {
  option: AnalysisOption;
  onClick: () => void;
}) {
  const key: ModeKey =
    option.mode === "self_analysis"
      ? "self"
      : option.mode === "merger_partnership_analysis"
        ? "merger"
        : "bench";
  const meta = MODE_META[key];

  return (
    <button
      onClick={onClick}
      className={clsx(
        "group relative text-left rounded-xl bg-bg-card border border-line shadow-card overflow-hidden transition-all duration-200",
        "hover:-translate-y-[2px] hover:shadow-elev",
        meta.ring,
      )}
    >
      {/* Glow overlay */}
      <div
        className={clsx(
          "absolute inset-0 opacity-70 bg-gradient-to-br pointer-events-none",
          meta.gradient,
        )}
        aria-hidden
      />

      <div className="relative p-6">
        <div className="flex items-center justify-between">
          <div
            className={clsx(
              "inline-flex h-11 w-11 items-center justify-center rounded-lg bg-bg-hover border border-line",
              meta.accent,
              "group-hover:scale-105 transition-transform",
            )}
          >
            {meta.icon}
          </div>
          <span className="text-[10px] uppercase tracking-[0.14em] text-ink-faint font-mono">
            {option.requires.length === 1
              ? "1 dataset"
              : `${option.requires.length} datasets`}
          </span>
        </div>

        <h3 className="mt-5 text-lg font-semibold text-ink text-balance">
          {option.title}
        </h3>
        <p className="mt-2 text-sm text-ink-muted leading-relaxed line-clamp-3">
          {option.description}
        </p>

        <div className="mt-5 space-y-1.5">
          {meta.highlights.map((h) => (
            <div key={h} className="flex items-center gap-2 text-xs text-ink-muted">
              <span className={clsx("inline-block h-1 w-1 rounded-full", "bg-current", meta.accent)} />
              <span>{h}</span>
            </div>
          ))}
        </div>

        <div className="mt-6 flex items-center justify-between border-t border-line pt-4">
          <span className={clsx("text-sm font-medium", meta.accent)}>
            {meta.cta}
          </span>
          <span
            className={clsx(
              "inline-flex h-8 w-8 items-center justify-center rounded-full border border-line bg-bg-hover transition-all",
              "group-hover:translate-x-0.5",
              meta.accent,
            )}
          >
            <IconArrow />
          </span>
        </div>
      </div>
    </button>
  );
}

/* -------------------------------------------------------------------------
 * Trust / disclosure footer
 * ------------------------------------------------------------------------- */
function TrustNotes() {
  const items = [
    {
      title: "Provenance-first",
      body: "Every metric is labeled REPORTED, CALCULATED, ESTIMATED or SCENARIO so you always know what came from data.",
    },
    {
      title: "Hypothetical, not forecast",
      body: "Merger and benchmark figures are analytical scenarios — never predictions of future performance.",
    },
    {
      title: "No assumption of intent",
      body: "Benchmarking flags gaps and suggests investigation — it never claims to know a competitor's strategy.",
    },
  ];

  return (
    <Card
      eyebrow="How analysis works"
      title="What you can rely on"
      subtitle="Guardrails baked into every pipeline."
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {items.map((it) => (
          <div key={it.title} className="rounded-lg border border-line bg-bg-soft/50 p-4">
            <div className="text-sm font-medium text-ink">{it.title}</div>
            <p className="mt-1.5 text-xs text-ink-muted leading-relaxed">{it.body}</p>
          </div>
        ))}
      </div>
      <div className="mt-4 flex items-center justify-end">
        <Link
          to={`/datasets/${window.location.pathname.split("/")[2] ?? ""}`}
          className="text-xs text-ink-muted hover:text-ink"
        >
          ← Back to dataset
        </Link>
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------------------
 * Icons
 * ------------------------------------------------------------------------- */
function IconSelf() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
      <path
        d="M4 20V4M4 20h16M8 16V9M12 16V6M16 16v-3M20 16v-5"
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
      />
    </svg>
  );
}

function IconMerger() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
      <circle cx="9" cy="12" r="5" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="15" cy="12" r="5" stroke="currentColor" strokeWidth="1.5" />
    </svg>
  );
}

function IconBench() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
      <circle cx="12" cy="12" r="8" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="12" cy="12" r="4" stroke="currentColor" strokeWidth="1.5" />
      <circle cx="12" cy="12" r="1.4" fill="currentColor" />
      <path d="M12 4v2M12 18v2M4 12h2M18 12h2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

function IconArrow() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
      <path
        d="M5 12h14m0 0-5-5m5 5-5 5"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
