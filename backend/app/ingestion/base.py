"""Abstract loader interface.

Every concrete loader (CSVLoader, ExcelLoader, ...) subclasses `DataLoader`
and speaks the same small vocabulary:

* `supports(format)` -> bool
* `load(source, options)` -> DatasetObject (with `.data` populated)
* `validate(dataset)` -> DatasetObject (with warnings/errors appended)
* `get_metadata(dataset)` -> DatasetObject (with `.schema` + `.metadata` filled)

The `IngestionManager` orchestrates these three phases.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional, Union

from app.ingestion.dataset import DatasetObject, FileFormat


LoadSource = Union[str, Path]


class DataLoader(ABC):
    """Base class for all data loaders."""

    #: Set of `FileFormat` values this loader can handle.
    supported_formats: frozenset[FileFormat] = frozenset()

    #: Human-friendly loader name used in metadata + logs.
    name: str = "DataLoader"

    # ------------------------------------------------------------------
    # Static / class helpers
    # ------------------------------------------------------------------
    @classmethod
    def supports(cls, fmt: FileFormat) -> bool:
        """Return True if this loader handles `fmt`."""
        return fmt in cls.supported_formats

    # ------------------------------------------------------------------
    # Instance interface
    # ------------------------------------------------------------------
    @abstractmethod
    def load(
        self,
        source: LoadSource,
        *,
        dataset: DatasetObject,
        options: Optional[Dict[str, Any]] = None,
    ) -> DatasetObject:
        """Read `source` and populate `dataset.data` + basic metadata.

        The loader MUST NOT mutate the source file on disk. It should
        respect `options` where relevant (e.g. sheet name for Excel,
        table name for SQLite).
        """

    def validate(self, dataset: DatasetObject) -> DatasetObject:  # noqa: D401
        """Loader-specific validation hook. Default: no-op.

        Cross-cutting validation lives in `app.ingestion.validator`.
        """
        return dataset

    def get_metadata(self, dataset: DatasetObject) -> DatasetObject:
        """Populate `dataset.schema` and generic metadata.

        Default implementation infers schema from `dataset.data`; subclasses
        may add format-specific keys to `dataset.metadata`.
        """
        from app.ingestion.schema import infer_schema  # local import avoids cycles

        if dataset.data is not None:
            dataset.refresh_shape()
            dataset.schema = infer_schema(dataset.data)
            dataset.metadata.setdefault("loader", self.name)
        return dataset
