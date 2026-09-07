import clsx from "clsx";
import type { AnalysisPriority, MetricStatus } from "@/lib/types";

// Status pill for metric values (REPORTED / CALCULATED / etc.)
const METRIC_STATUS_COLORS: Record<MetricStatus, string> = {
  reported: "text-good border-good/40 bg-good/10",
  calculated: "text-brand border-brand-muted/60 bg-brand-soft/40",
  estimated: "text-warn border-warn/40 bg-warn/10",
  scenario: "text-info border-info/40 bg-info/10",
  unavailable: "text-ink-faint border-line bg-bg-hover",
};

export function MetricStatusBadge({ value }: { value: MetricStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wider",
        METRIC_STATUS_COLORS[value] ?? METRIC_STATUS_COLORS.unavailable,
      )}
    >
      {value}
    </span>
  );
}

// Priority pill for gaps / risks
const PRIORITY_COLORS: Record<AnalysisPriority, string> = {
  high: "text-bad border-bad/40 bg-bad/10",
  medium: "text-warn border-warn/40 bg-warn/10",
  low: "text-ink-muted border-line bg-bg-hover",
};

export function PriorityBadge({ value }: { value: AnalysisPriority }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
        PRIORITY_COLORS[value] ?? PRIORITY_COLORS.low,
      )}
    >
      {value}
    </span>
  );
}
