"""Insight engine.

Turns raw metrics, ratios, trends, health scores, and gap analyses into
classified ``Insight`` objects (OBSERVATION / ANALYSIS / RECOMMENDATION).

Design principle:
  * every insight is data-driven \u2014 we only fire a rule when the underlying
    metric is present.
  * we never claim causation. Recommendations are always framed as
    "investigate ..." or "consider ..." rather than "do X to improve Y".
  * strengths / weaknesses / opportunities / risks are derived from the
    same rule outputs so the UI can render them side-by-side.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

from app.analysis.trend_analyzer import TrendResult
from app.analysis.types import (
    GapItem,
    HealthScore,
    Insight,
    InsightKind,
    LabeledMetric,
    MetricDirection,
    MetricId,
    MetricStatus,
    MetricUnit,
    Priority,
    SynergyItem,
    RiskItem,
)


# ---------------------------------------------------------------------------
# Output container
# ---------------------------------------------------------------------------
@dataclass
class InsightBundle:
    insights: List[Insight] = field(default_factory=list)
    recommendations: List[Insight] = field(default_factory=list)
    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)

    def add_observation(self, text: str, related: Iterable[str] = ()) -> None:
        self.insights.append(
            Insight(kind=InsightKind.OBSERVATION, text=text, related_metrics=list(related))
        )

    def add_analysis(
        self,
        text: str,
        related: Iterable[str] = (),
        priority: Priority = Priority.MEDIUM,
    ) -> None:
        self.insights.append(
            Insight(
                kind=InsightKind.ANALYSIS,
                text=text,
                related_metrics=list(related),
                priority=priority,
            )
        )

    def add_recommendation(
        self,
        text: str,
        related: Iterable[str] = (),
        priority: Priority = Priority.MEDIUM,
    ) -> None:
        self.recommendations.append(
            Insight(
                kind=InsightKind.RECOMMENDATION,
                text=text,
                related_metrics=list(related),
                priority=priority,
            )
        )


# ---------------------------------------------------------------------------
# Self-analysis insights
# ---------------------------------------------------------------------------
def generate_self_insights(
    metrics: List[LabeledMetric],
    ratios: List[LabeledMetric],
    trends: Dict[MetricId, TrendResult],
    health: HealthScore,
) -> InsightBundle:
    b = InsightBundle()
    by_id: Dict[MetricId, LabeledMetric] = {m.metric_id: m for m in metrics if _has_value(m)}
    ratios_by_id: Dict[MetricId, LabeledMetric] = {
        r.metric_id: r for r in ratios if _has_value(r)
    }

    _self_profitability(b, by_id, ratios_by_id)
    _self_leverage(b, ratios_by_id)
    _self_liquidity(b, ratios_by_id)
    _self_trends(b, trends)
    _self_banking(b, by_id, ratios_by_id)
    _self_health(b, health)

    return b


def _self_profitability(
    b: InsightBundle,
    metrics: Dict[MetricId, LabeledMetric],
    ratios: Dict[MetricId, LabeledMetric],
) -> None:
    net_margin = ratios.get(MetricId.NET_MARGIN)
    if net_margin and net_margin.value is not None:
        b.add_observation(
            f"Net profit margin is {net_margin.value:.2f}%.",
            related=[MetricId.NET_MARGIN.value],
        )
        if net_margin.value < 0:
            b.add_analysis(
                "Company is loss-making in aggregate over the observed data.",
                related=[MetricId.NET_MARGIN.value, MetricId.NET_PROFIT.value],
                priority=Priority.HIGH,
            )
            b.weaknesses.append("Negative net margin")
            b.risks.append("Sustained losses may erode equity and liquidity buffers")
            b.add_recommendation(
                "Investigate cost structure and revenue mix to identify margin improvement opportunities.",
                related=[MetricId.OPERATING_EXPENSES.value, MetricId.REVENUE.value],
                priority=Priority.HIGH,
            )
        elif net_margin.value >= 15:
            b.strengths.append(f"Healthy net margin at {net_margin.value:.1f}%")
        elif net_margin.value < 5:
            b.weaknesses.append(f"Thin net margin at {net_margin.value:.1f}%")

    gross = ratios.get(MetricId.GROSS_MARGIN)
    net = ratios.get(MetricId.NET_MARGIN)
    if gross and net and gross.value is not None and net.value is not None:
        gap = gross.value - net.value
        if gap > 25:
            b.add_analysis(
                f"Gross-to-net margin gap of {gap:.1f} pp suggests significant operating "
                "and non-operating cost drag between top line and bottom line.",
                related=[MetricId.GROSS_MARGIN.value, MetricId.NET_MARGIN.value],
                priority=Priority.MEDIUM,
            )
            b.add_recommendation(
                "Break down operating expenses, interest, and tax to find the largest margin leaks.",
                related=[MetricId.OPERATING_EXPENSES.value],
            )


def _self_leverage(b: InsightBundle, ratios: Dict[MetricId, LabeledMetric]) -> None:
    de = ratios.get(MetricId.DEBT_TO_EQUITY)
    if not de or de.value is None:
        return
    b.add_observation(
        f"Debt-to-equity ratio is {de.value:.2f}.",
        related=[MetricId.DEBT_TO_EQUITY.value],
    )
    if de.value > 2.0:
        b.add_analysis(
            "Leverage is high \u2014 debt is more than 2x equity.",
            related=[MetricId.DEBT_TO_EQUITY.value],
            priority=Priority.HIGH,
        )
        b.risks.append("High leverage exposes earnings to interest-rate and refinancing risk")
        b.add_recommendation(
            "Consider debt reduction or equity strengthening to improve balance-sheet resilience.",
            priority=Priority.HIGH,
        )
    elif de.value < 0.3:
        b.strengths.append(f"Conservative capital structure (D/E = {de.value:.2f})")


def _self_liquidity(b: InsightBundle, ratios: Dict[MetricId, LabeledMetric]) -> None:
    cr = ratios.get(MetricId.CURRENT_RATIO)
    if not cr or cr.value is None:
        return
    b.add_observation(
        f"Current ratio is {cr.value:.2f}.",
        related=[MetricId.CURRENT_RATIO.value],
    )
    if cr.value < 1.0:
        b.add_analysis(
            "Short-term liabilities exceed short-term assets \u2014 potential liquidity pressure.",
            related=[MetricId.CURRENT_RATIO.value],
            priority=Priority.HIGH,
        )
        b.risks.append("Liquidity pressure \u2014 current ratio below 1.0")
        b.add_recommendation(
            "Review working capital management and short-term financing to improve liquidity.",
            priority=Priority.HIGH,
        )
    elif cr.value >= 1.5:
        b.strengths.append("Comfortable liquidity buffer")


def _self_trends(b: InsightBundle, trends: Dict[MetricId, TrendResult]) -> None:
    revenue = trends.get(MetricId.REVENUE)
    if revenue and revenue.growth_rate is not None:
        b.add_observation(
            f"Revenue changed by {revenue.growth_rate:+.1f}% across {revenue.period_count} periods.",
            related=[MetricId.REVENUE.value],
        )
        if revenue.direction == "improving":
            b.strengths.append(f"Revenue trending up ({revenue.growth_rate:+.1f}%)")
            b.opportunities.append("Growth momentum may support expansion / new investments")
        elif revenue.direction == "declining":
            b.weaknesses.append(f"Revenue trending down ({revenue.growth_rate:+.1f}%)")
            b.add_analysis(
                "Revenue is declining across observed periods.",
                related=[MetricId.REVENUE.value],
                priority=Priority.HIGH,
            )
            b.add_recommendation(
                "Investigate demand, pricing, churn, and competitive positioning behind the revenue decline.",
                related=[MetricId.REVENUE.value],
                priority=Priority.HIGH,
            )

    profit = trends.get(MetricId.NET_PROFIT)
    if profit and profit.growth_rate is not None and profit.direction == "declining":
        b.weaknesses.append(f"Net profit trending down ({profit.growth_rate:+.1f}%)")
        b.add_analysis(
            "Bottom-line profit is trending down while revenue may still be growing \u2014 "
            "cost or interest / tax dynamics warrant attention.",
            related=[MetricId.NET_PROFIT.value],
            priority=Priority.HIGH,
        )


def _self_banking(
    b: InsightBundle,
    metrics: Dict[MetricId, LabeledMetric],
    ratios: Dict[MetricId, LabeledMetric],
) -> None:
    # Only fire the banking rules if banking-specific data exists.
    if not any(m in metrics for m in (MetricId.DEPOSITS, MetricId.LOANS, MetricId.NET_INTEREST_INCOME)):
        return

    cti = ratios.get(MetricId.COST_TO_INCOME)
    if cti and cti.value is not None:
        b.add_observation(
            f"Cost-to-income ratio is {cti.value:.2f}%.",
            related=[MetricId.COST_TO_INCOME.value],
        )
        if cti.value > 60:
            b.weaknesses.append(f"Cost-to-income at {cti.value:.1f}% \u2014 above efficient-bank benchmark")
            b.add_recommendation(
                "Review operating cost base against a peer bank benchmark to identify efficiency opportunities.",
                related=[MetricId.OPERATING_EXPENSES.value],
            )

    cdr = ratios.get(MetricId.CREDIT_DEPOSIT_RATIO)
    if cdr and cdr.value is not None:
        b.add_observation(
            f"Credit-to-deposit ratio is {cdr.value:.2f}%.",
            related=[MetricId.CREDIT_DEPOSIT_RATIO.value],
        )
        if cdr.value > 85:
            b.add_analysis(
                "Credit-to-deposit ratio is elevated \u2014 further loan growth may require additional funding.",
                related=[MetricId.CREDIT_DEPOSIT_RATIO.value],
                priority=Priority.MEDIUM,
            )

    gnpa_val = metrics.get(MetricId.GROSS_NPA)
    loans_val = metrics.get(MetricId.LOANS)
    if gnpa_val and loans_val and gnpa_val.value and loans_val.value:
        gnpa_pct = gnpa_val.value / loans_val.value * 100
        b.add_observation(
            f"Gross NPA represents {gnpa_pct:.2f}% of the loan book (calculated).",
            related=[MetricId.GROSS_NPA.value, MetricId.LOANS.value],
        )
        if gnpa_pct > 6:
            b.risks.append(f"Elevated gross NPA ratio at {gnpa_pct:.1f}%")


def _self_health(b: InsightBundle, health: HealthScore) -> None:
    b.add_observation(
        f"Overall financial health score is {health.overall_score:.1f}/100 (grade {health.grade}).",
    )
    if health.grade in ("A", "B"):
        b.strengths.append(f"Strong overall financial health (grade {health.grade})")
    elif health.grade in ("D", "F"):
        b.weaknesses.append(f"Overall financial health weak (grade {health.grade})")
        b.add_recommendation(
            "Focus improvement effort on the lowest-scoring health dimension first.",
        )

    # Surface the weakest dimension as an opportunity.
    if health.dimensions:
        weakest = min(health.dimensions.items(), key=lambda kv: kv[1])
        if weakest[1] < 60:
            b.opportunities.append(
                f"{weakest[0].capitalize()} scored only {weakest[1]:.0f}/100 \u2014 "
                "largest single lever for headline health improvement."
            )


# ---------------------------------------------------------------------------
# Merger insights
# ---------------------------------------------------------------------------
def generate_merger_insights(
    primary_metrics: Dict[MetricId, LabeledMetric],
    secondary_metrics: Dict[MetricId, LabeledMetric],
    combined_metrics: Dict[MetricId, LabeledMetric],
    synergies: List[SynergyItem],
    risks: List[RiskItem],
) -> InsightBundle:
    b = InsightBundle()

    _merger_scale(b, primary_metrics, secondary_metrics, combined_metrics)
    _merger_leverage(b, combined_metrics)
    _merger_customer_reach(b, primary_metrics, secondary_metrics, combined_metrics)

    for s in synergies:
        b.opportunities.append(f"{s.kind.capitalize()} synergy: {s.title}")

    for r in risks:
        b.risks.append(r.title)

    if not synergies:
        b.add_observation(
            "No quantifiable synergies could be identified from the available data.",
        )
    if not risks:
        b.add_observation(
            "No material data-driven risks were flagged in the combined view.",
        )

    return b


def _merger_scale(
    b: InsightBundle,
    a: Dict[MetricId, LabeledMetric],
    other: Dict[MetricId, LabeledMetric],
    combined: Dict[MetricId, LabeledMetric],
) -> None:
    rev_c = combined.get(MetricId.REVENUE)
    rev_a = a.get(MetricId.REVENUE)
    if rev_a and rev_c and rev_a.value and rev_c.value:
        uplift = (rev_c.value - rev_a.value) / rev_a.value * 100
        b.add_observation(
            f"Combined revenue is {rev_c.value:,.0f}, "
            f"up {uplift:+.1f}% vs. primary company's standalone revenue.",
            related=[MetricId.REVENUE.value],
        )
        if uplift >= 25:
            b.add_analysis(
                "Combination could materially increase revenue scale.",
                related=[MetricId.REVENUE.value],
                priority=Priority.MEDIUM,
            )
            b.opportunities.append(f"Revenue scale uplift of ~{uplift:.0f}% under the combined scenario")


def _merger_leverage(
    b: InsightBundle, combined: Dict[MetricId, LabeledMetric]
) -> None:
    de = combined.get(MetricId.DEBT_TO_EQUITY)
    if de and de.value is not None and de.value > 2.0:
        b.add_analysis(
            f"Combined debt-to-equity of {de.value:.2f} is elevated.",
            related=[MetricId.DEBT_TO_EQUITY.value],
            priority=Priority.HIGH,
        )
        b.risks.append("Combined balance sheet is highly leveraged")


def _merger_customer_reach(
    b: InsightBundle,
    a: Dict[MetricId, LabeledMetric],
    other: Dict[MetricId, LabeledMetric],
    combined: Dict[MetricId, LabeledMetric],
) -> None:
    ca = a.get(MetricId.CUSTOMERS)
    cb = other.get(MetricId.CUSTOMERS)
    cc = combined.get(MetricId.CUSTOMERS)
    if ca and cb and cc and ca.value and cc.value:
        b.add_observation(
            f"Combined customer base could reach {cc.value:,.0f} (subject to overlap).",
            related=[MetricId.CUSTOMERS.value],
        )
        if cb.value and cb.value >= ca.value * 0.3:
            b.opportunities.append(
                "Meaningful cross-sell opportunity given comparable customer bases"
            )


# ---------------------------------------------------------------------------
# Benchmark insights
# ---------------------------------------------------------------------------
def generate_benchmark_insights(gaps: List[GapItem]) -> InsightBundle:
    b = InsightBundle()

    if not gaps:
        b.add_observation("No comparable metrics were found across the two datasets.")
        return b

    high_pri = [g for g in gaps if g.priority == Priority.HIGH]
    med_pri = [g for g in gaps if g.priority == Priority.MEDIUM]

    for g in high_pri[:5]:
        _benchmark_gap_insight(b, g, priority=Priority.HIGH)
    for g in med_pri[:3]:
        _benchmark_gap_insight(b, g, priority=Priority.MEDIUM)

    if any(g.priority == Priority.HIGH for g in gaps):
        b.add_recommendation(
            "Focus on the high-priority gaps first \u2014 these have the largest "
            "impact on competitive parity.",
            priority=Priority.HIGH,
        )

    ahead_count = sum(1 for g in gaps if _is_ahead(g))
    behind_count = sum(1 for g in gaps if _is_behind(g))
    if ahead_count:
        b.strengths.append(f"Ahead of the benchmark on {ahead_count} metric(s)")
    if behind_count:
        b.weaknesses.append(f"Behind the benchmark on {behind_count} metric(s)")

    return b


def _benchmark_gap_insight(b: InsightBundle, g: GapItem, priority: Priority) -> None:
    if g.current_value is None or g.benchmark_value is None:
        return
    unit_suffix = _unit_suffix(g.unit)
    text_obs = (
        f"{g.display_name}: you {'ahead' if _is_ahead(g) else 'behind'} the "
        f"benchmark by {abs(g.absolute_gap or 0):.2f}{unit_suffix} "
        f"({(g.percentage_gap or 0):+.1f}%)."
    )
    b.add_observation(text_obs, related=[g.metric_id.value])

    if _is_behind(g):
        b.add_analysis(
            f"{g.display_name} sits below the benchmark \u2014 closing the gap could "
            "materially strengthen competitive positioning.",
            related=[g.metric_id.value],
            priority=priority,
        )
        target_hint = ""
        if g.near_term_target is not None:
            target_hint = f" Near-term target: {g.near_term_target:.2f}{unit_suffix}."
        b.add_recommendation(
            f"Investigate the drivers behind {g.display_name.lower()}.{target_hint}",
            related=[g.metric_id.value],
            priority=priority,
        )
        b.opportunities.append(
            f"{g.display_name} improvement to match benchmark ({g.benchmark_value:.2f}{unit_suffix})"
        )


def _unit_suffix(unit: MetricUnit) -> str:
    if unit == MetricUnit.PERCENT:
        return " pp"
    if unit == MetricUnit.RATIO:
        return "x"
    return ""


def _is_behind(g: GapItem) -> bool:
    if g.current_value is None or g.benchmark_value is None:
        return False
    if g.direction == MetricDirection.HIGHER_BETTER:
        return g.current_value < g.benchmark_value
    if g.direction == MetricDirection.LOWER_BETTER:
        return g.current_value > g.benchmark_value
    return False


def _is_ahead(g: GapItem) -> bool:
    if g.current_value is None or g.benchmark_value is None:
        return False
    if g.direction == MetricDirection.HIGHER_BETTER:
        return g.current_value > g.benchmark_value
    if g.direction == MetricDirection.LOWER_BETTER:
        return g.current_value < g.benchmark_value
    return False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _has_value(m: LabeledMetric) -> bool:
    return m.value is not None and m.status != MetricStatus.UNAVAILABLE
