"""Phase 3 exception hierarchy.

Inherits from Phase 1's ``IngestionError`` so the FastAPI global error
handler already knows how to convert them into structured JSON.
"""

from __future__ import annotations

from app.ingestion.exceptions import IngestionError


class AnalysisError(IngestionError):
    """Base class for all Phase 3 errors."""

    code = "ANALYSIS_ERROR"
    http_status = 422


class AnalysisNotSupportedError(AnalysisError):
    """The dataset simply doesn't contain enough for a given mode."""

    code = "ANALYSIS_NOT_SUPPORTED"
    http_status = 422


class IncompatibleDatasetsError(AnalysisError):
    """Two datasets can't be meaningfully combined / compared."""

    code = "INCOMPATIBLE_DATASETS"
    http_status = 422


class InsufficientDataError(AnalysisError):
    """A required metric or field is missing."""

    code = "INSUFFICIENT_DATA"
    http_status = 422
