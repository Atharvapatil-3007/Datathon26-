"""Result types produced by the Phase 2 profiling engine.

Everything here is a plain dataclass with a `.to_dict()` method that returns
JSON-safe primitives. That's what gets serialized into the API response and
persisted into the `datasets.profile` JSONB column.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.ingestion.dataset import InferredType

PHASE2_VERSION = "2.0"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ColumnClass(str, Enum):
    """The coarse-grained user-visible classification of a column."""

    NUMERICAL = "numerical"
    CATEGORICAL = "categorical"
    TEXT = "text"
    DATE = "date"
    DATETIME = "datetime"
    ID = "id"
    BOOLEAN = "boolean"
    UNKNOWN = "unknown"


class CardinalityClass(str, Enum):
    LOW = "low"          # < 5% unique OR <= 10 distinct
    MEDIUM = "medium"    # 5-50% unique
    HIGH = "high"        # > 50% unique
    UNIQUE = "unique"    # 100% unique (identifier candidate)


class QualityGrade(str, Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    F = "F"


class SectionStatus(str, Enum):
    OK = "ok"
    UNAVAILABLE = "unavailable"
    SKIPPED = "skipped"


# ---------------------------------------------------------------------------
# Column profile
# ---------------------------------------------------------------------------
@dataclass
class ColumnProfile:
    """Everything Phase 2 knows about a single column."""

    name: str
    dtype: str
    column_class: ColumnClass
    inferred_type: InferredType

    # Counts
    total: int
    non_null: int
    missing_count: int
    missing_ratio: float

    # Cardinality
    unique_count: int
    unique_ratio: float
    cardinality_class: CardinalityClass

    # Content
    sample_values: List[Any] = field(default_factory=list)
    most_frequent_value: Optional[Any] = None
    most_frequent_count: int = 0

    # Type-specific payloads
    statistics: Dict[str, Any] = field(default_factory=dict)
    distribution: Dict[str, Any] = field(default_factory=dict)
    outliers: Optional[Dict[str, Any]] = None
    top_values: List[Dict[str, Any]] = field(default_factory=list)

    # Column-level quality (0-100)
    quality_score: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "column_class": self.column_class.value,
            "inferred_type": self.inferred_type.value,
            "total": self.total,
            "non_null": self.non_null,
            "missing_count": self.missing_count,
            "missing_ratio": self.missing_ratio,
            "unique_count": self.unique_count,
            "unique_ratio": self.unique_ratio,
            "cardinality_class": self.cardinality_class.value,
            "sample_values": self.sample_values,
            "most_frequent_value": self.most_frequent_value,
            "most_frequent_count": self.most_frequent_count,
            "statistics": self.statistics,
            "distribution": self.distribution,
            "outliers": self.outliers,
            "top_values": self.top_values,
            "quality_score": round(self.quality_score, 2),
        }


# ---------------------------------------------------------------------------
# Dataset-level summaries
# ---------------------------------------------------------------------------
@dataclass
class DatasetOverview:
    rows: int
    columns: int
    size_bytes: Optional[int] = None
    numerical_columns: int = 0
    categorical_columns: int = 0
    text_columns: int = 0
    date_columns: int = 0
    datetime_columns: int = 0
    id_columns: int = 0
    boolean_columns: int = 0
    unknown_columns: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rows": self.rows,
            "columns": self.columns,
            "size_bytes": self.size_bytes,
            "numerical_columns": self.numerical_columns,
            "categorical_columns": self.categorical_columns,
            "text_columns": self.text_columns,
            "date_columns": self.date_columns,
            "datetime_columns": self.datetime_columns,
            "id_columns": self.id_columns,
            "boolean_columns": self.boolean_columns,
            "unknown_columns": self.unknown_columns,
        }


@dataclass
class MissingSummary:
    status: SectionStatus = SectionStatus.OK
    reason: Optional[str] = None
    total_missing: int = 0
    total_cells: int = 0
    missing_ratio: float = 0.0
    columns_with_missing: int = 0
    per_column: List[Dict[str, Any]] = field(default_factory=list)  # [{name, missing, missing_ratio}]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "total_missing": self.total_missing,
            "total_cells": self.total_cells,
            "missing_ratio": self.missing_ratio,
            "columns_with_missing": self.columns_with_missing,
            "per_column": self.per_column,
        }


@dataclass
class DuplicateSummary:
    status: SectionStatus = SectionStatus.OK
    reason: Optional[str] = None
    duplicate_rows: int = 0
    duplicate_ratio: float = 0.0
    unique_rows: int = 0
    duplicate_ids: List[Dict[str, Any]] = field(default_factory=list)  # [{column, duplicate_count}]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "duplicate_rows": self.duplicate_rows,
            "duplicate_ratio": self.duplicate_ratio,
            "unique_rows": self.unique_rows,
            "duplicate_ids": self.duplicate_ids,
        }


@dataclass
class CardinalityBreakdown:
    status: SectionStatus = SectionStatus.OK
    reason: Optional[str] = None
    low: List[str] = field(default_factory=list)
    medium: List[str] = field(default_factory=list)
    high: List[str] = field(default_factory=list)
    unique: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "low": self.low,
            "medium": self.medium,
            "high": self.high,
            "unique": self.unique,
        }


@dataclass
class CorrelationPair:
    column_a: str
    column_b: str
    coefficient: float
    strength: str  # 'very_strong' | 'strong' | 'moderate' | 'weak' | 'very_weak'
    direction: str  # 'positive' | 'negative'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "column_a": self.column_a,
            "column_b": self.column_b,
            "coefficient": round(self.coefficient, 4),
            "strength": self.strength,
            "direction": self.direction,
        }


@dataclass
class CorrelationSummary:
    status: SectionStatus = SectionStatus.OK
    reason: Optional[str] = None
    columns: List[str] = field(default_factory=list)
    matrix: List[List[float]] = field(default_factory=list)  # square, in `columns` order
    strong_positive: List[CorrelationPair] = field(default_factory=list)
    strong_negative: List[CorrelationPair] = field(default_factory=list)
    top_pairs: List[CorrelationPair] = field(default_factory=list)  # top-N by |coef|

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.value,
            "reason": self.reason,
            "columns": self.columns,
            "matrix": self.matrix,
            "strong_positive": [p.to_dict() for p in self.strong_positive],
            "strong_negative": [p.to_dict() for p in self.strong_negative],
            "top_pairs": [p.to_dict() for p in self.top_pairs],
        }


@dataclass
class QualityScore:
    overall_score: float = 0.0
    grade: QualityGrade = QualityGrade.F
    dimensions: Dict[str, float] = field(default_factory=dict)  # completeness/uniqueness/validity/consistency
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 2),
            "grade": self.grade.value,
            "dimensions": {k: round(v, 2) for k, v in self.dimensions.items()},
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------
@dataclass
class ProfilingResult:
    dataset_id: str
    overview: DatasetOverview
    column_profiles: List[ColumnProfile] = field(default_factory=list)
    missing: MissingSummary = field(default_factory=MissingSummary)
    duplicates: DuplicateSummary = field(default_factory=DuplicateSummary)
    cardinality: CardinalityBreakdown = field(default_factory=CardinalityBreakdown)
    correlations: CorrelationSummary = field(default_factory=CorrelationSummary)
    quality: QualityScore = field(default_factory=QualityScore)
    summary_text: str = ""
    warnings: List[str] = field(default_factory=list)
    profiling_time_ms: int = 0
    version: str = PHASE2_VERSION
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "overview": self.overview.to_dict(),
            "column_profiles": [c.to_dict() for c in self.column_profiles],
            "missing": self.missing.to_dict(),
            "duplicates": self.duplicates.to_dict(),
            "cardinality": self.cardinality.to_dict(),
            "correlations": self.correlations.to_dict(),
            "quality": self.quality.to_dict(),
            "summary_text": self.summary_text,
            "warnings": self.warnings,
            "metadata": {
                "profiling_time_ms": self.profiling_time_ms,
                "version": self.version,
                "generated_at": self.generated_at.isoformat(),
            },
        }
