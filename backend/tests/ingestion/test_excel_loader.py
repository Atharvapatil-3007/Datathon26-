"""Tests for the Excel loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.dataset import DatasetObject, FileFormat
from app.ingestion.exceptions import FileParsingError
from app.ingestion.loaders.excel_loader import ExcelLoader


def _load(path: Path, **options) -> DatasetObject:
    ds = DatasetObject(source_name=path.name, format=FileFormat.EXCEL_XLSX)
    loader = ExcelLoader()
    loader.load(path, dataset=ds, options=options or None)
    loader.get_metadata(ds)
    return ds


def test_loads_xlsx_default_sheet(xlsx_file: Path) -> None:
    ds = _load(xlsx_file)
    assert ds.rows == 3
    assert ds.column_names == ["a", "b"]
    assert ds.metadata["sheet_count"] == 1


def test_lists_all_sheets(xlsx_multisheet_file: Path) -> None:
    ds = _load(xlsx_multisheet_file)
    assert set(ds.metadata["sheet_names"]) == {"alpha", "beta"}
    assert ds.metadata["selected_sheet"] == "alpha"
    # Warning surfaced about additional sheets not loaded
    assert any("sheets" in w for w in ds.warnings)


def test_sheet_selection(xlsx_multisheet_file: Path) -> None:
    ds = _load(xlsx_multisheet_file, sheet_name="beta")
    assert ds.metadata["selected_sheet"] == "beta"
    assert ds.column_names == ["b"]
    assert ds.rows == 3


def test_missing_sheet_raises(xlsx_file: Path) -> None:
    ds = DatasetObject(source_name=xlsx_file.name, format=FileFormat.EXCEL_XLSX)
    with pytest.raises(FileParsingError):
        ExcelLoader().load(xlsx_file, dataset=ds, options={"sheet_name": "missing"})


def test_invalid_workbook_raises(tmp_path: Path) -> None:
    p = tmp_path / "fake.xlsx"
    p.write_bytes(b"not really xlsx")
    ds = DatasetObject(source_name=p.name, format=FileFormat.EXCEL_XLSX)
    with pytest.raises(FileParsingError):
        ExcelLoader().load(p, dataset=ds)
