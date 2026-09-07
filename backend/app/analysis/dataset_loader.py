"""Shared dataset-loading helper for the Phase 3 analyzers.

We reuse the existing Phase 1 detector + loader stack to fetch a
DataFrame for a stored dataset. Keeps analyzers pure: they take
``(dataset_row, dataframe)`` in and produce an ``AnalysisResult``.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from app.database.supabase import SupabaseService, get_supabase_service
from app.ingestion.dataset import DatasetObject, SourceType, FileFormat
from app.ingestion.detector import detect_format
from app.ingestion.exceptions import DatasetNotFoundError
from app.utils.logging import get_logger


log = get_logger(__name__)


def load_dataset_bundle(
    dataset_id: str,
    *,
    supabase: Optional[SupabaseService] = None,
    include_dataframe: bool = True,
) -> Tuple[Dict[str, Any], Optional[pd.DataFrame]]:
    """Return ``(dataset_row, dataframe)`` for a stored dataset.

    If ``include_dataframe`` is False (or the row has no storage_path we can
    use), the second element is ``None`` and analyzers fall back to profile-
    only aggregation.
    """
    service = supabase or get_supabase_service()
    row = service.get_dataset(dataset_id)  # raises DatasetNotFoundError if missing
    if not row.get("profile"):
        # Row exists but Phase 2 profile is missing (rare: profiling failed softly).
        raise DatasetNotFoundError(
            f"Dataset '{dataset_id}' has no Phase 2 profile \u2014 re-profile it first."
        )

    if not include_dataframe:
        return row, None

    storage_path = row.get("storage_path")
    if not storage_path:
        # SQL-sourced datasets don't keep a file on disk.
        log.info("dataframe_reload_skipped_no_storage", dataset_id=dataset_id)
        return row, None

    try:
        raw = service.download_dataset(storage_path)
    except Exception as exc:  # noqa: BLE001
        log.warning("dataframe_download_failed", dataset_id=dataset_id, error=str(exc))
        return row, None

    df = _load_from_bytes(raw, original_filename=row.get("original_filename") or "")
    return row, df


def _load_from_bytes(data: bytes, *, original_filename: str) -> Optional[pd.DataFrame]:
    """Persist raw bytes to a temp file and re-run the ingestion loader."""
    suffix = Path(original_filename).suffix or ".bin"
    fd, tmp_name = tempfile.mkstemp(prefix="phase3_", suffix=suffix)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_bytes(data)
        detection = detect_format(tmp_path, filename_hint=original_filename)
        loader = detection.loader_cls()
        ds = DatasetObject(
            dataset_id="phase3-hydrate",
            source_type=SourceType.FILE,
            source_name=original_filename,
            format=detection.format,
        )
        loader.load(tmp_path, dataset=ds, options=None)
        return ds.data
    except Exception as exc:  # noqa: BLE001
        log.warning("dataframe_parse_failed", filename=original_filename, error=str(exc))
        return None
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
