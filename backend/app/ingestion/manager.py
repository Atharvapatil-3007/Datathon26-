"""IngestionManager — the orchestrator.

End-to-end flow for a file upload:

    validate_file(...)                     # cheap sanity checks
    -> generate dataset_id
    -> upload original to Supabase Storage
    -> insert `datasets` row (status='uploaded')
    -> update status='detecting'
    -> detect_format(...)
    -> update status='processing'
    -> loader.load(...)
    -> loader.get_metadata(...)            # schema + per-format metadata
    -> validate_dataset(...)               # structural warnings/errors
    -> update `datasets` row (status='validated' | 'failed')
    -> return DatasetObject

Every branch that raises after a DB row was inserted will best-effort mark
that row as `failed` and record the error message.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional

from app.database.supabase import SupabaseService, get_supabase_service
from app.ingestion.dataset import (
    DatasetObject,
    DatasetStatus,
    FileFormat,
    SourceType,
)
from app.ingestion.detector import DetectionResult, detect_format
from app.ingestion.exceptions import (
    DatabaseConnectionError,
    DatasetNotFoundError,
    IngestionError,
    InvalidDatasetError,
    StorageUploadError,
)
from app.ingestion.loaders.sql_loader import SQLLoader
from app.ingestion.validator import validate_dataset, validate_file
from app.utils.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Result envelope
# ---------------------------------------------------------------------------
@dataclass
class IngestionResult:
    """What the API layer returns to the client."""

    dataset: DatasetObject
    detection: Optional[DetectionResult]
    duration_ms: int
    storage_path: Optional[str]
    profile: Optional[Dict[str, Any]] = None  # Phase 2 result (JSON-safe dict)

    def to_response(self, *, status: DatasetStatus) -> Dict[str, Any]:
        summary = self.dataset.to_summary()
        # Wrap the schema so callers get a dict with both columns and their
        # names. Matches what we persist to the `datasets.schema` JSONB column.
        schema_payload = {
            "columns": summary["schema"],
            "column_names": self.dataset.column_names,
        }
        return {
            "success": status == DatasetStatus.VALIDATED,
            "dataset_id": self.dataset.dataset_id,
            "filename": self.dataset.source_name,
            "format": self.dataset.format.value,
            "source_type": self.dataset.source_type.value,
            "rows": self.dataset.rows,
            "columns": self.dataset.columns,
            "column_names": self.dataset.column_names,
            "schema": schema_payload,
            "metadata": summary["metadata"],
            "warnings": summary["warnings"],
            "errors": summary["errors"],
            "status": status.value,
            "storage_path": self.storage_path,
            "duration_ms": self.duration_ms,
            "detection": self.detection.to_dict() if self.detection else None,
            "profile": self.profile,
        }


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class IngestionManager:
    """Orchestrates the ingestion pipeline."""

    def __init__(self, supabase: Optional[SupabaseService] = None) -> None:
        self.supabase = supabase or get_supabase_service()

    # ======================================================================
    # File uploads
    # ======================================================================
    def ingest_file(
        self,
        temp_path: str | Path,
        *,
        filename: str,
        mime_type: str,
        user_id: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None,
    ) -> tuple[IngestionResult, DatasetStatus]:
        """Run the full pipeline for a file that FastAPI has already saved
        to `temp_path`. Returns the ingestion result plus the final DB
        status so the API layer can pick the right HTTP code.
        """
        started = time.perf_counter()
        options = options or {}
        temp_path = Path(temp_path)
        dataset_id = str(uuid.uuid4())

        log.info(
            "ingest_started",
            dataset_id=dataset_id,
            filename=filename,
            mime_type=mime_type,
            size=temp_path.stat().st_size if temp_path.exists() else 0,
        )

        # 1. File-level validation ------------------------------------------------
        validate_file(temp_path, filename_hint=filename)

        # 2. Storage upload BEFORE parsing — we always want to preserve the source
        try:
            storage_path = self.supabase.upload_dataset(
                dataset_id=dataset_id,
                local_path=temp_path,
                original_filename=filename,
                content_type=mime_type or "application/octet-stream",
            )
        except StorageUploadError:
            raise

        # 3. Record row (status='uploaded')
        try:
            self.supabase.create_dataset_record(
                dataset_id=dataset_id,
                filename=Path(filename).name,
                original_filename=filename,
                source_type=SourceType.FILE.value,
                file_format=FileFormat.UNKNOWN.value,  # updated after detection
                mime_type=mime_type or "application/octet-stream",
                file_size=int(temp_path.stat().st_size),
                storage_path=storage_path,
                user_id=user_id,
            )
        except DatabaseConnectionError:
            # We already uploaded — clean up the orphan storage object
            self.supabase.delete_storage_object(storage_path)
            raise

        # From here on any failure must mark the row as 'failed'
        detection: Optional[DetectionResult] = None
        profile_payload: Optional[Dict[str, Any]] = None
        dataset = DatasetObject(
            dataset_id=dataset_id,
            source_name=filename,
            source_type=SourceType.FILE,
        )

        try:
            # 4. Detect format
            self.supabase.update_dataset_status(dataset_id, DatasetStatus.DETECTING)
            detection = detect_format(temp_path, filename_hint=filename)
            dataset.format = detection.format
            log.info(
                "format_detected",
                dataset_id=dataset_id,
                format=detection.format.value,
                loader=detection.loader_name,
                reason=detection.reason,
            )

            # 5. Load
            self.supabase.update_dataset_status(dataset_id, DatasetStatus.PROCESSING)
            loader = detection.loader_cls()
            log.info("loader_selected", dataset_id=dataset_id, loader=loader.name)
            loader.load(temp_path, dataset=dataset, options=options)
            loader.get_metadata(dataset)  # schema + format-specific metadata
            log.info(
                "dataset_loaded",
                dataset_id=dataset_id,
                rows=dataset.rows,
                columns=dataset.columns,
            )

            # 6. Dataset-level validation
            validate_dataset(dataset)

            # 7. Persist metadata + mark validated
            self.supabase.update_dataset_metadata(
                dataset, status=DatasetStatus.VALIDATED
            )
            final_status = DatasetStatus.VALIDATED

            # 8. Phase 2 profiling — runs against the in-memory DataFrame so
            # no storage round-trip is needed. Failures never abort Phase 1.
            profile_payload = self._run_profiling(dataset)

        except IngestionError as exc:
            log.error(
                "ingest_failed",
                dataset_id=dataset_id,
                code=exc.code,
                error=exc.message,
            )
            dataset.add_error(exc.message)
            self._safe_mark_failed(dataset, [exc.message])
            final_status = DatasetStatus.FAILED
            duration_ms = int((time.perf_counter() - started) * 1000)
            result = IngestionResult(
                dataset=dataset,
                detection=detection,
                duration_ms=duration_ms,
                storage_path=storage_path,
            )
            # Re-raise so the API returns a proper error response — but the
            # DB row is already updated and the file is preserved.
            exc.details.setdefault("dataset_id", dataset_id)
            exc.details.setdefault("duration_ms", duration_ms)
            raise
        except Exception as exc:  # noqa: BLE001
            log.exception("ingest_unexpected_failure", dataset_id=dataset_id)
            msg = f"Unexpected ingestion failure: {exc}"
            dataset.add_error(msg)
            self._safe_mark_failed(dataset, [msg])
            raise IngestionError(msg, code="INGESTION_ERROR", http_status=500) from exc

        duration_ms = int((time.perf_counter() - started) * 1000)
        log.info(
            "ingest_completed_with_profile" if profile_payload else "ingest_completed",
            dataset_id=dataset_id,
            duration_ms=duration_ms,
            status=final_status.value,
            rows=dataset.rows,
            columns=dataset.columns,
        )
        return (
            IngestionResult(
                dataset=dataset,
                detection=detection,
                duration_ms=duration_ms,
                storage_path=storage_path,
                profile=profile_payload,
            ),
            final_status,
        )

    # ======================================================================
    # External SQL databases (no file upload)
    # ======================================================================
    def ingest_sql(
        self,
        *,
        connection_string: str,
        query: Optional[str] = None,
        table_name: Optional[str] = None,
        row_limit: Optional[int] = None,
        user_id: Optional[str] = None,
    ) -> tuple[IngestionResult, DatasetStatus]:
        """Pull data from an external SQL database via SQLAlchemy.

        No file lives on disk in this path — storage_path stays None on the
        `datasets` row.
        """
        started = time.perf_counter()
        dataset_id = str(uuid.uuid4())
        display_name = table_name or "sql_query"

        log.info("sql_ingest_started", dataset_id=dataset_id, source=display_name)

        # DB row with no storage path
        try:
            self.supabase.create_dataset_record(
                dataset_id=dataset_id,
                filename=display_name,
                original_filename=display_name,
                source_type=SourceType.SQL_DATABASE.value,
                file_format=FileFormat.SQL.value,
                mime_type="application/sql",
                file_size=0,
                storage_path="",
                user_id=user_id,
            )
        except DatabaseConnectionError:
            raise

        dataset = DatasetObject(
            dataset_id=dataset_id,
            source_name=display_name,
            source_type=SourceType.SQL_DATABASE,
            format=FileFormat.SQL,
        )
        profile_payload: Optional[Dict[str, Any]] = None

        try:
            self.supabase.update_dataset_status(dataset_id, DatasetStatus.PROCESSING)
            loader = SQLLoader()
            loader.load(
                source="",
                dataset=dataset,
                options={
                    "connection_string": connection_string,
                    "query": query,
                    "table_name": table_name,
                    "row_limit": row_limit,
                },
            )
            loader.get_metadata(dataset)
            validate_dataset(dataset)
            self.supabase.update_dataset_metadata(dataset, status=DatasetStatus.VALIDATED)
            final_status = DatasetStatus.VALIDATED
            profile_payload = self._run_profiling(dataset)
        except IngestionError as exc:
            log.error("sql_ingest_failed", dataset_id=dataset_id, error=exc.message)
            dataset.add_error(exc.message)
            self._safe_mark_failed(dataset, [exc.message])
            exc.details.setdefault("dataset_id", dataset_id)
            raise
        except Exception as exc:  # noqa: BLE001
            msg = f"Unexpected SQL ingestion failure: {exc}"
            dataset.add_error(msg)
            self._safe_mark_failed(dataset, [msg])
            raise IngestionError(msg, code="INGESTION_ERROR", http_status=500) from exc

        duration_ms = int((time.perf_counter() - started) * 1000)
        return (
            IngestionResult(
                dataset=dataset,
                detection=None,
                duration_ms=duration_ms,
                storage_path=None,
                profile=profile_payload,
            ),
            final_status,
        )

    # ======================================================================
    # Phase 2 - profiling
    # ======================================================================
    def _run_profiling(self, dataset: DatasetObject) -> Optional[Dict[str, Any]]:
        """Run Phase 2 against `dataset.data` (already in memory).

        Failures never abort Phase 1 — they surface as a warning on the
        dataset and profile stays None.
        """
        try:
            from app.profiling.engine import get_profiling_engine  # local to avoid cycle

            result = get_profiling_engine().profile(dataset)
            payload = result.to_dict()
            self.supabase.save_profile(dataset.dataset_id, payload)
            log.info(
                "profile_persisted",
                dataset_id=dataset.dataset_id,
                duration_ms=result.profiling_time_ms,
            )
            return payload
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "phase2_profile_failed_soft",
                dataset_id=dataset.dataset_id,
                error=str(exc),
            )
            dataset.add_warning(f"Phase 2 profiling could not be completed: {exc}")
            return None

    def reprofile_dataset(
        self, dataset_id: str, *, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Re-hydrate a persisted dataset from Supabase Storage and re-profile.

        Used when the caller wants a fresh profile — e.g. after schema tweaks
        in the source system, or when the algorithm changes.
        """
        from app.ingestion.detector import detect_format  # local import
        from app.profiling.engine import get_profiling_engine

        row = self.supabase.get_dataset(dataset_id, user_id=user_id)  # raises if missing
        storage_path = row.get("storage_path")
        if not storage_path:
            raise InvalidDatasetError(
                "Dataset has no storage path (SQL sources cannot be re-profiled without re-connecting)",
                details={"dataset_id": dataset_id},
            )

        # Download to a NamedTemporaryFile
        import tempfile
        from pathlib import Path as _Path

        raw = self.supabase.download_dataset(storage_path)
        suffix = _Path(row.get("original_filename") or storage_path).suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name

        try:
            detection = detect_format(tmp_path, filename_hint=row.get("original_filename"))
            loader = detection.loader_cls()
            dataset = DatasetObject(
                dataset_id=dataset_id,
                source_name=row.get("original_filename") or "",
                source_type=SourceType(row.get("source_type", SourceType.FILE.value)),
                format=detection.format,
            )
            loader.load(tmp_path, dataset=dataset, options=None)
            loader.get_metadata(dataset)
            result = get_profiling_engine().profile(dataset)
            payload = result.to_dict()
            self.supabase.save_profile(dataset_id, payload)
            return payload
        finally:
            try:
                import os
                os.unlink(tmp_path)
            except OSError:
                pass

    def get_dataset_profile(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Return the persisted Phase 2 profile, or None if not profiled yet."""
        return self.supabase.get_profile(dataset_id)

    # ======================================================================
    # Read / delete pass-throughs
    # ======================================================================
    def get_dataset_summary(
        self, dataset_id: str, *, user_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Return the row for `dataset_id` or None if it doesn't exist.

        Softens the underlying service's raise-on-missing behaviour so
        callers can use the "if row is None" idiom. Passing ``user_id``
        also 404s rows belonging to a different owner (F-01).
        """
        try:
            return self.supabase.get_dataset(dataset_id, user_id=user_id)
        except DatasetNotFoundError:
            return None

    def list_datasets(
        self, *, limit: int = 100, offset: int = 0, user_id: Optional[str] = None
    ):
        return self.supabase.list_datasets(
            limit=limit, offset=offset, user_id=user_id
        )

    def delete_dataset(
        self, dataset_id: str, *, user_id: Optional[str] = None
    ) -> None:
        self.supabase.delete_dataset(dataset_id, user_id=user_id)

    # ======================================================================
    # Internals
    # ======================================================================
    def _safe_mark_failed(self, dataset: DatasetObject, errors: list[str]) -> None:
        try:
            # Persist as much metadata as we have; status='failed'
            self.supabase.update_dataset_metadata(dataset, status=DatasetStatus.FAILED)
        except Exception as exc:  # noqa: BLE001
            log.warning(
                "failed_to_mark_dataset_failed",
                dataset_id=dataset.dataset_id,
                error=str(exc),
            )
            # Best-effort minimal status flip
            try:
                self.supabase.update_dataset_status(
                    dataset.dataset_id, DatasetStatus.FAILED, errors=errors
                )
            except Exception:  # noqa: BLE001
                pass


# ---------------------------------------------------------------------------
# Singleton accessor (matches SupabaseService pattern)
# ---------------------------------------------------------------------------
_manager_instance: Optional[IngestionManager] = None


def get_ingestion_manager() -> IngestionManager:
    global _manager_instance
    if _manager_instance is None:
        _manager_instance = IngestionManager()
    return _manager_instance


def reset_ingestion_manager_for_tests() -> None:
    global _manager_instance
    _manager_instance = None
