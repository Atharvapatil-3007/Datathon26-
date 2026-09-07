"""Shared pytest fixtures for ingestion tests.

Every fixture that writes to disk uses `tmp_path` so tests are isolated
and self-cleaning. We also force the Supabase service into local-fallback
mode by wiping the module singleton and clearing SUPABASE_* env vars.
"""

from __future__ import annotations

import io
import json
import os
import sqlite3
import struct
import zipfile
from pathlib import Path
from typing import Iterator

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest


# ---------------------------------------------------------------------------
# Environment isolation
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _isolate_supabase(monkeypatch, tmp_path):
    """Force every test to use the local storage fallback.

    Note: we `setenv("")` instead of `delenv` because pydantic-settings would
    otherwise fall back to values in the developer's real `.env` file (which
    almost certainly has SUPABASE_URL etc. filled in). An empty env var
    beats the .env file in pydantic-settings' priority order.
    """
    for var in (
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "SUPABASE_ANON_KEY",
    ):
        monkeypatch.setenv(var, "")
    monkeypatch.setenv("LOCAL_STORAGE_DIR", str(tmp_path / ".local_storage"))
    monkeypatch.setenv("APP_LOG_LEVEL", "WARNING")

    # Reset cached settings & service singletons
    from app.config.settings import get_settings
    from app.database.supabase import reset_supabase_service_for_tests
    from app.ingestion.manager import reset_ingestion_manager_for_tests

    get_settings.cache_clear()  # type: ignore[attr-defined]
    reset_supabase_service_for_tests()
    reset_ingestion_manager_for_tests()
    yield
    get_settings.cache_clear()  # type: ignore[attr-defined]
    reset_supabase_service_for_tests()
    reset_ingestion_manager_for_tests()


# ---------------------------------------------------------------------------
# Fixture-file generators
# ---------------------------------------------------------------------------
@pytest.fixture
def csv_file(tmp_path: Path) -> Path:
    p = tmp_path / "people.csv"
    p.write_text(
        "id,name,age,city,signup_date\n"
        "1,Ada,36,London,2023-01-05\n"
        "2,Grace,41,New York,2023-02-14\n"
        "3,Linus,54,Helsinki,2023-03-20\n"
        "4,Guido,68,Amsterdam,2023-04-08\n"
        "5,Katherine,29,Boston,2023-05-11\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def tsv_file(tmp_path: Path) -> Path:
    p = tmp_path / "sample.tsv"
    p.write_text("a\tb\tc\n1\t2\t3\n4\t5\t6\n", encoding="utf-8")
    return p


@pytest.fixture
def csv_semicolon_file(tmp_path: Path) -> Path:
    p = tmp_path / "eu.csv"
    p.write_text("a;b;c\n1;2;3\n4;5;6\n", encoding="utf-8")
    return p


@pytest.fixture
def csv_headerless_file(tmp_path: Path) -> Path:
    p = tmp_path / "raw.csv"
    p.write_text("1,2,3\n4,5,6\n7,8,9\n", encoding="utf-8")
    return p


@pytest.fixture
def csv_missing_values_file(tmp_path: Path) -> Path:
    p = tmp_path / "missing.csv"
    p.write_text(
        "name,age,income\n"
        "Ada,36,\n"
        "Grace,,55000\n"
        "Linus,54,120000\n"
        "Guido,68,\n"
        "Katherine,29,\n"
        "Alan,32,\n",
        encoding="utf-8",
    )
    return p


@pytest.fixture
def empty_file(tmp_path: Path) -> Path:
    p = tmp_path / "empty.csv"
    p.write_bytes(b"")
    return p


@pytest.fixture
def json_array_file(tmp_path: Path) -> Path:
    p = tmp_path / "array.json"
    p.write_text(
        json.dumps([{"id": 1, "name": "Ada"}, {"id": 2, "name": "Grace"}]),
        encoding="utf-8",
    )
    return p


@pytest.fixture
def json_nested_file(tmp_path: Path) -> Path:
    p = tmp_path / "nested.json"
    p.write_text(
        json.dumps(
            [
                {"id": 1, "profile": {"city": "London", "age": 36}},
                {"id": 2, "profile": {"city": "Boston", "age": 29}},
            ]
        ),
        encoding="utf-8",
    )
    return p


@pytest.fixture
def json_wrapped_file(tmp_path: Path) -> Path:
    p = tmp_path / "wrapped.json"
    p.write_text(
        json.dumps({"results": [{"a": 1}, {"a": 2}, {"a": 3}], "count": 3}),
        encoding="utf-8",
    )
    return p


@pytest.fixture
def json_single_object_file(tmp_path: Path) -> Path:
    p = tmp_path / "single.json"
    p.write_text(json.dumps({"foo": 1, "bar": "baz"}), encoding="utf-8")
    return p


@pytest.fixture
def json_invalid_file(tmp_path: Path) -> Path:
    p = tmp_path / "broken.json"
    p.write_text("{not valid json,,,", encoding="utf-8")
    return p


@pytest.fixture
def jsonl_file(tmp_path: Path) -> Path:
    p = tmp_path / "events.jsonl"
    lines = [
        json.dumps({"event": "click", "n": 1}),
        json.dumps({"event": "view", "n": 2}),
        json.dumps({"event": "click", "n": 3}),
    ]
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return p


@pytest.fixture
def jsonl_malformed_file(tmp_path: Path) -> Path:
    p = tmp_path / "bad.jsonl"
    p.write_text(
        '{"event": "click", "n": 1}\n'
        "this is not json\n"
        '{"event": "view", "n": 2}\n',
        encoding="utf-8",
    )
    return p


@pytest.fixture
def parquet_file(tmp_path: Path) -> Path:
    p = tmp_path / "small.parquet"
    tbl = pa.table(
        {
            "id": [1, 2, 3, 4],
            "name": ["a", "b", "c", "d"],
            "price": [9.99, 19.5, 29.0, 39.75],
        }
    )
    pq.write_table(tbl, p)
    return p


@pytest.fixture
def parquet_corrupt_file(tmp_path: Path) -> Path:
    p = tmp_path / "broken.parquet"
    p.write_bytes(b"NOT_PARQUET" * 20)
    return p


@pytest.fixture
def xlsx_file(tmp_path: Path) -> Path:
    p = tmp_path / "book.xlsx"
    df = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
    df.to_excel(p, index=False, engine="openpyxl")
    return p


@pytest.fixture
def xlsx_multisheet_file(tmp_path: Path) -> Path:
    p = tmp_path / "multi.xlsx"
    with pd.ExcelWriter(p, engine="openpyxl") as w:
        pd.DataFrame({"a": [1, 2]}).to_excel(w, sheet_name="alpha", index=False)
        pd.DataFrame({"b": [3, 4, 5]}).to_excel(w, sheet_name="beta", index=False)
    return p


@pytest.fixture
def sqlite_file(tmp_path: Path) -> Path:
    p = tmp_path / "app.sqlite"
    conn = sqlite3.connect(p)
    conn.execute("create table users (id integer primary key, name text, age integer)")
    conn.executemany(
        "insert into users(name, age) values (?, ?)",
        [("Ada", 36), ("Grace", 41), ("Linus", 54)],
    )
    conn.execute("create table events (id integer primary key, kind text)")
    conn.executemany("insert into events(kind) values (?)", [("click",), ("view",)])
    conn.commit()
    conn.close()
    return p


@pytest.fixture
def zip_with_csv(tmp_path: Path, csv_file: Path) -> Path:
    p = tmp_path / "one.zip"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(csv_file, arcname="people.csv")
    return p


@pytest.fixture
def zip_with_multiple(tmp_path: Path, csv_file: Path, json_array_file: Path) -> Path:
    p = tmp_path / "multi.zip"
    with zipfile.ZipFile(p, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(csv_file, arcname="data/people.csv")
        zf.write(json_array_file, arcname="data/records.json")
        zf.writestr("readme.txt", "just a note")
    return p


@pytest.fixture
def zip_with_traversal(tmp_path: Path) -> Path:
    """Craft a ZIP whose member escapes the extraction directory."""
    p = tmp_path / "evil.zip"
    with zipfile.ZipFile(p, "w") as zf:
        # NOTE: writestr with a member name containing ../ is enough to
        # simulate a hostile archive.
        zf.writestr("../evil.csv", "a,b\n1,2\n")
        zf.writestr("safe.csv", "x,y\n1,2\n")
    return p


@pytest.fixture
def zip_only_unsupported(tmp_path: Path) -> Path:
    p = tmp_path / "unsupported.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("readme.md", "# hello")
        zf.writestr("run.exe", b"\x4D\x5A\x00\x00")  # MZ header, not extracted
    return p


@pytest.fixture
def zip_corrupt(tmp_path: Path) -> Path:
    p = tmp_path / "broken.zip"
    p.write_bytes(b"PK\x03\x04not-really-a-zip")
    return p


# ---------------------------------------------------------------------------
# DataFrame factory for schema-inference tests
# ---------------------------------------------------------------------------
@pytest.fixture
def rich_dataframe() -> pd.DataFrame:
    long_comment = (
        "This is a genuinely long free-form comment that easily exceeds "
        "the text length heuristic used by the schema inference module."
    )
    return pd.DataFrame(
        {
            "customer_id": range(1, 21),
            "age": [20 + i for i in range(20)],
            "income": [30000 + i * 1000 for i in range(20)],
            "city": (["London"] * 10) + (["Boston"] * 10),
            "signup_date": pd.date_range("2024-01-01", periods=20, freq="D"),
            "feedback": [long_comment] * 20,
            "rating": [1, 2, 3, 4, 5] * 4,
        }
    )
