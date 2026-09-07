"""Period-over-period trend analysis.

Given a DataFrame with a date column and one or more matched financial
columns, compute simple growth rates for a small set of flow metrics
(revenue / net profit / operating expenses / etc.).

Purely descriptive \u2014 the analyzer never extrapolates. Growth rates come
back as ``TrendResult`` with a ``direction`` label so the insight engine
can turn them into observations.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd

from app.analysis.semantic_matcher import match_columns
from app.analysis.types import MetricId


@dataclass
class TrendResult:
    metric_id: MetricId
    column: str
    growth_rate: Optional[float]   # simple last-vs-first percentage
    avg_period_growth: Optional[float]  # mean of period-over-period pct changes
    direction: str  # "improving" | "declining" | "stable" | "insufficient_data"
    period_series: Dict[str, float]   # {"2024-01": 100, ...}
    period_count: int


_TARGETS = {
    MetricId.REVENUE,
    MetricId.NET_PROFIT,
    MetricId.OPERATING_PROFIT,
    MetricId.OPERATING_EXPENSES,
    MetricId.EXPENSES_TOTAL,
    MetricId.EBITDA,
    MetricId.EBIT,
    MetricId.FREE_CASH_FLOW,
    MetricId.NET_INTEREST_INCOME,
    MetricId.DEPOSITS,
    MetricId.LOANS,
    MetricId.CUSTOMERS,
}


def analyze_trends(
    df: pd.DataFrame,
    date_column: Optional[str],
    numerical_column_names: List[str],
) -> Dict[MetricId, TrendResult]:
    """Compute trends for every matched target metric.

    Returns ``{}`` if the DataFrame doesn't have a usable date column or
    fewer than two rows.
    """
    if df is None or df.empty or not date_column or date_column not in df.columns:
        return {}
    if len(df) < 2:
        return {}

    working = df.copy()
    working[date_column] = pd.to_datetime(working[date_column], errors="coerce")
    working = working.dropna(subset=[date_column]).sort_values(date_column)
    if len(working) < 2:
        return {}

    matches = match_columns(numerical_column_names)
    picks = {mid: matches[mid][0] for mid in matches if matches[mid]}

    out: Dict[MetricId, TrendResult] = {}
    for mid, match in picks.items():
        if mid not in _TARGETS:
            continue
        if match.column not in working.columns:
            continue
        series = pd.to_numeric(working[match.column], errors="coerce")
        combined = pd.concat([working[date_column], series], axis=1).dropna()
        if len(combined) < 2:
            continue

        combined.columns = ["_date", "_value"]
        values = combined["_value"].to_numpy(dtype=float)
        first, last = float(values[0]), float(values[-1])

        overall_growth = None
        if first != 0:
            overall_growth = (last - first) / abs(first) * 100.0

        pct = combined["_value"].pct_change().dropna()
        avg_period = float(pct.mean() * 100.0) if not pct.empty else None

        period_series = _to_period_series(combined)
        direction = _classify_direction(overall_growth)

        out[mid] = TrendResult(
            metric_id=mid,
            column=match.column,
            growth_rate=overall_growth,
            avg_period_growth=avg_period,
            direction=direction,
            period_series=period_series,
            period_count=int(len(combined)),
        )
    return out


def _to_period_series(frame: pd.DataFrame) -> Dict[str, float]:
    result: Dict[str, float] = {}
    for ts, value in zip(frame["_date"].tolist(), frame["_value"].tolist()):
        try:
            key = pd.Timestamp(ts).strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            key = str(ts)
        try:
            result[key] = float(value)
        except (TypeError, ValueError):
            continue
    return result


def _classify_direction(growth: Optional[float]) -> str:
    if growth is None:
        return "insufficient_data"
    if growth > 2.5:
        return "improving"
    if growth < -2.5:
        return "declining"
    return "stable"
