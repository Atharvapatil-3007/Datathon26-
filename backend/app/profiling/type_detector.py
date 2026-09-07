"""Phase 2 column type detection.

Sharper than Phase 1's `schema.py`. Produces the coarse-grained user-facing
`ColumnClass` (numerical / categorical / text / date / datetime / id /
boolean / unknown) plus the finer `InferredType` reused from Phase 1.

Heuristics combine:
  * pandas dtype
  * cardinality (unique_count / total)
  * name hints (regex on the column name)
  * value patterns (UUID, sequential ints, boolean-like strings)
  * date sniffing (fraction of parseable values)

Every heuristic is deliberately conservative — when uncertain we prefer
`UNKNOWN` or `TEXT` over confidently mis-classifying.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np
import pandas as pd
from pandas.api import types as ptypes

from app.ingestion.dataset import InferredType
from app.profiling.types import CardinalityClass, ColumnClass


# ---------------------------------------------------------------------------
# Heuristic thresholds — tuned for financial / operational data
# ---------------------------------------------------------------------------
# Two-pattern identifier regex:
#   1. Standalone identifier words (`id`, `uuid`, `guid`, `key`, `code`, `hash`, `sku`, `isbn`)
#   2. Named-entity + identifier suffix (`customer_id`, `transaction_no`, `account_number`, ...)
# Deliberately narrow so "customer_name" does NOT match.
_IDENTIFIER_NAME = re.compile(
    r"(?:^|[_\-\s])(?:id|uuid|guid|key|code|hash|sku|isbn)(?:$|[_\-\s])"
    r"|"
    r"(?:^|[_\-\s])(?:account|transaction|txn|order|invoice|customer|user|record|payment|receipt|"
    r"employee|product|item|session|device|session|ref|reference)"
    r"(?:_id|_no|_code|_number|_ref|_key|_uuid|_hash)(?:$|[_\-\s])",
    re.IGNORECASE,
)
_DATE_NAME = re.compile(
    r"(?:^|[_\-\s])(?:date|time|dt|timestamp|created|updated|modified|at|on)(?:$|[_\-\s])",
    re.IGNORECASE,
)
_BOOL_NAME = re.compile(
    r"(?:^|[_\-\s])(?:is|has|can|should|will|active|enabled|deleted|flag)(?:_|$)",
    re.IGNORECASE,
)
_UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
_BOOL_TRUE = frozenset({"true", "t", "yes", "y", "1"})
_BOOL_FALSE = frozenset({"false", "f", "no", "n", "0"})
_BOOL_LIKE = _BOOL_TRUE | _BOOL_FALSE

_TEXT_MIN_AVG_LEN = 40
_CATEGORICAL_MAX_UNIQUE_RATIO = 0.05
_CATEGORICAL_ABS_MAX_UNIQUE = 50
_DATETIME_SUCCESS_THRESHOLD = 0.9
_DATETIME_SNIFF_SAMPLE = 50
_LOW_CARD_RATIO = 0.05
_HIGH_CARD_RATIO = 0.5


# ---------------------------------------------------------------------------
# Result envelope
# ---------------------------------------------------------------------------
@dataclass
class TypeDetection:
    column_class: ColumnClass
    inferred_type: InferredType
    cardinality_class: CardinalityClass
    unique_count: int
    unique_ratio: float


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def detect_column_type(name: str, series: pd.Series) -> TypeDetection:
    """Return the classification for a single column.

    `series` must already have Phase 1's "missing" values (empty strings,
    'NA', 'null', etc.) coerced to NaN — the caller handles that once so
    the detector doesn't repeat the work per module.
    """
    total = len(series)
    non_null = series.dropna()
    unique_count = int(non_null.nunique()) if not non_null.empty else 0
    unique_ratio = float(unique_count / total) if total else 0.0
    cardinality_class = _classify_cardinality(unique_count, unique_ratio, total)

    # Empty column -> UNKNOWN
    if non_null.empty:
        return TypeDetection(
            column_class=ColumnClass.UNKNOWN,
            inferred_type=InferredType.UNKNOWN,
            cardinality_class=cardinality_class,
            unique_count=0,
            unique_ratio=0.0,
        )

    inferred = _infer_native_type(series, non_null)
    column_class = _classify_column(
        name=name,
        series=series,
        non_null=non_null,
        inferred=inferred,
        unique_count=unique_count,
        unique_ratio=unique_ratio,
        total=total,
    )

    # If a column is classified as ID, upgrade inferred_type to IDENTIFIER
    if column_class == ColumnClass.ID and inferred in (InferredType.STRING, InferredType.INTEGER):
        inferred = InferredType.IDENTIFIER

    return TypeDetection(
        column_class=column_class,
        inferred_type=inferred,
        cardinality_class=cardinality_class,
        unique_count=unique_count,
        unique_ratio=unique_ratio,
    )


# ---------------------------------------------------------------------------
# Native type inference (dtype + boolean / date sniff on object columns)
# ---------------------------------------------------------------------------
def _infer_native_type(series: pd.Series, non_null: pd.Series) -> InferredType:
    if ptypes.is_bool_dtype(series):
        return InferredType.BOOLEAN
    if ptypes.is_integer_dtype(series):
        return InferredType.INTEGER
    if ptypes.is_float_dtype(series):
        # Ints promoted to float because of NaNs are still ints in intent.
        if _all_floats_are_int(non_null):
            return InferredType.INTEGER
        return InferredType.FLOAT
    if ptypes.is_datetime64_any_dtype(series):
        return InferredType.DATETIME

    # Object / string
    if ptypes.is_object_dtype(series) or ptypes.is_string_dtype(series):
        if _looks_boolean(non_null):
            return InferredType.BOOLEAN
        if _looks_datetime(non_null):
            return InferredType.DATETIME
        return InferredType.STRING

    return InferredType.UNKNOWN


# ---------------------------------------------------------------------------
# Column classification (ColumnClass)
# ---------------------------------------------------------------------------
def _classify_column(
    *,
    name: str,
    series: pd.Series,
    non_null: pd.Series,
    inferred: InferredType,
    unique_count: int,
    unique_ratio: float,
    total: int,
) -> ColumnClass:
    name_hint_id = bool(_IDENTIFIER_NAME.search(name))
    name_hint_date = bool(_DATE_NAME.search(name))
    name_hint_bool = bool(_BOOL_NAME.search(name))

    # 1. Booleans first — cheap and unambiguous.
    if inferred == InferredType.BOOLEAN:
        return ColumnClass.BOOLEAN
    if name_hint_bool and unique_count <= 2:
        return ColumnClass.BOOLEAN

    # 2. Datetime / date.
    if inferred == InferredType.DATETIME:
        return _date_or_datetime(non_null)
    if inferred in (InferredType.DATE,):
        return ColumnClass.DATE

    # 3. Identifier detection — high cardinality + name hint OR UUID-ish OR sequential ints.
    if _is_identifier(
        name_hint_id=name_hint_id,
        inferred=inferred,
        non_null=non_null,
        unique_count=unique_count,
        unique_ratio=unique_ratio,
        total=total,
    ):
        return ColumnClass.ID

    # 4. Numerical (only if we don't think it's an ID).
    if inferred in (InferredType.INTEGER, InferredType.FLOAT):
        # Very low-cardinality numeric columns (e.g. rating 1-5) read better
        # as categorical for dashboard purposes.
        if unique_count <= 10 and unique_ratio <= _LOW_CARD_RATIO and total >= 20:
            return ColumnClass.CATEGORICAL
        return ColumnClass.NUMERICAL

    # 5. String-based classification.
    if inferred == InferredType.STRING:
        avg_len = _avg_string_length(non_null)
        if avg_len >= _TEXT_MIN_AVG_LEN:
            return ColumnClass.TEXT
        if (
            unique_ratio <= _CATEGORICAL_MAX_UNIQUE_RATIO
            or unique_count <= _CATEGORICAL_ABS_MAX_UNIQUE
        ):
            return ColumnClass.CATEGORICAL
        return ColumnClass.TEXT

    return ColumnClass.UNKNOWN


def _date_or_datetime(non_null: pd.Series) -> ColumnClass:
    """Distinguish pure dates from full datetimes."""
    try:
        if ptypes.is_datetime64_any_dtype(non_null):
            times = non_null.dt.time
            # All midnight -> date-only
            if (times == pd.Timestamp("1970-01-01 00:00:00").time()).all():
                return ColumnClass.DATE
            return ColumnClass.DATETIME
    except Exception:  # noqa: BLE001
        pass
    return ColumnClass.DATETIME


def _is_identifier(
    *,
    name_hint_id: bool,
    inferred: InferredType,
    non_null: pd.Series,
    unique_count: int,
    unique_ratio: float,
    total: int,
) -> bool:
    fully_unique = unique_count == len(non_null) and unique_count > 1
    high_cardinality = unique_ratio >= 0.9

    # UUID-shaped strings are always identifiers.
    if inferred == InferredType.STRING and _uuid_ratio(non_null) >= 0.9:
        return True

    # A clear name hint promotes plausible identifier types to ID even when
    # the column isn't fully unique (e.g. `customer_id` repeats across
    # transactions but is still an FK-style identifier). We only require
    # at least 5 distinct values so tiny enum-like columns don't get
    # miscategorised.
    if name_hint_id and inferred in (InferredType.INTEGER, InferredType.STRING):
        if unique_count >= 5:
            return True

    # Fully unique strings without a name hint (e.g. hash columns).
    if fully_unique and inferred == InferredType.STRING and high_cardinality:
        return True

    return False


# ---------------------------------------------------------------------------
# Cardinality bucketing
# ---------------------------------------------------------------------------
def _classify_cardinality(
    unique_count: int, unique_ratio: float, total: int
) -> CardinalityClass:
    if total == 0 or unique_count == 0:
        return CardinalityClass.LOW
    if unique_ratio >= 0.999 and unique_count > 1:
        return CardinalityClass.UNIQUE
    if unique_ratio > _HIGH_CARD_RATIO:
        return CardinalityClass.HIGH
    if unique_ratio <= _LOW_CARD_RATIO or unique_count <= 10:
        return CardinalityClass.LOW
    return CardinalityClass.MEDIUM


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _all_floats_are_int(non_null: pd.Series) -> bool:
    try:
        sample = non_null.head(500)
        return bool(((sample % 1) == 0).all())
    except Exception:  # noqa: BLE001
        return False


def _looks_boolean(non_null: pd.Series) -> bool:
    sample = non_null.head(200)
    if sample.empty:
        return False
    try:
        lowered = sample.astype(str).str.strip().str.lower()
    except Exception:  # noqa: BLE001
        return False
    distinct = set(lowered.unique())
    if not distinct or len(distinct) > 4:
        return False
    return distinct.issubset(_BOOL_LIKE)


def _looks_datetime(non_null: pd.Series) -> bool:
    sample = non_null.head(_DATETIME_SNIFF_SAMPLE).astype(str)
    if sample.empty:
        return False
    try:
        parsed = pd.to_datetime(sample, errors="coerce", utc=False, format="mixed")
    except Exception:  # noqa: BLE001
        return False
    success = parsed.notna().mean()
    return bool(success >= _DATETIME_SUCCESS_THRESHOLD)


def _uuid_ratio(non_null: pd.Series) -> float:
    sample = non_null.head(200).astype(str)
    if sample.empty:
        return 0.0
    matches = sample.map(lambda s: bool(_UUID_PATTERN.match(s.strip())))
    return float(matches.mean())


def _avg_string_length(non_null: pd.Series) -> float:
    try:
        sample = non_null.head(200).astype(str)
        return float(sample.map(len).mean() or 0.0)
    except Exception:  # noqa: BLE001
        return 0.0
