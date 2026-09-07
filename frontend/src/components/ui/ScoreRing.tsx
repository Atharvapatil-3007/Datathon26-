import clsx from "clsx";
import { fmtDecimal } from "@/lib/format";

/**
 * Radial score dial. Used for financial health and data quality overall
 * scores. Color band mirrors the grading buckets: A=green, B=blue, C=amber,
 * D=orange, F=red.
 */
export function ScoreRing({
  score,
  outOf = 100,
  grade,
  label,
  size = "md",
  className,
}: {
  score: number;
  outOf?: number;
  grade?: string;
  label?: string;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const clamped = Math.max(0, Math.min(outOf, score));
  const pct = clamped / outOf;

  const dim = size === "sm" ? 96 : size === "lg" ? 176 : 144;
  const stroke = size === "sm" ? 8 : 10;
  const radius = (dim - stroke) / 2;
  const circumference = 2 * Math.PI * radius;
  const dash = pct * circumference;

  const color = scoreColor(clamped);
  const valueClass =
    size === "sm"
      ? "text-lg"
      : size === "lg"
        ? "text-4xl"
        : "text-3xl";

  return (
    <div
      className={clsx(
        "relative inline-flex flex-col items-center",
        className,
      )}
      style={{ width: dim, height: dim }}
    >
      <svg
        viewBox={`0 0 ${dim} ${dim}`}
        className="w-full h-full"
        aria-hidden
      >
        <circle
          cx={dim / 2}
          cy={dim / 2}
          r={radius}
          stroke="#1e2a4a"
          strokeWidth={stroke}
          fill="none"
        />
        <circle
          cx={dim / 2}
          cy={dim / 2}
          r={radius}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${dash} ${circumference}`}
          transform={`rotate(-90 ${dim / 2} ${dim / 2})`}
          style={{ transition: "stroke-dasharray 500ms ease" }}
        />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center leading-tight">
        <div className={clsx("font-semibold text-ink tabular-nums", valueClass)}>
          {fmtDecimal(score, size === "sm" ? 0 : 1)}
        </div>
        {(grade || label) && (
          <div className="mt-0.5 text-[11px] text-ink-muted">
            {label ?? `/ ${outOf}`}
            {grade && (
              <span className="ml-1 text-ink font-medium">· {grade}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export function scoreColor(score: number): string {
  if (score >= 90) return "#4ade80";
  if (score >= 80) return "#38bdf8";
  if (score >= 70) return "#facc15";
  if (score >= 60) return "#f59e0b";
  return "#f87171";
}

export function scoreLabel(score: number): string {
  if (score >= 90) return "Excellent";
  if (score >= 80) return "Healthy";
  if (score >= 70) return "Adequate";
  if (score >= 60) return "Watch";
  return "At risk";
}
