import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Card } from "@/components/ui/Card";
import { EmptyState, ErrorBanner, LoadingState } from "@/components/ui/States";
import { StatusBadge } from "@/components/ui/Badges";
import { api, ApiError } from "@/lib/api";
import { fmtBytes, fmtInt, fmtRelative } from "@/lib/format";
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

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Datasets</h1>
          <p className="text-sm text-ink-muted mt-1">
            Every dataset you've ingested, newest first.
          </p>
        </div>
        <Link to="/upload" className="btn-primary">
          + Upload new
        </Link>
      </div>

      {error && <ErrorBanner title="Could not load datasets" detail={error} />}

      <Card bodyClassName="p-0">
        {rows === null ? (
          <LoadingState message="Fetching datasets…" />
        ) : rows.length === 0 ? (
          <EmptyState
            title="No datasets yet"
            hint="Head to Upload to ingest your first CSV or Excel file."
            action={
              <Link to="/upload" className="btn-primary">
                Upload a dataset
              </Link>
            }
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-bg-soft border-b border-line">
                <tr className="text-left text-[11px] uppercase tracking-wider text-ink-faint">
                  <th className="px-5 py-3 font-medium">Filename</th>
                  <th className="px-5 py-3 font-medium">Format</th>
                  <th className="px-5 py-3 font-medium">Rows</th>
                  <th className="px-5 py-3 font-medium">Cols</th>
                  <th className="px-5 py-3 font-medium">Size</th>
                  <th className="px-5 py-3 font-medium">Status</th>
                  <th className="px-5 py-3 font-medium">Ingested</th>
                  <th className="px-5 py-3" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {rows.map((row) => (
                  <tr
                    key={row.id}
                    className="cursor-pointer"
                    onClick={() => navigate(`/datasets/${row.id}`)}
                  >
                    <td className="px-5 py-3">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-ink truncate max-w-[280px]">
                          {row.original_filename}
                        </span>
                      </div>
                    </td>
                    <td className="px-5 py-3 text-ink-muted uppercase text-[11px] font-medium">
                      {row.file_format}
                    </td>
                    <td className="px-5 py-3 text-ink-muted">{fmtInt(row.row_count)}</td>
                    <td className="px-5 py-3 text-ink-muted">{fmtInt(row.column_count)}</td>
                    <td className="px-5 py-3 text-ink-muted">{fmtBytes(row.file_size)}</td>
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
