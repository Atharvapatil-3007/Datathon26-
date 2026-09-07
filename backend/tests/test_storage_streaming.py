"""F-07: chunked upload / download in the Supabase storage backend."""

from __future__ import annotations

from pathlib import Path

from app.database.supabase import get_supabase_service


def test_download_to_file_streams_to_disk(csv_file: Path, tmp_path: Path) -> None:
    """Round-trip through the local backend's streaming download path."""
    service = get_supabase_service()

    # Push a file through the same upload path used by the ingestion manager
    # so we exercise the "Path is passed straight to the backend" code path.
    storage_path = service.upload_dataset(
        dataset_id="fake-dataset-id",
        local_path=csv_file,
        original_filename=csv_file.name,
        content_type="text/csv",
    )

    dest = tmp_path / "streamed.csv"
    service.download_dataset_to_file(storage_path, dest)

    assert dest.exists()
    assert dest.read_bytes() == csv_file.read_bytes()


def test_upload_dataset_accepts_path_without_prereading_bytes(csv_file: Path) -> None:
    """Simply verify the backend's ``upload`` no longer needs the caller to
    pre-read the file into memory (F-07 goal)."""
    service = get_supabase_service()

    # If the local backend's upload signature accepts a Path directly this
    # succeeds without loading the file bytes at the service layer.
    storage_path = service.upload_dataset(
        dataset_id="another-fake-id",
        local_path=csv_file,
        original_filename=csv_file.name,
        content_type="text/csv",
    )
    assert storage_path.endswith(csv_file.name)
