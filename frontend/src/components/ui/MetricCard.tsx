import { ReactNode } from "react";
import clsx from "clsx";
import { MetricStatusBadge } from "./StatusBadges";
import type { MetricStatus, MetricUnit } from "@/lib/types";
import { fmtCompactCurrency, fmtDecimal, fmtInt } from "@/lib/format";

/**
 * Executive KPI card.
 *
 * A single, consistent design used across analysis pages so that the "hero
 * row" (Revenue / Profit / Margin / Cash / Debt / etc.) always feels the
 * same regardless of which page renders it.
 */
export interface MetricCardProps {
  label: ReactNode;
  value: number | null | undefined;
  unit?: MetricUnit;
  status?: MetricStatus;
  /** Signed change vs. previous period (e.g. 12.4 for +12.4%). */
  changePct?: number | null;
  /** Human-readable comparison period (e.g. "vs FY2024"). */
  comparisonLabel?: ReactNode;
  /** Trend points for a mini sparkline (auto-scaled). */
  trend?: number[];
  /** Optional supporting text below the value. */
  hint?: ReactNode;
  /** Highlight variant — used when this card is the "hero" metric. */
  emphasise?: boolean;
  /** Compact mode: smaller value + no spark. */
  compact?: boolean;
  className?: string;
}

export function MetricCard({
  label,
  value,
  unit = "unknown",
  status,
  changePct,
  comparisonLabel,
  trend,
  hint,
  emphasise,
  compact,
  className,
}: MetricCardProps) {
  const change =
    changePct === null || changePct === undefined
      ? null
      : { value: changePct, positive: changePct >= 0 };

  return (
    <div
      className={clsx(
        "group relative overflow-hidden rounded-xl border p-4 transition-all",
        emphasise
          ? "border-brand-muted/70 bg-brand-soft/40 shadow-elev"
          : "border-line bg-bg-card hover:border-brand-muted/40 hover:bg-bg-hover/40",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="label truncate">{label}</div>
          <div
            className={clsx(
              "mt-1.5 font-semibold tracking-tight text-ink tabular-nums",
              compact ? "text-lg" : "text-2xl",
            )}
          >
            {formatValue(value, unit)}
          </div>
        </div>
        {status && <MetricStatusBadge value={status} />}
      </div>

      {(change || comparisonLabel) && !compact && (
        <div className="mt-2.5 flex items-center gap-2 text-[11px]">
          {change && (
            <span
              className={clsx(
                "inline-flex items-center gap-0.5 font-medium tabular-nums",
                change.positive ? "text-good" : "text-bad",
              )}
            >
              <span aria-hidden>{change.positive ? "▲" : "▼"}</span>
              {Math.abs(change.value).toFixed(1)}%
            </span>
          )}
          {comparisonLabel && (
            <span className="text-ink-faint">{comparisonLabel}</span>
          )}
        </div>
      )}

      {trend && trend.length > 1 && !compact && (
        <div className="mt-3 h-8">
          <Sparkline points={trend} positive={change?.positive ?? true} />
        </div>
      )}

      {hint && !compact && (
        <div className="mt-2 text-[11px] text-ink-faint line-clamp-2">{hint}</div>
      )}
    </div>
  );
}

function formatValue(value: number | null | undefined, unit: MetricUnit): string {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  switch (unit) {
    case "percent":
      return `${fmtDecimal(value, 2)}%`;
    case "ratio":
      return `${fmtDecimal(value, 2)}x`;
    case "count":
      return fmtInt(value);
    case "days":
      return `${fmtInt(value)}d`;
    case "currency":
      return fmtCompactCurrency(value);
    default:
      return fmtDecimal(value, 2);
  }
}

/**
 * Minimal SVG sparkline. Fixed viewBox; the parent controls sizing.
 */
function Sparkline({ points, positive }: { points: number[]; positive: boolean }) {
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const w = 120;
  const h = 32;
  const step = points.length > 1 ? w / (points.length - 1) : 0;
  const coords = points.map((p, i) => {
    const x = i * step;
    const y = h - ((p - min) / range) * h;
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const path = `M ${coords.join(" L ")}`;
  const areaPath = `${path} L ${w},${h} L 0,${h} Z`;
  const stroke = positive ? "#4ade80" : "#f87171";
  const fill = positive ? "rgba(74,222,128,0.14)" : "rgba(248,113,113,0.12)";

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      className="w-full h-full"
      preserveAspectRatio="none"
      aria-hidden
    >
      <path d={areaPath} fill={fill} />
      <path d={path} fill="none" stroke={stroke} strokeWidth="1.5" />
    </svg>
  );
}
