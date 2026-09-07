"""F-03: per-process DataFrame cache in dataset_loader."""

from __future__ import annotations

import pandas as pd

from app.analysis import dataset_loader
from app.database.supabase import get_supabase_service


def test_second_load_hits_cache(corporate_dataset_id: str, monkeypatch) -> None:
    """A repeat ``load_dataset_bundle`` for the same id must not re-download."""
    dataset_loader.clear_dataset_cache()

    service = get_supabase_service()
    original = service.download_dataset_to_file
    calls = {"count": 0}

    def counting_download(path: str, dest) -> None:
        calls["count"] += 1
        return original(path, dest)

    monkeypatch.setattr(service, "download_dataset_to_file", counting_download)

    row1, df1 = dataset_loader.load_dataset_bundle(
        corporate_dataset_id, supabase=service
    )
    row2, df2 = dataset_loader.load_dataset_bundle(
        corporate_dataset_id, supabase=service
    )

    assert calls["count"] == 1
    assert df1 is df2  # same cached object returned
    assert isinstance(df1, pd.DataFrame)
    assert row1["id"] == row2["id"] == corporate_dataset_id


def test_clear_cache_forces_redownload(
    corporate_dataset_id: str, monkeypatch
) -> None:
    dataset_loader.clear_dataset_cache()

    service = get_supabase_service()
    original = service.download_dataset_to_file
    calls = {"count": 0}

    def counting_download(path: str, dest) -> None:
        calls["count"] += 1
        return original(path, dest)

    monkeypatch.setattr(service, "download_dataset_to_file", counting_download)

    dataset_loader.load_dataset_bundle(corporate_dataset_id, supabase=service)
    dataset_loader.clear_dataset_cache()
    dataset_loader.load_dataset_bundle(corporate_dataset_id, supabase=service)

    assert calls["count"] == 2


def test_cache_evicts_oldest_beyond_cap(
    corporate_pnl_csv, competitor_pnl_csv, bank_dataset_csv, monkeypatch
) -> None:
    """Verify LRU eviction when cache exceeds ``_CACHE_MAX_ENTRIES``."""
    dataset_loader.clear_dataset_cache()
    monkeypatch.setattr(dataset_loader, "_CACHE_MAX_ENTRIES", 2)

    from tests.analysis.conftest import _ingest  # noqa: PLC0415

    ids = [
        _ingest(corporate_pnl_csv),
        _ingest(competitor_pnl_csv),
        _ingest(bank_dataset_csv),
    ]

    service = get_supabase_service()
    for did in ids:
        dataset_loader.load_dataset_bundle(did, supabase=service)

    # After three inserts with cap=2, only the last two ids survive.
    with dataset_loader._cache_lock:
        assert ids[0] not in dataset_loader._dataframe_cache
        assert ids[1] in dataset_loader._dataframe_cache
        assert ids[2] in dataset_loader._dataframe_cache
