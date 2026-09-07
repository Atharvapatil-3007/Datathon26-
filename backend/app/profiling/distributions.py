"""Distribution + top-value helpers.

Two shapes:

* Numerical distribution — fixed number of histogram bins with counts.
* Categorical / boolean / low-card distribution — top-N values with count
  and percentage.

Result dicts are JSON-safe and small enough to persist inside a JSONB
column without bloat.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List

import numpy as np
import pandas as pd


DEFAULT_HISTOGRAM_BINS = 20
DEFAULT_TOP_K = 10


# ---------------------------------------------------------------------------
# Numerical
# ---------------------------------------------------------------------------
def numerical_distribution(series: pd.Series, bins: int = DEFAULT_HISTOGRAM_BINS) -> Dict[str, Any]:
    non_null = pd.to_numeric(series, errors="coerce").dropna()
    if non_null.empty:
        return {"bins": [], "counts": [], "shape": "empty"}

    values = non_null.to_numpy(dtype=float, copy=False)
    lo = float(values.min())
    hi = float(values.max())

    # All values equal — one degenerate bin so the UI still renders something.
    if math.isclose(lo, hi):
        return {
            "bins": [lo, hi],
            "counts": [int(len(values))],
            "min": lo,
            "max": hi,
            "shape": "degenerate",
        }

    counts, edges = np.histogram(values, bins=bins)
    return {
        "bins": [float(e) for e in edges.tolist()],
        "counts": [int(c) for c in counts.tolist()],
        "min": lo,
        "max": hi,
        "shape": _describe_shape(values),
    }


def _describe_shape(values: np.ndarray) -> str:
    """Very coarse label describing the distribution."""
    try:
        mean = float(np.mean(values))
        median = float(np.median(values))
        std = float(np.std(values))
        if std == 0.0:
            return "constant"
        diff = (mean - median) / std
        if diff > 0.3:
            return "right_skewed"
        if diff < -0.3:
            return "left_skewed"
        return "approximately_symmetric"
    except Exception:  # noqa: BLE001
        return "unknown"


# ---------------------------------------------------------------------------
# Categorical / boolean
# ---------------------------------------------------------------------------
def top_values(series: pd.Series, k: int = DEFAULT_TOP_K) -> List[Dict[str, Any]]:
    non_null = series.dropna()
    if non_null.empty:
        return []
    counts = non_null.value_counts().head(k)
    total = float(len(non_null))
    return [
        {
            "value": _json_safe(v),
            "count": int(c),
            "ratio": round(float(c) / total, 6) if total else 0.0,
        }
        for v, c in counts.items()
    ]


def categorical_distribution(series: pd.Series, k: int = DEFAULT_TOP_K) -> Dict[str, Any]:
    non_null = series.dropna()
    if non_null.empty:
        return {"top_values": [], "other_count": 0, "unique_count": 0}
    counts = non_null.value_counts()
    top = counts.head(k)
    other_count = int(counts.iloc[k:].sum()) if len(counts) > k else 0
    total = float(len(non_null))
    return {
        "top_values": [
            {
                "value": _json_safe(v),
                "count": int(c),
                "ratio": round(float(c) / total, 6) if total else 0.0,
            }
            for v, c in top.items()
        ],
        "other_count": other_count,
        "unique_count": int(counts.shape[0]),
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _json_safe(v: Any) -> Any:
    if v is None:
        return None
    if isinstance(v, (str, bool, int)):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return str(v)
