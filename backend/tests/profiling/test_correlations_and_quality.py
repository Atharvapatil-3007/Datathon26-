"""Correlations + data-quality scoring."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.ingestion.dataset import InferredType
from app.profiling.correlations import analyze_correlations
from app.profiling.duplicates import analyze_duplicates
from app.profiling.missing import analyze_missing
from app.profiling.quality import (
    QualityWeights,
    score_column,
    score_dataset,
)
from app.profiling.types import (
    CardinalityClass,
    ColumnClass,
    ColumnProfile,
    QualityGrade,
    SectionStatus,
)


def _make_profile(name: str, cls: ColumnClass, **kwargs) -> ColumnProfile:
    defaults = dict(
        name=name,
        dtype="float64" if cls == ColumnClass.NUMERICAL else "object",
        column_class=cls,
        inferred_type=InferredType.FLOAT if cls == ColumnClass.NUMERICAL else InferredType.STRING,
        total=100,
        non_null=100,
        missing_count=0,
        missing_ratio=0.0,
        unique_count=10,
        unique_ratio=0.1,
        cardinality_class=CardinalityClass.LOW,
    )
    defaults.update(kwargs)
    return ColumnProfile(**defaults)


# ---------------------------------------------------------------------------
# Correlations
# ---------------------------------------------------------------------------
def test_correlations_strong_positive() -> None:
    rng = np.random.default_rng(0)
    x = rng.normal(size=200)
    y = x * 2 + rng.normal(scale=0.1, size=200)
    df = pd.DataFrame({"x": x, "y": y, "customer_id": rng.integers(0, 5, size=200)})
    profiles = [
        _make_profile("x", ColumnClass.NUMERICAL),
        _make_profile("y", ColumnClass.NUMERICAL),
        _make_profile("customer_id", ColumnClass.ID),
    ]
    r = analyze_correlations(df, profiles)
    assert r.status == SectionStatus.OK
    assert r.columns == ["x", "y"]  # id excluded
    assert r.strong_positive
    assert r.strong_positive[0].coefficient > 0.9


def test_correlations_insufficient_numeric_columns() -> None:
    df = pd.DataFrame({"only_num": range(50)})
    profiles = [_make_profile("only_num", ColumnClass.NUMERICAL)]
    r = analyze_correlations(df, profiles)
    assert r.status == SectionStatus.UNAVAILABLE


def test_correlations_skip_constant_column() -> None:
    df = pd.DataFrame({"a": range(50), "b": [5.0] * 50})
    profiles = [
        _make_profile("a", ColumnClass.NUMERICAL),
        _make_profile("b", ColumnClass.NUMERICAL),
    ]
    r = analyze_correlations(df, profiles)
    assert r.status == SectionStatus.UNAVAILABLE  # 'b' dropped -> only 1 usable


# ---------------------------------------------------------------------------
# Quality
# ---------------------------------------------------------------------------
def test_quality_grade_a_when_clean() -> None:
    df = pd.DataFrame({"x": range(100), "y": range(100)})
    profiles = [
        _make_profile("x", ColumnClass.NUMERICAL),
        _make_profile("y", ColumnClass.NUMERICAL),
    ]
    missing = analyze_missing(df)
    duplicates = analyze_duplicates(df, id_column_names=[])
    q = score_dataset(df, profiles, missing, duplicates)
    assert q.grade == QualityGrade.A


def test_quality_penalizes_high_missing_ratio() -> None:
    df = pd.DataFrame(
        {
            "x": [None] * 50 + list(range(50)),
            "y": [None] * 50 + list(range(50)),
        }
    )
    profiles = [
        _make_profile("x", ColumnClass.NUMERICAL, missing_count=50, missing_ratio=0.5),
        _make_profile("y", ColumnClass.NUMERICAL, missing_count=50, missing_ratio=0.5),
    ]
    missing = analyze_missing(df)
    duplicates = analyze_duplicates(df, id_column_names=[])
    q = score_dataset(df, profiles, missing, duplicates)
    assert q.dimensions["completeness"] < 60
    assert q.overall_score < 90


def test_column_quality_score_penalizes_missing() -> None:
    p = _make_profile("x", ColumnClass.NUMERICAL, missing_ratio=0.5)
    score = score_column(p)
    assert score < 90


def test_quality_weights_are_configurable() -> None:
    weights = QualityWeights(completeness=1.0, uniqueness=0.0, validity=0.0, consistency=0.0)
    df = pd.DataFrame({"x": [1, 2, 3, 4, 5]})
    profiles = [_make_profile("x", ColumnClass.NUMERICAL)]
    missing = analyze_missing(df)
    duplicates = analyze_duplicates(df, id_column_names=[])
    q = score_dataset(df, profiles, missing, duplicates, weights=weights)
    assert q.overall_score == q.dimensions["completeness"]
