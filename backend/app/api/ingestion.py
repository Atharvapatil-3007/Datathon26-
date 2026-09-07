"""HTTP API for the ingestion pipeline.

Routes:

    POST   /api/v1/ingestion/upload      Upload a file
    POST   /api/v1/ingestion/sql         Ingest from an external SQL DB
    GET    /api/v1/datasets              List datasets
    GET    /api/v1/datasets/{id}         Fetch a single dataset record
    DELETE /api/v1/datasets/{id}         Delete a dataset (storage + row)
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.config.settings import Settings, get_settings
from app.ingestion.exceptions import DatasetNotFoundError, FileTooLargeError, IngestionError
from app.ingestion.manager import IngestionManager, get_ingestion_manager
from app.utils.logging import get_logger

log = get_logger(__name__)


# ============================================================================
# Pydantic response models (OpenAPI docs)
# ============================================================================
# `schema` shadows a deprecated BaseModel method in Pydantic v2, so we keep
# the Python attribute as `schema_` and use aliases so the wire format still
# reads/writes `"schema"` as the API spec requires.
class IngestionResponse(BaseModel):
    success: bool
    dataset_id: str
    filename: str
    format: str
    source_type: str
    rows: int
    columns: int
    column_names: List[str]
    schema_: Optional[Dict[str, Any]] = Field(
        default=None, alias="schema", serialization_alias="schema"
    )
    metadata: Dict[str, Any] = {}
    warnings: List[str] = []
    errors: List[str] = []
    status: str
    storage_path: Optional[str] = None
    duration_ms: int
    detection: Optional[Dict[str, Any]] = None
    profile: Optional[Dict[str, Any]] = None  # Phase 2 result (may be None on soft failure)

    model_config = {"populate_by_name": True, "extra": "ignore"}


class ProfileResponse(BaseModel):
    """Response for Phase 2 profile endpoints."""

    dataset_id: str
    profile: Optional[Dict[str, Any]] = None
    profiled_at: Optional[str] = None

    model_config = {"extra": "allow"}


class DatasetSummary(BaseModel):
    id: str
    filename: str
    original_filename: str
    source_type: str
    file_format: str
    mime_type: str
    file_size: int
    storage_path: Optional[str] = None
    row_count: Optional[int] = None
    column_count: Optional[int] = None
    status: str
    schema_: Optional[Dict[str, Any]] = Field(
        default=None, alias="schema", serialization_alias="schema"
    )
    metadata: Optional[Dict[str, Any]] = None
    warnings: List[str] = []
    errors: List[str] = []
    created_at: str
    updated_at: str
    user_id: Optional[str] = None

    model_config = {"populate_by_name": True, "extra": "allow"}


class SQLIngestRequest(BaseModel):
    connection_string: str = Field(
        ...,
        description="SQLAlchemy URL, e.g. postgresql+psycopg2://user:pass@host:5432/db",
    )
    query: Optional[str] = None
    table_name: Optional[str] = None
    row_limit: Optional[int] = Field(default=None, ge=1, le=1_000_000)


# ============================================================================
# Routers — keep upload and read paths separate for readability
# ============================================================================
router_ingestion = APIRouter(prefix="/ingestion", tags=["ingestion"])
router_datasets = APIRouter(prefix="/datasets", tags=["datasets"])


# ----------------------------------------------------------------------------
# Upload
# ----------------------------------------------------------------------------
@router_ingestion.post(
    "/upload",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a dataset file and ingest it",
)
async def upload_dataset(
    file: UploadFile = File(..., description="Dataset file to ingest"),
    sheet_name: Optional[str] = Form(default=None, description="Excel sheet to load"),
    table_name: Optional[str] = Form(default=None, description="SQLite table to load"),
    delimiter: Optional[str] = Form(default=None, description="Override CSV delimiter"),
    encoding: Optional[str] = Form(default=None, description="Override CSV encoding"),
    member: Optional[str] = Form(default=None, description="ZIP member filename"),
    user_id: Optional[str] = Form(default=None, description="Auth-ready user identifier"),
    settings: Settings = Depends(get_settings),
    manager: IngestionManager = Depends(get_ingestion_manager),
) -> IngestionResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="Upload is missing a filename")

    options: Dict[str, Any] = {}
    if sheet_name:
        options["sheet_name"] = sheet_name
    if table_name:
        options["table_name"] = table_name
    if delimiter:
        options["delimiter"] = delimiter
    if encoding:
        options["encoding"] = encoding
    if member:
        options["member"] = member

    temp_path = await _save_upload_to_temp(file, settings.max_upload_size_bytes)
    log.info(
        "upload_received",
        filename=file.filename,
        content_type=file.content_type,
        temp_path=str(temp_path),
    )

    try:
        result, final_status = await run_in_threadpool(
            manager.ingest_file,
            str(temp_path),
            filename=file.filename,
            mime_type=file.content_type or "application/octet-stream",
            user_id=user_id,
            options=options,
        )
    finally:
        _cleanup_temp(temp_path)

    return IngestionResponse.model_validate(result.to_response(status=final_status))


# ----------------------------------------------------------------------------
# SQL ingest (no file)
# ----------------------------------------------------------------------------
@router_ingestion.post(
    "/sql",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Ingest a dataset from an external SQL database",
)
async def ingest_sql(
    payload: SQLIngestRequest,
    user_id: Optional[str] = Query(default=None),
    manager: IngestionManager = Depends(get_ingestion_manager),
) -> IngestionResponse:
    if not payload.query and not payload.table_name:
        raise HTTPException(
            status_code=400,
            detail="Provide either `query` or `table_name`",
        )

    result, final_status = await run_in_threadpool(
        manager.ingest_sql,
        connection_string=payload.connection_string,
        query=payload.query,
        table_name=payload.table_name,
        row_limit=payload.row_limit,
        user_id=user_id,
    )
    return IngestionResponse.model_validate(result.to_response(status=final_status))


# ----------------------------------------------------------------------------
# Read / list / delete
# ----------------------------------------------------------------------------
@router_datasets.get(
    "",
    response_model=List[DatasetSummary],
    summary="List ingested datasets (newest first)",
)
async def list_datasets(
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    manager: IngestionManager = Depends(get_ingestion_manager),
) -> List[DatasetSummary]:
    rows = await run_in_threadpool(manager.list_datasets, limit=limit, offset=offset)
    return [DatasetSummary.model_validate(r) for r in rows]


@router_datasets.get(
    "/{dataset_id}",
    response_model=DatasetSummary,
    summary="Fetch a single dataset by id",
)
async def get_dataset(
    dataset_id: str,
    manager: IngestionManager = Depends(get_ingestion_manager),
) -> DatasetSummary:
    row = await run_in_threadpool(manager.get_dataset_summary, dataset_id)
    if not row:
        raise DatasetNotFoundError(f"Dataset '{dataset_id}' not found")
    return DatasetSummary.model_validate(row)


@router_datasets.delete(
    "/{dataset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a dataset (storage object + metadata row)",
)
async def delete_dataset(
    dataset_id: str,
    manager: IngestionManager = Depends(get_ingestion_manager),
):
    await run_in_threadpool(manager.delete_dataset, dataset_id)
    return None


# ----------------------------------------------------------------------------
# Phase 2 - Profile endpoints
# ----------------------------------------------------------------------------
@router_datasets.get(
    "/{dataset_id}/profile",
    response_model=ProfileResponse,
    summary="Get the Phase 2 profiling result for a dataset",
)
async def get_profile(
    dataset_id: str,
    manager: IngestionManager = Depends(get_ingestion_manager),
) -> ProfileResponse:
    row = await run_in_threadpool(manager.get_dataset_summary, dataset_id)
    if row is None:
        raise DatasetNotFoundError(f"Dataset '{dataset_id}' not found")
    return ProfileResponse(
        dataset_id=dataset_id,
        profile=row.get("profile"),
        profiled_at=row.get("profiled_at"),
    )


@router_datasets.post(
    "/{dataset_id}/reprofile",
    response_model=ProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Re-run Phase 2 profiling by re-loading the dataset from storage",
)
async def reprofile(
    dataset_id: str,
    manager: IngestionManager = Depends(get_ingestion_manager),
) -> ProfileResponse:
    payload = await run_in_threadpool(manager.reprofile_dataset, dataset_id)
    return ProfileResponse(
        dataset_id=dataset_id,
        profile=payload,
        profiled_at=payload.get("metadata", {}).get("generated_at") if payload else None,
    )


# ============================================================================
# Helpers
# ============================================================================
_CHUNK_SIZE = 1024 * 1024  # 1 MiB


async def _save_upload_to_temp(upload: UploadFile, max_bytes: int) -> Path:
    """Stream `upload` to a temp file, enforcing `max_bytes` along the way."""
    suffix = Path(upload.filename or "").suffix
    fd, temp_name = tempfile.mkstemp(prefix="ingest_", suffix=suffix)
    os.close(fd)
    tmp = Path(temp_name)

    total = 0
    try:
        with open(tmp, "wb") as out:
            while True:
                chunk = await upload.read(_CHUNK_SIZE)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise FileTooLargeError(
                        f"Upload exceeds the maximum size of {max_bytes} bytes",
                        details={"limit_bytes": max_bytes},
                    )
                out.write(chunk)
    except Exception:
        _cleanup_temp(tmp)
        raise
    finally:
        await upload.close()

    return tmp


def _cleanup_temp(path: Path) -> None:
    try:
        if path.exists():
            path.unlink()
    except OSError as exc:  # noqa: BLE001
        log.warning("temp_cleanup_failed", path=str(path), error=str(exc))
