"""Dynamic financial health scoring.

Assembles a 0-100 score with A-F grade using whichever metrics + ratios the
extractor and ratio engine were able to compute. Every dimension is only
scored when its underlying data is present, so an incomplete dataset gets
an *incomplete* score rather than a fabricated one.

Dimensions (each 0-100):

* profitability  \u2014 NET_MARGIN, ROE, ROA
* liquidity      \u2014 CURRENT_RATIO, QUICK_RATIO
* leverage       \u2014 DEBT_TO_EQUITY (inverted \u2014 lower is better)
* efficiency     \u2014 ASSET_TURNOVER
* growth         \u2014 revenue trend growth rate

Overall = weighted average across the dimensions that were actually scored.
Weights adapt to the metric mix so a bank-focused dataset weights leverage
and profitability differently than a corporate one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

from app.analysis.trend_analyzer import TrendResult
from app.analysis.types import HealthScore, LabeledMetric, MetricId, MetricStatus


@dataclass
class HealthInputs:
    value_map: Dict[MetricId, float]
    ratios: List[LabeledMetric]
    trends: Dict[MetricId, TrendResult]


# ---------------------------------------------------------------------------
# Score curves: convert raw metric -> 0-100
# ---------------------------------------------------------------------------
def _score_range(value: float, poor: float, target: float, cap: float = 100.0) -> float:
    """Linearly map ``value`` between ``poor`` -> 0 and ``target`` -> 100.

    Anything above ``target`` clamps at 100 (unless we want to keep pushing).
    """
    if value <= poor:
        return 0.0
    if value >= target:
        return cap
    return round((value - poor) / (target - poor) * cap, 2)


def _inverse_score_range(value: float, target: float, poor: float, cap: float = 100.0) -> float:
    """Lower is better: ``target`` -> 100, ``poor`` -> 0."""
    if value <= target:
        return cap
    if value >= poor:
        return 0.0
    return round((poor - value) / (poor - target) * cap, 2)


# ---------------------------------------------------------------------------
# Dimension calculators
# ---------------------------------------------------------------------------
def _profitability(ratios: Dict[MetricId, LabeledMetric]) -> Optional[float]:
    scores: List[float] = []
    if _has(ratios, MetricId.NET_MARGIN):
        scores.append(_score_range(ratios[MetricId.NET_MARGIN].value or 0.0, poor=0, target=20))
    if _has(ratios, MetricId.ROE):
        scores.append(_score_range(ratios[MetricId.ROE].value or 0.0, poor=0, target=20))
    if _has(ratios, MetricId.ROA):
        scores.append(_score_range(ratios[MetricId.ROA].value or 0.0, poor=0, target=10))
    return _mean(scores)


def _liquidity(ratios: Dict[MetricId, LabeledMetric]) -> Optional[float]:
    scores: List[float] = []
    if _has(ratios, MetricId.CURRENT_RATIO):
        scores.append(_score_range(ratios[MetricId.CURRENT_RATIO].value or 0.0, poor=1.0, target=2.0))
    if _has(ratios, MetricId.QUICK_RATIO):
        scores.append(_score_range(ratios[MetricId.QUICK_RATIO].value or 0.0, poor=0.5, target=1.5))
    return _mean(scores)


def _leverage(ratios: Dict[MetricId, LabeledMetric]) -> Optional[float]:
    if not _has(ratios, MetricId.DEBT_TO_EQUITY):
        return None
    return _inverse_score_range(
        ratios[MetricId.DEBT_TO_EQUITY].value or 0.0,
        target=0.5,
        poor=2.5,
    )


def _efficiency(ratios: Dict[MetricId, LabeledMetric]) -> Optional[float]:
    scores: List[float] = []
    if _has(ratios, MetricId.ASSET_TURNOVER):
        scores.append(_score_range(ratios[MetricId.ASSET_TURNOVER].value or 0.0, poor=0.1, target=1.5))
    if _has(ratios, MetricId.INVENTORY_TURNOVER):
        scores.append(_score_range(ratios[MetricId.INVENTORY_TURNOVER].value or 0.0, poor=1.0, target=8.0))
    return _mean(scores)


def _growth(trends: Dict[MetricId, TrendResult]) -> Optional[float]:
    revenue = trends.get(MetricId.REVENUE)
    if revenue is None or revenue.growth_rate is None:
        return None
    # Growth of >= 15% overall -> 100; -10% or worse -> 0.
    return _score_range(revenue.growth_rate, poor=-10, target=15)


# ---------------------------------------------------------------------------
# Weights (configurable)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class HealthWeights:
    """Dimension weights for the overall health score.

    A finance SME can build a custom instance and pass it into ``score_health``
    without touching the module. The default weights below were chosen so
    profitability dominates and cannot be silently outweighed by leverage.
    """

    profitability: float = 0.30
    liquidity: float = 0.20
    leverage: float = 0.20
    efficiency: float = 0.15
    growth: float = 0.15

    def ordered(self) -> "list[tuple[str, float]]":
        return [
            ("profitability", self.profitability),
            ("liquidity", self.liquidity),
            ("leverage", self.leverage),
            ("efficiency", self.efficiency),
            ("growth", self.growth),
        ]


DEFAULT_HEALTH_WEIGHTS = HealthWeights()


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def score_health(
    inputs: HealthInputs,
    weights: HealthWeights = DEFAULT_HEALTH_WEIGHTS,
) -> HealthScore:
    ratios_by_id = {r.metric_id: r for r in inputs.ratios}

    dims: Dict[str, Optional[float]] = {
        "profitability": _profitability(ratios_by_id),
        "liquidity": _liquidity(ratios_by_id),
        "leverage": _leverage(ratios_by_id),
        "efficiency": _efficiency(ratios_by_id),
        "growth": _growth(inputs.trends),
    }

    # Weighted average over the dimensions that were actually scored.
    scored = [(name, dims[name], w) for name, w in weights.ordered() if dims[name] is not None]
    if not scored:
        return HealthScore(
            overall_score=0.0,
            grade="F",
            dimensions={},
            notes=[
                "Insufficient financial metrics to compute a health score.",
                "Provide at least revenue / profit / assets or equity in your dataset.",
            ],
        )

    total_w = sum(w for _, _, w in scored)
    overall = sum(v * w for _, v, w in scored) / total_w  # type: ignore[operator]
    notes = _generate_notes(dims, ratios_by_id, inputs.trends)

    return HealthScore(
        overall_score=float(overall),
        grade=_grade(overall),
        dimensions={k: float(v) for k, v in dims.items() if v is not None},
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _has(ratios: Dict[MetricId, LabeledMetric], mid: MetricId) -> bool:
    m = ratios.get(mid)
    return m is not None and m.status != MetricStatus.UNAVAILABLE and m.value is not None


def _mean(values: Iterable[float]) -> Optional[float]:
    vs = [v for v in values if v is not None]
    if not vs:
        return None
    return sum(vs) / len(vs)


def _grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _generate_notes(
    dims: Dict[str, Optional[float]],
    ratios: Dict[MetricId, LabeledMetric],
    trends: Dict[MetricId, TrendResult],
) -> List[str]:
    notes: List[str] = []
    missing = [k for k, v in dims.items() if v is None]
    if missing:
        notes.append(f"Dimensions not scored (missing data): {', '.join(missing)}.")
    if _has(ratios, MetricId.NET_MARGIN) and (ratios[MetricId.NET_MARGIN].value or 0) < 0:
        notes.append("Net margin is negative \u2014 the company is loss-making on aggregate.")
    if _has(ratios, MetricId.DEBT_TO_EQUITY) and (ratios[MetricId.DEBT_TO_EQUITY].value or 0) > 2.0:
        notes.append("Debt-to-equity above 2.0 signals elevated leverage.")
    if (
        _has(ratios, MetricId.CURRENT_RATIO)
        and (ratios[MetricId.CURRENT_RATIO].value or 0) < 1.0
    ):
        notes.append(
            "Current ratio below 1.0 \u2014 short-term liabilities exceed short-term assets."
        )
    revenue_trend = trends.get(MetricId.REVENUE)
    if revenue_trend and revenue_trend.direction == "declining":
        notes.append(
            f"Revenue is declining across observed periods "
            f"({revenue_trend.growth_rate:.1f}% total change)."
        )
    return notes
