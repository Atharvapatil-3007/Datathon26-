"""Tests for the JSON loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.ingestion.dataset import DatasetObject, FileFormat
from app.ingestion.exceptions import FileParsingError
from app.ingestion.loaders.json_loader import JSONLoader


def _load(path: Path) -> DatasetObject:
    ds = DatasetObject(source_name=path.name, format=FileFormat.JSON)
    loader = JSONLoader()
    loader.load(path, dataset=ds)
    loader.get_metadata(ds)
    return ds


def test_loads_array(json_array_file: Path) -> None:
    ds = _load(json_array_file)
    assert ds.rows == 2
    assert set(ds.column_names) == {"id", "name"}
    assert ds.metadata["json_shape"] == "array_of_objects"


def test_flattens_nested(json_nested_file: Path) -> None:
    ds = _load(json_nested_file)
    assert "profile.city" in ds.column_names
    assert "profile.age" in ds.column_names
    assert ds.metadata["flattened"] is True


def test_unwraps_array_under_key(json_wrapped_file: Path) -> None:
    ds = _load(json_wrapped_file)
    assert ds.rows == 3
    assert "a" in ds.column_names
    assert ds.metadata["json_shape"] == "object_wrapping_array"
    assert ds.metadata["unwrap_key"] == "results"


def test_single_object(json_single_object_file: Path) -> None:
    ds = _load(json_single_object_file)
    assert ds.rows == 1
    assert set(ds.column_names) == {"foo", "bar"}


def test_invalid_json_raises(json_invalid_file: Path) -> None:
    ds = DatasetObject(source_name=json_invalid_file.name, format=FileFormat.JSON)
    with pytest.raises(FileParsingError):
        JSONLoader().load(json_invalid_file, dataset=ds)
