import { ReactNode } from "react";
import clsx from "clsx";
import type { AnalysisPriority } from "@/lib/types";

export type InsightKind =
  | "observation"
  | "analysis"
  | "recommendation"
  | "risk"
  | "opportunity"
  | "warning";

interface KindStyle {
  icon: string;
  label: string;
  accent: string;
  ring: string;
  bg: string;
}

const KIND: Record<InsightKind, KindStyle> = {
  observation: {
    icon: "◆",
    label: "Observation",
    accent: "text-ink-muted",
    ring: "border-line",
    bg: "bg-bg-soft/50",
  },
  analysis: {
    icon: "◈",
    label: "Analysis",
    accent: "text-brand",
    ring: "border-brand-muted/40",
    bg: "bg-brand-soft/25",
  },
  recommendation: {
    icon: "→",
    label: "Recommendation",
    accent: "text-good",
    ring: "border-good/30",
    bg: "bg-good/5",
  },
  risk: {
    icon: "⚠",
    label: "Risk",
    accent: "text-bad",
    ring: "border-bad/30",
    bg: "bg-bad/5",
  },
  opportunity: {
    icon: "↑",
    label: "Opportunity",
    accent: "text-good",
    ring: "border-good/30",
    bg: "bg-good/5",
  },
  warning: {
    icon: "⚠",
    label: "Warning",
    accent: "text-warn",
    ring: "border-warn/40",
    bg: "bg-warn/5",
  },
};

/**
 * Consistent card for surfacing analytical insights — observations, risks,
 * opportunities, warnings, recommendations. Renders a small icon + label,
 * headline, optional body / why-it-matters section and a priority pill.
 */
export function InsightCard({
  kind,
  title,
  body,
  whyItMatters,
  priority,
  confidence,
  className,
}: {
  kind: InsightKind;
  title: ReactNode;
  body?: ReactNode;
  whyItMatters?: ReactNode;
  priority?: AnalysisPriority;
  confidence?: string;
  className?: string;
}) {
  const style = KIND[kind];
  return (
    <article
      className={clsx(
        "rounded-xl border p-4",
        style.ring,
        style.bg,
        className,
      )}
    >
      <div className="flex items-center gap-2">
        <span
          className={clsx(
            "inline-flex h-5 w-5 items-center justify-center rounded-md border font-semibold text-[11px]",
            style.ring,
            style.accent,
          )}
          aria-hidden
        >
          {style.icon}
        </span>
        <span
          className={clsx(
            "text-[10px] uppercase tracking-[0.14em] font-semibold",
            style.accent,
          )}
        >
          {style.label}
        </span>
        {priority && (
          <span
            className={clsx(
              "ml-auto rounded-md border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wider",
              priority === "high"
                ? "border-bad/50 bg-bad/10 text-bad"
                : priority === "medium"
                  ? "border-warn/50 bg-warn/10 text-warn"
                  : "border-line bg-bg-hover text-ink-muted",
            )}
          >
            {priority}
          </span>
        )}
      </div>
      <h4 className="mt-2 text-sm font-medium text-ink leading-snug">
        {title}
      </h4>
      {body && (
        <div className="mt-2 text-xs text-ink-muted leading-relaxed">
          {body}
        </div>
      )}
      {whyItMatters && (
        <div className="mt-3 border-t border-line/70 pt-3">
          <div className="label mb-1">Why it matters</div>
          <div className="text-xs text-ink-muted leading-relaxed">
            {whyItMatters}
          </div>
        </div>
      )}
      {confidence && (
        <div className="mt-3 text-[10px] uppercase tracking-widest text-ink-faint">
          Confidence · {confidence}
        </div>
      )}
    </article>
  );
}
