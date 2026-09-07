"""Missing-value analyzer.

Runs on a DataFrame that has already been passed through
`normalization.normalize_missing`, so 'N/A' / 'null' / '' etc. are already NaN.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from app.profiling.types import MissingSummary, SectionStatus


def analyze_missing(df: pd.DataFrame) -> MissingSummary:
    """Return per-column and dataset-level missing statistics."""
    total_rows = len(df)
    total_cols = df.shape[1]

    if total_cols == 0:
        return MissingSummary(
            status=SectionStatus.UNAVAILABLE,
            reason="Dataset has no columns",
        )

    per_column: List[Dict[str, object]] = []
    columns_with_missing = 0
    total_missing = 0

    for i in range(total_cols):
        col_name = str(df.columns[i])
        col = df.iloc[:, i]
        missing = int(col.isna().sum())
        ratio = float(missing / total_rows) if total_rows else 0.0
        if missing > 0:
            columns_with_missing += 1
        total_missing += missing
        per_column.append(
            {
                "column": col_name,
                "missing_count": missing,
                "missing_ratio": round(ratio, 6),
            }
        )

    per_column.sort(key=lambda r: r["missing_count"], reverse=True)
    total_cells = total_rows * total_cols
    overall_ratio = float(total_missing / total_cells) if total_cells else 0.0

    return MissingSummary(
        status=SectionStatus.OK,
        total_missing=total_missing,
        total_cells=total_cells,
        missing_ratio=round(overall_ratio, 6),
        columns_with_missing=columns_with_missing,
        per_column=per_column,
    )


def column_missing_stats(series: pd.Series, total_rows: int) -> Dict[str, float]:
    """Small helper for per-column profile building."""
    missing = int(series.isna().sum())
    ratio = float(missing / total_rows) if total_rows else 0.0
    return {
        "missing_count": missing,
        "missing_ratio": round(ratio, 6),
        "non_null": int(total_rows - missing),
    }
