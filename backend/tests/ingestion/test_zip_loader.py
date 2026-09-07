"""Tests for the ZIP loader (security-critical)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.dataset import DatasetObject, FileFormat, SourceType
from app.ingestion.exceptions import (
    InvalidDatasetError,
    UnsafeArchiveError,
)
from app.ingestion.loaders.zip_loader import ZIPLoader


def _load(path: Path, **options) -> DatasetObject:
    ds = DatasetObject(source_name=path.name, format=FileFormat.ZIP)
    loader = ZIPLoader()
    loader.load(path, dataset=ds, options=options or None)
    loader.get_metadata(ds)
    return ds


def test_loads_single_csv_from_zip(zip_with_csv: Path) -> None:
    ds = _load(zip_with_csv)
    assert ds.rows == 5
    assert "id" in ds.column_names
    assert ds.metadata["archive_member"] == "people.csv"
    assert ds.source_type == SourceType.ZIP_ARCHIVE


def test_picks_largest_supported_member(zip_with_multiple: Path) -> None:
    ds = _load(zip_with_multiple)
    # CSV people.csv is larger than the small JSON records -> picked
    assert ds.metadata["archive_member"].endswith(("people.csv", "records.json"))
    assert ds.rows > 0


def test_explicit_member_selection(zip_with_multiple: Path) -> None:
    ds = _load(zip_with_multiple, member="data/records.json")
    assert ds.metadata["archive_member"] == "data/records.json"


def test_path_traversal_is_rejected_or_skipped(zip_with_traversal: Path) -> None:
    """Whatever the loader does, it must NOT write outside the temp dir."""
    ds = _load(zip_with_traversal)
    # The safe member should be selected instead of the traversal one.
    assert ds.metadata["archive_member"] == "safe.csv"
    # No warning is enough — the traversal member was silently skipped.
    assert ds.rows == 1


def test_no_supported_files_raises(zip_only_unsupported: Path) -> None:
    ds = DatasetObject(source_name=zip_only_unsupported.name, format=FileFormat.ZIP)
    with pytest.raises(InvalidDatasetError):
        ZIPLoader().load(zip_only_unsupported, dataset=ds)


def test_corrupt_zip_raises(zip_corrupt: Path) -> None:
    ds = DatasetObject(source_name=zip_corrupt.name, format=FileFormat.ZIP)
    with pytest.raises(UnsafeArchiveError):
        ZIPLoader().load(zip_corrupt, dataset=ds)
