"""Tests for the Parquet loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.dataset import DatasetObject, FileFormat
from app.ingestion.exceptions import CorruptedFileError
from app.ingestion.loaders.parquet_loader import ParquetLoader


def _load(path: Path) -> DatasetObject:
    ds = DatasetObject(source_name=path.name, format=FileFormat.PARQUET)
    loader = ParquetLoader()
    loader.load(path, dataset=ds)
    loader.get_metadata(ds)
    return ds


def test_loads_parquet(parquet_file: Path) -> None:
    ds = _load(parquet_file)
    assert ds.rows == 4
    assert set(ds.column_names) == {"id", "name", "price"}
    assert ds.metadata["engine"] == "pyarrow"
    assert ds.metadata["num_row_groups"] >= 1


def test_corrupt_parquet_raises(parquet_corrupt_file: Path) -> None:
    ds = DatasetObject(source_name=parquet_corrupt_file.name, format=FileFormat.PARQUET)
    with pytest.raises(CorruptedFileError):
        ParquetLoader().load(parquet_corrupt_file, dataset=ds)
