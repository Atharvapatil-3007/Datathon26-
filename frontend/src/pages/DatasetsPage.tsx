import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { PageHeader } from "@/components/ui/PageHeader";
import { Button } from "@/components/ui/Button";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/ui/States";
import { StatusBadge } from "@/components/ui/Badges";
import { api, ApiError } from "@/lib/api";
import { fmtBytes, fmtInt, fmtRelative } from "@/lib/format";
import { rememberDataset } from "@/lib/assistantContext";
import type { DatasetSummary } from "@/lib/types";

export default function DatasetsPage() {
  const navigate = useNavigate();
  const [rows, setRows] = useState<DatasetSummary[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  useEffect(() => {
    const ctrl = new AbortController();
    (async () => {
      try {
        setError(null);
        const data = await api.listDatasets(100, 0, ctrl.signal);
        setRows(data);
      } catch (err) {
        if ((err as Error).name === "AbortError") return;
        setError(err instanceof ApiError ? err.message : (err as Error).message);
      }
    })();
    return () => ctrl.abort();
  }, []);

  async function deleteRow(id: string) {
    if (!confirm("Delete this dataset and its stored file?")) return;
    setDeletingId(id);
    try {
      await api.deleteDataset(id);
      setRows((prev) => (prev ? prev.filter((r) => r.id !== id) : prev));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : (err as Error).message);
    } finally {
      setDeletingId(null);
    }
  }

  const total = rows?.length ?? 0;
  const validated = rows?.filter((r) => r.status === "validated").length ?? 0;
  const failed = rows?.filter((r) => r.status === "failed").length ?? 0;

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow="Workspace"
        title="Datasets"
        subtitle="Every dataset you've ingested — profiled, ready for analysis, sorted newest first."
        actions={
          <Link to="/upload">
            <Button variant="primary">+ Upload dataset</Button>
          </Link>
        }
        meta={
          rows && (
            <div className="flex flex-wrap items-center gap-2">
              <span className="chip">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-brand" />
                {fmtInt(total)} total
              </span>
              <span className="chip text-good">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-good" />
                {fmtInt(validated)} validated
              </span>
              {failed > 0 && (
                <span className="chip text-bad">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-bad" />
                  {fmtInt(failed)} failed
                </span>
              )}
            </div>
          )
        }
      />

      {error && <ErrorBanner title="Could not load datasets" detail={error} />}

      <Card bodyClassName="p-0">
        {rows === null ? (
          <LoadingState message="Fetching datasets…" />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No datasets yet"
            hint="Ingest your first CSV, Excel, JSON or Parquet file to unlock profiling and analysis."
            action={
              <Link to="/upload">
                <Button variant="primary">Upload a dataset</Button>
              </Link>
            }
            icon={
              <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
                <path
                  d="M3 7a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7Z"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinejoin="round"
                />
              </svg>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-bg-soft border-b border-line">
                <tr className="text-left text-[11px] uppercase tracking-[0.08em] text-ink-faint">
                  <th className="px-5 py-3 font-medium">Dataset</th>
                  <th className="px-5 py-3 font-medium">Format</th>
                  <th className="px-5 py-3 font-medium text-right">Rows</th>
                  <th className="px-5 py-3 font-medium text-right">Cols</th>
                  <th className="px-5 py-3 font-medium text-right">Size</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Ingested</th>
                  <th className="px-5 py-3" aria-label="Actions" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((row) => (
                  <tr
                    key={row.id}
                    className="cursor-pointer transition-colors"
                    onClick={() => {
                      rememberDataset(row.id, row.original_filename);
                      navigate(`/datasets/${row.id}`);
                    }}
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-3 min-w-0">
                        <span className="h-8 w-8 rounded-md bg-bg-soft border border-line inline-flex items-center justify-center text-ink-muted shrink-0">
                          <IconDoc />
                        </span>
                        <div className="min-w-0">
                          <div className="font-medium text-ink truncate max-w-[300px]">
                            {row.original_filename}
                          </div>
                          <div className="text-[11px] text-ink-faint font-mono truncate max-w-[300px]">
                            {row.id}
                          </div>
                        </div>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-ink-muted uppercase text-[11px] font-medium tracking-wider">
                      {row.file_format}
                    </td>
                    <td className="px-5 py-3 text-ink num">{fmtInt(row.row_count)}</td>
                    <td className="px-5 py-3 text-ink num">{fmtInt(row.column_count)}</td>
                    <td className="px-5 py-3 text-ink-muted num">{fmtBytes(row.file_size)}</td>
                    <td className="px-5 py-3">
                      <StatusBadge value={row.status} />
                    </td>
                    <td className="px-5 py-3 text-ink-muted text-xs">
                      {fmtRelative(row.created_at)}
                    </td>
                    <td className="px-5 py-3 text-right">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          deleteRow(row.id);
                        }}
                        className="text-xs text-ink-faint hover:text-bad transition-colors disabled:opacity-40"
                        disabled={deletingId === row.id}
                        aria-label={`Delete ${row.original_filename}`}
                      >
                        {deletingId === row.id ? "Deleting…" : "Delete"}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>
    </div>
  );
}

function IconDoc() {
  return (
    <svg viewBox="0 0 24 24" fill="none" className="h-4 w-4">
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
