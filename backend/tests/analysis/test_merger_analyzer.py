"""Merger / partnership analyzer tests."""

from __future__ import annotations

import json

import pytest

from app.analysis.exceptions import IncompatibleDatasetsError
from app.analysis.merger_analyzer import run_merger_analysis
from app.analysis.types import AnalysisMode, MetricId, MetricStatus


def test_merger_analysis_smoke(corporate_dataset_id: str, competitor_dataset_id: str) -> None:
    result = run_merger_analysis(
        corporate_dataset_id, competitor_dataset_id, deal_type="merger"
    )
    payload = result.to_dict()
    assert isinstance(json.dumps(payload), str)
    assert payload["mode"] == AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS.value
    assert payload["primary_entity"] is not None
    assert payload["secondary_entity"] is not None
    assert payload["combined_scenario"] is not None
    assert payload["combined_scenario"]["metrics"]
    assert "Not a Forecast" in payload["combined_scenario"]["label"]


def test_combined_scenario_metrics_are_labeled_scenario(
    corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    result = run_merger_analysis(corporate_dataset_id, competitor_dataset_id)
    for m in result.combined_scenario.metrics:
        assert m.status == MetricStatus.SCENARIO


def test_combined_scenario_ratios_recalculated_not_summed(
    corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    result = run_merger_analysis(corporate_dataset_id, competitor_dataset_id)
    # Every combined ratio must be SCENARIO and reference "combined base"
    # in its notes (proof it was recalculated, not summed).
    for r in result.ratios:
        assert r.status == MetricStatus.SCENARIO
        assert any("combined" in note.lower() for note in r.notes)


def test_combined_revenue_is_the_sum(
    corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    result = run_merger_analysis(corporate_dataset_id, competitor_dataset_id)
    primary_rev = _find(result.primary_entity.metrics, MetricId.REVENUE)
    secondary_rev = _find(result.secondary_entity.metrics, MetricId.REVENUE)
    combined_rev = _find(result.combined_scenario.metrics, MetricId.REVENUE)
    assert primary_rev and secondary_rev and combined_rev
    assert abs((primary_rev.value + secondary_rev.value) - combined_rev.value) < 0.001


def test_merger_synergies_are_data_supported(
    corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    result = run_merger_analysis(corporate_dataset_id, competitor_dataset_id)
    # We should have at least a revenue synergy (both have REVENUE).
    assert any(s.kind == "revenue" for s in result.synergies)
    # Every synergy declares supporting_metrics.
    for s in result.synergies:
        assert s.supporting_metrics


def test_merger_risks_include_data_limitation_note(
    corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    result = run_merger_analysis(corporate_dataset_id, competitor_dataset_id)
    titles = [r.title for r in result.risks]
    assert any("data" in t.lower() for t in titles)


def test_merger_attractiveness_score_in_warnings(
    corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    result = run_merger_analysis(corporate_dataset_id, competitor_dataset_id)
    assert any(
        "Attractiveness" in w for w in result.warnings
    )


def test_same_dataset_rejected(corporate_dataset_id: str) -> None:
    with pytest.raises(IncompatibleDatasetsError):
        run_merger_analysis(corporate_dataset_id, corporate_dataset_id)


def _find(metrics, mid: MetricId):
    for m in metrics:
        if m.metric_id == mid and m.value is not None:
            return m
    return None
