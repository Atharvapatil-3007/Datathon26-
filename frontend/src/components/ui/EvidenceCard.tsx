import { ReactNode } from "react";
import clsx from "clsx";

/**
 * Small evidence panel used by the AI Assistant to attach data provenance
 * to a natural-language answer. Every field maps to a piece of information
 * from the underlying analysis result — nothing here is fabricated.
 */
export function EvidenceCard({
  title = "Evidence",
  source,
  confidence,
  status,
  children,
  className,
}: {
  title?: string;
  source?: ReactNode;
  confidence?: "High" | "Medium" | "Low";
  status?: "reported" | "calculated" | "estimated" | "scenario";
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={clsx(
        "rounded-lg border border-brand-muted/40 bg-brand-soft/20 px-3 py-2.5",
        className,
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <div className="eyebrow">{title}</div>
        <div className="flex items-center gap-1.5">
          {status && (
            <span className="inline-flex items-center rounded border border-brand-muted/60 bg-brand-soft/60 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-widest text-brand-strong">
              {status}
            </span>
          )}
          {confidence && (
            <span
              className={clsx(
                "text-[10px] uppercase tracking-widest font-semibold",
                confidence === "High" && "text-good",
                confidence === "Medium" && "text-warn",
                confidence === "Low" && "text-ink-muted",
              )}
            >
              {confidence}
            </span>
          )}
        </div>
      </div>
      <div className="mt-1.5 text-xs text-ink leading-relaxed">{children}</div>
      {source && (
        <div className="mt-2 border-t border-brand-muted/20 pt-1.5 text-[10px] text-ink-faint">
          Source · {source}
        </div>
      )}
    </div>
  );
}
