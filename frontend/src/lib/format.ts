/**
 * Number / date / percentage formatters used across the dashboard.
 *
 * All helpers gracefully handle `null` / `undefined` / `NaN` so components
 * can call them on raw API values without pre-guarding.
 */

const numberFormatter = new Intl.NumberFormat("en-US");
const compactFormatter = new Intl.NumberFormat("en-US", {
  notation: "compact",
  maximumFractionDigits: 1,
});
const percentFormatter = new Intl.NumberFormat("en-US", {
  style: "percent",
  minimumFractionDigits: 0,
  maximumFractionDigits: 2,
});

const decimalFormatter = new Intl.NumberFormat("en-US", {
  minimumFractionDigits: 0,
  maximumFractionDigits: 4,
});

function safeNumber(v: unknown): number | null {
  if (v === null || v === undefined) return null;
  const n = typeof v === "number" ? v : Number(v);
  if (!Number.isFinite(n)) return null;
  return n;
}

export function fmtInt(v: unknown): string {
  const n = safeNumber(v);
  return n === null ? "—" : numberFormatter.format(Math.round(n));
}

export function fmtCompact(v: unknown): string {
  const n = safeNumber(v);
  return n === null ? "—" : compactFormatter.format(n);
}

export function fmtDecimal(v: unknown, maxFraction = 4): string {
  const n = safeNumber(v);
  if (n === null) return "—";
  return new Intl.NumberFormat("en-US", {
    maximumFractionDigits: maxFraction,
  }).format(n);
}

export function fmtPercent(ratio: unknown, maxFraction = 2): string {
  const n = safeNumber(ratio);
  if (n === null) return "—";
  return percentFormatter.format(Math.min(Math.max(n, 0), 1)).replace(/\s/g, "") ||
    `${(n * 100).toFixed(maxFraction)}%`;
}

/**
 * Human-friendly compact currency for financial numbers.
 *
 * We do NOT force a currency symbol because the underlying datasets may be
 * in any currency (or none — some rows are counts). Callers can pass a
 * symbol explicitly when they know it.
 */
export function fmtCompactCurrency(v: unknown, symbol = ""): string {
  const n = safeNumber(v);
  if (n === null) return "—";
  const abs = Math.abs(n);
  let scaled: string;
  if (abs >= 1_000_000_000) scaled = `${(n / 1_000_000_000).toFixed(2)}B`;
  else if (abs >= 1_000_000) scaled = `${(n / 1_000_000).toFixed(2)}M`;
  else if (abs >= 1_000) scaled = `${(n / 1_000).toFixed(1)}K`;
  else scaled = decimalFormatter.format(n);
  return symbol ? `${symbol}${scaled}` : scaled;
}

/**
 * Compact percentage from a raw percentage value (e.g. 12.4 -> "12.4%").
 * Distinct from fmtPercent which expects a 0..1 ratio.
 */
export function fmtPercentValue(v: unknown, maxFraction = 1): string {
  const n = safeNumber(v);
  if (n === null) return "—";
  return `${n.toFixed(maxFraction)}%`;
}

/** Signed change: adds an explicit `+` for positive numbers. */
export function fmtSigned(v: unknown, suffix = ""): string {
  const n = safeNumber(v);
  if (n === null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${decimalFormatter.format(n)}${suffix}`;
}

/** Signed percent-value (e.g. 12.4 -> "+12.4%"). */
export function fmtSignedPercent(v: unknown, maxFraction = 1): string {
  const n = safeNumber(v);
  if (n === null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(maxFraction)}%`;
}

export function fmtBytes(bytes: unknown): string {
  const n = safeNumber(bytes);
  if (n === null || n < 0) return "—";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = n;
  let idx = 0;
  while (value >= 1024 && idx < units.length - 1) {
    value /= 1024;
    idx += 1;
  }
  return `${decimalFormatter.format(value)} ${units[idx]}`;
}

export function fmtDate(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("en-US", {
    year: "numeric",
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function fmtRelative(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  const seconds = (Date.now() - d.getTime()) / 1000;
  const buckets: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
    ["second", 1],
  ];
  const rtf = new Intl.RelativeTimeFormat("en", { numeric: "auto" });
  for (const [unit, secs] of buckets) {
    if (Math.abs(seconds) >= secs || unit === "second") {
      const value = -Math.round(seconds / secs);
      return rtf.format(value, unit);
    }
  }
  return "just now";
}
