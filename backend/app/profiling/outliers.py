"""IQR-based outlier detection for numerical columns.

Phase 2 only *reports* potential outliers. It never removes or transforms
anything — that's Phase 3's job. The result explicitly labels findings as
"potential outliers" via the `method: "iqr"` marker.
"""

from __future__ import annotations

import math
from typing import Any, Dict

import pandas as pd


IQR_MULTIPLIER = 1.5


def detect_outliers(series: pd.Series) -> Dict[str, Any]:
    """Return a small dict summarising potential outliers, or an empty dict
    if the column has too few values for IQR to be meaningful.
    """
    non_null = pd.to_numeric(series, errors="coerce").dropna()
    n = int(non_null.count())
    if n < 4:
        return {
            "method": "iqr",
            "count": 0,
            "ratio": 0.0,
            "lower_bound": None,
            "upper_bound": None,
            "reason": "insufficient_data",
        }

    q1 = float(non_null.quantile(0.25))
    q3 = float(non_null.quantile(0.75))
    iqr = q3 - q1

    # Constant column — no meaningful spread.
    if iqr == 0:
        return {
            "method": "iqr",
            "count": 0,
            "ratio": 0.0,
            "lower_bound": q1,
            "upper_bound": q3,
            "reason": "zero_iqr",
        }

    lower = q1 - IQR_MULTIPLIER * iqr
    upper = q3 + IQR_MULTIPLIER * iqr

    mask = (non_null < lower) | (non_null > upper)
    count = int(mask.sum())
    ratio = count / n

    return {
        "method": "iqr",
        "count": count,
        "ratio": round(ratio, 6),
        "lower_bound": _round(lower),
        "upper_bound": _round(upper),
        "q1": _round(q1),
        "q3": _round(q3),
        "iqr": _round(iqr),
    }


def _round(v: float) -> float:
    if math.isnan(v) or math.isinf(v):
        return 0.0
    return round(v, 6)
