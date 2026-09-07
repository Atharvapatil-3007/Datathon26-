"""Derived financial ratios.

Given a ``value_map`` of base metrics (produced by ``metric_extractor``),
compute the ratios listed in the spec \u2014 but *only* when the required
inputs are actually present and non-zero. Each ratio becomes a
``LabeledMetric`` with ``status=CALCULATED``, so the UI can visibly
distinguish it from reported values.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from app.analysis.metric_registry import get_definition
from app.analysis.types import (
    LabeledMetric,
    MetricDirection,
    MetricId,
    MetricStatus,
    MetricUnit,
)


# ---------------------------------------------------------------------------
# Ratio formulas
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RatioFormula:
    metric_id: MetricId
    numerator: MetricId
    denominator: MetricId
    multiplier: float = 1.0    # 100 for percentages, 1 for ratios
    #: Optional fallback numerator when the primary one isn't available.
    alt_numerator: Optional[Callable[[Dict[MetricId, float]], Optional[float]]] = None
    #: Optional fallback denominator (rare).
    alt_denominator: Optional[Callable[[Dict[MetricId, float]], Optional[float]]] = None


def _fallback_gross_profit(vm: Dict[MetricId, float]) -> Optional[float]:
    r, c = vm.get(MetricId.REVENUE), vm.get(MetricId.COGS)
    if r is None or c is None:
        return None
    return r - c


def _fallback_operating_profit(vm: Dict[MetricId, float]) -> Optional[float]:
    r, e = vm.get(MetricId.REVENUE), vm.get(MetricId.OPERATING_EXPENSES)
    if r is None or e is None:
        return None
    return r - e


def _bank_operating_income(vm: Dict[MetricId, float]) -> Optional[float]:
    nii = vm.get(MetricId.NET_INTEREST_INCOME)
    other = vm.get(MetricId.NON_INTEREST_INCOME)
    if nii is None and other is None:
        return None
    return (nii or 0.0) + (other or 0.0)


_FORMULAS: List[RatioFormula] = [
    # ----- Margins (percent) -----
    RatioFormula(
        MetricId.GROSS_MARGIN,
        numerator=MetricId.GROSS_PROFIT,
        denominator=MetricId.REVENUE,
        multiplier=100.0,
        alt_numerator=_fallback_gross_profit,
    ),
    RatioFormula(
        MetricId.OPERATING_MARGIN,
        numerator=MetricId.OPERATING_PROFIT,
        denominator=MetricId.REVENUE,
        multiplier=100.0,
        alt_numerator=_fallback_operating_profit,
    ),
    RatioFormula(
        MetricId.NET_MARGIN,
        numerator=MetricId.NET_PROFIT,
        denominator=MetricId.REVENUE,
        multiplier=100.0,
    ),
    RatioFormula(
        MetricId.FCF_MARGIN,
        numerator=MetricId.FREE_CASH_FLOW,
        denominator=MetricId.REVENUE,
        multiplier=100.0,
    ),

    # ----- Returns (percent) -----
    RatioFormula(MetricId.ROA, MetricId.NET_PROFIT, MetricId.ASSETS, multiplier=100.0),
    RatioFormula(MetricId.ROE, MetricId.NET_PROFIT, MetricId.EQUITY, multiplier=100.0),

    # ----- Solvency / liquidity (raw ratio) -----
    RatioFormula(MetricId.DEBT_TO_EQUITY, MetricId.DEBT, MetricId.EQUITY),
    RatioFormula(
        MetricId.CURRENT_RATIO,
        MetricId.CURRENT_ASSETS,
        MetricId.CURRENT_LIABILITIES,
    ),
    RatioFormula(
        MetricId.QUICK_RATIO,
        numerator=MetricId.CURRENT_ASSETS,
        denominator=MetricId.CURRENT_LIABILITIES,
        alt_numerator=lambda vm: (
            vm[MetricId.CURRENT_ASSETS] - vm[MetricId.INVENTORY]
            if MetricId.CURRENT_ASSETS in vm and MetricId.INVENTORY in vm
            else None
        ),
    ),

    # ----- Turnover (raw ratio) -----
    RatioFormula(MetricId.ASSET_TURNOVER, MetricId.REVENUE, MetricId.ASSETS),
    RatioFormula(
        MetricId.RECEIVABLES_TURNOVER, MetricId.REVENUE, MetricId.RECEIVABLES,
    ),
    RatioFormula(
        MetricId.INVENTORY_TURNOVER, MetricId.COGS, MetricId.INVENTORY,
    ),
    RatioFormula(
        MetricId.INTEREST_COVERAGE,
        numerator=MetricId.EBIT,
        denominator=MetricId.INTEREST_EXPENSE,
        alt_numerator=lambda vm: vm.get(MetricId.OPERATING_PROFIT),
    ),

    # ----- Banking (percent unless noted) -----
    RatioFormula(
        MetricId.COST_TO_INCOME,
        numerator=MetricId.OPERATING_EXPENSES,
        denominator=MetricId.NET_INTEREST_INCOME,
        multiplier=100.0,
        alt_denominator=_bank_operating_income,
    ),
    RatioFormula(
        MetricId.NIM,
        numerator=MetricId.NET_INTEREST_INCOME,
        denominator=MetricId.ASSETS,
        multiplier=100.0,
    ),
    RatioFormula(
        MetricId.CREDIT_DEPOSIT_RATIO,
        numerator=MetricId.LOANS,
        denominator=MetricId.DEPOSITS,
        multiplier=100.0,
    ),
    RatioFormula(
        MetricId.PROVISION_COVERAGE,
        numerator=MetricId.PROVISIONS,
        denominator=MetricId.GROSS_NPA,
        multiplier=100.0,
    ),
    RatioFormula(
        MetricId.CASA_RATIO,
        numerator=MetricId.CASA,
        denominator=MetricId.DEPOSITS,
        multiplier=100.0,
    ),
]


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def compute_ratios(
    value_map: Dict[MetricId, float],
) -> List[LabeledMetric]:
    """Return every ratio for which the required inputs exist.

    The result's ``value_map`` is *not* mutated by this call; callers may
    fold computed ratios back in afterwards if they wish.
    """
    out: List[LabeledMetric] = []
    for formula in _FORMULAS:
        metric = _apply(formula, value_map)
        if metric is not None:
            out.append(metric)
    return out


# ---------------------------------------------------------------------------
# Formula application
# ---------------------------------------------------------------------------
def _apply(formula: RatioFormula, vm: Dict[MetricId, float]) -> Optional[LabeledMetric]:
    numerator = _resolve(vm, formula.numerator, formula.alt_numerator)
    denominator = _resolve(vm, formula.denominator, formula.alt_denominator)
    if numerator is None or denominator is None:
        return None
    if denominator == 0:
        # Explicitly emit as UNAVAILABLE so the UI can show *why* it's blank.
        definition = get_definition(formula.metric_id)
        return LabeledMetric(
            metric_id=formula.metric_id,
            display_name=definition.display_name,
            value=None,
            unit=definition.unit,
            status=MetricStatus.UNAVAILABLE,
            direction=definition.direction,
            confidence=0.5,
            notes=[f"Denominator ({formula.denominator.value}) is zero \u2014 ratio undefined."],
        )

    value = (numerator / denominator) * formula.multiplier
    definition = get_definition(formula.metric_id)
    return LabeledMetric(
        metric_id=formula.metric_id,
        display_name=definition.display_name,
        value=value,
        unit=definition.unit,
        status=MetricStatus.CALCULATED,
        direction=definition.direction,
        source_columns=[],
        confidence=0.9,
        notes=[
            f"{formula.numerator.value} / {formula.denominator.value}"
            + ("  \u00d7 100" if formula.multiplier == 100.0 else ""),
        ],
    )


def _resolve(
    vm: Dict[MetricId, float],
    primary: MetricId,
    fallback: Optional[Callable[[Dict[MetricId, float]], Optional[float]]],
) -> Optional[float]:
    v = vm.get(primary)
    if v is not None:
        return v
    if fallback is None:
        return None
    return fallback(vm)
