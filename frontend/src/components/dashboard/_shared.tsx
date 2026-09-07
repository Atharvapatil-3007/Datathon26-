import { ReactNode } from "react";
import clsx from "clsx";
import { Card } from "@/components/ui/Card";
import type { ProfilingResult, SectionStatus } from "@/lib/types";

export type SectionProps = { profile: ProfilingResult };

/**
 * Render a card with a "section unavailable" state whenever the backend
 * returns `status: "unavailable"`. This keeps every dashboard section
 * consistently shaped and forgiving of partial profile failures.
 */
export function SectionShell({
  title,
  subtitle,
  action,
  status,
  reason,
  className,
  bodyClassName,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  action?: ReactNode;
  status?: SectionStatus;
  reason?: string | null;
  className?: string;
  bodyClassName?: string;
  children: ReactNode;
}) {
  return (
    <Card
      title={title}
      subtitle={subtitle}
      action={action}
      className={className}
      bodyClassName={bodyClassName}
    >
      {status && status !== "ok" ? (
        <p className="text-sm text-ink-muted">
          {reason ?? "This section is unavailable for the current dataset."}
        </p>
      ) : (
        children
      )}
    </Card>
  );
}

/** Small KPI tile used across sections. */
export function Kpi({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: ReactNode;
  hint?: ReactNode;
  tone?: "good" | "warn" | "bad" | "info";
}) {
  return (
    <div className="rounded-lg border border-line bg-bg-soft/40 p-4">
      <div className="label">{label}</div>
      <div
        className={clsx(
          "mt-1 text-2xl font-semibold tracking-tight",
          tone === "good" && "text-good",
          tone === "warn" && "text-warn",
          tone === "bad" && "text-bad",
          tone === "info" && "text-brand",
          !tone && "text-ink",
        )}
      >
        {value}
      </div>
      {hint && <div className="text-xs text-ink-muted mt-1">{hint}</div>}
    </div>
  );
}

/** Horizontal progress bar used for missing / quality ratios. */
export function Bar({ ratio, tone = "warn" }: { ratio: number; tone?: "good" | "warn" | "bad" | "info" }) {
  const pct = Math.max(0, Math.min(1, ratio));
  const color =
    tone === "good"
      ? "bg-good"
      : tone === "bad"
      ? "bg-bad"
      : tone === "info"
      ? "bg-brand"
      : "bg-warn";
  return (
    <div className="h-1.5 w-full rounded-full bg-bg-hover overflow-hidden">
      <div className={clsx("h-full rounded-full", color)} style={{ width: `${pct * 100}%` }} />
    </div>
  );
}

/** Common chart tooltip color used by Recharts. */
export const CHART_TOOLTIP_STYLE = {
  contentStyle: {
    background: "#141d33",
    border: "1px solid #243056",
    borderRadius: 8,
    fontSize: 12,
    color: "#e6ebf5",
  },
  labelStyle: { color: "#8590aa" },
  itemStyle: { color: "#e6ebf5" },
};
