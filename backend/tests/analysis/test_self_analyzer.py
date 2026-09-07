"""End-to-end self analysis: run the full pipeline against an ingested dataset."""

from __future__ import annotations

import json

import pytest

from app.analysis.exceptions import InsufficientDataError
from app.analysis.self_analyzer import run_self_analysis
from app.analysis.types import AnalysisMode, MetricId, MetricStatus


def test_self_analysis_covers_all_result_fields(corporate_dataset_id: str) -> None:
    result = run_self_analysis(corporate_dataset_id)
    payload = result.to_dict()

    # This must be JSON-safe end-to-end.
    assert isinstance(json.dumps(payload), str)

    assert payload["mode"] == AnalysisMode.SELF_ANALYSIS.value
    assert payload["primary_entity"] is not None
    assert payload["financial_health"] is not None
    assert isinstance(payload["metrics"], list) and payload["metrics"]
    assert isinstance(payload["ratios"], list)
    assert payload["summary_text"]


def test_self_analysis_finds_expected_metrics(corporate_dataset_id: str) -> None:
    result = run_self_analysis(corporate_dataset_id)
    by_id = {m.metric_id: m for m in result.metrics}
    assert MetricId.REVENUE in by_id
    assert MetricId.NET_PROFIT in by_id
    assert MetricId.ASSETS in by_id
    assert MetricId.EQUITY in by_id
    assert MetricId.DEBT in by_id
    # Each base metric should be REPORTED (or ESTIMATED for latest-of-period balance-sheet fallback).
    for m in result.metrics:
        assert m.status in (MetricStatus.REPORTED, MetricStatus.ESTIMATED)


def test_self_analysis_ratios_have_expected_shape(corporate_dataset_id: str) -> None:
    result = run_self_analysis(corporate_dataset_id)
    ratios = {r.metric_id: r for r in result.ratios}
    assert MetricId.NET_MARGIN in ratios
    assert MetricId.ROA in ratios
    assert MetricId.ROE in ratios
    for r in result.ratios:
        assert r.status in (MetricStatus.CALCULATED, MetricStatus.UNAVAILABLE)


def test_self_analysis_generates_insights(corporate_dataset_id: str) -> None:
    result = run_self_analysis(corporate_dataset_id)
    kinds = {i.kind.value for i in result.insights}
    # We should have at least observations.
    assert "observation" in kinds
    # Every insight text is non-empty.
    for i in result.insights + result.recommendations:
        assert i.text.strip()


def test_self_analysis_confidence_metadata(corporate_dataset_id: str) -> None:
    result = run_self_analysis(corporate_dataset_id)
    assert result.confidence is not None
    assert 0.0 <= result.confidence.metric_coverage <= 1.0
    assert 0.0 <= result.confidence.overall <= 1.0


def test_self_analysis_raises_on_dataset_without_metrics(tmp_path) -> None:
    # Ingest a dataset with no matchable column names.
    from tests.analysis.conftest import _write_csv
    from app.ingestion.manager import get_ingestion_manager

    p = tmp_path / "noise.csv"
    _write_csv(p, ["foo", "bar", "baz"], [[i, i * 2, i * 3] for i in range(5)])
    result, _ = get_ingestion_manager().ingest_file(
        temp_path=str(p), filename="noise.csv", mime_type="text/csv"
    )

    with pytest.raises(InsufficientDataError):
        run_self_analysis(result.dataset.dataset_id)
