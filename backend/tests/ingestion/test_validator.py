"""Tests for the validator."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.ingestion.dataset import DatasetObject
from app.ingestion.exceptions import (
    CorruptedFileError,
    EmptyDatasetError,
    FileTooLargeError,
    InvalidDatasetError,
)
from app.ingestion.validator import validate_dataset, validate_file


# ---------------------------------------------------------------------------
# File level
# ---------------------------------------------------------------------------
def test_validate_file_ok(csv_file: Path) -> None:
    result = validate_file(csv_file)
    assert result.valid is True


def test_validate_file_empty_raises(empty_file: Path) -> None:
    with pytest.raises(EmptyDatasetError):
        validate_file(empty_file)


def test_validate_file_missing_raises(tmp_path: Path) -> None:
    with pytest.raises(CorruptedFileError):
        validate_file(tmp_path / "does-not-exist.csv")


def test_validate_file_too_large(tmp_path: Path) -> None:
    p = tmp_path / "big.csv"
    p.write_bytes(b"x" * 1024)
    with pytest.raises(FileTooLargeError):
        validate_file(p, max_size_bytes=100)


def test_validate_file_unknown_extension_warns(tmp_path: Path) -> None:
    p = tmp_path / "mystery.xyz"
    p.write_text("a,b\n1,2\n")
    result = validate_file(p)
    assert result.valid is True
    assert any("extension" in w.lower() for w in result.warnings)


# ---------------------------------------------------------------------------
# Dataset level
# ---------------------------------------------------------------------------
def test_validate_dataset_ok() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    ds = DatasetObject(data=df)
    result = validate_dataset(ds)
    assert result.valid is True
    assert result.errors == []


def test_validate_dataset_zero_rows_warns_not_fatal() -> None:
    df = pd.DataFrame({"a": [], "b": []})
    ds = DatasetObject(data=df)
    result = validate_dataset(ds)
    assert result.valid is True
    assert any("0 rows" in w for w in result.warnings)


def test_validate_dataset_zero_columns_is_fatal() -> None:
    df = pd.DataFrame()
    ds = DatasetObject(data=df)
    with pytest.raises(InvalidDatasetError):
        validate_dataset(ds)


def test_validate_dataset_flags_duplicate_columns() -> None:
    df = pd.DataFrame([[1, 2], [3, 4]], columns=["a", "a"])
    ds = DatasetObject(data=df)
    result = validate_dataset(ds)
    assert any("Duplicate column" in w for w in result.warnings)


def test_validate_dataset_flags_all_null_column() -> None:
    df = pd.DataFrame({"a": [1, 2, 3], "b": [None, None, None]})
    ds = DatasetObject(data=df)
    result = validate_dataset(ds)
    assert any("entirely null" in w for w in result.warnings)


def test_validate_dataset_flags_high_missing_ratio() -> None:
    df = pd.DataFrame({"a": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10], "b": [1, None, None, None, None, None, None, 8, 9, 10]})
    ds = DatasetObject(data=df)
    result = validate_dataset(ds)
    assert any("missing values" in w for w in result.warnings)
