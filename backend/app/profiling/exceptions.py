"""Phase 2-specific exceptions.

Kept intentionally lightweight — the engine's per-section try/except means
most failures are captured *inside* the result under a `status: unavailable`
marker rather than propagated as exceptions.
"""

from __future__ import annotations

from app.ingestion.exceptions import IngestionError


class ProfilingError(IngestionError):
    """A profiling operation failed in a way that cannot be recovered from."""

    code = "PROFILING_ERROR"
    http_status = 422


class ProfileNotFoundError(IngestionError):
    """Requested profile has not been generated yet."""

    code = "PROFILE_NOT_FOUND"
    http_status = 404
