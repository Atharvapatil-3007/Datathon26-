"""Tests for the format detector."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.dataset import FileFormat
from app.ingestion.detector import detect_format
from app.ingestion.exceptions import UnsupportedFileTypeError


def test_detects_csv(csv_file: Path) -> None:
    r = detect_format(csv_file)
    assert r.format == FileFormat.CSV
    assert r.loader_name == "CSVLoader"


def test_detects_tsv(tsv_file: Path) -> None:
    r = detect_format(tsv_file)
    assert r.format == FileFormat.TSV
    assert r.loader_name == "CSVLoader"


def test_detects_csv_semicolon(csv_semicolon_file: Path) -> None:
    r = detect_format(csv_semicolon_file)
    assert r.format == FileFormat.CSV


def test_detects_json_array(json_array_file: Path) -> None:
    r = detect_format(json_array_file)
    assert r.format == FileFormat.JSON
    assert r.loader_name == "JSONLoader"


def test_detects_jsonl(jsonl_file: Path) -> None:
    r = detect_format(jsonl_file)
    # Extension is `.jsonl`; regardless of content sniff outcome, must resolve to JSONL.
    assert r.format == FileFormat.JSONL


def test_detects_parquet(parquet_file: Path) -> None:
    r = detect_format(parquet_file)
    assert r.format == FileFormat.PARQUET
    assert r.loader_name == "ParquetLoader"


def test_detects_xlsx(xlsx_file: Path) -> None:
    r = detect_format(xlsx_file)
    assert r.format == FileFormat.EXCEL_XLSX
    assert r.loader_name == "ExcelLoader"


def test_detects_sqlite(sqlite_file: Path) -> None:
    r = detect_format(sqlite_file)
    assert r.format == FileFormat.SQLITE
    assert r.loader_name == "SQLiteLoader"


def test_detects_zip(zip_with_csv: Path) -> None:
    r = detect_format(zip_with_csv)
    assert r.format == FileFormat.ZIP
    assert r.loader_name == "ZIPLoader"


def test_unsupported_binary_rejected(tmp_path: Path) -> None:
    p = tmp_path / "opaque.bin"
    p.write_bytes(b"\x00\x01\x02\x03\x04random-blob")
    with pytest.raises(UnsupportedFileTypeError):
        detect_format(p)


def test_filename_hint_used_for_extension(tmp_path: Path, csv_file: Path) -> None:
    # Simulate FastAPI's temp file scenario: renamed .tmp but hint carries .csv
    tmp_copy = tmp_path / "upload.tmp"
    tmp_copy.write_bytes(csv_file.read_bytes())
    r = detect_format(tmp_copy, filename_hint="people.csv")
    assert r.format == FileFormat.CSV
