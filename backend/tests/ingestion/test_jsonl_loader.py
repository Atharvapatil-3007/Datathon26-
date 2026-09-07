"""Tests for the JSONL loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.dataset import DatasetObject, FileFormat
from app.ingestion.exceptions import FileParsingError
from app.ingestion.loaders.jsonl_loader import JSONLLoader


def _load(path: Path) -> DatasetObject:
    ds = DatasetObject(source_name=path.name, format=FileFormat.JSONL)
    loader = JSONLLoader()
    loader.load(path, dataset=ds)
    loader.get_metadata(ds)
    return ds


def test_loads_valid_jsonl(jsonl_file: Path) -> None:
    ds = _load(jsonl_file)
    assert ds.rows == 3
    assert set(ds.column_names) == {"event", "n"}


def test_malformed_line_skipped_with_warning(jsonl_malformed_file: Path) -> None:
    ds = _load(jsonl_malformed_file)
    # Two well-formed lines should survive
    assert ds.rows == 2
    assert any("invalid JSONL" in w.lower() or "invalid jsonl" in w.lower() for w in ds.warnings)


def test_fully_invalid_jsonl_raises(tmp_path: Path) -> None:
    p = tmp_path / "junk.jsonl"
    p.write_text("not json\nstill not json\n{broken}\n", encoding="utf-8")
    ds = DatasetObject(source_name=p.name, format=FileFormat.JSONL)
    with pytest.raises(FileParsingError):
        JSONLLoader().load(p, dataset=ds)
