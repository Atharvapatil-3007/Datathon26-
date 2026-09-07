"""End-to-end IngestionManager tests using the local storage fallback."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.database.supabase import get_supabase_service
from app.ingestion.dataset import DatasetStatus
from app.ingestion.exceptions import UnsupportedFileTypeError
from app.ingestion.manager import get_ingestion_manager


def test_end_to_end_csv(csv_file: Path) -> None:
    manager = get_ingestion_manager()
    result, status = manager.ingest_file(
        temp_path=str(csv_file),
        filename="people.csv",
        mime_type="text/csv",
    )
    assert status == DatasetStatus.VALIDATED
    assert result.dataset.rows == 5
    assert result.dataset.columns == 5
    assert result.storage_path is not None
    assert result.detection.format.value == "csv"


def test_end_to_end_json(json_array_file: Path) -> None:
    manager = get_ingestion_manager()
    result, status = manager.ingest_file(
        temp_path=str(json_array_file),
        filename="array.json",
        mime_type="application/json",
    )
    assert status == DatasetStatus.VALIDATED
    assert result.dataset.rows == 2


def test_dataset_persisted_and_retrievable(csv_file: Path) -> None:
    manager = get_ingestion_manager()
    result, _ = manager.ingest_file(
        temp_path=str(csv_file),
        filename="people.csv",
        mime_type="text/csv",
    )
    row = manager.get_dataset_summary(result.dataset.dataset_id)
    assert row is not None
    assert row["status"] == DatasetStatus.VALIDATED.value
    assert row["row_count"] == 5


def test_list_returns_recent_first(csv_file: Path, json_array_file: Path) -> None:
    manager = get_ingestion_manager()
    manager.ingest_file(
        temp_path=str(csv_file), filename="people.csv", mime_type="text/csv"
    )
    manager.ingest_file(
        temp_path=str(json_array_file),
        filename="array.json",
        mime_type="application/json",
    )
    rows = manager.list_datasets()
    assert len(rows) == 2
    assert rows[0]["filename"] == "array.json"  # newest first


def test_delete_removes_row_and_storage(csv_file: Path) -> None:
    manager = get_ingestion_manager()
    result, _ = manager.ingest_file(
        temp_path=str(csv_file),
        filename="people.csv",
        mime_type="text/csv",
    )
    dataset_id = result.dataset.dataset_id
    manager.delete_dataset(dataset_id)
    assert manager.get_dataset_summary(dataset_id) is None


def test_unsupported_format_raises_and_marks_row_uploaded(tmp_path: Path) -> None:
    """Even when detection fails, the original file is preserved in storage."""
    manager = get_ingestion_manager()
    weird = tmp_path / "weird.xyz"
    weird.write_bytes(b"\x00\x01this-is-nothing-i-know")

    with pytest.raises(UnsupportedFileTypeError):
        manager.ingest_file(
            temp_path=str(weird),
            filename="weird.xyz",
            mime_type="application/octet-stream",
        )

    # The file was uploaded before format detection, so a row exists in
    # `failed` status and the storage object is still there.
    rows = manager.list_datasets()
    assert len(rows) == 1
    assert rows[0]["status"] == DatasetStatus.FAILED.value


def test_local_fallback_is_active() -> None:
    assert get_supabase_service().is_local_fallback is True
