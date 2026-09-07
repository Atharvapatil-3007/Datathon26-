"""Ingestion-specific exception hierarchy.

Every exception carries a stable machine-readable `code`. The FastAPI error
handler converts these into structured JSON so the frontend never sees raw
Python tracebacks.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class IngestionError(Exception):
    """Base class for all ingestion errors."""

    code: str = "INGESTION_ERROR"
    http_status: int = 400

    def __init__(
        self,
        message: str,
        *,
        code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        http_status: Optional[int] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if http_status is not None:
            self.http_status = http_status
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class UnsupportedFileTypeError(IngestionError):
    code = "UNSUPPORTED_FILE_TYPE"
    http_status = 415


class InvalidDatasetError(IngestionError):
    code = "INVALID_DATASET"
    http_status = 422


class FileParsingError(IngestionError):
    code = "FILE_PARSING_ERROR"
    http_status = 422


class EmptyDatasetError(IngestionError):
    code = "EMPTY_DATASET"
    http_status = 422


class CorruptedFileError(IngestionError):
    code = "CORRUPTED_FILE"
    http_status = 422


class DatabaseConnectionError(IngestionError):
    code = "DATABASE_CONNECTION_ERROR"
    http_status = 503


class StorageUploadError(IngestionError):
    code = "STORAGE_UPLOAD_ERROR"
    http_status = 503


class DatasetValidationError(IngestionError):
    code = "DATASET_VALIDATION_ERROR"
    http_status = 422


class FileTooLargeError(IngestionError):
    code = "FILE_TOO_LARGE"
    http_status = 413


class UnsafeArchiveError(IngestionError):
    """Raised when a ZIP archive is unsafe (path traversal, zip-bomb, etc.)."""

    code = "UNSAFE_ARCHIVE"
    http_status = 422


class DatasetNotFoundError(IngestionError):
    code = "DATASET_NOT_FOUND"
    http_status = 404
