/**
 * TypeScript mirror of the backend response contracts.
 *
 * These types must stay in sync with:
 *   backend/app/ingestion/dataset.py
 *   backend/app/profiling/types.py
 *   backend/app/api/ingestion.py (IngestionResponse, DatasetSummary, ProfileResponse)
 *
 * Every field marked optional here is nullable in the backend either by
 * design (SectionStatus.UNAVAILABLE) or because it depends on the dataset
 * type (e.g. no `outliers` on a text column).
 */

// ---------------------------------------------------------------------------
// Enums (string unions match the Python enum `.value`)
// ---------------------------------------------------------------------------
export type ColumnClass =
  | "numerical"
  | "categorical"
  | "text"
  | "date"
  | "datetime"
  | "id"
  | "boolean"
  | "unknown";

export type InferredType =
  | "integer"
  | "float"
  | "boolean"
  | "datetime"
  | "date"
  | "string"
  | "categorical"
  | "identifier"
  | "text"
  | "unknown";

export type CardinalityClass = "low" | "medium" | "high" | "unique";

export type QualityGrade = "A" | "B" | "C" | "D" | "F";

export type SectionStatus = "ok" | "unavailable" | "skipped";

export type SourceType = "file" | "sql_database" | "zip_archive";

export type DatasetStatus =
  | "uploaded"
  | "detecting"
  | "processing"
  | "validated"
  | "failed";

// ---------------------------------------------------------------------------
// Profiling primitives
// ---------------------------------------------------------------------------
export interface HistogramDistribution {
  bins: number[];
  counts: number[];
  min?: number;
  max?: number;
  shape?: string;
}

export interface CategoricalDistribution {
  top_values: TopValue[];
  other_count: number;
  unique_count: number;
}

export interface TopValue {
  value: string | number | boolean | null;
  count: number;
  ratio: number;
}

export interface NumericalStatistics {
  count: number;
  mean?: number;
  median?: number;
  std?: number;
  min?: number;
  max?: number;
  q1?: number;
  q3?: number;
  iqr?: number;
  percentiles?: {
    p10?: number;
    p25?: number;
    p50?: number;
    p75?: number;
    p90?: number;
  };
  sum?: number;
}

export interface CategoricalStatistics {
  count: number;
  unique_count: number;
  mode?: string | number | boolean | null;
  mode_frequency?: number;
  mode_ratio?: number;
}

export interface TextStatistics {
  count: number;
  unique_count: number;
  avg_length?: number;
  min_length?: number;
  max_length?: number;
}

export interface DatetimeStatistics {
  count: number;
  unique_count?: number;
  min?: string;
  max?: string;
  range_days?: number;
}

export interface BooleanStatistics {
  count: number;
  true_count: number;
  false_count: number;
  true_ratio?: number;
}

export interface IdStatistics {
  count: number;
  unique_count: number;
  duplicate_count: number;
  uniqueness_ratio: number;
}

export interface OutlierInfo {
  method: string;
  count: number;
  ratio: number;
  lower_bound?: number | null;
  upper_bound?: number | null;
  q1?: number;
  q3?: number;
  iqr?: number;
  reason?: string;
}

// Per-column statistics is a union of type-specific dicts; the frontend
// safely reads whichever fields are present.
export type ColumnStatistics =
  | NumericalStatistics
  | CategoricalStatistics
  | TextStatistics
  | DatetimeStatistics
  | BooleanStatistics
  | IdStatistics
  | Record<string, unknown>;

export type ColumnDistribution =
  | HistogramDistribution
  | CategoricalDistribution
  | Record<string, unknown>;

// ---------------------------------------------------------------------------
// Column profile
// ---------------------------------------------------------------------------
export interface ColumnProfile {
  name: string;
  dtype: string;
  column_class: ColumnClass;
  inferred_type: InferredType;
  total: number;
  non_null: number;
  missing_count: number;
  missing_ratio: number;
  unique_count: number;
  unique_ratio: number;
  cardinality_class: CardinalityClass;
  sample_values: Array<string | number | boolean | null>;
  most_frequent_value: string | number | boolean | null;
  most_frequent_count: number;
  statistics: ColumnStatistics;
  distribution: ColumnDistribution;
  outliers: OutlierInfo | null;
  top_values: TopValue[];
  quality_score: number;
}

// ---------------------------------------------------------------------------
// Dataset-level sections
// ---------------------------------------------------------------------------
export interface DatasetOverview {
  rows: number;
  columns: number;
  size_bytes: number | null;
  numerical_columns: number;
  categorical_columns: number;
  text_columns: number;
  date_columns: number;
  datetime_columns: number;
  id_columns: number;
  boolean_columns: number;
  unknown_columns: number;
}

export interface MissingSummary {
  status: SectionStatus;
  reason: string | null;
  total_missing: number;
  total_cells: number;
  missing_ratio: number;
  columns_with_missing: number;
  per_column: Array<{
    column: string;
    missing_count: number;
    missing_ratio: number;
  }>;
}

export interface DuplicateSummary {
  status: SectionStatus;
  reason: string | null;
  duplicate_rows: number;
  duplicate_ratio: number;
  unique_rows: number;
  duplicate_ids: Array<{
    column: string;
    duplicate_value_count: number;
    duplicate_row_count: number;
    examples: Array<{ value: string | number | boolean | null; count: number }>;
  }>;
}

export interface CardinalityBreakdown {
  status: SectionStatus;
  reason: string | null;
  low: string[];
  medium: string[];
  high: string[];
  unique: string[];
}

export interface CorrelationPair {
  column_a: string;
  column_b: string;
  coefficient: number;
  strength: "very_strong" | "strong" | "moderate" | "weak" | "very_weak";
  direction: "positive" | "negative";
}

export interface CorrelationSummary {
  status: SectionStatus;
  reason: string | null;
  columns: string[];
  matrix: number[][];
  strong_positive: CorrelationPair[];
  strong_negative: CorrelationPair[];
  top_pairs: CorrelationPair[];
}

export interface QualityScore {
  overall_score: number;
  grade: QualityGrade;
  dimensions: {
    completeness?: number;
    uniqueness?: number;
    validity?: number;
    consistency?: number;
  };
  notes: string[];
}

// ---------------------------------------------------------------------------
// Top-level profiling result (payload of `profile` field)
// ---------------------------------------------------------------------------
export interface ProfilingResult {
  dataset_id: string;
  overview: DatasetOverview;
  column_profiles: ColumnProfile[];
  missing: MissingSummary;
  duplicates: DuplicateSummary;
  cardinality: CardinalityBreakdown;
  correlations: CorrelationSummary;
  quality: QualityScore;
  summary_text: string;
  warnings: string[];
  metadata: {
    profiling_time_ms: number;
    version: string;
    generated_at: string;
  };
}

// ---------------------------------------------------------------------------
// API responses (map directly to Pydantic models in the backend)
// ---------------------------------------------------------------------------
export interface IngestionResponse {
  success: boolean;
  dataset_id: string;
  filename: string;
  format: string;
  source_type: SourceType;
  rows: number;
  columns: number;
  column_names: string[];
  schema: {
    columns: Array<Record<string, unknown>>;
    column_names: string[];
  } | null;
  metadata: Record<string, unknown>;
  warnings: string[];
  errors: string[];
  status: DatasetStatus;
  storage_path: string | null;
  duration_ms: number;
  detection: {
    format: string;
    mime_type: string;
    size_bytes: number;
    loader: string;
    extension: string;
    reason: string;
  } | null;
  profile: ProfilingResult | null;
}

export interface DatasetSummary {
  id: string;
  filename: string;
  original_filename: string;
  source_type: string;
  file_format: string;
  mime_type: string;
  file_size: number;
  storage_path: string | null;
  row_count: number | null;
  column_count: number | null;
  status: DatasetStatus;
  schema: Record<string, unknown> | null;
  metadata: Record<string, unknown> | null;
  warnings: string[];
  errors: string[];
  created_at: string;
  updated_at: string;
  user_id?: string | null;
  profile?: ProfilingResult | null;
  profiled_at?: string | null;
}

export interface ProfileResponse {
  dataset_id: string;
  profile: ProfilingResult | null;
  profiled_at: string | null;
}

// ---------------------------------------------------------------------------
// Error envelope
// ---------------------------------------------------------------------------
export interface ApiErrorPayload {
  success: false;
  error: {
    code: string;
    message: string;
    details?: unknown;
  };
}

// ---------------------------------------------------------------------------
// Health
// ---------------------------------------------------------------------------
export interface HealthResponse {
  status: string;
  supabase_configured: boolean;
  local_fallback: boolean;
}


// ===========================================================================
// Phase 3 - Financial Intelligence
// ===========================================================================
export type AnalysisMode =
  | "self_analysis"
  | "merger_partnership_analysis"
  | "competitor_market_benchmark";

export type MetricStatus =
  | "reported"
  | "calculated"
  | "estimated"
  | "scenario"
  | "unavailable";

export type MetricUnit = "currency" | "percent" | "ratio" | "count" | "days" | "unknown";

export type MetricDirection = "higher_better" | "lower_better" | "neutral";

export type AnalysisPriority = "high" | "medium" | "low";

export type InsightKind = "observation" | "analysis" | "recommendation";

export type ComparisonStatus = "ahead" | "behind" | "level" | "na";

export interface LabeledMetric {
  metric_id: string;
  display_name: string;
  value: number | null;
  unit: MetricUnit;
  status: MetricStatus;
  direction: MetricDirection;
  source_columns: string[];
  confidence: number;
  period_series: Record<string, number> | null;
  notes: string[];
}

export interface EntitySnapshot {
  entity_id: string;
  display_name: string;
  metrics: LabeledMetric[];
  period_start: string | null;
  period_end: string | null;
  unit_hint?: string | null;
  entity_type?: string | null;
  notes: string[];
}

export interface AnalysisHealthScore {
  overall_score: number;
  grade: string;
  dimensions: Record<string, number>;
  notes: string[];
}

export interface ComparisonRow {
  metric_id: string;
  display_name: string;
  unit: MetricUnit;
  direction: MetricDirection;
  primary_value: number | null;
  secondary_value: number | null;
  market_value: number | null;
  absolute_gap: number | null;
  percentage_gap: number | null;
  status: ComparisonStatus;
}

export interface GapItem {
  metric_id: string;
  display_name: string;
  unit: MetricUnit;
  current_value: number | null;
  benchmark_value: number | null;
  absolute_gap: number | null;
  percentage_gap: number | null;
  near_term_target: number | null;
  long_term_target: number | null;
  priority: AnalysisPriority;
  importance: string;
  required_improvement: string | null;
  direction: MetricDirection;
}

export interface CombinedScenario {
  label: string;
  metrics: LabeledMetric[];
  caveats: string[];
}

export interface SynergyItem {
  kind: string;
  title: string;
  description: string;
  magnitude_hint: string | null;
  supporting_metrics: string[];
}

export interface RiskItem {
  severity: AnalysisPriority;
  title: string;
  description: string;
  supporting_metrics: string[];
}

export interface AnalysisInsight {
  kind: InsightKind;
  text: string;
  related_metrics: string[];
  priority: AnalysisPriority;
}

export interface AnalysisConfidence {
  overall: number;
  metric_coverage: number;
  period_coverage: number | null;
  notes: string[];
}

export interface AnalysisResult {
  mode: AnalysisMode;
  primary_entity: EntitySnapshot | null;
  secondary_entity: EntitySnapshot | null;
  market_entity: EntitySnapshot | null;
  financial_health: AnalysisHealthScore | null;
  combined_scenario: CombinedScenario | null;
  metrics: LabeledMetric[];
  ratios: LabeledMetric[];
  comparisons: ComparisonRow[];
  gaps: GapItem[];
  synergies: SynergyItem[];
  risks: RiskItem[];
  strengths: string[];
  weaknesses: string[];
  opportunities: string[];
  insights: AnalysisInsight[];
  recommendations: AnalysisInsight[];
  summary_text: string;
  warnings: string[];
  confidence: AnalysisConfidence | null;
  metadata: {
    version: string;
    generated_at: string;
  };
}

export interface AnalysisOption {
  mode: AnalysisMode;
  title: string;
  description: string;
  requires: string[];
}

export interface AnalysisOptionsResponse {
  modes: AnalysisOption[];
}


