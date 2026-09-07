import { ChangeEvent, DragEvent, useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { Card } from "@/components/ui/Card";
import { ErrorBanner, InfoBanner, LoadingState } from "@/components/ui/States";
import { api, ApiError } from "@/lib/api";
import { fmtBytes } from "@/lib/format";
import type { HealthResponse } from "@/lib/types";

// Stages we surface to the user while the request is in flight. These are
// informational only — we don't fake progress percentages because the
// backend response is synchronous.
const STAGES = [
  "Uploading file to storage",
  "Detecting format",
  "Validating dataset",
  "Understanding your dataset",
];

const ACCEPTED = [".csv", ".tsv", ".txt", ".xlsx", ".xls", ".json", ".jsonl", ".parquet", ".db", ".sqlite", ".zip"];

export default function UploadPage() {
  const navigate = useNavigate();
  const inputRef = useRef<HTMLInputElement>(null);

  const [file, setFile] = useState<File | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [stage, setStage] = useState(0);
  const [error, setError] = useState<{ title: string; detail?: string } | null>(null);
  const [health, setHealth] = useState<HealthResponse | null>(null);

  // Advanced options
  const [sheetName, setSheetName] = useState("");
  const [tableName, setTableName] = useState("");
  const [delimiter, setDelimiter] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);

  // Poll health once so we can warn the user if the backend is offline.
  useEffect(() => {
    const ctrl = new AbortController();
    api
      .health(ctrl.signal)
      .then(setHealth)
      .catch(() => setHealth(null));
    return () => ctrl.abort();
  }, []);

  // Animate stage indicator during upload for perceived responsiveness.
  useEffect(() => {
    if (!uploading) return;
    setStage(0);
    let idx = 0;
    const timer = window.setInterval(() => {
      idx = Math.min(idx + 1, STAGES.length - 1);
      setStage(idx);
    }, 700);
    return () => window.clearInterval(timer);
  }, [uploading]);

  const pickFile = useCallback((f: File | null) => {
    setError(null);
    setFile(f);
  }, []);

  const onDrop = useCallback((e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files.length) pickFile(e.dataTransfer.files[0]);
  }, [pickFile]);

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) pickFile(e.target.files[0]);
  };

  async function submit() {
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      const result = await api.uploadDataset(file, {
        sheetName: sheetName || undefined,
        tableName: tableName || undefined,
        delimiter: delimiter || undefined,
      });
      // Success — jump straight to the dashboard for this dataset.
      navigate(`/datasets/${result.dataset_id}`);
    } catch (err) {
      if (err instanceof ApiError) {
        setError({
          title: `Upload failed (${err.code})`,
          detail: err.message,
        });
      } else {
        setError({ title: "Upload failed", detail: (err as Error).message });
      }
      setUploading(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">Ingest a dataset</h1>
        <p className="text-sm text-ink-muted mt-1">
          Drop a CSV, Excel, JSON, JSONL, Parquet, SQLite, or ZIP file. Phase 1
          validates it, Phase 2 profiles it, and the dashboard opens automatically.
        </p>
      </div>

      {health && !health.supabase_configured && (
        <InfoBanner>
          Running in <strong className="font-medium">local storage</strong> mode
          (no Supabase configured). Uploaded files live under{" "}
          <code className="text-brand">.local_storage/</code> in the backend.
        </InfoBanner>
      )}

      {error && <ErrorBanner title={error.title} detail={error.detail} onDismiss={() => setError(null)} />}

      <Card>
        {uploading ? (
          <UploadingProgress stage={stage} filename={file?.name ?? ""} />
        ) : (
          <DropZone
            file={file}
            dragOver={dragOver}
            onSelect={() => inputRef.current?.click()}
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={onDrop}
            onClear={() => pickFile(null)}
          />
        )}

        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept={ACCEPTED.join(",")}
          onChange={onInputChange}
        />

        <div className="mt-5 flex items-center justify-between gap-3">
          <button
            onClick={() => setShowAdvanced((v) => !v)}
            className="text-xs text-ink-muted hover:text-ink"
          >
            {showAdvanced ? "Hide" : "Show"} advanced options
          </button>
          <div className="flex items-center gap-2">
            {file && !uploading && (
              <button className="btn" onClick={() => pickFile(null)}>
                Clear
              </button>
            )}
            <button
              className="btn-primary"
              onClick={submit}
              disabled={!file || uploading}
            >
              {uploading ? "Working…" : "Ingest dataset"}
            </button>
          </div>
        </div>

        {showAdvanced && (
          <div className="mt-5 grid grid-cols-1 sm:grid-cols-3 gap-4 pt-5 border-t border-line">
            <AdvancedInput
              label="Excel sheet name"
              value={sheetName}
              onChange={setSheetName}
              placeholder="e.g. Q1_transactions"
            />
            <AdvancedInput
              label="SQLite table name"
              value={tableName}
              onChange={setTableName}
              placeholder="e.g. transactions"
            />
            <AdvancedInput
              label="CSV delimiter override"
              value={delimiter}
              onChange={setDelimiter}
              placeholder="Auto-detected"
            />
          </div>
        )}
      </Card>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function DropZone({
  file,
  dragOver,
  onSelect,
  onDragOver,
  onDragLeave,
  onDrop,
  onClear,
}: {
  file: File | null;
  dragOver: boolean;
  onSelect: () => void;
  onDragOver: (e: DragEvent<HTMLDivElement>) => void;
  onDragLeave: () => void;
  onDrop: (e: DragEvent<HTMLDivElement>) => void;
  onClear: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      onDragOver={onDragOver}
      onDragLeave={onDragLeave}
      onDrop={onDrop}
      className={clsx(
        "rounded-xl border-2 border-dashed px-6 py-12 text-center cursor-pointer transition-colors",
        dragOver
          ? "border-brand bg-brand-soft/40"
          : "border-line hover:border-brand-muted hover:bg-bg-hover/40",
      )}
    >
      {file ? (
        <div className="flex flex-col items-center gap-2">
          <div className="h-12 w-12 rounded-lg bg-brand-soft border border-brand-muted flex items-center justify-center text-brand">
            <FileIcon />
          </div>
          <p className="font-medium text-ink">{file.name}</p>
          <p className="text-xs text-ink-muted">{fmtBytes(file.size)}</p>
          <button
            onClick={(e) => {
              e.stopPropagation();
              onClear();
            }}
            className="text-xs text-ink-muted hover:text-ink underline underline-offset-2 mt-1"
          >
            Choose a different file
          </button>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-2">
          <div className="h-12 w-12 rounded-lg bg-bg-hover border border-line flex items-center justify-center text-ink-faint">
            <UploadIcon />
          </div>
          <p className="text-sm text-ink">
            <span className="text-brand font-medium">Click to browse</span> or drop a file here
          </p>
          <p className="text-xs text-ink-faint">
            CSV · TSV · Excel · JSON · JSONL · Parquet · SQLite · ZIP
          </p>
        </div>
      )}
    </div>
  );
}

function AdvancedInput({
  label,
  value,
  onChange,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
}) {
  return (
    <label className="flex flex-col gap-1.5">
      <span className="label">{label}</span>
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="bg-bg-soft border border-line rounded-md px-3 py-2 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-brand-muted"
      />
    </label>
  );
}

function UploadingProgress({ stage, filename }: { stage: number; filename: string }) {
  return (
    <div className="py-6">
      <LoadingState message={`Understanding ${filename}…`} />
      <ol className="mt-6 space-y-2 max-w-md mx-auto">
        {STAGES.map((label, i) => (
          <li key={label} className="flex items-center gap-3 text-sm">
            <span
              className={clsx(
                "h-5 w-5 rounded-full flex items-center justify-center text-[11px] font-medium",
                i < stage && "bg-good/20 text-good",
                i === stage && "bg-brand-soft border border-brand-muted text-brand",
                i > stage && "bg-bg-hover text-ink-faint",
              )}
            >
              {i < stage ? "✓" : i === stage ? "…" : i + 1}
            </span>
            <span className={i <= stage ? "text-ink" : "text-ink-faint"}>{label}</span>
          </li>
        ))}
      </ol>
    </div>
  );
}

function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
      <path
        d="M14 3v4a1 1 0 0 0 1 1h4M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8l-5-5Z"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function UploadIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
      <path
        d="M12 15V3m0 0-4 4m4-4 4 4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"
        stroke="currentColor"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
