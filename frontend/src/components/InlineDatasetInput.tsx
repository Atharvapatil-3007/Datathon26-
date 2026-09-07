import { ChangeEvent, DragEvent, useCallback, useRef, useState } from "react";
import clsx from "clsx";
import { api, ApiError } from "@/lib/api";
import { fmtBytes, fmtInt, fmtRelative } from "@/lib/format";
import { DatasetPicker } from "./DatasetPicker";
import { ErrorBanner, LoadingState } from "./ui/States";
import type { DatasetSummary } from "@/lib/types";

/**
 * "Bring another dataset" input used inside the Merger + Benchmark pages.
 *
 * Users can either
 *   (1) upload a fresh file, which gets routed through the same Phase 1 +
 *       Phase 2 pipeline as any other upload, and is then automatically
 *       selected; or
 *   (2) pick from datasets they've previously uploaded.
 *
 * This directly matches Section 6 of the spec: the second dataset must go
 * through the existing validation + profiling infrastructure. We do NOT
 * duplicate that infrastructure — this component just fires the existing
 * upload endpoint.
 */

const ACCEPTED = [
  ".csv",
  ".tsv",
  ".txt",
  ".xlsx",
  ".xls",
  ".json",
  ".jsonl",
  ".parquet",
  ".db",
  ".sqlite",
  ".zip",
];

type Mode = "upload" | "pick";

export function InlineDatasetInput({
  label,
  hint,
  excludeId,
  selected,
  onSelect,
  optional = false,
}: {
  label: string;
  hint?: string;
  excludeId?: string;
  selected: DatasetSummary | null;
  onSelect: (row: DatasetSummary | null) => void;
  optional?: boolean;
}) {
  const [mode, setMode] = useState<Mode>("upload");
  const inputRef = useRef<HTMLInputElement>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);

  const uploadFile = useCallback(
    async (file: File) => {
      setError(null);
      setUploading(true);
      try {
        const result = await api.uploadDataset(file);
        // Fetch the full DatasetSummary so downstream analysis picks up the
        // persisted profile / row / column counts.
        const summary = await api.getDataset(result.dataset_id);
        onSelect(summary);
      } catch (err) {
        setError(err instanceof ApiError ? err.message : (err as Error).message);
      } finally {
        setUploading(false);
      }
    },
    [onSelect],
  );

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) void uploadFile(e.target.files[0]);
    // reset so the same file can be re-selected later
    if (inputRef.current) inputRef.current.value = "";
  };
  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length) void uploadFile(e.dataTransfer.files[0]);
  };

  return (
    <div>
      <div className="mb-2 flex items-baseline justify-between">
        <div className="label">
          {label}
          {optional && <span className="ml-2 text-[11px] text-ink-faint">(optional)</span>}
        </div>
        {hint && <div className="text-[11px] text-ink-faint">{hint}</div>}
      </div>

      {selected ? (
        <SelectedCard row={selected} onClear={() => onSelect(null)} />
      ) : (
        <>
          <ModeSwitch mode={mode} onChange={setMode} />
          {error && <ErrorBanner title="Upload failed" detail={error} onDismiss={() => setError(null)} />}
          {mode === "upload" ? (
            uploading ? (
              <div className="rounded-lg border border-line bg-bg-soft/40 p-6">
                <LoadingState message="Validating and profiling…" />
              </div>
            ) : (
              <div
                onClick={() => inputRef.current?.click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragOver(true);
                }}
                onDragLeave={() => setDragOver(false)}
                onDrop={onDrop}
                className={clsx(
                  "rounded-lg border-2 border-dashed px-4 py-8 text-center cursor-pointer transition-colors",
                  dragOver
                    ? "border-brand bg-brand-soft/40"
                    : "border-line hover:border-brand-muted hover:bg-bg-hover/40",
                )}
              >
                <div className="flex flex-col items-center gap-1">
                  <div className="h-9 w-9 rounded-md bg-bg-hover border border-line flex items-center justify-center text-ink-faint">
                    <svg viewBox="0 0 24 24" fill="none" className="h-5 w-5">
                      <path
                        d="M12 15V3m0 0-4 4m4-4 4 4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
                        stroke="currentColor"
                        strokeWidth="1.5"
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      />
                    </svg>
                  </div>
                  <p className="text-xs text-ink">
                    <span className="text-brand font-medium">Click to browse</span> or drop a file
                  </p>
                  <p className="text-[10px] text-ink-faint">
                    CSV · TSV · Excel · JSON · JSONL · Parquet · SQLite · ZIP
                  </p>
                  <p className="text-[10px] text-ink-faint mt-1">
                    Runs through the same validation + profiling as any other upload.
                  </p>
                </div>
                <input
                  ref={inputRef}
                  type="file"
                  className="hidden"
                  accept={ACCEPTED.join(",")}
                  onChange={onInputChange}
                />
              </div>
            )
          ) : (
            <DatasetPicker
              label=""
              excludeId={excludeId}
              selectedId={null}
              onSelect={onSelect}
            />
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function ModeSwitch({
  mode,
  onChange,
}: {
  mode: Mode;
  onChange: (m: Mode) => void;
}) {
  return (
    <div className="mb-3 inline-flex rounded-md border border-line overflow-hidden text-xs">
      <button
        onClick={() => onChange("upload")}
        className={clsx(
          "px-3 py-1.5",
          mode === "upload"
            ? "bg-brand-soft/60 text-ink"
            : "bg-bg-soft text-ink-muted hover:text-ink",
        )}
      >
        Upload new
      </button>
      <button
        onClick={() => onChange("pick")}
        className={clsx(
          "px-3 py-1.5 border-l border-line",
          mode === "pick"
            ? "bg-brand-soft/60 text-ink"
            : "bg-bg-soft text-ink-muted hover:text-ink",
        )}
      >
        Pick existing
      </button>
    </div>
  );
}

function SelectedCard({
  row,
  onClear,
}: {
  row: DatasetSummary;
  onClear: () => void;
}) {
  return (
    <div className="rounded-lg border border-brand-muted bg-brand-soft/30 px-4 py-3 flex items-start justify-between gap-3">
      <div className="min-w-0">
        <div className="text-sm font-medium text-ink truncate">
          {row.original_filename}
        </div>
        <div className="text-[11px] text-ink-muted mt-0.5">
          {fmtInt(row.row_count)} rows · {fmtInt(row.column_count)} cols ·{" "}
          {fmtBytes(row.file_size)} · {fmtRelative(row.created_at)}
        </div>
      </div>
      <button
        onClick={onClear}
        className="text-xs text-ink-faint hover:text-ink shrink-0"
      >
        Change
      </button>
    </div>
  );
}
