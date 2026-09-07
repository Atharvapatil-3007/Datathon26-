"""Dataset validator.

Two levels of validation:

* File level  — runs BEFORE the loader touches the file. Cheap sanity checks
                against the path itself (existence, size, extension, etc).
* Dataset level — runs AFTER the loader has produced a DatasetObject.
                  Structural sanity of the parsed frame.

A `ValidationResult` separates non-fatal `warnings` from fatal `errors`.
Only fatal errors abort the ingestion pipeline. Warnings are recorded on
the DatasetObject for downstream consumption.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

import pandas as pd

from app.config.settings import get_settings
from app.ingestion.dataset import DatasetObject
from app.ingestion.exceptions import (
    CorruptedFileError,
    EmptyDatasetError,
    FileTooLargeError,
    InvalidDatasetError,
    UnsupportedFileTypeError,
)


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------
@dataclass
class ValidationResult:
    valid: bool = True
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def warn(self, msg: str) -> None:
        if msg not in self.warnings:
            self.warnings.append(msg)

    def fail(self, msg: str) -> None:
        self.valid = False
        if msg not in self.errors:
            self.errors.append(msg)

    def to_dict(self) -> dict:
        return {"valid": self.valid, "warnings": self.warnings, "errors": self.errors}


# ---------------------------------------------------------------------------
# File-level validation
# ---------------------------------------------------------------------------
_SUPPORTED_EXTENSIONS = {
    ".csv", ".tsv", ".txt",
    ".xlsx", ".xlsm", ".xls",
    ".json", ".jsonl", ".ndjson",
    ".parquet", ".pq",
    ".db", ".sqlite", ".sqlite3",
    ".zip",
}


def validate_file(
    path: str | Path,
    *,
    filename_hint: Optional[str] = None,
    max_size_bytes: Optional[int] = None,
) -> ValidationResult:
    """Cheap checks on the file itself. Raises on hard errors, warns otherwise."""
    result = ValidationResult()
    p = Path(path)

    if not p.exists():
        raise CorruptedFileError(f"File not found: {p}")
    if not p.is_file():
        raise CorruptedFileError(f"Not a regular file: {p}")

    try:
        size = p.stat().st_size
    except OSError as exc:
        raise CorruptedFileError(f"Cannot stat file: {exc}") from exc

    if size == 0:
        raise EmptyDatasetError("Uploaded file is empty (0 bytes)")

    settings = get_settings()
    limit = max_size_bytes if max_size_bytes is not None else settings.max_upload_size_bytes
    if size > limit:
        raise FileTooLargeError(
            f"File size {size} bytes exceeds the limit of {limit} bytes",
            details={"size_bytes": size, "limit_bytes": limit},
        )

    ext = (Path(filename_hint).suffix if filename_hint else p.suffix).lower()
    if ext and ext not in _SUPPORTED_EXTENSIONS:
        # Not an error — the detector may still recognize the content — but flag it.
        result.warn(f"Extension '{ext}' is not in the known list; relying on content detection")

    if not _readable(p):
        raise CorruptedFileError(f"File is not readable: {p}")

    return result


def _readable(p: Path) -> bool:
    try:
        with open(p, "rb") as f:
            f.read(16)
        return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Dataset-level validation
# ---------------------------------------------------------------------------
_INVALID_COLUMN_NAME = re.compile(r"^\s*$")  # entirely whitespace / empty
_MISSING_WARN_THRESHOLD = 0.05  # warn when a column exceeds this null ratio
_HIGH_MISSING_THRESHOLD = 0.5   # warn strongly at 50 %+


def validate_dataset(dataset: DatasetObject) -> ValidationResult:
    """Run structural checks on a fully-loaded DatasetObject.

    Populates `dataset.warnings` and `dataset.errors` and returns the same
    information as a `ValidationResult`.
    """
    result = ValidationResult()

    df = dataset.data
    if df is None:
        raise InvalidDatasetError("DatasetObject has no data payload after load")

    if not isinstance(df, pd.DataFrame):
        raise InvalidDatasetError(
            f"Loader produced unexpected data type: {type(df).__name__}"
        )

    # Shape checks
    if df.shape[1] == 0:
        raise InvalidDatasetError("Dataset has no columns")
    if df.shape[0] == 0:
        # For most real-world sources this is fatal; warn instead of raising
        # so metadata-only ingestion (e.g. empty SQL table) can still proceed.
        result.warn("Dataset has 0 rows")

    _check_column_names(df, result)
    _check_empty_columns(df, result)
    _check_empty_rows(df, result)
    _check_missing_ratios(df, result)

    # Reflect on the DatasetObject
    for w in result.warnings:
        dataset.add_warning(w)
    for e in result.errors:
        dataset.add_error(e)

    return result


# ---------------------------------------------------------------------------
# Column-level checks
# ---------------------------------------------------------------------------
def _check_column_names(df: pd.DataFrame, result: ValidationResult) -> None:
    names = [str(c) for c in df.columns]

    # Duplicates
    seen: dict[str, int] = {}
    for n in names:
        seen[n] = seen.get(n, 0) + 1
    dupes = sorted([n for n, c in seen.items() if c > 1])
    if dupes:
        result.warn(f"Duplicate column names detected: {dupes[:5]}")

    # Invalid names
    invalid = [n for n in names if not n or _INVALID_COLUMN_NAME.match(n)]
    if invalid:
        result.warn(f"{len(invalid)} column(s) have empty/whitespace-only names")

    # Unusual characters (informational, not a hard failure)
    unusual = [n for n in names if any(ch in n for ch in "\n\r\t")]
    if unusual:
        result.warn(f"{len(unusual)} column name(s) contain whitespace/control characters")


def _check_empty_columns(df: pd.DataFrame, result: ValidationResult) -> None:
    if len(df) == 0:
        return
    # Iterate by position: df[name] returns a DataFrame (not a Series) when
    # column names duplicate, which breaks `.isna().all()`.
    all_null: list[str] = []
    for i in range(df.shape[1]):
        col = df.iloc[:, i]
        if col.isna().all():
            all_null.append(str(df.columns[i]))
    if all_null:
        result.warn(f"{len(all_null)} column(s) are entirely null: {all_null[:5]}")


def _check_empty_rows(df: pd.DataFrame, result: ValidationResult) -> None:
    if len(df) == 0:
        return
    all_null_rows = int(df.isna().all(axis=1).sum())
    if all_null_rows:
        pct = round(100 * all_null_rows / len(df), 2)
        result.warn(f"{all_null_rows} entirely-empty row(s) ({pct}%)")


def _check_missing_ratios(df: pd.DataFrame, result: ValidationResult) -> None:
    if len(df) == 0:
        return
    # Positional iteration for the same reason as _check_empty_columns.
    for i in range(df.shape[1]):
        col_name = str(df.columns[i])
        ratio = float(df.iloc[:, i].isna().mean())
        if ratio >= _HIGH_MISSING_THRESHOLD:
            result.warn(
                f"Column '{col_name}' has {round(ratio * 100, 1)}% missing values"
            )
        elif ratio >= _MISSING_WARN_THRESHOLD:
            result.warn(
                f"Column '{col_name}' contains {round(ratio * 100, 1)}% missing values"
            )


__all__ = ["ValidationResult", "validate_file", "validate_dataset"]

# Import kept for public alias; helps callers who only need the exception.
_ = UnsupportedFileTypeError
