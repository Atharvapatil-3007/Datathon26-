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


# ---------------------------------------------------------------------------
# F-04: configurable weights
# ---------------------------------------------------------------------------
def test_health_weights_are_configurable() -> None:
    """Passing custom weights should demonstrably move the overall score."""
    from app.analysis.health_scorer import HealthWeights

    # Same inputs, two very different weight profiles.
    vm = {
        MetricId.REVENUE: 1000.0,
        MetricId.NET_PROFIT: 300.0,           # 30 % net margin -> capped at 100
        MetricId.ASSETS: 2000.0,              # ROA = 15 % -> capped at 100
        MetricId.EQUITY: 1500.0,              # ROE = 20 % -> hits target
        MetricId.DEBT: 10000.0,               # D/E ~6.7 -> leverage dimension = 0
        MetricId.CURRENT_ASSETS: 300.0,
        MetricId.CURRENT_LIABILITIES: 1000.0, # current ratio 0.3 -> liquidity 0
    }
    ratios = compute_ratios(vm)

    heavy_profit = HealthWeights(
        profitability=1.0, liquidity=0.0, leverage=0.0, efficiency=0.0, growth=0.0
    )
    heavy_lev = HealthWeights(
        profitability=0.0, liquidity=0.0, leverage=1.0, efficiency=0.0, growth=0.0
    )

    high = score_health(
        HealthInputs(value_map=vm, ratios=ratios, trends={}), weights=heavy_profit
    )
    low = score_health(
        HealthInputs(value_map=vm, ratios=ratios, trends={}), weights=heavy_lev
    )
    assert high.overall_score > 90
    assert low.overall_score < 20


def test_attractiveness_weights_are_configurable() -> None:
    from app.analysis.merger_analyzer import (
        AttractivenessWeights,
        _attractiveness_score,
    )
    from app.analysis.types import HealthScore

    health = HealthScore(overall_score=80.0, grade="B", dimensions={})
    args = {
        "combined_health": health,
        "combined_ratios": [],
        "primary_value_map": {MetricId.REVENUE: 100.0},
        "secondary_value_map": {MetricId.REVENUE: 100.0},
        "synergies": [],
        "risks": [],
    }

    default_score = _attractiveness_score(**args)

    # Zero-out every driver \u2014 result should be exactly base_score.
    all_off = AttractivenessWeights(
        base_score=50.0,
        health_delta_weight=0.0,
        revenue_uplift_multiplier=0.0,
        revenue_uplift_cap=0.0,
        loss_making_penalty=0.0,
        material_synergy_weight=0.0,
        material_synergy_cap=0.0,
        high_risk_penalty=0.0,
        high_risk_cap=0.0,
    )
    silenced = _attractiveness_score(**args, weights=all_off)
    assert silenced == 50.0
    assert default_score != silenced  # defaults produce a different number
