"""Standardized in-memory representation of an ingested dataset.

Phase 2 (Data Understanding) will consume `DatasetObject` and must NOT
care what the original source was (CSV, Excel, SQL, ZIP, ...). Everything
loader-specific is hidden behind this interface.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

import pandas as pd


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------
class SourceType(str, Enum):
    """Where the data originated."""

    FILE = "file"
    SQL_DATABASE = "sql_database"
    ZIP_ARCHIVE = "zip_archive"


class FileFormat(str, Enum):
    """Concrete on-disk / on-wire format detected by the detector."""

    CSV = "csv"
    TSV = "tsv"
    EXCEL_XLSX = "xlsx"
    EXCEL_XLS = "xls"
    JSON = "json"
    JSONL = "jsonl"
    PARQUET = "parquet"
    SQLITE = "sqlite"
    ZIP = "zip"
    SQL = "sql"
    UNKNOWN = "unknown"


class DatasetStatus(str, Enum):
    """Persisted lifecycle status of a dataset row in Supabase."""

    UPLOADED = "uploaded"
    DETECTING = "detecting"
    PROCESSING = "processing"
    VALIDATED = "validated"
    FAILED = "failed"


class InferredType(str, Enum):
    """Coarse-grained data type inferred for each column."""

    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    DATE = "date"
    STRING = "string"
    CATEGORICAL = "categorical"
    IDENTIFIER = "identifier"
    TEXT = "text"
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Per-column schema
# ---------------------------------------------------------------------------
@dataclass
class ColumnSchema:
    """Lightweight per-column metadata produced during Phase 1.

    Deliberately conservative — Phase 3 handles heavy feature engineering.
    """

    name: str
    dtype: str  # native pandas/polars dtype string (e.g. 'int64')
    inferred_type: InferredType
    nullable: bool
    unique_count: int
    missing_count: int
    missing_ratio: float
    sample_values: List[Any] = field(default_factory=list)

    is_identifier: bool = False
    is_categorical: bool = False
    is_numerical: bool = False
    is_datetime: bool = False
    is_text: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dtype": self.dtype,
            "inferred_type": self.inferred_type.value,
            "nullable": self.nullable,
            "unique_count": self.unique_count,
            "missing_count": self.missing_count,
            "missing_ratio": self.missing_ratio,
            "sample_values": self.sample_values,
            "is_identifier": self.is_identifier,
            "is_categorical": self.is_categorical,
            "is_numerical": self.is_numerical,
            "is_datetime": self.is_datetime,
            "is_text": self.is_text,
        }


# ---------------------------------------------------------------------------
# DatasetObject
# ---------------------------------------------------------------------------
@dataclass
class DatasetObject:
    """The single artefact passed from Phase 1 → Phase 2.

    `data` is a pandas.DataFrame for structured/tabular sources. Loaders
    that produce Polars frames should convert once, at the loader boundary,
    to keep Phase 2 uniform.
    """

    # Identity
    dataset_id: str = field(default_factory=lambda: str(uuid.uuid4()))

    # Payload
    data: Optional[pd.DataFrame] = None

    # Provenance
    source_type: SourceType = SourceType.FILE
    source_name: str = ""  # original filename / connection identifier
    format: FileFormat = FileFormat.UNKNOWN

    # Shape (populated post-load)
    rows: int = 0
    columns: int = 0
    column_names: List[str] = field(default_factory=list)

    # Schema / metadata
    schema: List[ColumnSchema] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # Diagnostics
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    # Book-keeping
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ------------------------------------------------------------------
    # Convenience helpers
    # ------------------------------------------------------------------
    def add_warning(self, msg: str) -> None:
        if msg and msg not in self.warnings:
            self.warnings.append(msg)

    def add_error(self, msg: str) -> None:
        if msg and msg not in self.errors:
            self.errors.append(msg)

    def refresh_shape(self) -> None:
        """Sync `rows`, `columns`, `column_names` with `data`."""
        if self.data is None:
            self.rows = 0
            self.columns = 0
            self.column_names = []
            return
        self.rows = int(len(self.data))
        self.columns = int(len(self.data.columns))
        self.column_names = [str(c) for c in self.data.columns]

    def schema_as_dict_list(self) -> List[Dict[str, Any]]:
        return [c.to_dict() for c in self.schema]

    def to_summary(self) -> Dict[str, Any]:
        """Serializable summary — does NOT include the raw dataframe."""
        return {
            "dataset_id": self.dataset_id,
            "source_type": self.source_type.value,
            "source_name": self.source_name,
            "format": self.format.value,
            "rows": self.rows,
            "columns": self.columns,
            "column_names": self.column_names,
            "schema": self.schema_as_dict_list(),
            "metadata": self.metadata,
            "warnings": self.warnings,
            "errors": self.errors,
            "created_at": self.created_at.isoformat(),
        }
