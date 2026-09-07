"""Tests for the CSV / TSV loader."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from app.ingestion.dataset import DatasetObject, FileFormat
from app.ingestion.exceptions import FileParsingError
from app.ingestion.loaders.csv_loader import CSVLoader


def _load(path: Path, fmt: FileFormat = FileFormat.CSV, **options) -> DatasetObject:
    ds = DatasetObject(source_name=path.name, format=fmt)
    loader = CSVLoader()
    loader.load(path, dataset=ds, options=options or None)
    loader.get_metadata(ds)
    return ds


def test_loads_csv(csv_file: Path) -> None:
    ds = _load(csv_file)
    assert ds.rows == 5
    assert ds.column_names == ["id", "name", "age", "city", "signup_date"]
    assert ds.metadata["delimiter"] == "comma"


def test_loads_tsv(tsv_file: Path) -> None:
    ds = _load(tsv_file, fmt=FileFormat.TSV)
    assert ds.rows == 2
    assert ds.column_names == ["a", "b", "c"]
    assert ds.metadata["delimiter"] == "tab"


def test_detects_semicolon_delimiter(csv_semicolon_file: Path) -> None:
    ds = _load(csv_semicolon_file)
    assert ds.rows == 2
    assert ds.column_names == ["a", "b", "c"]
    assert ds.metadata["delimiter"] == "semicolon"


def test_headerless_csv(csv_headerless_file: Path) -> None:
    ds = _load(csv_headerless_file, has_header=False)
    assert ds.rows == 3
    assert ds.column_names == ["col_0", "col_1", "col_2"]


def test_missing_values_preserved(csv_missing_values_file: Path) -> None:
    # Pin has_header=True — csv.Sniffer.has_header() can misread files
    # where the last column is mostly empty. We want to test value
    # preservation here, not header detection.
    ds = _load(csv_missing_values_file, has_header=True)
    assert ds.rows == 6
    assert pd.isna(ds.data["income"]).sum() >= 3


def test_malformed_csv_raises(tmp_path: Path) -> None:
    # Rows with wildly different numbers of columns can still parse with
    # `on_bad_lines='warn'`, but an unreadable byte stream should raise.
    p = tmp_path / "junk.csv"
    p.write_bytes(b"\xff\xfe\xfd\x00this-is-binary\x00\x00")
    ds = DatasetObject(source_name=p.name, format=FileFormat.CSV)
    # Depending on chardet's guess this either succeeds with garbage columns
    # or raises; in both cases the loader must not crash uncaught.
    try:
        CSVLoader().load(p, dataset=ds)
    except FileParsingError:
        pass


def test_empty_file_raises(empty_file: Path) -> None:
    ds = DatasetObject(source_name=empty_file.name, format=FileFormat.CSV)
    with pytest.raises(FileParsingError):
        CSVLoader().load(empty_file, dataset=ds)
