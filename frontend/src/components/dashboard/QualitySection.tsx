import clsx from "clsx";
import { SectionProps, SectionShell, Bar } from "./_shared";
import { GradeBadge } from "@/components/ui/Badges";
import { fmtDecimal } from "@/lib/format";

export function QualitySection({ profile }: SectionProps) {
  const q = profile.quality;
  const overall = q.overall_score;

  return (
    <SectionShell
      title="Data quality score"
      subtitle="Overall grade + per-dimension breakdown of the dataset's health."
    >
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Big score */}
        <div className="flex flex-col items-center justify-center py-6 md:py-2">
          <div className="relative">
            <svg viewBox="0 0 120 120" className="w-40 h-40">
              <circle cx="60" cy="60" r="52" stroke="#243056" strokeWidth="10" fill="none" />
              <circle
                cx="60"
                cy="60"
                r="52"
                stroke={ringColor(overall)}
                strokeWidth="10"
                fill="none"
                strokeLinecap="round"
                strokeDasharray={`${(Math.max(0, Math.min(100, overall)) / 100) * 326.7} 326.7`}
                transform="rotate(-90 60 60)"
                style={{ transition: "stroke-dasharray 400ms ease" }}
              />
            </svg>
            <div className="absolute inset-0 flex flex-col items-center justify-center">
              <div className="text-3xl font-semibold tracking-tight text-ink">
                {fmtDecimal(overall, 1)}
              </div>
              <div className="text-xs text-ink-muted">out of 100</div>
            </div>
          </div>
          <div className="mt-3 flex items-center gap-2 text-sm text-ink-muted">
            Grade <GradeBadge value={q.grade} />
          </div>
        </div>

        {/* Dimensions */}
        <div className="md:col-span-2 space-y-4">
          <Dimension label="Completeness" value={q.dimensions.completeness} />
          <Dimension label="Uniqueness" value={q.dimensions.uniqueness} />
          <Dimension label="Validity" value={q.dimensions.validity} />
          <Dimension label="Consistency" value={q.dimensions.consistency} />
        </div>
      </div>

      {q.notes.length > 0 && (
        <ul className="mt-5 space-y-1 text-xs text-ink-muted">
          {q.notes.map((n) => (
            <li key={n} className="flex items-start gap-2">
              <span className="text-warn">•</span>
              <span>{n}</span>
            </li>
          ))}
        </ul>
      )}
    </SectionShell>
  );
}

function Dimension({ label, value }: { label: string; value?: number }) {
  if (value === undefined || value === null) {
    return (
      <div className="flex items-center justify-between text-sm text-ink-muted">
        <span>{label}</span>
        <span>—</span>
      </div>
    );
  }
  const tone = value >= 90 ? "good" : value >= 70 ? "info" : value >= 60 ? "warn" : "bad";
  return (
    <div>
      <div className="flex items-center justify-between text-sm">
        <span className="text-ink">{label}</span>
        <span className={clsx(
          "font-mono font-medium",
          tone === "good" && "text-good",
          tone === "info" && "text-brand",
          tone === "warn" && "text-warn",
          tone === "bad" && "text-bad",
        )}>
          {fmtDecimal(value, 1)}
        </span>
      </div>
      <div className="mt-1">
        <Bar ratio={value / 100} tone={tone} />
      </div>
    </div>
  );
}

function ringColor(score: number): string {
  if (score >= 90) return "#4ade80";
  if (score >= 80) return "#38bdf8";
  if (score >= 70) return "#facc15";
  if (score >= 60) return "#f59e0b";
  return "#f87171";
}
