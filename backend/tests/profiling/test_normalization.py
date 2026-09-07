"""Normalization: textual missing tokens should become NaN."""

from __future__ import annotations

import pandas as pd

from app.profiling.normalization import normalize_missing


def test_common_tokens_become_nan() -> None:
    df = pd.DataFrame(
        {
            "name": ["Ada", "", "  ", "N/A", "null", "NONE", "Alice"],
            "notes": ["nan", "-", "unknown", "hi", "bye", "", "?"],
        }
    )
    out = normalize_missing(df)

    # name has 5 missing tokens: '', '  ', 'N/A', 'null', 'NONE'
    assert out["name"].isna().sum() == 5
    # notes has 5 missing tokens: 'nan', '-', 'unknown', '', '?'
    assert out["notes"].isna().sum() == 5


def test_original_dataframe_is_not_mutated() -> None:
    df = pd.DataFrame({"x": ["N/A", "value"]})
    _ = normalize_missing(df)
    assert df["x"].tolist() == ["N/A", "value"]


def test_numeric_columns_are_untouched() -> None:
    df = pd.DataFrame({"amount": [1.0, 2.0, None, 4.0]})
    out = normalize_missing(df)
    assert out["amount"].isna().sum() == 1
    assert out["amount"].dropna().tolist() == [1.0, 2.0, 4.0]
