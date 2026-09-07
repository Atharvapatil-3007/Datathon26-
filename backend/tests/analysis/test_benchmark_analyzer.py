"""Benchmark analyzer tests."""

from __future__ import annotations

import json

import pytest

from app.analysis.benchmark_analyzer import run_benchmark_analysis
from app.analysis.exceptions import IncompatibleDatasetsError
from app.analysis.types import (
    AnalysisMode,
    MetricDirection,
    MetricId,
    Priority,
)


def test_benchmark_smoke(corporate_dataset_id: str, competitor_dataset_id: str) -> None:
    result = run_benchmark_analysis(corporate_dataset_id, competitor_dataset_id)
    payload = result.to_dict()
    assert isinstance(json.dumps(payload), str)
    assert payload["mode"] == AnalysisMode.COMPETITOR_MARKET_BENCHMARK.value
    assert payload["primary_entity"] is not None
    assert payload["secondary_entity"] is not None
    assert isinstance(payload["comparisons"], list)
    assert payload["comparisons"]


def test_benchmark_produces_behind_status_for_worse_metrics(
    corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    """The corporate fixture has lower revenue + net profit + margin than the
    competitor \u2014 those rows must come back with status='behind'.
    """
    result = run_benchmark_analysis(corporate_dataset_id, competitor_dataset_id)
    by_id = {c.metric_id: c for c in result.comparisons}
    assert by_id[MetricId.REVENUE].status == "behind"
    assert by_id[MetricId.NET_PROFIT].status == "behind"


def test_direction_flip_for_lower_better(
    corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    """D/E is LOWER_BETTER \u2014 the ahead/behind flag must respect direction."""
    result = run_benchmark_analysis(corporate_dataset_id, competitor_dataset_id)
    de = next((c for c in result.comparisons if c.metric_id == MetricId.DEBT_TO_EQUITY), None)
    if not de or de.primary_value is None or de.secondary_value is None:
        pytest.skip("D/E not computable for both datasets in fixture")
    expected = "behind" if de.primary_value > de.secondary_value else "ahead"
    assert de.status == expected


def test_gaps_only_include_behind_rows(
    corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    result = run_benchmark_analysis(corporate_dataset_id, competitor_dataset_id)
    for g in result.gaps:
        row = next((c for c in result.comparisons if c.metric_id == g.metric_id), None)
        assert row is not None and row.status == "behind"


def test_near_term_target_is_between_current_and_benchmark(
    corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    result = run_benchmark_analysis(corporate_dataset_id, competitor_dataset_id)
    for g in result.gaps:
        if g.current_value is None or g.benchmark_value is None or g.near_term_target is None:
            continue
        lo, hi = sorted([g.current_value, g.benchmark_value])
        assert lo - 1e-6 <= g.near_term_target <= hi + 1e-6


def test_priority_high_when_high_importance_metric_gaps(
    corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    result = run_benchmark_analysis(corporate_dataset_id, competitor_dataset_id)
    # Revenue has ~28% gap between fixtures \u2014 must land as HIGH priority.
    rev_gap = next((g for g in result.gaps if g.metric_id == MetricId.REVENUE), None)
    assert rev_gap is not None
    assert rev_gap.priority == Priority.HIGH


def test_gaps_sorted_by_priority(
    corporate_dataset_id: str, competitor_dataset_id: str
) -> None:
    result = run_benchmark_analysis(corporate_dataset_id, competitor_dataset_id)
    priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
    seen = [priority_order[g.priority] for g in result.gaps]
    assert seen == sorted(seen)


def test_same_dataset_rejected(corporate_dataset_id: str) -> None:
    with pytest.raises(IncompatibleDatasetsError):
        run_benchmark_analysis(corporate_dataset_id, corporate_dataset_id)
