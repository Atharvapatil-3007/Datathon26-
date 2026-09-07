"""End-to-end API tests for Phase 2 profiling."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient

    from app.main import _build_app

    app = _build_app()
    with TestClient(app) as c:
        yield c


def test_upload_returns_profile_inline(client, csv_file: Path) -> None:
    with open(csv_file, "rb") as f:
        r = client.post(
            "/api/v1/ingestion/upload",
            files={"file": ("people.csv", f, "text/csv")},
        )
    assert r.status_code == 201, r.text
    body = r.json()

    assert body["success"] is True
    assert "profile" in body
    profile = body["profile"]
    assert profile is not None
    assert profile["dataset_id"] == body["dataset_id"]
    assert profile["overview"]["rows"] == 5
    assert profile["overview"]["columns"] == 5
    assert "quality" in profile
    assert 0 <= profile["quality"]["overall_score"] <= 100
    assert "summary_text" in profile
    assert profile["metadata"]["version"] == "2.0"


def test_get_profile_endpoint(client, csv_file: Path) -> None:
    with open(csv_file, "rb") as f:
        upload = client.post(
            "/api/v1/ingestion/upload",
            files={"file": ("people.csv", f, "text/csv")},
        )
    dataset_id = upload.json()["dataset_id"]

    r = client.get(f"/api/v1/datasets/{dataset_id}/profile")
    assert r.status_code == 200
    body = r.json()
    assert body["dataset_id"] == dataset_id
    assert body["profile"] is not None
    assert "overview" in body["profile"]


def test_reprofile_endpoint(client, csv_file: Path) -> None:
    with open(csv_file, "rb") as f:
        upload = client.post(
            "/api/v1/ingestion/upload",
            files={"file": ("people.csv", f, "text/csv")},
        )
    dataset_id = upload.json()["dataset_id"]

    r = client.post(f"/api/v1/datasets/{dataset_id}/reprofile")
    assert r.status_code == 200
    body = r.json()
    assert body["dataset_id"] == dataset_id
    assert body["profile"]["overview"]["rows"] == 5


def test_get_profile_for_missing_dataset_returns_404(client) -> None:
    r = client.get("/api/v1/datasets/does-not-exist/profile")
    assert r.status_code == 404
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "DATASET_NOT_FOUND"
