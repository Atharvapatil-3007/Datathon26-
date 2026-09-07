"""Self financial analysis.

Assembles the full ``AnalysisResult`` for ``AnalysisMode.SELF_ANALYSIS``.

Pipeline:
    dataset_id
      \u2193
    load persisted Phase 2 profile + optional DataFrame
      \u2193
    metric_extractor  -> LabeledMetric list + value_map + shape/period info
      \u2193
    ratio_engine      -> CALCULATED ratios
      \u2193
    trend_analyzer    -> period-over-period growth rates
      \u2193
    health_scorer     -> dimensional health score
      \u2193
    insight_engine    -> observations / analysis / recommendations
      \u2193
    AnalysisResult(mode=SELF_ANALYSIS)
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import pandas as pd

from app.analysis.dataset_loader import load_dataset_bundle
from app.analysis.exceptions import InsufficientDataError
from app.analysis.health_scorer import HealthInputs, score_health
from app.analysis.insight_engine import generate_self_insights
from app.analysis.metric_extractor import ExtractionResult, extract_metrics
from app.analysis.ratio_engine import compute_ratios
from app.analysis.trend_analyzer import analyze_trends
from app.analysis.types import (
    AnalysisMode,
    AnalysisResult,
    Confidence,
    EntitySnapshot,
    LabeledMetric,
    MetricId,
    MetricStatus,
)
from app.utils.logging import get_logger


log = get_logger(__name__)


# Metrics we consider "core" for a financial dataset. Coverage of these
# feeds the ``Confidence.metric_coverage`` score.
_CORE_METRICS = (
    MetricId.REVENUE,
    MetricId.NET_PROFIT,
    MetricId.OPERATING_PROFIT,
    MetricId.ASSETS,
    MetricId.LIABILITIES,
    MetricId.EQUITY,
    MetricId.CASH,
)


def run_self_analysis(
    dataset_id: str,
    *,
    display_name: Optional[str] = None,
) -> AnalysisResult:
    """Public entrypoint used by the API layer."""
    started = time.perf_counter()

    row, df = load_dataset_bundle(dataset_id)
    profile: Dict[str, Any] = row.get("profile") or {}
    filename = display_name or row.get("original_filename") or dataset_id

    log.info("self_analysis_started", dataset_id=dataset_id, filename=filename)

    # 1. Extract base metrics.
    extraction = extract_metrics(profile, df=df)
    if not extraction.metrics:
        raise InsufficientDataError(
            "No recognized financial metrics were found in this dataset. "
            "Add columns like 'revenue', 'net profit', 'assets', etc.",
            details={"detected_shape": extraction.detected_shape},
        )

    # 2. Compute ratios.
    ratios = compute_ratios(extraction.value_map)

    # 3. Trends (needs the raw DataFrame + date column).
    date_column = _find_date_column(profile)
    numerical_names = _numerical_column_names(profile)
    trends = analyze_trends(df, date_column, numerical_names) if df is not None else {}
    _attach_trends_to_metrics(extraction.metrics, trends)

    # 4. Health score.
    health = score_health(
        HealthInputs(
            value_map=extraction.value_map,
            ratios=ratios,
            trends=trends,
        )
    )

    # 5. Insights.
    bundle = generate_self_insights(extraction.metrics, ratios, trends, health)

    # 6. Assemble entity snapshot + result.
    entity = EntitySnapshot(
        entity_id=dataset_id,
        display_name=filename,
        metrics=extraction.metrics + ratios,
        period_start=extraction.period_start,
        period_end=extraction.period_end,
        notes=extraction.warnings,
    )

    result = AnalysisResult(
        mode=AnalysisMode.SELF_ANALYSIS,
        primary_entity=entity,
        financial_health=health,
        metrics=extraction.metrics,
        ratios=ratios,
        insights=bundle.insights,
        recommendations=bundle.recommendations,
        strengths=bundle.strengths,
        weaknesses=bundle.weaknesses,
        opportunities=bundle.opportunities,
        risks=[],       # risk *items* live in the bundle; for self mode the strings are enough
        summary_text=_summary_text(filename, extraction, ratios, health),
        warnings=extraction.warnings + list(bundle.risks),  # risks surface here for UI
        confidence=_build_confidence(extraction, df, trends),
    )

    log.info(
        "self_analysis_completed",
        dataset_id=dataset_id,
        metrics=len(extraction.metrics),
        ratios=len(ratios),
        insights=len(bundle.insights) + len(bundle.recommendations),
        health_score=health.overall_score,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _find_date_column(profile: Dict[str, Any]) -> Optional[str]:
    for c in profile.get("column_profiles") or []:
        if c.get("column_class") in ("date", "datetime"):
            return c.get("name")
    return None


def _numerical_column_names(profile: Dict[str, Any]) -> List[str]:
    return [
        c.get("name")
        for c in profile.get("column_profiles") or []
        if c.get("column_class") == "numerical" and c.get("name")
    ]


def _attach_trends_to_metrics(
    metrics: List[LabeledMetric], trends: Dict[MetricId, "object"]
) -> None:
    """Fold the ``period_series`` from each trend into the corresponding metric."""
    from app.analysis.trend_analyzer import TrendResult

    trend_map: Dict[MetricId, TrendResult] = trends  # type: ignore[assignment]
    for m in metrics:
        t = trend_map.get(m.metric_id)
        if t and t.period_series:
            m.period_series = t.period_series
            if t.growth_rate is not None:
                m.notes.append(
                    f"Total change across observed periods: {t.growth_rate:+.1f}%."
                )


def _build_confidence(
    extraction: ExtractionResult,
    df: Optional[pd.DataFrame],
    trends: Dict[MetricId, "object"],
) -> Confidence:
    covered = sum(1 for mid in _CORE_METRICS if mid in extraction.value_map)
    metric_coverage = covered / len(_CORE_METRICS)

    period_coverage: Optional[float] = None
    if df is not None and len(df) > 0:
        period_coverage = min(1.0, len(df) / 12)  # 12 periods \u2248 full year of monthlies

    overall = metric_coverage
    if period_coverage is not None:
        overall = 0.6 * metric_coverage + 0.4 * period_coverage

    notes = []
    if metric_coverage < 0.4:
        notes.append(
            "Fewer than 40% of core financial metrics were identified in the dataset."
        )
    if not trends:
        notes.append("Period-over-period trends could not be computed for this dataset.")
    return Confidence(
        overall=overall,
        metric_coverage=metric_coverage,
        period_coverage=period_coverage,
        notes=notes,
    )


def _summary_text(
    display_name: str,
    extraction: ExtractionResult,
    ratios: List[LabeledMetric],
    health,
) -> str:
    revenue = _value(extraction, MetricId.REVENUE)
    net_profit = _value(extraction, MetricId.NET_PROFIT)
    net_margin = _ratio_value(ratios, MetricId.NET_MARGIN)

    parts: List[str] = [f"Financial snapshot for '{display_name}'."]

    if revenue is not None:
        parts.append(f"Aggregate revenue: {revenue:,.0f}.")
    if net_profit is not None:
        parts.append(f"Net profit: {net_profit:,.0f}.")
    if net_margin is not None:
        parts.append(f"Net margin: {net_margin:.2f}%.")
    parts.append(
        f"Overall financial health score is {health.overall_score:.1f}/100 (grade {health.grade})."
    )
    return " ".join(parts)


def _value(extraction: ExtractionResult, mid: MetricId) -> Optional[float]:
    return extraction.value_map.get(mid)


def _ratio_value(ratios: List[LabeledMetric], mid: MetricId) -> Optional[float]:
    for r in ratios:
        if r.metric_id == mid and r.status != MetricStatus.UNAVAILABLE:
            return r.value
    return None
