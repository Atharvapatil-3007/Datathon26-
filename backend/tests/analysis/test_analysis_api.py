"""HTTP-level Phase 3 tests."""

from __future__ import annotations

import pytest


@pytest.fixture
def client():
    from fastapi.testclient import TestClient
    from app.main import _build_app

    app = _build_app()
    with TestClient(app) as c:
        yield c


def test_options_endpoint_lists_three_modes(client) -> None:
    r = client.get("/api/v1/analysis/options")
    assert r.status_code == 200
    body = r.json()
    modes = {m["mode"] for m in body["modes"]}
    assert modes == {
        "self_analysis",
        "merger_partnership_analysis",
        "competitor_market_benchmark",
    }


def test_self_analysis_endpoint(client, corporate_dataset_id: str) -> None:
    r = client.post(
        "/api/v1/analysis/self",
        json={"dataset_id": corporate_dataset_id, "display_name": "Acme Corp"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "self_analysis"
    assert body["primary_entity"]["display_name"] == "Acme Corp"


def test_merger_analysis_endpoint(
    client, corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    r = client.post(
        "/api/v1/analysis/merger",
        json={
            "primary_dataset_id": corporate_dataset_id,
            "secondary_dataset_id": competitor_dataset_id,
            "deal_type": "merger",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "merger_partnership_analysis"
    assert body["combined_scenario"] is not None


def test_benchmark_analysis_endpoint(
    client, corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    r = client.post(
        "/api/v1/analysis/benchmark",
        json={
            "primary_dataset_id": corporate_dataset_id,
            "competitor_dataset_id": competitor_dataset_id,
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "competitor_market_benchmark"
    assert body["gaps"], "expected at least one gap for this fixture pair"


def test_self_analysis_404_on_missing_dataset(client) -> None:
    r = client.post(
        "/api/v1/analysis/self",
        json={"dataset_id": "does-not-exist"},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "DATASET_NOT_FOUND"


def test_merger_endpoint_rejects_same_dataset(client, corporate_dataset_id: str) -> None:
    r = client.post(
        "/api/v1/analysis/merger",
        json={
            "primary_dataset_id": corporate_dataset_id,
            "secondary_dataset_id": corporate_dataset_id,
        },
    )
    assert r.status_code == 422
    body = r.json()
    assert body["error"]["code"] == "INCOMPATIBLE_DATASETS"
