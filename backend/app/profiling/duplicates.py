"""Duplicate detection.

Two kinds:

1. Row-level duplicates — full-row matches. Phase 2 reports counts; it does
   NOT delete anything (that's Phase 3 territory).
2. Value duplicates in identifier columns — an ID appearing more than once
   is almost always a data-quality issue.
"""

from __future__ import annotations

from typing import Dict, List

import pandas as pd

from app.profiling.types import DuplicateSummary, SectionStatus


def analyze_duplicates(
    df: pd.DataFrame,
    id_column_names: List[str],
) -> DuplicateSummary:
    """Compute row + ID duplicate counts. Never mutates `df`."""
    total_rows = len(df)
    if total_rows == 0:
        return DuplicateSummary(
            status=SectionStatus.UNAVAILABLE,
            reason="Dataset has no rows",
        )

    try:
        # Hashing rows is O(n) — pandas does it efficiently.
        dup_mask = df.duplicated(keep="first")
        duplicate_rows = int(dup_mask.sum())
    except TypeError:
        # Unhashable content (dict / list columns). Fall back to a slower path
        # by casting the whole frame to string.
        try:
            dup_mask = df.astype(str).duplicated(keep="first")
            duplicate_rows = int(dup_mask.sum())
        except Exception:  # noqa: BLE001
            return DuplicateSummary(
                status=SectionStatus.UNAVAILABLE,
                reason="Row hashing failed (unsupported column contents)",
            )

    duplicate_ratio = float(duplicate_rows / total_rows) if total_rows else 0.0
    unique_rows = total_rows - duplicate_rows

    id_report: List[Dict[str, object]] = []
    for name in id_column_names:
        if name not in df.columns:
            continue
        col = df[name] if df.columns.get_loc(name) is not None else None
        # Guard against duplicate column labels
        if isinstance(col, pd.DataFrame):
            col = col.iloc[:, 0]
        try:
            counts = col.dropna().value_counts()
            dupe_values = counts[counts > 1]
            id_report.append(
                {
                    "column": name,
                    "duplicate_value_count": int(dupe_values.shape[0]),
                    "duplicate_row_count": int(dupe_values.sum() - dupe_values.shape[0]),
                    "examples": [
                        {"value": _json_safe(v), "count": int(c)}
                        for v, c in dupe_values.head(5).items()
                    ],
                }
            )
        except Exception:  # noqa: BLE001
            continue

    return DuplicateSummary(
        status=SectionStatus.OK,
        duplicate_rows=duplicate_rows,
        duplicate_ratio=round(duplicate_ratio, 6),
        unique_rows=unique_rows,
        duplicate_ids=id_report,
    )


def _json_safe(v: object) -> object:
    if isinstance(v, (str, int, float, bool)) or v is None:
        return v
    return str(v)
