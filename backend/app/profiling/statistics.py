"""Per-column statistics.

Every helper returns a plain JSON-safe dict — no numpy scalars, no
Timestamps, no NaN. That way the result can go straight into the API
response and into Supabase JSONB without a second serialization pass.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
from pandas.api import types as ptypes


_PERCENTILES = [0.10, 0.25, 0.50, 0.75, 0.90]


# ---------------------------------------------------------------------------
# Public entrypoints — one per column class
# ---------------------------------------------------------------------------
def numerical_stats(series: pd.Series) -> Dict[str, Any]:
    """Descriptive statistics for a numerical column."""
    non_null = pd.to_numeric(series, errors="coerce").dropna()
    if non_null.empty:
        return {"count": 0}

    q10, q25, q50, q75, q90 = non_null.quantile(_PERCENTILES).tolist()
    iqr = q75 - q25

    return {
        "count": int(non_null.count()),
        "mean": _safe_float(non_null.mean()),
        "median": _safe_float(q50),
        "std": _safe_float(non_null.std(ddof=1) if non_null.count() > 1 else 0.0),
        "min": _safe_float(non_null.min()),
        "max": _safe_float(non_null.max()),
        "q1": _safe_float(q25),
        "q3": _safe_float(q75),
        "iqr": _safe_float(iqr),
        "percentiles": {
            "p10": _safe_float(q10),
            "p25": _safe_float(q25),
            "p50": _safe_float(q50),
            "p75": _safe_float(q75),
            "p90": _safe_float(q90),
        },
        "sum": _safe_float(non_null.sum()),
    }


def categorical_stats(series: pd.Series) -> Dict[str, Any]:
    non_null = series.dropna()
    if non_null.empty:
        return {"count": 0, "unique_count": 0}
    counts = non_null.value_counts()
    mode_value = counts.index[0]
    return {
        "count": int(non_null.count()),
        "unique_count": int(non_null.nunique()),
        "mode": _json_safe(mode_value),
        "mode_frequency": int(counts.iloc[0]),
        "mode_ratio": _safe_float(float(counts.iloc[0]) / float(non_null.count())),
    }


def text_stats(series: pd.Series) -> Dict[str, Any]:
    non_null = series.dropna()
    if non_null.empty:
        return {"count": 0, "unique_count": 0}
    lengths = non_null.astype(str).map(len)
    return {
        "count": int(non_null.count()),
        "unique_count": int(non_null.nunique()),
        "avg_length": _safe_float(float(lengths.mean())),
        "min_length": int(lengths.min()),
        "max_length": int(lengths.max()),
    }


def datetime_stats(series: pd.Series) -> Dict[str, Any]:
    """Min / max / range for date or datetime columns."""
    parsed = _to_datetime(series)
    non_null = parsed.dropna()
    if non_null.empty:
        return {"count": 0}
    min_dt = non_null.min()
    max_dt = non_null.max()
    range_days = int((max_dt - min_dt).days) if pd.notna(min_dt) and pd.notna(max_dt) else 0

    return {
        "count": int(non_null.count()),
        "unique_count": int(non_null.nunique()),
        "min": min_dt.isoformat() if pd.notna(min_dt) else None,
        "max": max_dt.isoformat() if pd.notna(max_dt) else None,
        "range_days": range_days,
    }


def boolean_stats(series: pd.Series) -> Dict[str, Any]:
    non_null = series.dropna()
    if non_null.empty:
        return {"count": 0, "true_count": 0, "false_count": 0}
    coerced = _coerce_bool(non_null)
    true_count = int(coerced.sum())
    false_count = int((~coerced).sum())
    return {
        "count": int(non_null.count()),
        "true_count": true_count,
        "false_count": false_count,
        "true_ratio": _safe_float(true_count / non_null.count()),
    }


def id_stats(series: pd.Series) -> Dict[str, Any]:
    """Uniqueness-focused statistics for an identifier column."""
    non_null = series.dropna()
    if non_null.empty:
        return {"count": 0, "unique_count": 0, "duplicate_count": 0, "uniqueness_ratio": 0.0}
    unique = int(non_null.nunique())
    total = int(non_null.count())
    return {
        "count": total,
        "unique_count": unique,
        "duplicate_count": total - unique,
        "uniqueness_ratio": _safe_float(unique / total),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _to_datetime(series: pd.Series) -> pd.Series:
    if ptypes.is_datetime64_any_dtype(series):
        return series
    try:
        return pd.to_datetime(series, errors="coerce", utc=False, format="mixed")
    except Exception:  # noqa: BLE001
        return pd.Series(pd.NaT, index=series.index)


def _coerce_bool(series: pd.Series) -> pd.Series:
    if ptypes.is_bool_dtype(series):
        return series
    truthy = {"true", "t", "yes", "y", "1"}
    return series.astype(str).str.strip().str.lower().isin(truthy)


def _safe_float(v: Any) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 6)


def _json_safe(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (str, bool, int)):
        return v
    if isinstance(v, float):
        return _safe_float(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return _safe_float(float(v))
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return str(v)
