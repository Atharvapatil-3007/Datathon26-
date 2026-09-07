"""Competitor + market benchmarking analysis.

Assembles the ``AnalysisResult`` for
``AnalysisMode.COMPETITOR_MARKET_BENCHMARK``.

Inputs:
    * ``primary_id``  \u2014 our company
    * ``competitor_id`` \u2014 competitor to benchmark against
    * ``market_id``   \u2014 optional market / industry / peer-median dataset

Pipeline:
    load all bundles  \u2192 extract metrics for each  \u2192 build ComparisonRow list
    \u2192 filter behind rows into GapItems with priority + near/long-term targets
    \u2192 insight_engine.generate_benchmark_insights  \u2192 AnalysisResult
"""

from __future__ import annotations

import time
from typing import Dict, List, Optional, Tuple

from app.analysis.dataset_loader import load_dataset_bundle
from app.analysis.exceptions import (
    IncompatibleDatasetsError,
    InsufficientDataError,
)
from app.analysis.health_scorer import HealthInputs, score_health
from app.analysis.insight_engine import generate_benchmark_insights
from app.analysis.metric_extractor import extract_metrics
from app.analysis.metric_registry import get_definition
from app.analysis.ratio_engine import compute_ratios
from app.analysis.types import (
    AnalysisMode,
    AnalysisResult,
    ComparisonRow,
    Confidence,
    EntitySnapshot,
    GapItem,
    LabeledMetric,
    MetricDirection,
    MetricId,
    MetricStatus,
    MetricUnit,
    Priority,
)
from app.utils.logging import get_logger


log = get_logger(__name__)


# Metrics that are always worth comparing when both sides expose them.
_METRICS_OF_INTEREST: Tuple[MetricId, ...] = (
    # Absolute scale (context)
    MetricId.REVENUE,
    MetricId.NET_PROFIT,
    MetricId.OPERATING_PROFIT,
    MetricId.EBITDA,
    MetricId.ASSETS,
    MetricId.EQUITY,
    MetricId.CUSTOMERS,
    MetricId.DEPOSITS,
    MetricId.LOANS,
    # Ratios (efficiency + health)
    MetricId.GROSS_MARGIN,
    MetricId.OPERATING_MARGIN,
    MetricId.NET_MARGIN,
    MetricId.ROA,
    MetricId.ROE,
    MetricId.DEBT_TO_EQUITY,
    MetricId.CURRENT_RATIO,
    MetricId.ASSET_TURNOVER,
    MetricId.INTEREST_COVERAGE,
    MetricId.FCF_MARGIN,
    MetricId.COST_TO_INCOME,
    MetricId.NIM,
    MetricId.CREDIT_DEPOSIT_RATIO,
    MetricId.CASA_RATIO,
    MetricId.PROVISION_COVERAGE,
)

# Importance tiering used for gap priority classification.
_IMPORTANCE: Dict[MetricId, str] = {
    MetricId.REVENUE: "high",
    MetricId.NET_PROFIT: "high",
    MetricId.NET_MARGIN: "high",
    MetricId.ROE: "high",
    MetricId.DEBT_TO_EQUITY: "high",
    MetricId.GROSS_NPA: "high",
    MetricId.NET_NPA: "high",
    MetricId.CAPITAL_ADEQUACY: "high",
    MetricId.OPERATING_MARGIN: "medium",
    MetricId.OPERATING_PROFIT: "medium",
    MetricId.EBITDA: "medium",
    MetricId.GROSS_MARGIN: "medium",
    MetricId.ROA: "medium",
    MetricId.ASSET_TURNOVER: "medium",
    MetricId.COST_TO_INCOME: "medium",
    MetricId.CURRENT_RATIO: "medium",
    MetricId.NIM: "medium",
    MetricId.ASSETS: "low",
    MetricId.EQUITY: "low",
    MetricId.CUSTOMERS: "low",
    MetricId.DEPOSITS: "low",
    MetricId.LOANS: "low",
    MetricId.INTEREST_COVERAGE: "medium",
    MetricId.FCF_MARGIN: "medium",
    MetricId.CREDIT_DEPOSIT_RATIO: "low",
    MetricId.CASA_RATIO: "low",
    MetricId.PROVISION_COVERAGE: "medium",
}


def run_benchmark_analysis(
    primary_dataset_id: str,
    competitor_dataset_id: str,
    *,
    market_dataset_id: Optional[str] = None,
    primary_display_name: Optional[str] = None,
    competitor_display_name: Optional[str] = None,
    market_display_name: Optional[str] = None,
) -> AnalysisResult:
    started = time.perf_counter()

    if primary_dataset_id == competitor_dataset_id:
        raise IncompatibleDatasetsError(
            "Primary and competitor datasets must be different.",
        )

    a_row, a_df = load_dataset_bundle(primary_dataset_id)
    b_row, b_df = load_dataset_bundle(competitor_dataset_id)
    m_row, m_df = (None, None)
    if market_dataset_id:
        m_row, m_df = load_dataset_bundle(market_dataset_id)

    a_profile = a_row.get("profile") or {}
    b_profile = b_row.get("profile") or {}

    a_name = primary_display_name or a_row.get("original_filename") or primary_dataset_id
    b_name = competitor_display_name or b_row.get("original_filename") or competitor_dataset_id
    m_name = None
    if m_row:
        m_name = market_display_name or m_row.get("original_filename") or market_dataset_id

    log.info(
        "benchmark_analysis_started",
        primary=primary_dataset_id,
        competitor=competitor_dataset_id,
        market=market_dataset_id,
    )

    a_extract = extract_metrics(a_profile, df=a_df)
    b_extract = extract_metrics(b_profile, df=b_df)
    m_extract = extract_metrics(m_row["profile"], df=m_df) if m_row else None

    if not a_extract.metrics or not b_extract.metrics:
        raise InsufficientDataError(
            "Both primary and competitor datasets need at least one recognized "
            "financial metric to compare."
        )

    a_ratios = compute_ratios(a_extract.value_map)
    b_ratios = compute_ratios(b_extract.value_map)
    m_ratios = compute_ratios(m_extract.value_map) if m_extract else []

    # Combine base + ratio value maps for comparison lookups.
    a_combined = _combined_value_map(a_extract.value_map, a_ratios)
    b_combined = _combined_value_map(b_extract.value_map, b_ratios)
    m_combined = _combined_value_map(m_extract.value_map if m_extract else {}, m_ratios)

    # Health scores (context only \u2014 not the same as gap analysis).
    primary_health = score_health(
        HealthInputs(value_map=a_extract.value_map, ratios=a_ratios, trends={})
    )

    # Build comparison table.
    comparisons = _build_comparisons(a_combined, b_combined, m_combined)
    gaps = _build_gaps(comparisons)
    warnings = _check_compatibility(a_extract, b_extract, m_extract)

    bundle = generate_benchmark_insights(gaps)

    primary_entity = EntitySnapshot(
        entity_id=primary_dataset_id,
        display_name=a_name,
        metrics=a_extract.metrics + a_ratios,
        period_start=a_extract.period_start,
        period_end=a_extract.period_end,
    )
    competitor_entity = EntitySnapshot(
        entity_id=competitor_dataset_id,
        display_name=b_name,
        metrics=b_extract.metrics + b_ratios,
        period_start=b_extract.period_start,
        period_end=b_extract.period_end,
    )
    market_entity: Optional[EntitySnapshot] = None
    if m_extract and m_row:
        market_entity = EntitySnapshot(
            entity_id=market_dataset_id or "market",
            display_name=m_name or "Market",
            metrics=m_extract.metrics + m_ratios,
            period_start=m_extract.period_start,
            period_end=m_extract.period_end,
        )

    result = AnalysisResult(
        mode=AnalysisMode.COMPETITOR_MARKET_BENCHMARK,
        primary_entity=primary_entity,
        secondary_entity=competitor_entity,
        market_entity=market_entity,
        financial_health=primary_health,
        comparisons=comparisons,
        gaps=gaps,
        insights=bundle.insights,
        recommendations=bundle.recommendations,
        strengths=bundle.strengths,
        weaknesses=bundle.weaknesses,
        opportunities=bundle.opportunities,
        summary_text=_summary_text(a_name, b_name, m_name, comparisons, gaps),
        warnings=warnings,
        confidence=_confidence(comparisons, gaps),
    )

    log.info(
        "benchmark_analysis_completed",
        primary=primary_dataset_id,
        competitor=competitor_dataset_id,
        comparisons=len(comparisons),
        gaps=len(gaps),
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return result


# ---------------------------------------------------------------------------
# Comparison + gap construction
# ---------------------------------------------------------------------------
def _combined_value_map(
    base: Dict[MetricId, float], ratios: List[LabeledMetric]
) -> Dict[MetricId, float]:
    out: Dict[MetricId, float] = dict(base)
    for r in ratios:
        if r.value is not None and r.status != MetricStatus.UNAVAILABLE:
            out[r.metric_id] = r.value
    return out


def _build_comparisons(
    a: Dict[MetricId, float],
    b: Dict[MetricId, float],
    m: Dict[MetricId, float],
) -> List[ComparisonRow]:
    rows: List[ComparisonRow] = []
    for mid in _METRICS_OF_INTEREST:
        va = a.get(mid)
        vb = b.get(mid)
        vm = m.get(mid)
        if va is None and vb is None:
            continue
        definition = get_definition(mid)
        absolute_gap: Optional[float] = None
        percentage_gap: Optional[float] = None
        status_label = "na"

        if va is not None and vb is not None:
            absolute_gap = va - vb
            if vb != 0:
                percentage_gap = absolute_gap / abs(vb) * 100
            status_label = _classify_status(va, vb, definition.direction)

        rows.append(
            ComparisonRow(
                metric_id=mid,
                display_name=definition.display_name,
                unit=definition.unit,
                direction=definition.direction,
                primary_value=va,
                secondary_value=vb,
                market_value=vm,
                absolute_gap=absolute_gap,
                percentage_gap=percentage_gap,
                status=status_label,
            )
        )

    # Order: behind rows first (need attention), then ahead, then na.
    order = {"behind": 0, "ahead": 1, "level": 2, "na": 3}
    rows.sort(key=lambda r: (order.get(r.status, 3), r.metric_id.value))
    return rows


def _classify_status(
    primary: float, benchmark: float, direction: MetricDirection
) -> str:
    if primary == benchmark:
        return "level"
    higher_wins = direction == MetricDirection.HIGHER_BETTER
    lower_wins = direction == MetricDirection.LOWER_BETTER
    if not higher_wins and not lower_wins:
        return "level"  # neutral direction \u2014 don't call it behind/ahead
    if higher_wins:
        return "ahead" if primary > benchmark else "behind"
    return "ahead" if primary < benchmark else "behind"


def _build_gaps(comparisons: List[ComparisonRow]) -> List[GapItem]:
    gaps: List[GapItem] = []
    for row in comparisons:
        if row.status != "behind":
            continue
        if row.primary_value is None or row.secondary_value is None:
            continue

        # Half-way to the benchmark = near-term target.
        near_term = (row.primary_value + row.secondary_value) / 2
        long_term = row.secondary_value

        importance = _IMPORTANCE.get(row.metric_id, "low")
        priority = _priority_from(importance, row.percentage_gap or 0.0)

        required = _required_improvement_text(
            row.primary_value, near_term, row.secondary_value, row.unit
        )

        gaps.append(
            GapItem(
                metric_id=row.metric_id,
                display_name=row.display_name,
                unit=row.unit,
                current_value=row.primary_value,
                benchmark_value=row.secondary_value,
                absolute_gap=row.absolute_gap,
                percentage_gap=row.percentage_gap,
                near_term_target=near_term,
                long_term_target=long_term,
                priority=priority,
                importance=importance,
                required_improvement=required,
                direction=row.direction,
            )
        )

    # Highest-priority gaps first, tie-broken by absolute magnitude.
    priority_order = {Priority.HIGH: 0, Priority.MEDIUM: 1, Priority.LOW: 2}
    gaps.sort(
        key=lambda g: (
            priority_order.get(g.priority, 3),
            -abs(g.percentage_gap or 0),
        )
    )
    return gaps


def _priority_from(importance: str, pct_gap: float) -> Priority:
    magnitude = abs(pct_gap)
    if importance == "high" and magnitude >= 10:
        return Priority.HIGH
    if importance == "high" and magnitude >= 3:
        return Priority.MEDIUM
    if importance == "medium" and magnitude >= 15:
        return Priority.HIGH
    if importance == "medium" and magnitude >= 5:
        return Priority.MEDIUM
    if importance == "low" and magnitude >= 25:
        return Priority.MEDIUM
    return Priority.LOW


def _required_improvement_text(
    current: float, near_term: float, benchmark: float, unit: MetricUnit
) -> str:
    suffix = " pp" if unit == MetricUnit.PERCENT else ("x" if unit == MetricUnit.RATIO else "")
    delta_near = near_term - current
    delta_long = benchmark - current
    return (
        f"{delta_near:+.2f}{suffix} to reach near-term target, "
        f"{delta_long:+.2f}{suffix} to match benchmark."
    )


# ---------------------------------------------------------------------------
# Compatibility
# ---------------------------------------------------------------------------
def _check_compatibility(
    a: "ExtractionResult",  # type: ignore[name-defined]
    b: "ExtractionResult",  # type: ignore[name-defined]
    m: Optional["ExtractionResult"],  # type: ignore[name-defined]
) -> List[str]:
    warnings: List[str] = []
    overlap = set(a.value_map) & set(b.value_map)
    if len(overlap) < 3:
        warnings.append(
            f"Only {len(overlap)} metric(s) overlap between primary and competitor "
            "datasets \u2014 the benchmark view will be sparse."
        )
    if a.period_start and b.period_start and a.period_start[:4] != b.period_start[:4]:
        warnings.append(
            "Datasets appear to cover different reporting periods \u2014 comparisons "
            "should be interpreted with that in mind."
        )
    if m is not None:
        market_overlap = set(a.value_map) & set(m.value_map)
        if not market_overlap:
            warnings.append(
                "Market dataset does not share any metrics with the primary "
                "\u2014 market column will remain blank across comparisons."
            )
    return warnings


# ---------------------------------------------------------------------------
# Confidence
# ---------------------------------------------------------------------------
def _confidence(comparisons: List[ComparisonRow], gaps: List[GapItem]) -> Confidence:
    total = len(comparisons)
    behind = sum(1 for c in comparisons if c.status == "behind")
    coverage = total / len(_METRICS_OF_INTEREST) if _METRICS_OF_INTEREST else 0.0
    notes: List[str] = []
    if total < 3:
        notes.append("Very few comparable metrics \u2014 confidence in overall picture is limited.")
    if not gaps:
        notes.append("No behind-benchmark gaps detected; the primary company may be at or ahead of parity.")
    return Confidence(
        overall=min(1.0, coverage),
        metric_coverage=coverage,
        notes=notes,
    )


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
def _summary_text(
    a_name: str,
    b_name: str,
    m_name: Optional[str],
    comparisons: List[ComparisonRow],
    gaps: List[GapItem],
) -> str:
    behind = [c for c in comparisons if c.status == "behind"]
    ahead = [c for c in comparisons if c.status == "ahead"]

    parts = [
        f"Benchmarking {a_name} vs {b_name}"
        + (f" (with {m_name} as a market reference)" if m_name else "")
        + "."
    ]
    parts.append(
        f"{len(comparisons)} metric(s) compared: "
        f"{len(ahead)} ahead, {len(behind)} behind."
    )
    high_pri = [g for g in gaps if g.priority == Priority.HIGH]
    if high_pri:
        names = ", ".join(g.display_name for g in high_pri[:3])
        parts.append(
            f"{len(high_pri)} high-priority gap(s) identified"
            f" (top: {names})."
        )
    else:
        parts.append("No high-priority competitive gaps identified.")
    return " ".join(parts)
