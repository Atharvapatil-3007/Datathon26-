"""Missing / duplicates / cardinality analyzers."""

from __future__ import annotations

import pandas as pd

from app.profiling.cardinality import summarize_cardinality
from app.profiling.duplicates import analyze_duplicates
from app.profiling.missing import analyze_missing
from app.profiling.type_detector import detect_column_type
from app.profiling.types import (
    CardinalityClass,
    ColumnClass,
    ColumnProfile,
    SectionStatus,
)
from app.ingestion.dataset import InferredType


# ---------------------------------------------------------------------------
# Missing
# ---------------------------------------------------------------------------
def test_missing_summary_counts() -> None:
    df = pd.DataFrame(
        {
            "a": [1, None, 3, None, 5],
            "b": [1, 2, 3, 4, 5],
            "c": [None, None, None, None, None],
        }
    )
    r = analyze_missing(df)
    assert r.status == SectionStatus.OK
    assert r.total_missing == 7
    assert r.columns_with_missing == 2  # a + c

    per_col = {row["column"]: row for row in r.per_column}
    assert per_col["c"]["missing_count"] == 5
    assert per_col["b"]["missing_count"] == 0


def test_missing_no_columns() -> None:
    r = analyze_missing(pd.DataFrame())
    assert r.status == SectionStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# Duplicates
# ---------------------------------------------------------------------------
def test_duplicate_rows_and_ids() -> None:
    df = pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 4, 5, 1, 2],
            "amount": [100, 200, 300, 400, 500, 100, 200],
        }
    )
    r = analyze_duplicates(df, id_column_names=["customer_id"])
    assert r.status == SectionStatus.OK
    assert r.duplicate_rows == 2  # rows 5, 6 are dupes of 0, 1
    assert r.unique_rows == 5

    id_report = r.duplicate_ids[0]
    assert id_report["column"] == "customer_id"
    assert id_report["duplicate_value_count"] == 2  # ids 1 and 2 both appear twice


def test_duplicate_empty_df() -> None:
    r = analyze_duplicates(pd.DataFrame(), id_column_names=[])
    assert r.status == SectionStatus.UNAVAILABLE


# ---------------------------------------------------------------------------
# Cardinality summary
# ---------------------------------------------------------------------------
def test_cardinality_summary_bucketing() -> None:
    df = pd.DataFrame(
        {
            "grade": ["A", "B", "C"] * 40,
            "amount": pd.Series(range(120)),
            "user_id": [f"u-{i}" for i in range(120)],
        }
    )

    profiles = []
    for name in df.columns:
        det = detect_column_type(name, df[name])
        profiles.append(
            ColumnProfile(
                name=name,
                dtype=str(df[name].dtype),
                column_class=det.column_class,
                inferred_type=det.inferred_type,
                total=len(df),
                non_null=int(df[name].notna().sum()),
                missing_count=0,
                missing_ratio=0.0,
                unique_count=det.unique_count,
                unique_ratio=det.unique_ratio,
                cardinality_class=det.cardinality_class,
            )
        )

    r = summarize_cardinality(profiles)
    assert r.status == SectionStatus.OK
    assert "grade" in r.low
    assert "user_id" in r.unique
    # `amount` should end up somewhere between (medium/high)
    assert "amount" in (r.high + r.unique + r.medium)


def test_cardinality_summary_empty_profiles() -> None:
    r = summarize_cardinality([])
    assert r.status == SectionStatus.UNAVAILABLE
