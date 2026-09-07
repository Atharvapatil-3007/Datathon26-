"""End-to-end Phase 3 flow test.

Exercises the full post-upload flow that a real user would drive from the
frontend:

    upload  ->  Phase 1 validate  ->  Phase 2 profile
        ->  GET /analysis/options  (mode selection)
        ->  POST /analysis/self
        ->  upload second dataset  ->  POST /analysis/merger
        ->  upload third dataset   ->  POST /analysis/benchmark (with market)

This is a *black-box* API-level test: it never reaches into internal state
except to build the CSV fixtures. Everything else goes through HTTP so we
catch bugs in the router wiring, validation, and JSON serialization.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


# ---------------------------------------------------------------------------
# Local test fixtures — separate CSVs so Phase 1 has to actually detect the
# format and Phase 2 has real numerical + date columns to profile.
# ---------------------------------------------------------------------------
def _write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def _make_pnl_csv(path: Path, base_revenue: float, growth: float) -> None:
    start = datetime(2024, 1, 1)
    rows = []
    revenue = base_revenue
    for i in range(4):
        rows.append(
            [
                (start + timedelta(days=90 * i)).strftime("%Y-%m-%d"),
                round(revenue, 2),
                round(revenue * 0.55, 2),   # cogs
                round(revenue * 0.20, 2),   # operating_expenses
                round(revenue * 0.15, 2),   # net_profit
                round(revenue * 3.5, 2),    # assets
                round(revenue * 1.8, 2),    # liabilities
                round(revenue * 1.7, 2),    # equity
                round(revenue * 0.9, 2),    # debt
                round(revenue * 0.6, 2),    # cash
            ]
        )
        revenue *= 1 + growth
    _write_csv(
        path,
        [
            "period_date",
            "revenue",
            "cogs",
            "operating_expenses",
            "net_profit",
            "total_assets",
            "total_liabilities",
            "equity",
            "debt",
            "cash",
        ],
        rows,
    )


@pytest.fixture
def client():
    from app.main import _build_app

    with TestClient(_build_app()) as c:
        yield c


@pytest.fixture
def three_csvs(tmp_path: Path) -> tuple[Path, Path, Path]:
    """Three distinct financial datasets we can use as primary / competitor / market."""
    our_path = tmp_path / "our_company.csv"
    competitor_path = tmp_path / "competitor.csv"
    market_path = tmp_path / "market.csv"
    _make_pnl_csv(our_path, base_revenue=100.0, growth=0.08)
    _make_pnl_csv(competitor_path, base_revenue=140.0, growth=0.10)
    _make_pnl_csv(market_path, base_revenue=120.0, growth=0.09)
    return our_path, competitor_path, market_path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _upload(client: TestClient, path: Path) -> str:
    with path.open("rb") as fh:
        r = client.post(
            "/api/v1/ingestion/upload",
            files={"file": (path.name, fh, "text/csv")},
        )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["success"] is True
    assert body["status"] == "validated"
    assert body["profile"] is not None, "expected Phase 2 profile in response"
    assert body["profile"]["column_profiles"], "profile has column data"
    return body["dataset_id"]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_options_endpoint_has_stable_shape(client) -> None:
    r = client.get("/api/v1/analysis/options")
    assert r.status_code == 200
    body = r.json()
    ids = {m["mode"] for m in body["modes"]}
    assert ids == {
        "self_analysis",
        "merger_partnership_analysis",
        "competitor_market_benchmark",
    }
    # Every mode carries a human-readable title and 'requires' list.
    for m in body["modes"]:
        assert m["title"].strip()
        assert m["description"].strip()
        assert isinstance(m["requires"], list) and m["requires"]


def test_full_flow_upload_profile_self_analyze(client, three_csvs) -> None:
    ours, _, _ = three_csvs
    dataset_id = _upload(client, ours)

    # Analysis mode selection is available.
    assert client.get("/api/v1/analysis/options").status_code == 200

    # Self analysis on the newly uploaded dataset.
    r = client.post(
        "/api/v1/analysis/self",
        json={"dataset_id": dataset_id, "display_name": "Our Company"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "self_analysis"
    assert body["primary_entity"]["display_name"] == "Our Company"
    # We expect at least revenue + net_profit metrics.
    metric_ids = {m["metric_id"] for m in body["metrics"]}
    assert "revenue" in metric_ids
    assert "net_profit" in metric_ids
    # Ratios present.
    ratio_ids = {r["metric_id"] for r in body["ratios"]}
    assert "net_margin" in ratio_ids
    # Financial health is populated.
    assert body["financial_health"] is not None
    assert body["financial_health"]["grade"] in {"A", "B", "C", "D", "F"}


def test_full_flow_upload_profile_merger(client, three_csvs) -> None:
    ours, competitor, _ = three_csvs
    primary_id = _upload(client, ours)
    secondary_id = _upload(client, competitor)

    r = client.post(
        "/api/v1/analysis/merger",
        json={
            "primary_dataset_id": primary_id,
            "secondary_dataset_id": secondary_id,
            "deal_type": "acquisition",
            "primary_display_name": "Our Company",
            "secondary_display_name": "Target Company",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "merger_partnership_analysis"
    assert body["combined_scenario"] is not None
    # Every metric in the combined scenario must be labeled SCENARIO.
    for m in body["combined_scenario"]["metrics"]:
        assert m["status"] == "scenario"
    # Ratios computed off combined base — status also SCENARIO.
    for r_row in body["ratios"]:
        assert r_row["status"] == "scenario"
    # Attractiveness score surfaces as a warning line.
    assert any("Attractiveness" in w for w in body["warnings"])


def test_full_flow_upload_profile_benchmark_with_market(client, three_csvs) -> None:
    ours, competitor, market = three_csvs
    primary_id = _upload(client, ours)
    competitor_id = _upload(client, competitor)
    market_id = _upload(client, market)

    r = client.post(
        "/api/v1/analysis/benchmark",
        json={
            "primary_dataset_id": primary_id,
            "competitor_dataset_id": competitor_id,
            "market_dataset_id": market_id,
            "primary_display_name": "Our Company",
            "competitor_display_name": "Competitor",
            "market_display_name": "Market Avg",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mode"] == "competitor_market_benchmark"
    assert body["market_entity"] is not None
    assert body["comparisons"], "expected at least one comparable metric"
    # Market column populated on at least one comparison row.
    assert any(c.get("market_value") is not None for c in body["comparisons"])
    # Gaps are ordered high-priority first.
    priorities = [g["priority"] for g in body["gaps"]]
    order = {"high": 0, "medium": 1, "low": 2}
    for i in range(1, len(priorities)):
        assert order[priorities[i - 1]] <= order[priorities[i]]


def test_error_flow_missing_dataset(client) -> None:
    r = client.post(
        "/api/v1/analysis/self",
        json={"dataset_id": "definitely-not-there"},
    )
    assert r.status_code == 404
    body = r.json()
    assert body["success"] is False
    assert body["error"]["code"] == "DATASET_NOT_FOUND"


def test_error_flow_merger_same_dataset(client, three_csvs) -> None:
    ours, _, _ = three_csvs
    dataset_id = _upload(client, ours)
    r = client.post(
        "/api/v1/analysis/merger",
        json={
            "primary_dataset_id": dataset_id,
            "secondary_dataset_id": dataset_id,
        },
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "INCOMPATIBLE_DATASETS"


def test_only_selected_mode_runs(client, three_csvs, caplog) -> None:
    """When Self is requested, Merger and Benchmark analyzers must NOT execute.

    We assert this by checking the log signal each analyzer emits at start;
    only one of the three should appear.
    """
    import logging

    ours, _, _ = three_csvs
    dataset_id = _upload(client, ours)

    caplog.clear()
    with caplog.at_level(logging.INFO):
        r = client.post(
            "/api/v1/analysis/self",
            json={"dataset_id": dataset_id},
        )
    assert r.status_code == 200
    messages = " ".join(rec.getMessage() for rec in caplog.records)
    assert "self_analysis_started" in messages
    assert "merger_analysis_started" not in messages
    assert "benchmark_analysis_started" not in messages
