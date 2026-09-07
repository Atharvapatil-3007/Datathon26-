"""Schema inference helpers.

Given a pandas DataFrame, produce a list of `ColumnSchema` entries with
conservative type inference and flags. Phase 3 is expected to build on top
of this — Phase 1 keeps it deliberately shallow.
"""

from __future__ import annotations

import math
import re
from typing import Any, Iterable, List

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

from app.ingestion.dataset import ColumnSchema, InferredType


# Heuristics
_MAX_SAMPLE_VALUES = 5
_CATEGORICAL_MAX_UNIQUE_RATIO = 0.05  # < 5 % unique -> categorical
_CATEGORICAL_ABS_MAX_UNIQUE = 50      # or absolute cap of 50 distinct values
_TEXT_MIN_AVG_LEN = 40                # avg string length > 40 -> "text"
_IDENTIFIER_NAME_HINTS = re.compile(
    r"(?:^|[_\-\s])(id|uuid|guid|key|code|hash|sku|isbn|number|no)(?:$|[_\-\s])",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def infer_schema(df: pd.DataFrame) -> List[ColumnSchema]:
    """Return per-column `ColumnSchema` entries for `df`."""
    schemas: List[ColumnSchema] = []
    total_rows = len(df)
    # Positional iteration so duplicate column names don't turn `df[name]`
    # into a DataFrame instead of a Series.
    for i in range(df.shape[1]):
        col = df.iloc[:, i]
        schemas.append(_infer_column(str(df.columns[i]), col, total_rows))
    return schemas


# ---------------------------------------------------------------------------
# Column-level inference
# ---------------------------------------------------------------------------
def _infer_column(name: str, series: pd.Series, total_rows: int) -> ColumnSchema:
    dtype_str = str(series.dtype)
    missing_count = int(series.isna().sum())
    missing_ratio = float(missing_count / total_rows) if total_rows else 0.0

    non_null = series.dropna()
    unique_count = int(non_null.nunique()) if not non_null.empty else 0
    sample_values = _sample_values(non_null)

    inferred = _infer_type(series, non_null)

    is_numerical = inferred in (InferredType.INTEGER, InferredType.FLOAT)
    is_datetime = inferred in (InferredType.DATETIME, InferredType.DATE)
    is_categorical, is_text, is_identifier = _infer_flags(
        name, non_null, unique_count, total_rows, inferred
    )

    # Identifier promotion overrides categorical / text flags
    if is_identifier:
        is_categorical = False
        is_text = False
        if inferred == InferredType.STRING:
            inferred = InferredType.IDENTIFIER

    return ColumnSchema(
        name=name,
        dtype=dtype_str,
        inferred_type=inferred,
        nullable=missing_count > 0,
        unique_count=unique_count,
        missing_count=missing_count,
        missing_ratio=round(missing_ratio, 6),
        sample_values=sample_values,
        is_identifier=is_identifier,
        is_categorical=is_categorical,
        is_numerical=is_numerical,
        is_datetime=is_datetime,
        is_text=is_text,
    )


def _infer_type(series: pd.Series, non_null: pd.Series) -> InferredType:
    if non_null.empty:
        return InferredType.UNKNOWN

    if ptypes.is_bool_dtype(series):
        return InferredType.BOOLEAN
    if ptypes.is_integer_dtype(series):
        return InferredType.INTEGER
    if ptypes.is_float_dtype(series):
        # Some ints get loaded as float when there are NaNs — try to detect.
        if _looks_like_integer(non_null):
            return InferredType.INTEGER
        return InferredType.FLOAT
    if ptypes.is_datetime64_any_dtype(series):
        return InferredType.DATETIME

    # Object / string columns — try to sniff datetime.
    if ptypes.is_object_dtype(series) or ptypes.is_string_dtype(series):
        if _looks_like_datetime(non_null):
            return InferredType.DATETIME
        return InferredType.STRING

    return InferredType.UNKNOWN


def _infer_flags(
    name: str,
    non_null: pd.Series,
    unique_count: int,
    total_rows: int,
    inferred: InferredType,
) -> tuple[bool, bool, bool]:
    """Return (is_categorical, is_text, is_identifier)."""
    is_categorical = False
    is_text = False
    is_identifier = False

    if unique_count == 0 or total_rows == 0:
        return is_categorical, is_text, is_identifier

    unique_ratio = unique_count / total_rows

    # Identifier heuristic: unique per row, name hints, or hash-like strings.
    name_hint = bool(_IDENTIFIER_NAME_HINTS.search(name))
    fully_unique = unique_count == len(non_null) and unique_count > 1
    if fully_unique and (name_hint or inferred in (InferredType.INTEGER, InferredType.STRING)):
        is_identifier = True

    if inferred == InferredType.STRING and not is_identifier:
        avg_len = _average_string_length(non_null)
        if avg_len >= _TEXT_MIN_AVG_LEN:
            is_text = True
        elif (
            unique_ratio <= _CATEGORICAL_MAX_UNIQUE_RATIO
            or unique_count <= _CATEGORICAL_ABS_MAX_UNIQUE
        ):
            is_categorical = True

    # Low-cardinality integer columns can also be categorical (e.g. rating 1-5).
    # Require both a small absolute count AND that the column isn't nearly
    # unique per row (which would make it look like an identifier).
    if inferred == InferredType.INTEGER and not is_identifier:
        if unique_count <= 10 and unique_ratio <= 0.5:
            is_categorical = True

    return is_categorical, is_text, is_identifier


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _looks_like_integer(non_null: pd.Series) -> bool:
    try:
        sample = non_null.head(500)
        return bool(((sample % 1) == 0).all())
    except Exception:
        return False


_DATETIME_SNIFF_SAMPLE = 25
_DATETIME_SUCCESS_THRESHOLD = 0.9


def _looks_like_datetime(non_null: pd.Series) -> bool:
    sample = non_null.head(_DATETIME_SNIFF_SAMPLE).astype(str)
    if sample.empty:
        return False
    try:
        # `format='mixed'` silences pandas' inference warning and still
        # allows per-element parsing — exactly what a sniff needs.
        parsed = pd.to_datetime(sample, errors="coerce", utc=False, format="mixed")
    except Exception:
        return False
    success = parsed.notna().mean()
    return bool(success >= _DATETIME_SUCCESS_THRESHOLD)


def _average_string_length(non_null: pd.Series) -> float:
    try:
        sample = non_null.head(200).astype(str)
        return float(sample.map(len).mean() or 0.0)
    except Exception:
        return 0.0


def _sample_values(non_null: pd.Series) -> List[Any]:
    """Return up to N JSON-serializable sample values."""
    if non_null.empty:
        return []
    head = non_null.head(_MAX_SAMPLE_VALUES).tolist()
    return [_json_safe(v) for v in head]


def _json_safe(v: Any) -> Any:
    """Best-effort conversion of numpy / pandas scalars to plain Python."""
    if v is None:
        return None
    if isinstance(v, (str, bool, int)):
        return v
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        if math.isnan(f) or math.isinf(f):
            return None
        return f
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, (pd.Timestamp,)):
        return v.isoformat()
    if isinstance(v, (np.ndarray,)):
        return [_json_safe(x) for x in v.tolist()]
    if isinstance(v, (list, tuple)):
        return [_json_safe(x) for x in v]
    if isinstance(v, dict):
        return {str(k): _json_safe(val) for k, val in v.items()}
    return str(v)


def jsonify_records(rows: Iterable[dict]) -> List[dict]:
    """Convert a list of pandas .to_dict('records') rows to JSON-safe dicts."""
    return [{k: _json_safe(v) for k, v in r.items()} for r in rows]
