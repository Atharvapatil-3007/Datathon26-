"""Shared dataset-loading helper for the Phase 3 analyzers.

We reuse the existing Phase 1 detector + loader stack to fetch a
DataFrame for a stored dataset. Keeps analyzers pure: they take
``(dataset_row, dataframe)`` in and produce an ``AnalysisResult``.

Includes a small per-process LRU cache for hydrated DataFrames (F-03).
Dataset IDs are UUIDs assigned at upload time, so a given ID always
maps to the same bytes; caching the parsed DataFrame is safe and
avoids a redundant Supabase round-trip when multiple analyses run on
the same dataset (e.g. self, then merger, then benchmark).
"""

from __future__ import annotations

import os
import tempfile
import threading
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from app.database.supabase import SupabaseService, get_supabase_service
from app.ingestion.dataset import DatasetObject, SourceType, FileFormat
from app.ingestion.detector import detect_format
from app.ingestion.exceptions import DatasetNotFoundError
from app.utils.logging import get_logger


log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Per-process DataFrame cache (F-03)
# ---------------------------------------------------------------------------
_CACHE_MAX_ENTRIES = 4
_dataframe_cache: "OrderedDict[str, pd.DataFrame]" = OrderedDict()
_cache_lock = threading.Lock()


def clear_dataset_cache() -> None:
    """Empty the DataFrame cache. Intended for tests + explicit invalidation."""
    with _cache_lock:
        _dataframe_cache.clear()


def _cache_get(dataset_id: str) -> Optional[pd.DataFrame]:
    with _cache_lock:
        df = _dataframe_cache.get(dataset_id)
        if df is not None:
            _dataframe_cache.move_to_end(dataset_id)  # mark as recently used
        return df


def _cache_put(dataset_id: str, df: pd.DataFrame) -> None:
    with _cache_lock:
        _dataframe_cache[dataset_id] = df
        _dataframe_cache.move_to_end(dataset_id)
        while len(_dataframe_cache) > _CACHE_MAX_ENTRIES:
            _dataframe_cache.popitem(last=False)  # evict LRU


def load_dataset_bundle(
    dataset_id: str,
    *,
    supabase: Optional[SupabaseService] = None,
    include_dataframe: bool = True,
    user_id: Optional[str] = None,
) -> Tuple[Dict[str, Any], Optional[pd.DataFrame]]:
    """Return ``(dataset_row, dataframe)`` for a stored dataset.

    If ``include_dataframe`` is False (or the row has no storage_path we can
    use), the second element is ``None`` and analyzers fall back to profile-
    only aggregation. Passing ``user_id`` enforces app-layer ownership
    (F-01): a mismatched owner is reported as not-found.
    """
    service = supabase or get_supabase_service()
    row = service.get_dataset(dataset_id, user_id=user_id)  # raises if missing / not owned
    if not row.get("profile"):
        # Row exists but Phase 2 profile is missing (rare: profiling failed softly).
        raise DatasetNotFoundError(
            f"Dataset '{dataset_id}' has no Phase 2 profile \u2014 re-profile it first."
        )

    if not include_dataframe:
        return row, None

    cached = _cache_get(dataset_id)
    if cached is not None:
        log.debug("dataframe_cache_hit", dataset_id=dataset_id)
        return row, cached

    storage_path = row.get("storage_path")
    if not storage_path:
        # SQL-sourced datasets don't keep a file on disk.
        log.info("dataframe_reload_skipped_no_storage", dataset_id=dataset_id)
        return row, None

    df = _stream_and_parse(
        service,
        storage_path=storage_path,
        original_filename=row.get("original_filename") or "",
        dataset_id=dataset_id,
    )
    if df is not None:
        _cache_put(dataset_id, df)
    return row, df


def _stream_and_parse(
    service: SupabaseService,
    *,
    storage_path: str,
    original_filename: str,
    dataset_id: str,
) -> Optional[pd.DataFrame]:
    """Stream storage \u2192 temp file \u2192 loader (F-07 chunked download)."""
    suffix = Path(original_filename).suffix or ".bin"
    fd, tmp_name = tempfile.mkstemp(prefix="phase3_", suffix=suffix)
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        service.download_dataset_to_file(storage_path, tmp_path)
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
        log.warning(
            "dataframe_download_or_parse_failed",
            dataset_id=dataset_id,
            filename=original_filename,
            error=str(exc),
        )
        return None
    finally:
        try:
            tmp_path.unlink(missing_ok=True)
        except OSError:
            pass
