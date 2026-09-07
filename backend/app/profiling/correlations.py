"""Correlation analysis (Pearson) for numerical columns only.

Skips identifiers, booleans, categoricals, dates — computing Pearson on
those produces meaningless numbers and confuses the dashboard.

The matrix is returned as a plain 2-D list in the same order as `columns`
so the frontend can render a heatmap without needing to reshape.
"""

from __future__ import annotations

import math
from typing import List, Optional

import pandas as pd

from app.profiling.types import (
    ColumnClass,
    ColumnProfile,
    CorrelationPair,
    CorrelationSummary,
    SectionStatus,
)


# Strength buckets (using |coefficient|)
_STRENGTHS = [
    (0.80, "very_strong"),
    (0.60, "strong"),
    (0.40, "moderate"),
    (0.20, "weak"),
    (0.00, "very_weak"),
]

_STRONG_THRESHOLD = 0.60
_TOP_PAIRS_LIMIT = 10
_MIN_NON_NULL = 10  # Pearson on <10 points is noise


def analyze_correlations(
    df: pd.DataFrame,
    column_profiles: List[ColumnProfile],
) -> CorrelationSummary:
    """Compute Pearson correlations between eligible numerical columns."""
    numeric_names = _select_numeric_columns(column_profiles)

    if len(numeric_names) < 2:
        return CorrelationSummary(
            status=SectionStatus.UNAVAILABLE,
            reason="Need at least two numerical columns for correlation",
        )

    # Coerce (safely) and drop constant / near-empty columns.
    frame = _prepare_numeric_frame(df[numeric_names])
    usable = list(frame.columns)
    if len(usable) < 2:
        return CorrelationSummary(
            status=SectionStatus.UNAVAILABLE,
            reason="Numerical columns have insufficient variance or non-null values",
        )

    try:
        matrix_df = frame.corr(method="pearson", min_periods=_MIN_NON_NULL)
    except Exception as exc:  # noqa: BLE001
        return CorrelationSummary(
            status=SectionStatus.UNAVAILABLE,
            reason=f"Correlation computation failed: {exc}",
        )

    # Convert NaN to None so the payload stays JSON-safe.
    matrix: List[List[Optional[float]]] = []
    for row in matrix_df.values.tolist():
        matrix.append([_safe(v) for v in row])

    pairs = _unique_pairs(usable, matrix_df)

    strong_positive = [p for p in pairs if p.coefficient >= _STRONG_THRESHOLD]
    strong_negative = [p for p in pairs if p.coefficient <= -_STRONG_THRESHOLD]
    top_pairs = sorted(pairs, key=lambda p: abs(p.coefficient), reverse=True)[:_TOP_PAIRS_LIMIT]

    return CorrelationSummary(
        status=SectionStatus.OK,
        columns=usable,
        matrix=[[0.0 if v is None else v for v in row] for row in matrix],
        strong_positive=sorted(strong_positive, key=lambda p: -p.coefficient),
        strong_negative=sorted(strong_negative, key=lambda p: p.coefficient),
        top_pairs=top_pairs,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _select_numeric_columns(profiles: List[ColumnProfile]) -> List[str]:
    return [
        p.name
        for p in profiles
        if p.column_class == ColumnClass.NUMERICAL
    ]


def _prepare_numeric_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Coerce to numeric, drop columns that don't have enough usable data."""
    numeric = df.apply(lambda s: pd.to_numeric(s, errors="coerce"))
    keep: List[str] = []
    for col in numeric.columns:
        s = numeric[col].dropna()
        if len(s) < _MIN_NON_NULL:
            continue
        if s.std(ddof=1) == 0 or math.isnan(float(s.std(ddof=1))):
            continue
        keep.append(col)
    return numeric[keep]


def _unique_pairs(names: List[str], matrix_df: pd.DataFrame) -> List[CorrelationPair]:
    pairs: List[CorrelationPair] = []
    for i, a in enumerate(names):
        for j, b in enumerate(names):
            if j <= i:
                continue
            try:
                coef = float(matrix_df.at[a, b])
            except Exception:  # noqa: BLE001
                continue
            if math.isnan(coef) or math.isinf(coef):
                continue
            pairs.append(
                CorrelationPair(
                    column_a=a,
                    column_b=b,
                    coefficient=coef,
                    strength=_strength_label(abs(coef)),
                    direction="positive" if coef >= 0 else "negative",
                )
            )
    return pairs


def _strength_label(abs_coef: float) -> str:
    for threshold, label in _STRENGTHS:
        if abs_coef >= threshold:
            return label
    return "very_weak"


def _safe(v: float) -> Optional[float]:
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    if math.isnan(f) or math.isinf(f):
        return None
    return round(f, 4)
