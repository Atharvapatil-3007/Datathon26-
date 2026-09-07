"""Metric extractor.

Takes:
  * the persisted Phase 2 profile (``datasets.profile`` JSONB), and
  * optionally the raw DataFrame (loaded on demand from Supabase Storage)

and produces:
  * a list of ``LabeledMetric`` \u2014 the canonical financial metrics we
    could identify in the dataset
  * a ``value_map`` \u2014 ``metric_id -> value`` for use by the ratio engine

Aggregation rules (only invoked for numerical columns):

* CURRENCY and COUNT metrics: use ``sum`` when the dataset looks transactional
  (many rows, no explicit period column) and ``mean``-style aggregation on
  point-in-time balance sheet items when a date column exists.
* PERCENT metrics stored raw as columns: use ``mean`` (percentages should
  never be summed).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import math
import pandas as pd

from app.analysis.metric_registry import METRIC_REGISTRY, base_metrics, get_definition
from app.analysis.semantic_matcher import ColumnMatch, match_columns, pick_best
from app.analysis.types import (
    LabeledMetric,
    MetricDirection,
    MetricId,
    MetricStatus,
    MetricUnit,
)


# ---------------------------------------------------------------------------
# Extractor result
# ---------------------------------------------------------------------------
@dataclass
class ExtractionResult:
    metrics: List[LabeledMetric] = field(default_factory=list)
    value_map: Dict[MetricId, float] = field(default_factory=dict)
    match_summary: List[Dict[str, Any]] = field(default_factory=list)
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    detected_shape: str = "unknown"  # "transactional" | "periodic" | "single_period" | "unknown"
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def extract_metrics(
    profile: Dict[str, Any],
    df: Optional[pd.DataFrame] = None,
) -> ExtractionResult:
    """Turn a Phase 2 profile into labeled canonical metrics.

    Parameters
    ----------
    profile : dict
        The persisted profile payload (from ``datasets.profile`` JSONB or the
        upload response). Must contain ``column_profiles``.
    df : pandas.DataFrame, optional
        The raw dataframe. When supplied, enables period-based aggregation
        (latest value per periodic column) which is critical for point-in-time
        balance-sheet metrics.
    """
    result = ExtractionResult()

    columns = _column_profiles(profile)
    if not columns:
        result.warnings.append("Profile contains no column profiles")
        return result

    # Group columns by class for easier access.
    numerical_cols = [c for c in columns if c["column_class"] == "numerical"]
    count_cols = [c for c in columns if c["column_class"] == "categorical"]  # for fallbacks
    date_cols = [
        c for c in columns if c["column_class"] in ("date", "datetime")
    ]

    # Detect dataset shape (helps decide aggregation).
    row_count = _overview_int(profile, "rows")
    result.detected_shape = _detect_shape(row_count, date_cols)

    # Extract period range if present.
    if date_cols:
        stats = date_cols[0].get("statistics", {}) or {}
        result.period_start = stats.get("min")
        result.period_end = stats.get("max")

    # Match column names to canonical metrics.
    match_groups = match_columns([c["name"] for c in numerical_cols])
    result.match_summary = _matched_summary(match_groups)
    picks = pick_best(match_groups)

    # Build LabeledMetric for every metric that was matched.
    for metric_id, best_match in picks.items():
        column_profile = _find_column(numerical_cols, best_match.column)
        if column_profile is None:
            continue
        metric = _build_metric_from_column(
            metric_id=metric_id,
            column_profile=column_profile,
            match=best_match,
            df=df,
            date_columns=date_cols,
            shape=result.detected_shape,
        )
        result.metrics.append(metric)
        if metric.value is not None and metric.status != MetricStatus.UNAVAILABLE:
            result.value_map[metric_id] = float(metric.value)

    # Sort by category first (income statement -> balance sheet -> banking -> ratios)
    # so the UI shows the most-important-first.
    result.metrics.sort(key=lambda m: (get_definition(m.metric_id).category, m.metric_id.value))
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _column_profiles(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    cols = profile.get("column_profiles") or []
    return [c for c in cols if isinstance(c, dict)]


def _overview_int(profile: Dict[str, Any], key: str) -> int:
    overview = profile.get("overview") or {}
    try:
        return int(overview.get(key) or 0)
    except (TypeError, ValueError):
        return 0


def _detect_shape(row_count: int, date_columns: List[Dict[str, Any]]) -> str:
    """Rough classification used to pick the aggregation strategy."""
    if row_count == 0:
        return "unknown"
    if row_count == 1:
        return "single_period"
    if date_columns and row_count <= 60:
        return "periodic"          # e.g. quarterly / monthly statements
    return "transactional"


def _find_column(cols: List[Dict[str, Any]], name: str) -> Optional[Dict[str, Any]]:
    for c in cols:
        if c.get("name") == name:
            return c
    return None


def _matched_summary(groups: Dict[MetricId, List[ColumnMatch]]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for mid, matches in groups.items():
        out.append(
            {
                "metric_id": mid.value,
                "picked_column": matches[0].column if matches else None,
                "confidence": matches[0].confidence if matches else 0.0,
                "other_candidates": [m.column for m in matches[1:]],
            }
        )
    return out


# ---------------------------------------------------------------------------
# Value aggregation
# ---------------------------------------------------------------------------
_INCOME_METRICS = {
    MetricId.REVENUE,
    MetricId.COGS,
    MetricId.OPERATING_EXPENSES,
    MetricId.EXPENSES_TOTAL,
    MetricId.INTEREST_EXPENSE,
    MetricId.INTEREST_INCOME,
    MetricId.TAX,
    MetricId.GROSS_PROFIT,
    MetricId.OPERATING_PROFIT,
    MetricId.EBITDA,
    MetricId.EBIT,
    MetricId.NET_PROFIT,
    MetricId.NET_INTEREST_INCOME,
    MetricId.NON_INTEREST_INCOME,
    MetricId.PROVISIONS,
    MetricId.CASH_FLOW_OPERATIONS,
    MetricId.FREE_CASH_FLOW,
    MetricId.CAPEX,
}

_POINT_IN_TIME_METRICS = {
    MetricId.ASSETS,
    MetricId.CURRENT_ASSETS,
    MetricId.NON_CURRENT_ASSETS,
    MetricId.LIABILITIES,
    MetricId.CURRENT_LIABILITIES,
    MetricId.EQUITY,
    MetricId.DEBT,
    MetricId.CASH,
    MetricId.INVENTORY,
    MetricId.RECEIVABLES,
    MetricId.WORKING_CAPITAL,
    MetricId.DEPOSITS,
    MetricId.CASA,
    MetricId.LOANS,
    MetricId.GROSS_NPA,
    MetricId.NET_NPA,
    MetricId.CUSTOMERS,
    MetricId.EMPLOYEES,
}


def _build_metric_from_column(
    *,
    metric_id: MetricId,
    column_profile: Dict[str, Any],
    match: ColumnMatch,
    df: Optional[pd.DataFrame],
    date_columns: List[Dict[str, Any]],
    shape: str,
) -> LabeledMetric:
    definition = get_definition(metric_id)
    stats = column_profile.get("statistics") or {}
    notes: List[str] = []

    # ---- Choose value based on unit + shape ----
    value: Optional[float] = None
    status = MetricStatus.REPORTED

    if definition.unit == MetricUnit.PERCENT:
        # Percentages stored as a column: use mean, not sum.
        value = _finite(stats.get("mean"))
        if value is not None:
            notes.append("Aggregated as mean of column values (percentage metric).")

    elif metric_id in _POINT_IN_TIME_METRICS and shape == "periodic":
        # Balance sheet / stock metric with periodic data: pick the latest value.
        # Preferred source order:
        #   1. `statistics.latest_value` \u2014 written by Phase 2 when a date
        #      column was detected (F-05, exact).
        #   2. live DataFrame lookup via _extract_latest_value.
        #   3. `max` fallback (marked ESTIMATED).
        profile_latest = _finite(stats.get("latest_value"))
        if profile_latest is not None:
            value = profile_latest
            notes.append("Latest value across periods (from Phase 2 profile).")
        else:
            latest = _extract_latest_value(df, column_profile["name"], date_columns)
            if latest is not None:
                value = latest
                notes.append("Latest value across periods.")
            else:
                value = _finite(stats.get("max"))
                status = MetricStatus.ESTIMATED
                notes.append(
                    "Latest-by-date unavailable; used max as an approximation."
                )

    elif metric_id in _INCOME_METRICS and shape == "periodic":
        # Flow metric across multiple periods: sum is the natural roll-up.
        value = _finite(stats.get("sum"))
        notes.append("Summed across periods.")

    elif shape == "single_period":
        # One row: the single value is the metric.
        value = _finite(stats.get("mean") or stats.get("sum"))
        notes.append("Single-period value.")

    else:  # transactional or unknown
        # Sum for flow (revenue = sum of all transactions), mean for percent.
        value = _finite(stats.get("sum"))
        if value is None:
            value = _finite(stats.get("mean"))
        notes.append("Aggregated across all rows.")

    if value is None:
        status = MetricStatus.UNAVAILABLE

    return LabeledMetric(
        metric_id=metric_id,
        display_name=definition.display_name,
        value=value,
        unit=definition.unit,
        status=status,
        direction=definition.direction,
        source_columns=[match.column],
        confidence=match.confidence,
        notes=notes,
    )


def _extract_latest_value(
    df: Optional[pd.DataFrame],
    column_name: str,
    date_columns: List[Dict[str, Any]],
) -> Optional[float]:
    """Return the value of ``column_name`` in the most recent row."""
    if df is None or df.empty or not date_columns:
        return None
    if column_name not in df.columns:
        return None
    date_col = date_columns[0]["name"]
    if date_col not in df.columns:
        return None
    try:
        dates = pd.to_datetime(df[date_col], errors="coerce")
        latest_idx = dates.idxmax()
        if pd.isna(latest_idx):
            return None
        return _finite(df.loc[latest_idx, column_name])
    except Exception:  # noqa: BLE001
        return None


def _finite(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return f
