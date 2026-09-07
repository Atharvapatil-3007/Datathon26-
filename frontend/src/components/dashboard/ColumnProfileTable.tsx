import { useMemo, useState } from "react";
import clsx from "clsx";
import { SectionProps, SectionShell, Bar } from "./_shared";
import { CardinalityBadge, ColumnClassBadge } from "@/components/ui/Badges";
import { fmtDecimal, fmtInt, fmtPercent } from "@/lib/format";
import type { ColumnClass, ColumnProfile } from "@/lib/types";

type SortKey = "name" | "class" | "missing" | "unique" | "quality";
type SortDir = "asc" | "desc";

const CLASS_FILTERS: ColumnClass[] = [
  "numerical",
  "categorical",
  "text",
  "date",
  "datetime",
  "id",
  "boolean",
  "unknown",
];

export function ColumnProfileTable({ profile }: SectionProps) {
  const [query, setQuery] = useState("");
  const [activeClasses, setActiveClasses] = useState<Set<ColumnClass>>(new Set());
  const [sortKey, setSortKey] = useState<SortKey>("quality");
  const [sortDir, setSortDir] = useState<SortDir>("asc");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    let list = profile.column_profiles.filter((c) => {
      if (activeClasses.size > 0 && !activeClasses.has(c.column_class)) return false;
      if (q && !c.name.toLowerCase().includes(q)) return false;
      return true;
    });
    list = [...list].sort((a, b) => {
      const dir = sortDir === "asc" ? 1 : -1;
      switch (sortKey) {
        case "name":
          return dir * a.name.localeCompare(b.name);
        case "class":
          return dir * a.column_class.localeCompare(b.column_class);
        case "missing":
          return dir * (a.missing_ratio - b.missing_ratio);
        case "unique":
          return dir * (a.unique_ratio - b.unique_ratio);
        case "quality":
          return dir * (a.quality_score - b.quality_score);
      }
    });
    return list;
  }, [profile.column_profiles, query, activeClasses, sortKey, sortDir]);

  const toggleClass = (cls: ColumnClass) => {
    setActiveClasses((prev) => {
      const next = new Set(prev);
      if (next.has(cls)) next.delete(cls);
      else next.add(cls);
      return next;
    });
  };

  const setSort = (key: SortKey) => {
    if (sortKey === key) setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    else {
      setSortKey(key);
      setSortDir(key === "name" ? "asc" : "desc");
    }
  };

  return (
    <SectionShell
      title="Column profile"
      subtitle={`${profile.column_profiles.length} columns — sortable and filterable.`}
      bodyClassName="p-0"
    >
      <div className="px-5 pb-3 flex flex-wrap items-center gap-2 justify-between border-b border-line">
        <input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search columns…"
          className="bg-bg-soft border border-line rounded-md px-3 py-1.5 text-sm text-ink placeholder:text-ink-faint focus:outline-none focus:border-brand-muted w-64"
        />
        <div className="flex flex-wrap gap-1">
          {CLASS_FILTERS.map((cls) => (
            <button
              key={cls}
              onClick={() => toggleClass(cls)}
              className={clsx(
                "px-2 py-0.5 text-[11px] rounded-md border capitalize",
                activeClasses.has(cls)
                  ? "border-brand text-brand bg-brand-soft/60"
                  : "border-line text-ink-muted hover:text-ink hover:bg-bg-hover",
              )}
            >
              {cls}
            </button>
          ))}
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-bg-soft/60 border-b border-line">
            <tr className="text-left text-[11px] uppercase tracking-wider text-ink-faint">
              <Th label="Column" sortKey="name" current={sortKey} dir={sortDir} onSort={setSort} />
              <Th label="Type" sortKey="class" current={sortKey} dir={sortDir} onSort={setSort} />
              <Th label="Missing" sortKey="missing" current={sortKey} dir={sortDir} onSort={setSort} />
              <Th label="Unique" sortKey="unique" current={sortKey} dir={sortDir} onSort={setSort} />
              <th className="px-4 py-2 font-medium">Cardinality</th>
              <Th label="Quality" sortKey="quality" current={sortKey} dir={sortDir} onSort={setSort} />
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {rows.map((c) => (
              <Row key={c.name} c={c} />
            ))}
          </tbody>
        </table>
        {rows.length === 0 && (
          <div className="p-8 text-center text-sm text-ink-muted">
            No columns match the current filter.
          </div>
        )}
      </div>
    </SectionShell>
  );
}

function Th({
  label,
  sortKey,
  current,
  dir,
  onSort,
}: {
  label: string;
  sortKey: SortKey;
  current: SortKey;
  dir: SortDir;
  onSort: (k: SortKey) => void;
}) {
  const active = sortKey === current;
  return (
    <th
      className="px-4 py-2 font-medium cursor-pointer select-none whitespace-nowrap"
      onClick={() => onSort(sortKey)}
    >
      <span
        className={clsx(
          "inline-flex items-center gap-1",
          active ? "text-ink" : "hover:text-ink",
        )}
      >
        {label}
        <span className="text-[10px] opacity-70">
          {active ? (dir === "asc" ? "▲" : "▼") : ""}
        </span>
      </span>
    </th>
  );
}

function Row({ c }: { c: ColumnProfile }) {
  return (
    <tr className="text-ink-muted">
      <td className="px-4 py-2.5">
        <div className="font-medium text-ink truncate max-w-[300px]" title={c.name}>
          {c.name}
        </div>
        <div className="text-[11px] text-ink-faint font-mono">{c.dtype}</div>
      </td>
      <td className="px-4 py-2.5">
        <ColumnClassBadge value={c.column_class} />
      </td>
      <td className="px-4 py-2.5 min-w-[140px]">
        <div className="flex items-center gap-2">
          <span className="text-ink">{fmtPercent(c.missing_ratio)}</span>
          <span className="text-[11px] text-ink-faint">({fmtInt(c.missing_count)})</span>
        </div>
        <div className="mt-1"><Bar ratio={c.missing_ratio} tone={c.missing_ratio > 0.2 ? "bad" : "warn"} /></div>
      </td>
      <td className="px-4 py-2.5 min-w-[140px]">
        <div className="flex items-center gap-2">
          <span className="text-ink">{fmtPercent(c.unique_ratio)}</span>
          <span className="text-[11px] text-ink-faint">({fmtInt(c.unique_count)})</span>
        </div>
      </td>
      <td className="px-4 py-2.5">
        <CardinalityBadge value={c.cardinality_class} />
      </td>
      <td className="px-4 py-2.5 min-w-[160px]">
        <div className="flex items-center gap-2">
          <span
            className={clsx(
              "font-mono text-ink",
              c.quality_score >= 90 && "text-good",
              c.quality_score < 60 && "text-bad",
            )}
          >
            {fmtDecimal(c.quality_score, 1)}
          </span>
          <span className="text-[11px] text-ink-faint">/ 100</span>
        </div>
        <div className="mt-1">
          <Bar
            ratio={c.quality_score / 100}
            tone={c.quality_score >= 90 ? "good" : c.quality_score >= 70 ? "info" : c.quality_score >= 60 ? "warn" : "bad"}
          />
        </div>
      </td>
    </tr>
  );
}
