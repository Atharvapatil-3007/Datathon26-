import { useEffect, useState } from "react";
import clsx from "clsx";
import { api, ApiError } from "@/lib/api";
import { fmtInt, fmtRelative } from "@/lib/format";
import type { DatasetSummary } from "@/lib/types";
import { LoadingState, ErrorBanner, EmptyState } from "@/components/ui/States";

/**
 * Compact list of datasets a user can pick from. Used by merger + benchmark
 * modes to select the "other" dataset. The one currently open is excluded.
 */
export function DatasetPicker({
  excludeId,
  selectedId,
  onSelect,
  label,
  hint,
}: {
  excludeId?: string;
  selectedId?: string | null;
  onSelect: (row: DatasetSummary) => void;
  label: string;
  hint?: string;
}) {
  const [rows, setRows] = useState<DatasetSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    (async () => {
      try {
        const data = await api.listDatasets(50, 0, ctrl.signal);
        setRows(data.filter((r) => r.id !== excludeId && r.status === "validated"));
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError(err instanceof ApiError ? err.message : (err as Error).message);
      }
    })();
    return () => ctrl.abort();
  }, [excludeId]);

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <div className="label">{label}</div>
        {hint && <div className="text-[11px] text-ink-faint">{hint}</div>}
      </div>
      {error && <ErrorBanner title="Couldn't list datasets" detail={error} />}
      {rows === null && !error && <LoadingState message="Loading datasets…" />}
      {rows && rows.length === 0 && (
        <EmptyState
          title="No other datasets available"
          hint="Upload another dataset to use this analysis mode."
        />
      )}
      {rows && rows.length > 0 && (
        <div className="border border-line rounded-lg divide-y divide-line max-h-72 overflow-y-auto bg-bg-soft/40">
          {rows.map((r) => {
            const selected = r.id === selectedId;
            return (
              <button
                key={r.id}
                onClick={() => onSelect(r)}
                className={clsx(
                  "w-full text-left px-4 py-2.5 transition-colors flex items-center justify-between gap-3",
                  selected
                    ? "bg-brand-soft/60 border-l-2 border-brand"
                    : "hover:bg-bg-hover",
                )}
              >
                <div className="min-w-0">
                  <div className="text-sm font-medium text-ink truncate">
                    {r.original_filename}
                  </div>
                  <div className="text-[11px] text-ink-faint mt-0.5">
                    {fmtInt(r.row_count)} rows · {fmtInt(r.column_count)} cols · {fmtRelative(r.created_at)}
                  </div>
                </div>
                {selected && (
                  <span className="text-brand text-xs font-medium">Selected</span>
                )}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
