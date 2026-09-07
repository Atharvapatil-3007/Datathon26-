"""Ingestion package - format detection, validation, loaders, and orchestration."""

from app.ingestion.dataset import DatasetObject, ColumnSchema
from app.ingestion.exceptions import (
    IngestionError,
    UnsupportedFileTypeError,
    InvalidDatasetError,
    FileParsingError,
    EmptyDatasetError,
    CorruptedFileError,
    DatabaseConnectionError,
    StorageUploadError,
    DatasetValidationError,
)

__all__ = [
    "DatasetObject",
    "ColumnSchema",
    "IngestionError",
    "UnsupportedFileTypeError",
    "InvalidDatasetError",
    "FileParsingError",
    "EmptyDatasetError",
    "CorruptedFileError",
    "DatabaseConnectionError",
    "StorageUploadError",
    "DatasetValidationError",
]
