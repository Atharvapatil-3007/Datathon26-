/**
 * Centralized brand identity for the platform.
 *
 * Every place that renders the product name, tagline or description should
 * import from here rather than hard-coding strings. This lets us rename the
 * product later by editing a single file.
 */

export const BRAND = {
  /** Display name shown across the UI. */
  name: "FinSight",
  /** Short one-line tagline used under the logo. */
  tagline: "Financial Intelligence Platform",
  /** Longer description for empty states and landing surfaces. */
  description:
    "Enterprise-grade financial intelligence — ingest, profile, benchmark and decide with confidence.",
  /** Domain / brand identifier used for meta tags. */
  domain: "finsight.app",
  /** Copyright / footer line. */
  footer: "Financial Intelligence · Ingest · Profile · Analyze · Decide",
} as const;

/** Value-only shortcut for React contexts. */
export type Brand = typeof BRAND;
