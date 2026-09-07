"""HTTP-level smoke tests using FastAPI's TestClient."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def client():
    # Import inside the fixture so isolated env / cache clearing has happened.
    from fastapi.testclient import TestClient

    from app.main import _build_app

    app = _build_app()
    with TestClient(app) as c:
        yield c


def test_health_endpoint(client) -> None:
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["local_fallback"] is True


def test_upload_csv_flow(client, csv_file: Path) -> None:
    with open(csv_file, "rb") as f:
        r = client.post(
            "/api/v1/ingestion/upload",
            files={"file": ("people.csv", f, "text/csv")},
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["success"] is True
    assert body["format"] == "csv"
    assert body["rows"] == 5
    assert body["columns"] == 5
    assert "schema" in body
    assert body["status"] == "validated"


def test_upload_unsupported_returns_structured_error(client, tmp_path: Path) -> None:
    weird = tmp_path / "weird.xyz"
    weird.write_bytes(b"\x00\x01nothing-recognizable")
    with open(weird, "rb") as f:
        r = client.post(
            "/api/v1/ingestion/upload",
            files={"file": ("weird.xyz", f, "application/octet-stream")},
        )
    assert r.status_code == 415
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "UNSUPPORTED_FILE_TYPE"


def test_list_and_get_and_delete_dataset(client, csv_file: Path) -> None:
    with open(csv_file, "rb") as f:
        upload = client.post(
            "/api/v1/ingestion/upload",
            files={"file": ("people.csv", f, "text/csv")},
        )
    dataset_id = upload.json()["dataset_id"]

    listed = client.get("/api/v1/datasets")
    assert listed.status_code == 200
    assert any(row["id"] == dataset_id for row in listed.json())

    fetched = client.get(f"/api/v1/datasets/{dataset_id}")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == dataset_id

    deleted = client.delete(f"/api/v1/datasets/{dataset_id}")
    assert deleted.status_code == 204

    missing = client.get(f"/api/v1/datasets/{dataset_id}")
    assert missing.status_code == 404
