import { SectionProps, SectionShell, Kpi } from "./_shared";
import { fmtBytes, fmtInt } from "@/lib/format";

export function OverviewSection({ profile }: SectionProps) {
  const o = profile.overview;

  return (
    <SectionShell
      title="Dataset overview"
      subtitle="Shape and column composition of the ingested dataset."
    >
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
        <Kpi label="Rows" value={fmtInt(o.rows)} />
        <Kpi label="Columns" value={fmtInt(o.columns)} />
        <Kpi label="In-memory size" value={fmtBytes(o.size_bytes)} />
        <Kpi
          label="Profiling time"
          value={`${fmtInt(profile.metadata.profiling_time_ms)} ms`}
          hint={`v${profile.metadata.version}`}
        />
      </div>

      <div className="mt-5 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        <TypeTile label="Numerical" value={o.numerical_columns} tone="info" />
        <TypeTile label="Categorical" value={o.categorical_columns} tone="good" />
        <TypeTile label="Text" value={o.text_columns} tone="info" />
        <TypeTile
          label="Date / time"
          value={o.date_columns + o.datetime_columns}
          tone="warn"
        />
        <TypeTile label="Boolean" value={o.boolean_columns} tone="info" />
        <TypeTile
          label="Identifier"
          value={o.id_columns}
          tone="info"
          hint={o.unknown_columns > 0 ? `+${o.unknown_columns} unknown` : undefined}
        />
      </div>
    </SectionShell>
  );
}

function TypeTile({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: number;
  hint?: string;
  tone: "info" | "good" | "warn";
}) {
  return (
    <div className="rounded-md border border-line bg-bg-soft/40 px-3 py-3">
      <div className="text-[11px] uppercase tracking-wider text-ink-faint">{label}</div>
      <div
        className={
          "mt-1 text-xl font-semibold " +
          (tone === "good" ? "text-good" : tone === "warn" ? "text-warn" : "text-brand")
        }
      >
        {value}
      </div>
      {hint && <div className="text-[10px] text-ink-faint mt-0.5">{hint}</div>}
    </div>
  );
}
