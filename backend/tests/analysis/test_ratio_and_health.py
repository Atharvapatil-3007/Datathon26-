"""Ratio engine + health scorer tests."""

from __future__ import annotations

from app.analysis.health_scorer import HealthInputs, score_health
from app.analysis.ratio_engine import compute_ratios
from app.analysis.types import MetricId, MetricStatus


def _to_map(ratios):
    return {r.metric_id: r for r in ratios}


def test_ratios_compute_from_base_values() -> None:
    vm = {
        MetricId.REVENUE: 1000.0,
        MetricId.NET_PROFIT: 100.0,
        MetricId.ASSETS: 5000.0,
        MetricId.EQUITY: 2000.0,
        MetricId.DEBT: 1500.0,
    }
    ratios = _to_map(compute_ratios(vm))
    assert ratios[MetricId.NET_MARGIN].value == 10.0     # 100/1000 * 100
    assert ratios[MetricId.ROA].value == 2.0             # 100/5000 * 100
    assert ratios[MetricId.ROE].value == 5.0             # 100/2000 * 100
    assert ratios[MetricId.DEBT_TO_EQUITY].value == 0.75  # 1500/2000
    for r in ratios.values():
        assert r.status in (MetricStatus.CALCULATED, MetricStatus.UNAVAILABLE)


def test_gross_margin_fallback_from_revenue_minus_cogs() -> None:
    vm = {MetricId.REVENUE: 1000.0, MetricId.COGS: 600.0}
    ratios = _to_map(compute_ratios(vm))
    assert MetricId.GROSS_MARGIN in ratios
    assert ratios[MetricId.GROSS_MARGIN].value == 40.0  # (1000-600)/1000 * 100


def test_ratio_with_zero_denominator_is_unavailable() -> None:
    vm = {MetricId.NET_PROFIT: 50.0, MetricId.EQUITY: 0.0}
    ratios = _to_map(compute_ratios(vm))
    roe = ratios.get(MetricId.ROE)
    assert roe is not None
    assert roe.status == MetricStatus.UNAVAILABLE
    assert any("zero" in n.lower() or "undefined" in n.lower() for n in roe.notes)


def test_health_score_all_dimensions_present() -> None:
    vm = {
        MetricId.REVENUE: 1000.0,
        MetricId.NET_PROFIT: 200.0,
        MetricId.ASSETS: 5000.0,
        MetricId.EQUITY: 2000.0,
        MetricId.DEBT: 500.0,
        MetricId.CURRENT_ASSETS: 800.0,
        MetricId.CURRENT_LIABILITIES: 400.0,
    }
    ratios = compute_ratios(vm)
    score = score_health(HealthInputs(value_map=vm, ratios=ratios, trends={}))
    # Healthy company \u2014 should be in A/B range.
    assert score.overall_score >= 70
    assert score.grade in ("A", "B", "C")
    assert "profitability" in score.dimensions


def test_health_score_falls_back_when_no_metrics() -> None:
    score = score_health(HealthInputs(value_map={}, ratios=[], trends={}))
    assert score.grade == "F"
    assert score.dimensions == {}
    assert any("insufficient" in n.lower() for n in score.notes)


def test_health_notes_flag_negative_margin() -> None:
    vm = {MetricId.REVENUE: 1000.0, MetricId.NET_PROFIT: -50.0}
    ratios = compute_ratios(vm)
    score = score_health(HealthInputs(value_map=vm, ratios=ratios, trends={}))
    assert any("loss" in n.lower() or "negative" in n.lower() for n in score.notes)
