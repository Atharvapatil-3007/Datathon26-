"""Statistics + distributions + outliers modules."""

from __future__ import annotations

import numpy as np
import pandas as pd

from app.profiling import distributions as dist
from app.profiling import statistics as stats
from app.profiling.outliers import detect_outliers


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------
def test_numerical_stats_basic() -> None:
    s = pd.Series([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    r = stats.numerical_stats(s)
    assert r["count"] == 10
    assert r["min"] == 1.0
    assert r["max"] == 10.0
    assert r["median"] == 5.5
    assert r["q1"] == 3.25
    assert r["q3"] == 7.75


def test_numerical_stats_handles_nan() -> None:
    s = pd.Series([1.0, float("nan"), 3.0])
    r = stats.numerical_stats(s)
    assert r["count"] == 2
    assert r["mean"] == 2.0


def test_categorical_stats_mode() -> None:
    s = pd.Series(["A", "A", "B", "C", "A"])
    r = stats.categorical_stats(s)
    assert r["mode"] == "A"
    assert r["mode_frequency"] == 3


def test_text_stats_lengths() -> None:
    s = pd.Series(["hi", "there", "world"])
    r = stats.text_stats(s)
    assert r["min_length"] == 2
    assert r["max_length"] == 5


def test_datetime_stats_range() -> None:
    s = pd.to_datetime(pd.Series(["2024-01-01", "2024-01-10", "2024-01-05"]))
    r = stats.datetime_stats(s)
    assert r["range_days"] == 9


def test_id_stats_uniqueness() -> None:
    s = pd.Series([1, 2, 3, 4, 5, 1])
    r = stats.id_stats(s)
    assert r["unique_count"] == 5
    assert r["duplicate_count"] == 1


# ---------------------------------------------------------------------------
# Distributions
# ---------------------------------------------------------------------------
def test_numerical_histogram_shape() -> None:
    s = pd.Series(np.random.default_rng(1).normal(size=500))
    r = dist.numerical_distribution(s, bins=10)
    assert len(r["counts"]) == 10
    assert len(r["bins"]) == 11
    assert sum(r["counts"]) == 500


def test_numerical_histogram_constant_column() -> None:
    s = pd.Series([5.0] * 20)
    r = dist.numerical_distribution(s)
    assert r["shape"] in ("constant", "degenerate")


def test_categorical_top_values() -> None:
    s = pd.Series(["A"] * 5 + ["B"] * 3 + ["C"] * 2)
    r = dist.categorical_distribution(s, k=2)
    assert r["top_values"][0]["value"] == "A"
    assert r["top_values"][0]["count"] == 5
    assert r["other_count"] == 2  # C moved into "other"


# ---------------------------------------------------------------------------
# Outliers
# ---------------------------------------------------------------------------
def test_outliers_iqr_detects_extreme_value() -> None:
    s = pd.Series(list(range(1, 101)) + [10_000])
    r = detect_outliers(s)
    assert r["method"] == "iqr"
    assert r["count"] >= 1


def test_outliers_insufficient_data() -> None:
    s = pd.Series([1.0, 2.0])
    r = detect_outliers(s)
    assert r["reason"] == "insufficient_data"


def test_outliers_zero_iqr() -> None:
    s = pd.Series([5.0] * 20)
    r = detect_outliers(s)
    assert r["reason"] == "zero_iqr"
    assert r["count"] == 0
