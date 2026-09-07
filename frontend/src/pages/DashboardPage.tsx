import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { ErrorBanner, InfoBanner, WarningBanner } from "@/components/ui/States";
import { Tabs, TabItem, TabPanel } from "@/components/ui/Tabs";
import { PageSkeleton, MetricSkeletonRow } from "@/components/ui/Skeleton";
import { GradeBadge } from "@/components/ui/Badges";
import { api, ApiError } from "@/lib/api";
import { fmtBytes, fmtInt, fmtPercent } from "@/lib/format";
import { rememberDataset } from "@/lib/assistantContext";
import { ChatPanel } from "@/components/chat/ChatPanel";
import type { DatasetSummary, ProfilingResult } from "@/lib/types";

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

type TabId =
  | "overview"
  | "quality"
  | "columns"
  | "distributions"
  | "correlations"
  | "outliers";

export default function DashboardPage() {
  const { datasetId = "" } = useParams();
  const [dataset, setDataset] = useState<DatasetSummary | null>(null);
  const [profile, setProfile] = useState<ProfilingResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reprofiling, setReprofiling] = useState(false);
  const [tab, setTab] = useState<TabId>("overview");

  useEffect(() => {
    if (!datasetId) return;
    const ctrl = new AbortController();
    (async () => {
      try {
        setError(null);
        const summary = await api.getDataset(datasetId, ctrl.signal);
        setDataset(summary);
        rememberDataset(summary.id, summary.original_filename);
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

  const tabs = useMemo<TabItem<TabId>[]>(
    () => [
      { id: "overview", label: "Overview" },
      { id: "quality", label: "Data quality" },
      { id: "columns", label: "Columns", hint: profile ? String(profile.column_profiles.length) : undefined },
      { id: "distributions", label: "Distributions" },
      { id: "correlations", label: "Correlations" },
      { id: "outliers", label: "Outliers" },
    ],
    [profile],
  );

  if (!datasetId) return null;

  if (error) {
    return (
      <div className="space-y-4">
        <PageHeader
          crumbs={[{ label: "Datasets", to: "/datasets" }]}
          title="Dataset"
        />
        <ErrorBanner title="Could not load dashboard" detail={error} />
      </div>
    );
  }

  if (!dataset) {
    return <PageSkeleton />;
  }

  return (
    <div className="space-y-6">
      <PageHeader
        crumbs={[
          { label: "Datasets", to: "/datasets" },
          { label: dataset.original_filename },
        ]}
        eyebrow="Phase 2 · Dataset intelligence"
        title={dataset.original_filename}
        subtitle="Automatic profiling extracted structure, quality, distributions and relationships in one pass."
        actions={
          <>
            <Button onClick={reprofile} loading={reprofiling} disabled={reprofiling}>
              {reprofiling ? "Re-profiling…" : "Re-run profiling"}
            </Button>
            {profile && (
              <Link to={`/datasets/${datasetId}/analysis`}>
                <Button variant="primary">Run analysis →</Button>
              </Link>
            )}
          </>
        }
      />

      {/* Intelligence hero — dataset fingerprint */}
      <IntelligenceHero dataset={dataset} profile={profile} />

      {!profile ? (
        <Card>
          <InfoBanner>
            Profile is not yet available for this dataset. Click{" "}
            <em>Re-run profiling</em> to generate it now.
          </InfoBanner>
          <div className="mt-4">
            <MetricSkeletonRow />
          </div>
        </Card>
      ) : (
        <>
          {profile.warnings.length > 0 && (
            <WarningBanner>
              <div className="font-medium text-warn mb-1">
                {profile.warnings.length} profiling warning
                {profile.warnings.length > 1 ? "s" : ""}
              </div>
              <ul className="space-y-1">
                {profile.warnings.slice(0, 3).map((w) => (
                  <li key={w}>· {w}</li>
                ))}
                {profile.warnings.length > 3 && (
                  <li className="text-ink-faint">
                    + {profile.warnings.length - 3} more
                  </li>
                )}
              </ul>
            </WarningBanner>
          )}

          <Tabs items={tabs} active={tab} onChange={setTab} />

          <TabPanel id="overview" active={tab === "overview"} className="space-y-6">
            <Card
              eyebrow="Summary"
              title="What the profiler learned"
              subtitle="Human-readable synthesis of the automatic profiling."
            >
              <p className="text-sm text-ink-muted leading-relaxed">
                {profile.summary_text}
              </p>
            </Card>
            <OverviewSection profile={profile} />
          </TabPanel>

          <TabPanel id="quality" active={tab === "quality"} className="space-y-6">
            <QualitySection profile={profile} />
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <MissingSection profile={profile} />
              <DuplicatesSection profile={profile} />
            </div>
            <CardinalitySection profile={profile} />
          </TabPanel>

          <TabPanel id="columns" active={tab === "columns"}>
            <ColumnProfileTable profile={profile} />
          </TabPanel>

          <TabPanel id="distributions" active={tab === "distributions"} className="space-y-6">
            <DistributionsSection profile={profile} />
            <StatisticsSection profile={profile} />
          </TabPanel>

          <TabPanel id="correlations" active={tab === "correlations"}>
            <CorrelationsSection profile={profile} />
          </TabPanel>

          <TabPanel id="outliers" active={tab === "outliers"}>
            <OutliersSection profile={profile} />
          </TabPanel>

          {/* Dataset Intelligence Chatbot */}
          <div className="mt-2">
            <ChatPanel
              datasetId={datasetId}
              datasetName={dataset.original_filename}
              analysisMode="self_analysis"
            />
          </div>
        </>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Intelligence hero — dataset fingerprint stripe
 * ------------------------------------------------------------------------- */
function IntelligenceHero({
  dataset,
  profile,
}: {
  dataset: DatasetSummary;
  profile: ProfilingResult | null;
}) {
  const rows = dataset.row_count ?? profile?.overview.rows ?? null;
  const cols = dataset.column_count ?? profile?.overview.columns ?? null;

  return (
    <Card raised className="hero-bg" bodyClassName="p-0">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-px bg-line/50 rounded-xl overflow-hidden">
        <HeroStat label="Rows" value={fmtInt(rows)} sub={fmtBytes(dataset.file_size)} />
        <HeroStat
          label="Columns"
          value={fmtInt(cols)}
          sub={
            profile
              ? `${profile.overview.numerical_columns} numeric · ${profile.overview.categorical_columns} categorical`
              : undefined
          }
        />
        <HeroStat
          label="Missing"
          value={profile ? fmtPercent(profile.missing.missing_ratio) : "—"}
          sub={profile ? `${fmtInt(profile.missing.columns_with_missing)} column(s)` : undefined}
        />
        <HeroStat
          label="Quality"
          value={profile ? profile.quality.overall_score.toFixed(1) : "—"}
          sub={profile ? `Grade ${profile.quality.grade}` : undefined}
          badge={profile && <GradeBadge value={profile.quality.grade} />}
        />
        <HeroStat
          label="Format"
          value={dataset.file_format?.toUpperCase() ?? "—"}
          sub={
            profile
              ? `${fmtInt(profile.metadata.profiling_time_ms)} ms · v${profile.metadata.version}`
              : undefined
          }
        />
      </div>
    </Card>
  );
}

function HeroStat({
  label,
  value,
  sub,
  badge,
}: {
  label: string;
  value: string;
  sub?: string;
  badge?: React.ReactNode;
}) {
  return (
    <div className="bg-bg-card px-4 py-4">
      <div className="flex items-center justify-between gap-2">
        <div className="label">{label}</div>
        {badge}
      </div>
      <div className="mt-1 text-2xl font-semibold text-ink tabular-nums tracking-tight">
        {value}
      </div>
      {sub && <div className="text-[11px] text-ink-faint mt-1 truncate">{sub}</div>}
    </div>
  );
}
