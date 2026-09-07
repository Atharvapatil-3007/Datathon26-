"""Supabase service layer.

Wraps two concerns behind a single facade:

* **Storage** (Supabase Storage bucket for original uploaded files)
* **Metadata** (Supabase PostgreSQL `datasets` table)

Everything else in the codebase talks to `SupabaseService` — no loader or
API route ever imports the Supabase client directly. This keeps
persistence logic in one place and makes it trivial to swap in a mock
service for tests.

If Supabase env vars are missing we transparently fall back to a
local filesystem + in-memory backend so the hackathon build works out of
the box. The fallback is emphatically NOT for production.
"""

from __future__ import annotations

import json
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config.settings import Settings, get_settings
from app.ingestion.dataset import DatasetObject, DatasetStatus
from app.ingestion.exceptions import (
    DatabaseConnectionError,
    DatasetNotFoundError,
    StorageUploadError,
)
from app.utils.logging import get_logger

log = get_logger(__name__)

_DATASETS_TABLE = "datasets"


# ===========================================================================
# Public facade
# ===========================================================================
class SupabaseService:
    """Combined storage + metadata service.

    Instantiate once (see `get_supabase_service()`); safe to share across
    requests. All operations are synchronous — call from FastAPI handlers
    inside `run_in_threadpool` / `asyncio.to_thread` if the endpoint is
    async.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        if self.settings.supabase_configured:
            self._backend: _Backend = _SupabaseBackend(self.settings)
            log.info("supabase_backend_initialized", bucket=self.settings.supabase_storage_bucket)
        else:
            if not self.settings.allow_local_fallback:
                # F-12: refuse to boot with an unconfigured backend in
                # production. Better to fail fast than silently store data on
                # a container's local disk that vanishes on redeploy.
                raise DatabaseConnectionError(
                    "Supabase is not configured and LOCAL_FALLBACK_ENABLED is "
                    "false (or APP_ENV=production). Set SUPABASE_URL + "
                    "SUPABASE_SERVICE_ROLE_KEY, or explicitly opt in with "
                    "LOCAL_FALLBACK_ENABLED=true for non-production use."
                )
            self._backend = _LocalBackend(self.settings)
            log.warning(
                "supabase_not_configured_using_local_fallback",
                storage_dir=str(self.settings.local_storage_path),
                app_env=self.settings.app_env,
            )

    # ---- Storage --------------------------------------------------------
    def generate_storage_path(self, dataset_id: str, original_filename: str) -> str:
        """Return the canonical object path for a dataset upload."""
        safe_name = _sanitize_filename(original_filename)
        return f"datasets/{dataset_id}/original/{safe_name}"

    def upload_dataset(
        self,
        *,
        dataset_id: str,
        local_path: str | Path,
        original_filename: str,
        content_type: str,
    ) -> str:
        """Upload `local_path` to storage and return the storage path."""
        storage_path = self.generate_storage_path(dataset_id, original_filename)
        try:
            self._backend.upload(Path(local_path), storage_path, content_type)
        except Exception as exc:  # noqa: BLE001
            raise StorageUploadError(f"Storage upload failed: {exc}") from exc
        log.info(
            "storage_upload_complete",
            dataset_id=dataset_id,
            storage_path=storage_path,
            size=Path(local_path).stat().st_size,
        )
        return storage_path

    def delete_storage_object(self, storage_path: str) -> None:
        try:
            self._backend.delete(storage_path)
        except Exception as exc:  # noqa: BLE001
            # Non-fatal — log and swallow so DB cleanup can proceed
            log.warning("storage_delete_failed", storage_path=storage_path, error=str(exc))

    # ---- Metadata / datasets table -------------------------------------
    def create_dataset_record(
        self,
        *,
        dataset_id: str,
        original_filename: str,
        filename: str,
        source_type: str,
        file_format: str,
        mime_type: str,
        file_size: int,
        storage_path: str,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        now = _now_iso()
        row = {
            "id": dataset_id,
            "user_id": user_id,
            "filename": filename,
            "original_filename": original_filename,
            "source_type": source_type,
            "file_format": file_format,
            "mime_type": mime_type,
            "file_size": int(file_size),
            "storage_path": storage_path,
            "row_count": None,
            "column_count": None,
            "status": DatasetStatus.UPLOADED.value,
            "schema": None,
            "metadata": None,
            "warnings": [],
            "errors": [],
            "created_at": now,
            "updated_at": now,
        }
        try:
            self._backend.insert_dataset(row)
        except Exception as exc:  # noqa: BLE001
            raise DatabaseConnectionError(f"Could not insert dataset row: {exc}") from exc
        return row

    def update_dataset_status(
        self,
        dataset_id: str,
        status: DatasetStatus,
        *,
        errors: Optional[List[str]] = None,
    ) -> None:
        patch: Dict[str, Any] = {"status": status.value, "updated_at": _now_iso()}
        if errors is not None:
            patch["errors"] = errors
        try:
            self._backend.update_dataset(dataset_id, patch)
        except Exception as exc:  # noqa: BLE001
            raise DatabaseConnectionError(
                f"Failed to update status for dataset {dataset_id}: {exc}"
            ) from exc

    # ---- Phase 2 profile persistence -----------------------------------
    def save_profile(self, dataset_id: str, profile_payload: Dict[str, Any]) -> None:
        """Persist a Phase 2 profiling result into `datasets.profile` (JSONB)."""
        patch = {
            "profile": profile_payload,
            "profiled_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        try:
            self._backend.update_dataset(dataset_id, patch)
        except Exception as exc:  # noqa: BLE001
            raise DatabaseConnectionError(
                f"Failed to save profile for dataset {dataset_id}: {exc}"
            ) from exc

    def get_profile(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        """Fetch the persisted profile payload, or None if not profiled yet."""
        row = self._backend.get_dataset(dataset_id)
        if row is None:
            raise DatasetNotFoundError(f"Dataset '{dataset_id}' not found")
        return row.get("profile")

    # ---- Original file re-download (used when re-profiling) -------------
    def download_dataset(self, storage_path: str) -> bytes:
        """Return the raw bytes of an uploaded dataset."""
        try:
            return self._backend.download(storage_path)
        except Exception as exc:  # noqa: BLE001
            raise StorageUploadError(
                f"Failed to download dataset from storage: {exc}"
            ) from exc

    def download_dataset_to_file(self, storage_path: str, dest_path: Path) -> None:
        """Stream a stored object to a local file (F-07 chunked download)."""
        try:
            self._backend.download_to_file(storage_path, Path(dest_path))
        except Exception as exc:  # noqa: BLE001
            raise StorageUploadError(
                f"Failed to download dataset from storage: {exc}"
            ) from exc

    def update_dataset_metadata(
        self,
        dataset_object: DatasetObject,
        *,
        status: DatasetStatus = DatasetStatus.VALIDATED,
    ) -> None:
        """Persist the outcome of a successful (or partly successful) ingest."""
        patch: Dict[str, Any] = {
            "row_count": dataset_object.rows,
            "column_count": dataset_object.columns,
            "schema": {
                "columns": dataset_object.schema_as_dict_list(),
                "column_names": dataset_object.column_names,
            },
            "metadata": dataset_object.metadata,
            "warnings": dataset_object.warnings,
            "errors": dataset_object.errors,
            "status": status.value,
            "updated_at": _now_iso(),
        }
        try:
            self._backend.update_dataset(dataset_object.dataset_id, patch)
        except Exception as exc:  # noqa: BLE001
            raise DatabaseConnectionError(
                f"Failed to persist metadata for dataset {dataset_object.dataset_id}: {exc}"
            ) from exc

    def get_dataset(
        self, dataset_id: str, *, user_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetch a single dataset row.

        When ``user_id`` is provided (F-01: app-layer isolation) the caller
        is asserting ownership. A row belonging to a different user is
        reported as not-found so we never leak the existence of another
        user's dataset. This is the foundation used by every read / delete
        / analysis path; upgrading to JWT-derived identity later is a
        drop-in change at the API dependency layer.
        """
        row = self._backend.get_dataset(dataset_id)
        if row is None:
            raise DatasetNotFoundError(f"Dataset '{dataset_id}' not found")
        if user_id is not None and _owner_of(row) != user_id:
            raise DatasetNotFoundError(f"Dataset '{dataset_id}' not found")
        return row

    def list_datasets(
        self,
        limit: int = 100,
        offset: int = 0,
        *,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        rows = self._backend.list_datasets(limit=limit, offset=offset, user_id=user_id)
        return rows

    def delete_dataset(
        self, dataset_id: str, *, user_id: Optional[str] = None
    ) -> None:
        row = self._backend.get_dataset(dataset_id)
        if row is None:
            raise DatasetNotFoundError(f"Dataset '{dataset_id}' not found")
        if user_id is not None and _owner_of(row) != user_id:
            raise DatasetNotFoundError(f"Dataset '{dataset_id}' not found")
        storage_path = row.get("storage_path")
        if storage_path:
            self.delete_storage_object(storage_path)
        try:
            self._backend.delete_dataset(dataset_id)
        except Exception as exc:  # noqa: BLE001
            raise DatabaseConnectionError(
                f"Failed to delete dataset row {dataset_id}: {exc}"
            ) from exc

    # ---- Test / dev helper ---------------------------------------------
    @property
    def is_local_fallback(self) -> bool:
        return isinstance(self._backend, _LocalBackend)


# ===========================================================================
# Backend interface + implementations
# ===========================================================================
class _Backend:
    """Minimal duck-typed interface — no ABCMeta to keep introspection simple."""

    # storage
    def upload(self, local_path: Path, storage_path: str, content_type: str) -> None:
        raise NotImplementedError

    def download(self, storage_path: str) -> bytes:
        raise NotImplementedError

    def download_to_file(self, storage_path: str, dest_path: Path) -> None:
        """Stream a stored object to ``dest_path`` in fixed-size chunks.

        Default fallback loops over ``download()`` (backend-specific
        overrides should perform a real streaming read).
        """
        raise NotImplementedError

    def delete(self, storage_path: str) -> None:
        raise NotImplementedError

    # metadata
    def insert_dataset(self, row: Dict[str, Any]) -> None:
        raise NotImplementedError

    def update_dataset(self, dataset_id: str, patch: Dict[str, Any]) -> None:
        raise NotImplementedError

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        raise NotImplementedError

    def list_datasets(
        self, *, limit: int, offset: int, user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def delete_dataset(self, dataset_id: str) -> None:
        raise NotImplementedError


# ---------------------------------------------------------------------------
# Supabase (real) backend
# ---------------------------------------------------------------------------
class _SupabaseBackend(_Backend):
    def __init__(self, settings: Settings) -> None:
        try:
            from supabase import create_client, Client  # local import — optional dep
        except ImportError as exc:  # pragma: no cover
            raise DatabaseConnectionError(
                "The `supabase` package is not installed. `pip install supabase`."
            ) from exc

        self.settings = settings
        self.bucket = settings.supabase_storage_bucket
        self._bucket_verified = False
        try:
            self.client: "Client" = create_client(  # type: ignore[name-defined]
                settings.supabase_url,
                settings.supabase_service_role_key,
            )
        except Exception as exc:  # noqa: BLE001
            raise DatabaseConnectionError(
                "Failed to initialize Supabase client "
                f"({type(exc).__name__}: {exc}). "
                "Check that SUPABASE_URL points at your project (e.g. "
                "https://xxxxx.supabase.co) and that SUPABASE_SERVICE_ROLE_KEY "
                "is the long 'service_role' JWT from Project Settings -> API. "
                "To fall back to local storage for dev, blank both values in .env."
            ) from exc

    # ---- Storage -------------------------------------------------------
    def _ensure_bucket(self) -> None:
        """Create the storage bucket if it doesn't already exist.

        Runs at most once per process. Uses the service_role key, which has
        the privileges to manage buckets. If bucket creation fails (e.g. RLS
        prevents it), the exception surfaces at first upload and the user
        can create it manually in the Supabase dashboard.
        """
        if self._bucket_verified:
            return
        try:
            existing = self.client.storage.list_buckets()
            names = {b.name if hasattr(b, "name") else b.get("name") for b in existing}
        except Exception:  # noqa: BLE001
            # If listing fails we still attempt a create; harmless if it exists.
            names = set()

        if self.bucket not in names:
            try:
                self.client.storage.create_bucket(
                    self.bucket,
                    options={"public": False},
                )
                log.info("supabase_bucket_created", bucket=self.bucket)
            except Exception as exc:  # noqa: BLE001
                msg = str(exc)
                # Race / already exists — treat as success
                if "already exists" in msg.lower() or "duplicate" in msg.lower():
                    pass
                else:
                    raise DatabaseConnectionError(
                        f"Bucket '{self.bucket}' is missing and could not be "
                        f"auto-created ({msg}). Create it manually in the "
                        "Supabase dashboard: Storage -> New bucket -> "
                        f"name='{self.bucket}', public=off."
                    ) from exc
        self._bucket_verified = True

    def upload(self, local_path: Path, storage_path: str, content_type: str) -> None:
        self._ensure_bucket()
        # F-07: hand the Path directly so storage3 opens the file and the
        # underlying httpx multipart encoder streams chunks over the wire.
        # This keeps peak memory bounded regardless of upload size.
        self.client.storage.from_(self.bucket).upload(
            path=storage_path,
            file=local_path,
            file_options={"content-type": content_type, "upsert": "true"},
        )

    def download(self, storage_path: str) -> bytes:
        # Kept for callers who genuinely want the bytes (small profiles).
        return self.client.storage.from_(self.bucket).download(storage_path)

    def download_to_file(self, storage_path: str, dest_path: Path) -> None:
        """Stream a stored object straight to ``dest_path`` (F-07).

        Uses ``httpx.stream`` against the signed URL so we never hold the
        whole payload in memory. Chunk size is 1 MiB.
        """
        try:
            import httpx  # bundled with the supabase client
        except ImportError as exc:  # pragma: no cover
            raise DatabaseConnectionError("httpx is required for streaming download") from exc

        signed = self.client.storage.from_(self.bucket).create_signed_url(
            storage_path, expires_in=300
        )
        signed_url = signed.get("signedURL") or signed.get("signed_url") or signed.get("signedUrl")
        if not signed_url:
            # Fall back to non-streaming path if the response shape changes.
            dest_path.write_bytes(self.download(storage_path))
            return

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        with httpx.stream("GET", signed_url, timeout=60.0) as response:
            response.raise_for_status()
            with open(dest_path, "wb") as out:
                for chunk in response.iter_bytes(chunk_size=1024 * 1024):
                    if chunk:
                        out.write(chunk)

    def delete(self, storage_path: str) -> None:
        self.client.storage.from_(self.bucket).remove([storage_path])

    # ---- Metadata ------------------------------------------------------
    def insert_dataset(self, row: Dict[str, Any]) -> None:
        self.client.table(_DATASETS_TABLE).insert(row).execute()

    def update_dataset(self, dataset_id: str, patch: Dict[str, Any]) -> None:
        self.client.table(_DATASETS_TABLE).update(patch).eq("id", dataset_id).execute()

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        resp = (
            self.client.table(_DATASETS_TABLE)
            .select("*")
            .eq("id", dataset_id)
            .limit(1)
            .execute()
        )
        rows = getattr(resp, "data", None) or []
        return rows[0] if rows else None

    def list_datasets(
        self, *, limit: int, offset: int, user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        q = (
            self.client.table(_DATASETS_TABLE)
            .select("*")
            .order("created_at", desc=True)
        )
        if user_id is not None:
            q = q.eq("user_id", user_id)
        resp = q.range(offset, offset + limit - 1).execute()
        return list(getattr(resp, "data", None) or [])

    def delete_dataset(self, dataset_id: str) -> None:
        self.client.table(_DATASETS_TABLE).delete().eq("id", dataset_id).execute()


# ---------------------------------------------------------------------------
# Local filesystem fallback (dev + tests only)
# ---------------------------------------------------------------------------
class _LocalBackend(_Backend):
    """Files on disk + a JSON side-table. Not concurrent-safe across processes."""

    def __init__(self, settings: Settings) -> None:
        self.root = settings.local_storage_path
        self.storage_root = self.root / "storage"
        self.metadata_file = self.root / "datasets.json"
        self.storage_root.mkdir(parents=True, exist_ok=True)
        if not self.metadata_file.exists():
            self.metadata_file.write_text("[]", encoding="utf-8")
        self._lock = threading.Lock()

    # ---- Storage -------------------------------------------------------
    def upload(self, local_path: Path, storage_path: str, content_type: str) -> None:
        target = (self.storage_root / storage_path).resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, target)

    def download(self, storage_path: str) -> bytes:
        target = (self.storage_root / storage_path).resolve()
        if not target.is_file():
            raise StorageUploadError(f"Storage object not found: {storage_path}")
        return target.read_bytes()

    def download_to_file(self, storage_path: str, dest_path: Path) -> None:
        target = (self.storage_root / storage_path).resolve()
        if not target.is_file():
            raise StorageUploadError(f"Storage object not found: {storage_path}")
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        # shutil.copyfile uses a 64 KB buffer under the hood \u2014 chunked I/O by design.
        shutil.copyfile(target, dest_path)

    def delete(self, storage_path: str) -> None:
        target = (self.storage_root / storage_path).resolve()
        if target.is_file():
            target.unlink(missing_ok=True)

    # ---- Metadata ------------------------------------------------------
    def _read_all(self) -> List[Dict[str, Any]]:
        try:
            return json.loads(self.metadata_file.read_text(encoding="utf-8") or "[]")
        except json.JSONDecodeError:
            return []

    def _write_all(self, rows: List[Dict[str, Any]]) -> None:
        tmp = self.metadata_file.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(rows, default=_json_default), encoding="utf-8")
        tmp.replace(self.metadata_file)

    def insert_dataset(self, row: Dict[str, Any]) -> None:
        with self._lock:
            rows = self._read_all()
            rows.append(row)
            self._write_all(rows)

    def update_dataset(self, dataset_id: str, patch: Dict[str, Any]) -> None:
        with self._lock:
            rows = self._read_all()
            for r in rows:
                if r.get("id") == dataset_id:
                    r.update(patch)
                    break
            else:
                raise DatasetNotFoundError(f"Dataset '{dataset_id}' not found")
            self._write_all(rows)

    def get_dataset(self, dataset_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            for r in self._read_all():
                if r.get("id") == dataset_id:
                    return dict(r)
        return None

    def list_datasets(
        self, *, limit: int, offset: int, user_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        with self._lock:
            rows = self._read_all()
        if user_id is not None:
            rows = [r for r in rows if _owner_of(r) == user_id]
        rows.sort(key=lambda r: r.get("created_at", ""), reverse=True)
        return rows[offset : offset + limit]

    def delete_dataset(self, dataset_id: str) -> None:
        with self._lock:
            rows = self._read_all()
            new_rows = [r for r in rows if r.get("id") != dataset_id]
            if len(new_rows) == len(rows):
                raise DatasetNotFoundError(f"Dataset '{dataset_id}' not found")
            self._write_all(new_rows)


# ===========================================================================
# Utilities
# ===========================================================================
def _owner_of(row: Dict[str, Any]) -> Optional[str]:
    """Return the user_id stored on a dataset row (None if not tagged)."""
    return row.get("user_id")


_INVALID_FILENAME_CHARS = str.maketrans({c: "_" for c in '<>:"/\\|?*\n\r\t'})


def _sanitize_filename(name: str) -> str:
    """Replace path separators and dangerous characters; enforce a length cap."""
    if not name:
        return f"upload-{uuid.uuid4().hex}.bin"
    clean = Path(name).name.translate(_INVALID_FILENAME_CHARS).strip(" .")
    return clean[:200] or f"upload-{uuid.uuid4().hex}.bin"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _json_default(v: Any) -> Any:
    if isinstance(v, (datetime,)):
        return v.isoformat()
    return str(v)


# ===========================================================================
# Module-level singleton
# ===========================================================================
_service_instance: Optional[SupabaseService] = None
_service_lock = threading.Lock()


def get_supabase_service() -> SupabaseService:
    """Return the process-wide `SupabaseService` (lazy singleton)."""
    global _service_instance
    if _service_instance is None:
        with _service_lock:
            if _service_instance is None:
                _service_instance = SupabaseService()
    return _service_instance


def reset_supabase_service_for_tests() -> None:
    """Test-only hook to clear the module singleton."""
    global _service_instance
    with _service_lock:
        _service_instance = None
