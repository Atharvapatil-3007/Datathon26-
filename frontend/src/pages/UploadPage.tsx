import { ChangeEvent, DragEvent, useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import clsx from "clsx";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { ErrorBanner, InfoBanner } from "@/components/ui/States";
import { StepTracker } from "@/components/ui/StepTracker";
import { BRAND } from "@/config/brand";
import { api, ApiError } from "@/lib/api";
import { fmtBytes } from "@/lib/format";
import { rememberDataset } from "@/lib/assistantContext";
import type { HealthResponse } from "@/lib/types";

/* -------------------------------------------------------------------------
 * Upload flow — Phase 1
 *
 * A premium drop-zone that runs the file through the ingestion pipeline:
 *   Upload → Detect format → Validate → Understand (profile) → Ready.
 * The visual language mirrors an enterprise onboarding flow.
 * ------------------------------------------------------------------------- */

const ACCEPTED_LABELS = [
  "CSV",
  "TSV",
  "Excel",
  "JSON",
  "JSONL",
  "Parquet",
  "SQLite",
  "ZIP",
];

const ACCEPTED_EXTS = [
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

const STAGES = [
  { id: "upload", label: "Uploading", hint: "Streaming to backend" },
  { id: "detect", label: "Detecting format", hint: "Auto-classify" },
  { id: "validate", label: "Validating", hint: "Schema + integrity" },
  { id: "profile", label: "Understanding", hint: "Profiling engine" },
  { id: "ready", label: "Ready", hint: "Open dashboard" },
];

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

  useEffect(() => {
    const ctrl = new AbortController();
    api.health(ctrl.signal).then(setHealth).catch(() => setHealth(null));
    return () => ctrl.abort();
  }, []);

  useEffect(() => {
    if (!uploading) return;
    setStage(0);
    let idx = 0;
    const timer = window.setInterval(() => {
      idx = Math.min(idx + 1, STAGES.length - 2); // stop just before "ready" until success
      setStage(idx);
    }, 700);
    return () => window.clearInterval(timer);
  }, [uploading]);

  const pickFile = useCallback((f: File | null) => {
    setError(null);
    setFile(f);
  }, []);

  const onDrop = useCallback(
    (e: DragEvent<HTMLDivElement>) => {
      e.preventDefault();
      setDragOver(false);
      if (e.dataTransfer.files.length) pickFile(e.dataTransfer.files[0]);
    },
    [pickFile],
  );

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
      setStage(STAGES.length - 1);
      rememberDataset(result.dataset_id, result.filename);
      // Brief pause so the "ready" step is visible before the page transitions.
      setTimeout(() => navigate(`/datasets/${result.dataset_id}`), 350);
    } catch (err) {
      if (err instanceof ApiError) {
        setError({ title: `Upload failed · ${err.code}`, detail: err.message });
      } else {
        setError({ title: "Upload failed", detail: (err as Error).message });
      }
      setUploading(false);
    }
  }

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Phase 1 · Ingest"
        title="Ingest a financial dataset"
        subtitle={`Drop a file — ${BRAND.name} validates it, understands its structure and opens the intelligence dashboard automatically.`}
      />

      {health && !health.supabase_configured && (
        <InfoBanner>
          Running in <strong className="font-medium">local storage</strong> mode
          (no Supabase configured). Uploaded files live under{" "}
          <code className="text-brand">.local_storage/</code> in the backend.
        </InfoBanner>
      )}

      {error && (
        <ErrorBanner
          title={error.title}
          detail={error.detail}
          onDismiss={() => setError(null)}
        />
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <Card className="lg:col-span-2" bodyClassName="p-0">
          {uploading ? (
            <UploadingPanel stage={stage} filename={file?.name ?? ""} />
          ) : (
            <div className="p-5">
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

              <input
                ref={inputRef}
                type="file"
                className="hidden"
                accept={ACCEPTED_EXTS.join(",")}
                onChange={onInputChange}
              />

              <div className="mt-5 flex items-center justify-between gap-3">
                <button
                  onClick={() => setShowAdvanced((v) => !v)}
                  className="text-xs text-ink-muted hover:text-ink transition-colors"
                >
                  {showAdvanced ? "Hide" : "Show"} advanced options
                </button>
                <div className="flex items-center gap-2">
                  {file && (
                    <Button onClick={() => pickFile(null)} size="md">
                      Clear
                    </Button>
                  )}
                  <Button
                    variant="primary"
                    onClick={submit}
                    disabled={!file}
                    size="md"
                  >
                    Ingest dataset
                  </Button>
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
            </div>
          )}
        </Card>

        {/* Right rail — pipeline explainer */}
        <PipelineExplainer />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Drop zone
 * ------------------------------------------------------------------------- */
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
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      role="button"
      tabIndex={0}
      aria-label="Upload dataset — click or drop a file"
      className={clsx(
        "group rounded-2xl border-2 border-dashed px-6 py-14 text-center cursor-pointer transition-all",
        dragOver
          ? "border-brand bg-brand-soft/50 shadow-glow"
          : "border-line hover:border-brand-muted hover:bg-bg-hover/50",
      )}
    >
      {file ? (
        <div className="flex flex-col items-center gap-2">
          <div className="h-14 w-14 rounded-xl bg-brand-soft border border-brand-muted flex items-center justify-center text-brand shadow-insetTop">
            <FileIcon />
          </div>
          <p className="font-medium text-ink text-lg">{file.name}</p>
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
        <div className="flex flex-col items-center gap-3">
          <div className="h-14 w-14 rounded-xl bg-bg-hover border border-line flex items-center justify-center text-ink-muted group-hover:text-brand group-hover:border-brand-muted transition-colors">
            <UploadIcon />
          </div>
          <p className="text-base text-ink font-medium">
            <span className="text-brand">Click to browse</span> or drop a file here
          </p>
          <p className="text-xs text-ink-muted max-w-md">
            Encrypted upload · never modified · streamed straight to the profiling pipeline.
          </p>
          <div className="mt-2 flex flex-wrap justify-center gap-1.5">
            {ACCEPTED_LABELS.map((l) => (
              <span key={l} className="chip">
                {l}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Uploading panel — step tracker + soft progress
 * ------------------------------------------------------------------------- */
function UploadingPanel({ stage, filename }: { stage: number; filename: string }) {
  return (
    <div className="p-6">
      <div className="text-center max-w-md mx-auto">
        <div className="eyebrow">Understanding your dataset</div>
        <h3 className="mt-1 heading-2 truncate">{filename}</h3>
        <p className="mt-1.5 text-xs text-ink-muted">
          Validating structure, inferring types, computing distributions.
        </p>
      </div>
      <div className="mt-8">
        <StepTracker steps={STAGES} current={stage} />
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------
 * Right rail — pipeline explainer
 * ------------------------------------------------------------------------- */
function PipelineExplainer() {
  const items = [
    {
      title: "Ingestion & validation",
      body: "File is detected, schema is inferred, and integrity checks run before anything is stored.",
    },
    {
      title: "Understanding your data",
      body: "Column types, distributions, missing values, duplicates and correlations are profiled automatically.",
    },
    {
      title: "Financial intelligence",
      body: "Self, merger and benchmark analysis pipelines unlock once the profile is ready.",
    },
  ];
  return (
    <Card eyebrow="How ingestion works" title="From raw file to insights">
      <ol className="space-y-4">
        {items.map((it, i) => (
          <li key={it.title} className="flex gap-3">
            <span className="flex-shrink-0 h-6 w-6 inline-flex items-center justify-center rounded-md bg-brand-soft border border-brand-muted text-brand text-[11px] font-semibold">
              {i + 1}
            </span>
            <div>
              <div className="text-sm font-medium text-ink">{it.title}</div>
              <div className="text-xs text-ink-muted mt-0.5 leading-relaxed">
                {it.body}
              </div>
            </div>
          </li>
        ))}
      </ol>
      <div className="mt-5 rounded-lg border border-line bg-bg-soft/50 p-3 text-[11px] text-ink-faint leading-relaxed">
        We never mutate your data. Every derived metric declares whether it was
        <span className="text-ink"> reported</span>,
        <span className="text-ink"> calculated</span>,
        <span className="text-ink"> estimated</span> or
        <span className="text-ink"> scenario</span>.
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------------------
 * Advanced input
 * ------------------------------------------------------------------------- */
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
        className="input"
      />
    </label>
  );
}

/* -------------------------------------------------------------------------
 * Icons
 * ------------------------------------------------------------------------- */
function FileIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-7 w-7">
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
    <svg viewBox="0 0 24 24" fill="none" className="h-7 w-7">
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
