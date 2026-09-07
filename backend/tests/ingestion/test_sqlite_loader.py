"""Tests for the SQLite loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.dataset import DatasetObject, FileFormat
from app.ingestion.exceptions import CorruptedFileError, InvalidDatasetError
from app.ingestion.loaders.sqlite_loader import SQLiteLoader


def _load(path: Path, **options) -> DatasetObject:
    ds = DatasetObject(source_name=path.name, format=FileFormat.SQLITE)
    loader = SQLiteLoader()
    loader.load(path, dataset=ds, options=options or None)
    loader.get_metadata(ds)
    return ds


def test_lists_tables_and_loads_largest(sqlite_file: Path) -> None:
    ds = _load(sqlite_file)
    assert set(ds.metadata["tables"]) == {"users", "events"}
    # users has 3 rows, events has 2 -> users is picked
    assert ds.metadata["selected_table"] == "users"
    assert ds.rows == 3
    # Multi-table warning surfaced
    assert any("tables" in w for w in ds.warnings)


def test_explicit_table_selection(sqlite_file: Path) -> None:
    ds = _load(sqlite_file, table_name="events")
    assert ds.metadata["selected_table"] == "events"
    assert set(ds.column_names) == {"id", "kind"}
    assert ds.rows == 2


def test_missing_table_raises(sqlite_file: Path) -> None:
    ds = DatasetObject(source_name=sqlite_file.name, format=FileFormat.SQLITE)
    with pytest.raises(InvalidDatasetError):
        SQLiteLoader().load(sqlite_file, dataset=ds, options={"table_name": "nope"})


def test_invalid_sqlite_raises(tmp_path: Path) -> None:
    p = tmp_path / "not-really.db"
    p.write_bytes(b"random garbage that is not sqlite")
    ds = DatasetObject(source_name=p.name, format=FileFormat.SQLITE)
    # sqlite3 may accept the file but fail listing tables -> InvalidDatasetError
    # OR reject the file outright -> CorruptedFileError
    with pytest.raises((CorruptedFileError, InvalidDatasetError, Exception)):
        SQLiteLoader().load(p, dataset=ds)
