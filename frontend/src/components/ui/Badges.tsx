import clsx from "clsx";
import type {
  CardinalityClass,
  ColumnClass,
  DatasetStatus,
  QualityGrade,
} from "@/lib/types";

const CLASS_COLORS: Record<ColumnClass, string> = {
  numerical: "text-brand border-brand-muted/60 bg-brand-soft/50",
  categorical: "text-good border-good/40 bg-good/10",
  text: "text-info border-info/40 bg-info/10",
  date: "text-warn border-warn/40 bg-warn/10",
  datetime: "text-warn border-warn/40 bg-warn/10",
  id: "text-ink-muted border-line bg-bg-hover",
  boolean: "text-info border-info/40 bg-info/10",
  unknown: "text-bad border-bad/40 bg-bad/10",
};

export function ColumnClassBadge({ value }: { value: ColumnClass }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium capitalize",
        CLASS_COLORS[value] ?? CLASS_COLORS.unknown,
      )}
    >
      {value}
    </span>
  );
}

const CARDINALITY_LABEL: Record<CardinalityClass, string> = {
  low: "Low",
  medium: "Medium",
  high: "High",
  unique: "Unique",
};
export function CardinalityBadge({ value }: { value: CardinalityClass }) {
  return <span className="badge">{CARDINALITY_LABEL[value]}</span>;
}

const STATUS_COLORS: Record<DatasetStatus, string> = {
  uploaded: "text-ink-muted border-line bg-bg-hover",
  detecting: "text-info border-info/40 bg-info/10",
  processing: "text-info border-info/40 bg-info/10",
  validated: "text-good border-good/40 bg-good/10",
  failed: "text-bad border-bad/40 bg-bad/10",
};
export function StatusBadge({ value }: { value: DatasetStatus }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-[11px] font-medium capitalize",
        STATUS_COLORS[value] ?? "text-ink-muted border-line bg-bg-hover",
      )}
    >
      {value}
    </span>
  );
}

const GRADE_COLORS: Record<QualityGrade, string> = {
  A: "text-good border-good/50 bg-good/10",
  B: "text-info border-info/50 bg-info/10",
  C: "text-warn border-warn/50 bg-warn/10",
  D: "text-warn border-warn/50 bg-warn/10",
  F: "text-bad border-bad/50 bg-bad/10",
};
export function GradeBadge({ value }: { value: QualityGrade }) {
  return (
    <span
      className={clsx(
        "inline-flex items-center justify-center rounded-md border px-2 py-1 text-sm font-semibold w-9",
        GRADE_COLORS[value] ?? GRADE_COLORS.F,
      )}
    >
      {value}
    </span>
  );
}
