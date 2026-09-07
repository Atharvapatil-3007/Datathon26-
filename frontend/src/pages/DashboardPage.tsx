import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { ErrorBanner, InfoBanner, LoadingState } from "@/components/ui/States";
import { api, ApiError } from "@/lib/api";
import type { DatasetSummary, ProfilingResult } from "@/lib/types";

// Section renderers live in Task 12; imported once implemented.
import { OverviewSection } from "@/components/dashboard/OverviewSection";
import { QualitySection } from "@/components/dashboard/QualitySection";
import { ColumnProfileTable } from "@/components/dashboard/ColumnProfileTable";
import { MissingSection } from "@/components/dashboard/MissingSection";
import { DuplicatesSection } from "@/components/dashboard/DuplicatesSection";
import { CardinalitySection } from "@/components/dashboard/CardinalitySection";
import { StatisticsSection } from "@/components/dashboard/StatisticsSection";
import { DistributionsSection } from "@/components/dashboard/DistributionsSection";
import { CorrelationsSection } from "@/components/dashboard/CorrelationsSection";
import { OutliersSection } from "@/components/dashboard/OutliersSection";

export default function DashboardPage() {
  const { datasetId = "" } = useParams();
  const [dataset, setDataset] = useState<DatasetSummary | null>(null);
  const [profile, setProfile] = useState<ProfilingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reprofiling, setReprofiling] = useState(false);

  useEffect(() => {
    if (!datasetId) return;
    const ctrl = new AbortController();
    (async () => {
      try {
        setError(null);
        const summary = await api.getDataset(datasetId, ctrl.signal);
        setDataset(summary);
        // The dataset row often already contains the profile (persisted in
        // datasets.profile JSONB during ingestion). If missing we fall back
        // to the dedicated endpoint.
        if (summary.profile) {
          setProfile(summary.profile);
        } else {
          const p = await api.getProfile(datasetId, ctrl.signal);
          setProfile(p.profile);
        }
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError(err instanceof ApiError ? err.message : (err as Error).message);
      }
    })();
    return () => ctrl.abort();
  }, [datasetId]);

  async function reprofile() {
    setReprofiling(true);
    setError(null);
    try {
      const p = await api.reprofile(datasetId);
      setProfile(p.profile);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setReprofiling(false);
    }
  }

  if (!datasetId) return null;

  if (error) {
    return (
      <div className="space-y-4">
        <BackLink />
        <ErrorBanner title="Could not load dashboard" detail={error} />
      </div>
    );
  }

  if (!dataset) {
    return (
      <div>
        <BackLink />
        <LoadingState message="Loading dataset…" />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div className="min-w-0">
          <BackLink />
          <h1 className="text-2xl font-semibold tracking-tight truncate">
            {dataset.original_filename}
          </h1>
          <p className="text-xs text-ink-muted mt-1 font-mono truncate">
            {dataset.id}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button className="btn" onClick={reprofile} disabled={reprofiling}>
            {reprofiling ? "Re-profiling…" : "Re-run profiling"}
          </button>
          {profile && (
            <Link to={`/datasets/${datasetId}/analysis`} className="btn-primary">
              Run analysis →
            </Link>
          )}
        </div>
      </div>

      {!profile ? (
        <Card>
          <InfoBanner>
            Profile is not yet available for this dataset. Click{" "}
            <em>Re-run profiling</em> to generate it now.
          </InfoBanner>
        </Card>
      ) : (
        <>
          {/* Auto-generated summary at the top */}
          <Card title="Understanding summary">
            <p className="text-sm text-ink-muted leading-relaxed">
              {profile.summary_text}
            </p>
            {profile.warnings.length > 0 && (
              <ul className="mt-3 space-y-1 text-xs text-warn">
                {profile.warnings.map((w) => (
                  <li key={w}>⚠ {w}</li>
                ))}
              </ul>
            )}
          </Card>

          <OverviewSection profile={profile} />
          <QualitySection profile={profile} />
          <ColumnProfileTable profile={profile} />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <MissingSection profile={profile} />
            <DuplicatesSection profile={profile} />
          </div>
          <CardinalitySection profile={profile} />
          <StatisticsSection profile={profile} />
          <DistributionsSection profile={profile} />
          <CorrelationsSection profile={profile} />
          <OutliersSection profile={profile} />
        </>
      )}
    </div>
  );
}

function BackLink() {
  return (
    <Link
      to="/datasets"
      className="inline-flex items-center gap-1 text-xs text-ink-muted hover:text-ink"
    >
      ← All datasets
    </Link>
  );
}
