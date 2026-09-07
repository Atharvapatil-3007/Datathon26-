"""Query engine — turns a classified query + chat context into evidence.

Every intent has a small handler that returns an ``EvidenceBundle``. The
engine never fabricates values: if the required inputs aren't present in
the extraction/ratio/trend maps, or the requested period isn't available
in the DataFrame, the handler returns an ``UNAVAILABLE`` bundle that
clearly explains what's missing.

Note: nothing here calls an LLM. The bundle's ``headline`` field is a
short deterministic statement — the answer generator wraps it into
customer-facing prose.
"""

from __future__ import annotations

import math
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

from app.analysis.metric_registry import METRIC_REGISTRY, get_definition
from app.analysis.trend_analyzer import TrendResult
from app.analysis.types import (
    AnalysisMode,
    ComparisonRow,
    GapItem,
    LabeledMetric,
    MetricDirection,
    MetricId,
    MetricStatus,
    MetricUnit,
    Priority,
    RiskItem,
    SynergyItem,
)
from app.chatbot.context_builder import ChatContext, EntityContext
from app.chatbot.types import (
    AnswerClassification,
    CalculationTrace,
    ChatEvidence,
    ChatIntent,
    ClassifiedQuery,
    ConfidenceLevel,
    EntityRef,
    EvidenceBundle,
    PeriodRef,
    QuerySlots,
)


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _format_value(value: Optional[float], unit: MetricUnit) -> str:
    if value is None or (isinstance(value, float) and (math.isnan(value) or math.isinf(value))):
        return "—"
    if unit == MetricUnit.PERCENT:
        return f"{value:.2f}%"
    if unit == MetricUnit.RATIO:
        return f"{value:.2f}x"
    if unit == MetricUnit.COUNT:
        return f"{value:,.0f}"
    if unit == MetricUnit.DAYS:
        return f"{value:,.0f} days"
    # currency / unknown — no symbol because we don't know it
    return f"{value:,.2f}"


def _entity_label(ref: EntityRef, ctx: ChatContext) -> str:
    if ref == EntityRef.SECONDARY and ctx.secondary:
        return ctx.secondary.display_name
    if ref == EntityRef.MARKET and ctx.market:
        return ctx.market.display_name
    if ref == EntityRef.COMBINED:
        return "Combined scenario"
    return ctx.primary.display_name


def _entity_for(ref: EntityRef, ctx: ChatContext) -> Optional[EntityContext]:
    if ref == EntityRef.SECONDARY:
        return ctx.secondary
    if ref == EntityRef.MARKET:
        return ctx.market
    if ref == EntityRef.PRIMARY:
        return ctx.primary
    return None  # COMBINED lives on the analysis_result


def _metric_id_from_value(v: str) -> Optional[MetricId]:
    try:
        return MetricId(v)
    except ValueError:
        return None


def _def_unit(mid: MetricId) -> MetricUnit:
    return METRIC_REGISTRY[mid].unit


def _classification_for_status(status: MetricStatus) -> AnswerClassification:
    return {
        MetricStatus.REPORTED: AnswerClassification.REPORTED,
        MetricStatus.CALCULATED: AnswerClassification.CALCULATED,
        MetricStatus.SCENARIO: AnswerClassification.SCENARIO,
        MetricStatus.ESTIMATED: AnswerClassification.ESTIMATED,
        MetricStatus.UNAVAILABLE: AnswerClassification.UNAVAILABLE,
    }.get(status, AnswerClassification.INFORMATIONAL)


def _confidence_from_coverage(coverage: float) -> ConfidenceLevel:
    if coverage >= 0.75:
        return ConfidenceLevel.HIGH
    if coverage >= 0.4:
        return ConfidenceLevel.MEDIUM
    if coverage > 0:
        return ConfidenceLevel.LOW
    return ConfidenceLevel.NONE


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def answer(query: ClassifiedQuery, context: ChatContext) -> EvidenceBundle:
    """Return the evidence bundle for one classified query."""
    intent = query.intent

    dispatchers = {
        ChatIntent.GREETING: _handle_greeting,
        ChatIntent.HELP: _handle_help,
        ChatIntent.DATASET_OVERVIEW: _handle_dataset_overview,
        ChatIntent.COLUMN_LOOKUP: _handle_columns,
        ChatIntent.DATA_QUALITY: _handle_data_quality,
        ChatIntent.PERIOD_RANGE: _handle_period_range,
        ChatIntent.METRIC_LOOKUP: _handle_metric_lookup,
        ChatIntent.RATIO_LOOKUP: _handle_ratio_lookup,
        ChatIntent.PERIOD_COMPARISON: _handle_period_comparison,
        ChatIntent.TREND_ANALYSIS: _handle_trend,
        ChatIntent.FINANCIAL_HEALTH: _handle_health,
        ChatIntent.RISK_ANALYSIS: _handle_risks,
        ChatIntent.STRENGTH_ANALYSIS: _handle_strengths,
        ChatIntent.OPPORTUNITY_ANALYSIS: _handle_opportunities,
        ChatIntent.WEAKNESS_ANALYSIS: _handle_weaknesses,
        ChatIntent.RECOMMENDATION: _handle_recommendations,
        ChatIntent.EXPLANATION: _handle_explanation,
        ChatIntent.MERGER_OVERVIEW: _handle_merger_overview,
        ChatIntent.MERGER_METRIC: _handle_merger_metric,
        ChatIntent.MERGER_SYNERGY: _handle_merger_synergies,
        ChatIntent.MERGER_RISK: _handle_merger_risks,
        ChatIntent.MERGER_COMPATIBILITY: _handle_merger_compatibility,
        ChatIntent.COMPETITOR_COMPARISON: _handle_competitor_comparison,
        ChatIntent.MARKET_BENCHMARK: _handle_market_benchmark,
        ChatIntent.GAP_ANALYSIS: _handle_gaps,
        ChatIntent.ROADMAP: _handle_roadmap,
        ChatIntent.UNSUPPORTED: _handle_unsupported,
        ChatIntent.UNRELATED: _handle_unsupported,
    }

    handler = dispatchers.get(intent, _handle_unsupported)
    try:
        return handler(query, context)
    except Exception as exc:  # noqa: BLE001
        return EvidenceBundle(
            intent=intent,
            classification=AnswerClassification.UNAVAILABLE,
            confidence=ConfidenceLevel.NONE,
            headline="I hit an error trying to answer that question.",
            notes=[str(exc)],
        )


# ---------------------------------------------------------------------------
# Handlers — dataset understanding
# ---------------------------------------------------------------------------
def _handle_greeting(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    return EvidenceBundle(
        intent=ChatIntent.GREETING,
        classification=AnswerClassification.INFORMATIONAL,
        confidence=ConfidenceLevel.HIGH,
        headline=(
            f"Hi — I'm the assistant for {ctx.primary.display_name}. "
            f"Ask me about your metrics, trends, ratios, risks, or the "
            f"{ctx.analysis_mode.value.replace('_', ' ')} results."
        ),
    )


def _handle_help(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    tips = [
        "What was our revenue in the latest period?",
        "How financially healthy are we?",
        "What is our biggest risk?",
        "How is our net margin trending?",
    ]
    if ctx.analysis_mode == AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS:
        tips = [
            "What would combined revenue look like?",
            "What synergies could exist?",
            "What are the biggest merger risks?",
            "How compatible are the two companies?",
        ]
    if ctx.analysis_mode == AnalysisMode.COMPETITOR_MARKET_BENCHMARK:
        tips = [
            "Where are we behind the competitor?",
            "What's our biggest gap?",
            "How do our margins compare?",
            "What should we improve first?",
        ]
    return EvidenceBundle(
        intent=ChatIntent.HELP,
        classification=AnswerClassification.INFORMATIONAL,
        confidence=ConfidenceLevel.HIGH,
        headline="I answer questions grounded in your uploaded dataset and its analysis.",
        notes=tips,
    )


def _handle_dataset_overview(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    profile = ctx.primary.profile
    overview = profile.get("overview") or {}
    rows = overview.get("rows")
    cols = overview.get("columns")

    evidence: List[ChatEvidence] = []
    if rows is not None:
        evidence.append(
            ChatEvidence(
                label="Rows",
                value=float(rows),
                display_value=f"{rows:,}",
                unit=MetricUnit.COUNT.value,
                source="profile",
                status=AnswerClassification.REPORTED,
            )
        )
    if cols is not None:
        evidence.append(
            ChatEvidence(
                label="Columns",
                value=float(cols),
                display_value=f"{cols:,}",
                unit=MetricUnit.COUNT.value,
                source="profile",
                status=AnswerClassification.REPORTED,
            )
        )
    q = profile.get("quality") or {}
    if q:
        evidence.append(
            ChatEvidence(
                label="Overall quality score",
                value=q.get("overall_score"),
                display_value=(
                    f"{q.get('overall_score', 0):.1f} (grade {q.get('grade', '?')})"
                ),
                unit=None,
                source="profile.quality",
                status=AnswerClassification.CALCULATED,
            )
        )

    headline = (
        f"{ctx.primary.display_name} has {rows:,} rows across {cols:,} columns."
        if rows is not None and cols is not None
        else "Dataset overview:"
    )
    return EvidenceBundle(
        intent=ChatIntent.DATASET_OVERVIEW,
        classification=AnswerClassification.REPORTED,
        confidence=ConfidenceLevel.HIGH if evidence else ConfidenceLevel.LOW,
        headline=headline,
        evidence=evidence,
        notes=[profile.get("summary_text")] if profile.get("summary_text") else [],
    )


def _handle_columns(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    profile = ctx.primary.profile
    cols = profile.get("column_profiles") or []
    if not cols:
        return _empty_bundle(
            ChatIntent.COLUMN_LOOKUP,
            "The dataset profile does not contain any column information.",
        )
    evidence = [
        ChatEvidence(
            label=c.get("name", "?"),
            display_value=f"{c.get('name')} ({c.get('column_class', 'unknown')})",
            source="profile.column_profiles",
            status=AnswerClassification.REPORTED,
        )
        for c in cols[:50]
    ]
    return EvidenceBundle(
        intent=ChatIntent.COLUMN_LOOKUP,
        classification=AnswerClassification.REPORTED,
        confidence=ConfidenceLevel.HIGH,
        headline=(
            f"The dataset has {len(cols)} columns: "
            + ", ".join(c.get("name", "?") for c in cols[:8])
            + ("…" if len(cols) > 8 else ".")
        ),
        evidence=evidence,
    )


def _handle_data_quality(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    profile = ctx.primary.profile
    quality = profile.get("quality") or {}
    missing = profile.get("missing") or {}
    dupes = profile.get("duplicates") or {}

    evidence: List[ChatEvidence] = []
    if quality:
        evidence.append(
            ChatEvidence(
                label="Overall quality",
                value=quality.get("overall_score"),
                display_value=(
                    f"{quality.get('overall_score', 0):.1f}/100 (grade {quality.get('grade', '?')})"
                ),
                source="profile.quality",
                status=AnswerClassification.CALCULATED,
            )
        )
    if missing.get("status") == "ok":
        evidence.append(
            ChatEvidence(
                label="Missing values",
                value=missing.get("total_missing"),
                display_value=(
                    f"{missing.get('total_missing', 0):,} cells ("
                    f"{(missing.get('missing_ratio') or 0.0) * 100:.2f}% of the data)"
                ),
                source="profile.missing",
                status=AnswerClassification.REPORTED,
            )
        )
    if dupes.get("status") == "ok":
        evidence.append(
            ChatEvidence(
                label="Duplicate rows",
                value=dupes.get("duplicate_rows"),
                display_value=(
                    f"{dupes.get('duplicate_rows', 0):,} rows ("
                    f"{(dupes.get('duplicate_ratio') or 0.0) * 100:.2f}%)"
                ),
                source="profile.duplicates",
                status=AnswerClassification.REPORTED,
            )
        )

    headline = "Data quality summary."
    if quality:
        headline = (
            f"Overall data quality is {quality.get('overall_score', 0):.1f}/100 "
            f"(grade {quality.get('grade', '?')})."
        )
    return EvidenceBundle(
        intent=ChatIntent.DATA_QUALITY,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.HIGH if evidence else ConfidenceLevel.LOW,
        headline=headline,
        evidence=evidence,
        notes=list(quality.get("notes") or []),
    )


def _handle_period_range(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    ext = ctx.primary.extraction
    start = ext.period_start if ext else None
    end = ext.period_end if ext else None
    if not start and not end:
        return _empty_bundle(
            ChatIntent.PERIOD_RANGE,
            "The dataset does not contain a recognised date column, so I "
            "can't determine its reporting period range.",
        )
    return EvidenceBundle(
        intent=ChatIntent.PERIOD_RANGE,
        classification=AnswerClassification.REPORTED,
        confidence=ConfidenceLevel.HIGH,
        headline=(
            f"The dataset covers {start or 'earliest available'} to "
            f"{end or 'latest available'}."
        ),
        evidence=[
            ChatEvidence(
                label="Earliest period",
                display_value=start,
                source="profile.date_column",
                status=AnswerClassification.REPORTED,
            ),
            ChatEvidence(
                label="Latest period",
                display_value=end,
                source="profile.date_column",
                status=AnswerClassification.REPORTED,
            ),
        ],
    )


# ---------------------------------------------------------------------------
# Handlers — metric lookup (single value)
# ---------------------------------------------------------------------------
def _handle_metric_lookup(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    slots = query.slots
    if not slots.metric_ids:
        return _empty_bundle(ChatIntent.METRIC_LOOKUP, "I couldn't identify a metric in that question.")

    metric_id = _metric_id_from_value(slots.metric_ids[0])
    if metric_id is None:
        return _empty_bundle(ChatIntent.METRIC_LOOKUP, "Unrecognised metric.")

    entity_ref = slots.entity
    entity_ctx = _entity_for(entity_ref, ctx)
    if entity_ctx is None or not entity_ctx.has_data():
        return _no_entity_data(ChatIntent.METRIC_LOOKUP, entity_ref, ctx)

    if slots.periods:
        return _metric_at_period(metric_id, entity_ref, entity_ctx, ctx, slots.periods[0])

    return _metric_aggregate(metric_id, entity_ref, entity_ctx, ctx)


def _handle_ratio_lookup(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    slots = query.slots
    metric_id = None
    for m_value in slots.metric_ids:
        mid = _metric_id_from_value(m_value)
        if mid is None:
            continue
        defn = METRIC_REGISTRY.get(mid)
        if defn and defn.is_derived:
            metric_id = mid
            break
    if metric_id is None:
        return _empty_bundle(ChatIntent.RATIO_LOOKUP, "No ratio recognised in that question.")

    entity_ctx = _entity_for(slots.entity, ctx) or ctx.primary
    match = next((r for r in entity_ctx.ratios if r.metric_id == metric_id), None)
    if match is None:
        return _missing_ratio(metric_id, entity_ctx, slots.entity, ctx)
    return _ratio_bundle(match, entity_ctx, slots.entity, ctx)


def _handle_period_comparison(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    slots = query.slots
    if not slots.metric_ids or len(slots.periods) < 1:
        return _empty_bundle(
            ChatIntent.PERIOD_COMPARISON,
            "I need a metric and at least one period (or two periods) to compare.",
        )
    metric_id = _metric_id_from_value(slots.metric_ids[0])
    if metric_id is None:
        return _empty_bundle(ChatIntent.PERIOD_COMPARISON, "Unrecognised metric.")

    entity_ref = slots.entity
    entity_ctx = _entity_for(entity_ref, ctx)
    if entity_ctx is None or not entity_ctx.has_data():
        return _no_entity_data(ChatIntent.PERIOD_COMPARISON, entity_ref, ctx)

    a = slots.periods[0]
    b = slots.periods[1] if len(slots.periods) > 1 else PeriodRef(kind="previous", label="previous period")

    a_val, a_label, a_note = _metric_by_period(metric_id, entity_ctx, a)
    b_val, b_label, b_note = _metric_by_period(metric_id, entity_ctx, b)

    unit = _def_unit(metric_id)
    entity_name = _entity_label(entity_ref, ctx)

    evidence = [
        ChatEvidence(
            label=f"{METRIC_REGISTRY[metric_id].display_name} — {a_label}",
            value=a_val,
            display_value=_format_value(a_val, unit),
            metric_id=metric_id.value,
            period=a_label,
            entity=entity_ref.value,
            entity_name=entity_name,
            unit=unit.value,
            source="metric_extractor+period_filter",
            status=(
                AnswerClassification.REPORTED
                if a_val is not None
                else AnswerClassification.UNAVAILABLE
            ),
        ),
        ChatEvidence(
            label=f"{METRIC_REGISTRY[metric_id].display_name} — {b_label}",
            value=b_val,
            display_value=_format_value(b_val, unit),
            metric_id=metric_id.value,
            period=b_label,
            entity=entity_ref.value,
            entity_name=entity_name,
            unit=unit.value,
            source="metric_extractor+period_filter",
            status=(
                AnswerClassification.REPORTED
                if b_val is not None
                else AnswerClassification.UNAVAILABLE
            ),
        ),
    ]
    notes: List[str] = [n for n in (a_note, b_note) if n]

    if a_val is None or b_val is None:
        return EvidenceBundle(
            intent=ChatIntent.PERIOD_COMPARISON,
            classification=AnswerClassification.UNAVAILABLE,
            confidence=ConfidenceLevel.LOW,
            headline=(
                f"I can't compare {METRIC_REGISTRY[metric_id].display_name} across "
                f"those periods — one or both values are unavailable in the dataset."
            ),
            evidence=evidence,
            notes=notes,
            metric_hint=metric_id.value,
            entity_hint=entity_ref,
            period_hint=a,
        )

    delta = a_val - b_val
    pct = (delta / abs(b_val) * 100.0) if b_val else None
    calc = CalculationTrace(
        formula=f"({_format_value(a_val, unit)} - {_format_value(b_val, unit)}) / |{_format_value(b_val, unit)}| × 100",
        result=pct,
        inputs={a_label: a_val, b_label: b_val},
        explanation="Change in the metric from the earlier period to the later period.",
    )
    display_pct = f"{pct:+.2f}%" if pct is not None else "not calculable"
    display_abs = _format_value(delta, unit)
    headline = (
        f"{METRIC_REGISTRY[metric_id].display_name} changed by {display_abs} "
        f"({display_pct}) between {b_label} and {a_label}."
    )
    return EvidenceBundle(
        intent=ChatIntent.PERIOD_COMPARISON,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.HIGH,
        headline=headline,
        evidence=evidence,
        calculations=[calc],
        notes=notes,
        metric_hint=metric_id.value,
        entity_hint=entity_ref,
        period_hint=a,
    )


def _handle_trend(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    slots = query.slots
    metric_id = _metric_id_from_value(slots.metric_ids[0]) if slots.metric_ids else None
    if metric_id is None:
        return _empty_bundle(ChatIntent.TREND_ANALYSIS, "Which metric's trend would you like?")

    entity_ref = slots.entity
    entity_ctx = _entity_for(entity_ref, ctx) or ctx.primary
    trend = entity_ctx.trends.get(metric_id)
    if trend is None:
        # Try to derive series from the DataFrame directly.
        derived = _derive_trend(entity_ctx, metric_id)
        if derived is None:
            return _empty_bundle(
                ChatIntent.TREND_ANALYSIS,
                (
                    f"I don't have a time series for "
                    f"{METRIC_REGISTRY[metric_id].display_name} in "
                    f"{_entity_label(entity_ref, ctx)}."
                ),
            )
        trend = derived

    unit = _def_unit(metric_id)
    entity_name = _entity_label(entity_ref, ctx)
    evidence: List[ChatEvidence] = []
    for period_label, value in list(trend.period_series.items())[:8]:
        evidence.append(
            ChatEvidence(
                label=f"{METRIC_REGISTRY[metric_id].display_name} — {period_label}",
                value=value,
                display_value=_format_value(value, unit),
                metric_id=metric_id.value,
                period=period_label,
                entity=entity_ref.value,
                entity_name=entity_name,
                unit=unit.value,
                source="trend_analyzer",
                status=AnswerClassification.REPORTED,
            )
        )

    growth_note = None
    calc: List[CalculationTrace] = []
    if trend.growth_rate is not None:
        calc.append(
            CalculationTrace(
                formula="(latest - earliest) / |earliest| × 100",
                result=trend.growth_rate,
                explanation="Total change across observed periods.",
            )
        )
        growth_note = (
            f"Total change: {trend.growth_rate:+.2f}%. Direction: "
            f"{trend.direction.replace('_', ' ')}."
        )

    headline = (
        f"{METRIC_REGISTRY[metric_id].display_name} is {trend.direction.replace('_', ' ')} "
        f"across {trend.period_count} observed periods for {entity_name}."
    )
    notes = [growth_note] if growth_note else []
    return EvidenceBundle(
        intent=ChatIntent.TREND_ANALYSIS,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.HIGH if len(evidence) >= 2 else ConfidenceLevel.MEDIUM,
        headline=headline,
        evidence=evidence,
        calculations=calc,
        notes=notes,
        metric_hint=metric_id.value,
        entity_hint=entity_ref,
    )


# ---------------------------------------------------------------------------
# Handlers — health / SWOT / recommendation
# ---------------------------------------------------------------------------
def _handle_health(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    ar = ctx.analysis_result
    if not ar or not ar.financial_health:
        return _empty_bundle(
            ChatIntent.FINANCIAL_HEALTH,
            "No financial health score has been calculated for this dataset yet.",
        )
    fh = ar.financial_health
    evidence = [
        ChatEvidence(
            label="Overall health score",
            value=fh.overall_score,
            display_value=f"{fh.overall_score:.1f}/100 (grade {fh.grade})",
            source="health_scorer",
            status=AnswerClassification.CALCULATED,
        )
    ]
    for name, value in fh.dimensions.items():
        evidence.append(
            ChatEvidence(
                label=f"Dimension: {name}",
                value=value,
                display_value=f"{value:.1f}/100",
                source="health_scorer",
                status=AnswerClassification.CALCULATED,
            )
        )
    weakest = None
    if fh.dimensions:
        weakest = min(fh.dimensions.items(), key=lambda kv: kv[1])
    headline = (
        f"Overall financial health is {fh.overall_score:.1f}/100 (grade {fh.grade}) "
        f"for {ctx.primary.display_name}."
    )
    if weakest:
        headline += f" Weakest dimension: {weakest[0]} at {weakest[1]:.1f}/100."
    return EvidenceBundle(
        intent=ChatIntent.FINANCIAL_HEALTH,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.HIGH,
        headline=headline,
        evidence=evidence,
        notes=list(fh.notes),
    )


def _handle_risks(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    ar = ctx.analysis_result
    risks = list(ar.risks) if ar and ar.risks else []
    if not risks:
        return _empty_bundle(
            ChatIntent.RISK_ANALYSIS,
            "No material data-driven risks were identified for this analysis.",
        )
    high = [r for r in risks if r.severity == Priority.HIGH]
    ordered: List[RiskItem] = high + [r for r in risks if r not in high]
    evidence = [
        ChatEvidence(
            label=r.title,
            display_value=r.description,
            source="analysis_result.risks",
            status=AnswerClassification.CALCULATED,
        )
        for r in ordered[:6]
    ]
    headline = (
        f"{len(risks)} risk(s) surfaced; "
        f"{len(high)} at high severity."
        if risks
        else "No risks identified."
    )
    return EvidenceBundle(
        intent=ChatIntent.RISK_ANALYSIS,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.HIGH,
        headline=headline,
        evidence=evidence,
    )


def _handle_strengths(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    ar = ctx.analysis_result
    strengths = list(ar.strengths) if ar else []
    if not strengths:
        return _empty_bundle(
            ChatIntent.STRENGTH_ANALYSIS,
            "No standout strengths were identified from the available data.",
        )
    evidence = [
        ChatEvidence(label=s, source="analysis_result.strengths", status=AnswerClassification.CALCULATED)
        for s in strengths[:6]
    ]
    return EvidenceBundle(
        intent=ChatIntent.STRENGTH_ANALYSIS,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.HIGH,
        headline=f"{len(strengths)} strength(s) identified from the analysis.",
        evidence=evidence,
    )


def _handle_opportunities(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    ar = ctx.analysis_result
    items = list(ar.opportunities) if ar else []
    if not items:
        return _empty_bundle(
            ChatIntent.OPPORTUNITY_ANALYSIS,
            "No opportunities were highlighted from the available data.",
        )
    return EvidenceBundle(
        intent=ChatIntent.OPPORTUNITY_ANALYSIS,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.HIGH,
        headline=f"{len(items)} opportunit(y|ies) identified.".replace("|", "y"),
        evidence=[
            ChatEvidence(label=o, source="analysis_result.opportunities", status=AnswerClassification.CALCULATED)
            for o in items[:6]
        ],
    )


def _handle_weaknesses(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    ar = ctx.analysis_result
    items = list(ar.weaknesses) if ar else []
    if not items:
        return _empty_bundle(
            ChatIntent.WEAKNESS_ANALYSIS,
            "No specific weaknesses were flagged from the available data.",
        )
    return EvidenceBundle(
        intent=ChatIntent.WEAKNESS_ANALYSIS,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.HIGH,
        headline=f"{len(items)} weakness(es) flagged.",
        evidence=[
            ChatEvidence(label=w, source="analysis_result.weaknesses", status=AnswerClassification.CALCULATED)
            for w in items[:6]
        ],
    )


def _handle_recommendations(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    ar = ctx.analysis_result
    recs = list(ar.recommendations) if ar and ar.recommendations else []
    if not recs:
        return _empty_bundle(
            ChatIntent.RECOMMENDATION,
            "No data-supported recommendations were generated for this analysis.",
        )
    evidence = [
        ChatEvidence(
            label=r.text,
            source="analysis_result.recommendations",
            status=AnswerClassification.CALCULATED,
        )
        for r in recs[:6]
    ]
    return EvidenceBundle(
        intent=ChatIntent.RECOMMENDATION,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.HIGH,
        headline=(
            f"{len(recs)} recommendation(s) from the analysis. "
            "These are suggested areas to investigate, not guaranteed outcomes."
        ),
        evidence=evidence,
    )


def _handle_explanation(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    """"Why is X low?" — surface health notes + insights that mention the metric."""
    ar = ctx.analysis_result
    if not ar:
        return _empty_bundle(ChatIntent.EXPLANATION, "No analysis result is available yet.")
    notes = list(ar.warnings)
    if ar.financial_health:
        notes.extend(ar.financial_health.notes)
    related_texts: List[str] = []
    for i in ar.insights + ar.recommendations:
        if any(mid in query.slots.metric_ids for mid in i.related_metrics):
            related_texts.append(i.text)
    if not notes and not related_texts:
        return _empty_bundle(
            ChatIntent.EXPLANATION,
            "The analysis result doesn't include enough evidence to explain that "
            "without speculating.",
        )
    evidence = [
        ChatEvidence(label=t, source="analysis_result.insights", status=AnswerClassification.CALCULATED)
        for t in related_texts[:6]
    ]
    return EvidenceBundle(
        intent=ChatIntent.EXPLANATION,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.MEDIUM,
        headline=(
            "Here's what the analysis surfaces about that. "
            "Any relationships are described but not claimed as causation."
        ),
        evidence=evidence,
        notes=notes[:6] + ["The dataset shows relationships; it does not by itself establish causation."],
    )


# ---------------------------------------------------------------------------
# Handlers — merger
# ---------------------------------------------------------------------------
def _handle_merger_overview(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    if ctx.analysis_mode != AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS or not ctx.analysis_result:
        return _mode_mismatch(ChatIntent.MERGER_OVERVIEW, "merger analysis")
    ar = ctx.analysis_result
    scenario = ar.combined_scenario
    if not scenario or not scenario.metrics:
        return _empty_bundle(
            ChatIntent.MERGER_OVERVIEW,
            "The combined scenario contains no metrics — verify both datasets have overlapping fields.",
        )
    evidence: List[ChatEvidence] = []
    for m in scenario.metrics[:8]:
        evidence.append(
            ChatEvidence(
                label=m.display_name,
                value=m.value,
                display_value=_format_value(m.value, m.unit),
                metric_id=m.metric_id.value,
                unit=m.unit.value,
                entity=EntityRef.COMBINED.value,
                entity_name="Combined scenario",
                source="merger_analyzer.combined_scenario",
                status=AnswerClassification.SCENARIO,
            )
        )
    return EvidenceBundle(
        intent=ChatIntent.MERGER_OVERVIEW,
        classification=AnswerClassification.SCENARIO,
        confidence=ConfidenceLevel.MEDIUM,
        headline=(
            f"Hypothetical combined scenario for "
            f"{ctx.primary.display_name} + "
            f"{ctx.secondary.display_name if ctx.secondary else 'the other company'}. "
            "Not a forecast."
        ),
        evidence=evidence,
        notes=list(scenario.caveats),
        entity_hint=EntityRef.COMBINED,
    )


def _handle_merger_metric(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    if ctx.analysis_mode != AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS or not ctx.analysis_result:
        return _mode_mismatch(ChatIntent.MERGER_METRIC, "merger analysis")
    slots = query.slots
    if not slots.metric_ids:
        return _handle_merger_overview(query, ctx)
    metric_id = _metric_id_from_value(slots.metric_ids[0])
    if metric_id is None:
        return _empty_bundle(ChatIntent.MERGER_METRIC, "Unrecognised metric.")
    ar = ctx.analysis_result
    scenario_metric = _find(ar.combined_scenario.metrics if ar.combined_scenario else [], metric_id)
    a_metric = _find(ar.primary_entity.metrics if ar.primary_entity else [], metric_id)
    b_metric = _find(ar.secondary_entity.metrics if ar.secondary_entity else [], metric_id)

    evidence: List[ChatEvidence] = []
    for label, m, entity_ref, entity_name in (
        (ctx.primary.display_name, a_metric, EntityRef.PRIMARY, ctx.primary.display_name),
        (
            ctx.secondary.display_name if ctx.secondary else "Other",
            b_metric,
            EntityRef.SECONDARY,
            ctx.secondary.display_name if ctx.secondary else "Other",
        ),
        ("Combined scenario", scenario_metric, EntityRef.COMBINED, "Combined scenario"),
    ):
        if m is None or m.value is None:
            continue
        evidence.append(
            ChatEvidence(
                label=f"{m.display_name} — {label}",
                value=m.value,
                display_value=_format_value(m.value, m.unit),
                metric_id=m.metric_id.value,
                unit=m.unit.value,
                entity=entity_ref.value,
                entity_name=entity_name,
                source="merger_analyzer",
                status=_classification_for_status(m.status),
            )
        )

    if not evidence:
        return _empty_bundle(
            ChatIntent.MERGER_METRIC,
            f"{METRIC_REGISTRY[metric_id].display_name} isn't available in either dataset.",
        )

    headline = (
        f"{METRIC_REGISTRY[metric_id].display_name} across the merger scenario "
        "(primary + secondary + combined)."
    )
    return EvidenceBundle(
        intent=ChatIntent.MERGER_METRIC,
        classification=AnswerClassification.SCENARIO,
        confidence=ConfidenceLevel.HIGH if len(evidence) == 3 else ConfidenceLevel.MEDIUM,
        headline=headline,
        evidence=evidence,
        notes=[
            "Combined values are arithmetic sums of standalone figures — not adjusted for overlap.",
        ],
        metric_hint=metric_id.value,
    )


def _handle_merger_synergies(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    if ctx.analysis_mode != AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS or not ctx.analysis_result:
        return _mode_mismatch(ChatIntent.MERGER_SYNERGY, "merger analysis")
    synergies: List[SynergyItem] = list(ctx.analysis_result.synergies)
    if not synergies:
        return _empty_bundle(
            ChatIntent.MERGER_SYNERGY,
            "No data-supported synergies were identified from the two datasets.",
        )
    evidence = [
        ChatEvidence(
            label=s.title,
            display_value=s.description,
            source="merger_analyzer.synergies",
            status=AnswerClassification.SCENARIO,
        )
        for s in synergies[:6]
    ]
    return EvidenceBundle(
        intent=ChatIntent.MERGER_SYNERGY,
        classification=AnswerClassification.SCENARIO,
        confidence=ConfidenceLevel.MEDIUM,
        headline=f"{len(synergies)} potential synergy area(s) surfaced from the data.",
        evidence=evidence,
        notes=["Synergy magnitudes cannot be quantified from standalone datasets alone."],
    )


def _handle_merger_risks(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    if ctx.analysis_mode != AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS or not ctx.analysis_result:
        return _mode_mismatch(ChatIntent.MERGER_RISK, "merger analysis")
    return _handle_risks(query, ctx)


def _handle_merger_compatibility(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    if ctx.analysis_mode != AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS or not ctx.analysis_result:
        return _mode_mismatch(ChatIntent.MERGER_COMPATIBILITY, "merger analysis")
    ar = ctx.analysis_result
    a_metrics = set(m.metric_id for m in (ar.primary_entity.metrics if ar.primary_entity else []) if m.value is not None)
    b_metrics = set(m.metric_id for m in (ar.secondary_entity.metrics if ar.secondary_entity else []) if m.value is not None)
    overlap = a_metrics & b_metrics
    only_a = a_metrics - b_metrics
    only_b = b_metrics - a_metrics
    evidence = [
        ChatEvidence(
            label="Overlapping metrics",
            value=float(len(overlap)),
            display_value=f"{len(overlap)} metric(s)",
            source="merger_analyzer",
            status=AnswerClassification.REPORTED,
        ),
        ChatEvidence(
            label="Only in primary",
            value=float(len(only_a)),
            display_value=f"{len(only_a)} metric(s)",
            source="merger_analyzer",
            status=AnswerClassification.REPORTED,
        ),
        ChatEvidence(
            label="Only in secondary",
            value=float(len(only_b)),
            display_value=f"{len(only_b)} metric(s)",
            source="merger_analyzer",
            status=AnswerClassification.REPORTED,
        ),
    ]
    if ar.confidence:
        evidence.append(
            ChatEvidence(
                label="Metric coverage confidence",
                value=ar.confidence.metric_coverage,
                display_value=f"{ar.confidence.metric_coverage * 100:.1f}%",
                source="merger_analyzer.confidence",
                status=AnswerClassification.CALCULATED,
            )
        )
    return EvidenceBundle(
        intent=ChatIntent.MERGER_COMPATIBILITY,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.MEDIUM,
        headline=(
            f"Metric compatibility between the two datasets: {len(overlap)} shared "
            f"metric(s); {len(only_a)} only in the primary, {len(only_b)} only in the secondary."
        ),
        evidence=evidence,
        notes=list(ar.warnings),
    )


# ---------------------------------------------------------------------------
# Handlers — benchmark
# ---------------------------------------------------------------------------
def _handle_competitor_comparison(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    if ctx.analysis_mode != AnalysisMode.COMPETITOR_MARKET_BENCHMARK or not ctx.analysis_result:
        return _mode_mismatch(ChatIntent.COMPETITOR_COMPARISON, "competitor benchmark analysis")
    ar = ctx.analysis_result
    metric_id = _metric_id_from_value(query.slots.metric_ids[0]) if query.slots.metric_ids else None
    rows: List[ComparisonRow] = list(ar.comparisons)
    if metric_id:
        rows = [r for r in rows if r.metric_id == metric_id]
    if not rows:
        return _empty_bundle(
            ChatIntent.COMPETITOR_COMPARISON,
            "No comparable metrics were found between the primary and competitor datasets.",
        )
    focus = rows[0] if metric_id else rows[0]
    evidence = _comparison_evidence(focus, ctx, include_market=False)
    all_metric_evidence: List[ChatEvidence] = []
    for r in rows[:5]:
        all_metric_evidence.extend(_comparison_evidence(r, ctx, include_market=False))
    headline = _comparison_headline(focus, ctx)
    return EvidenceBundle(
        intent=ChatIntent.COMPETITOR_COMPARISON,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.HIGH,
        headline=headline,
        evidence=all_metric_evidence if not metric_id else evidence,
        notes=["Only the competitor dataset you uploaded informs this comparison."],
        metric_hint=focus.metric_id.value,
        entity_hint=EntityRef.SECONDARY,
    )


def _handle_market_benchmark(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    if ctx.analysis_mode != AnalysisMode.COMPETITOR_MARKET_BENCHMARK or not ctx.analysis_result:
        return _mode_mismatch(ChatIntent.MARKET_BENCHMARK, "competitor benchmark analysis")
    ar = ctx.analysis_result
    if ar.market_entity is None:
        return _empty_bundle(
            ChatIntent.MARKET_BENCHMARK,
            "No market benchmark dataset was uploaded for this analysis.",
        )
    metric_id = _metric_id_from_value(query.slots.metric_ids[0]) if query.slots.metric_ids else None
    rows: List[ComparisonRow] = [r for r in ar.comparisons if r.market_value is not None]
    if metric_id:
        rows = [r for r in rows if r.metric_id == metric_id]
    if not rows:
        return _empty_bundle(
            ChatIntent.MARKET_BENCHMARK,
            "The market dataset does not share the requested metric with the primary dataset.",
        )
    evidence: List[ChatEvidence] = []
    for r in rows[:6]:
        evidence.extend(_comparison_evidence(r, ctx, include_market=True))
    focus = rows[0]
    return EvidenceBundle(
        intent=ChatIntent.MARKET_BENCHMARK,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.MEDIUM,
        headline=_comparison_headline(focus, ctx, include_market=True),
        evidence=evidence,
        notes=[
            "Market values come from the market dataset you uploaded — no other market data is used.",
        ],
        metric_hint=focus.metric_id.value,
        entity_hint=EntityRef.MARKET,
    )


def _handle_gaps(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    if ctx.analysis_mode != AnalysisMode.COMPETITOR_MARKET_BENCHMARK or not ctx.analysis_result:
        return _mode_mismatch(ChatIntent.GAP_ANALYSIS, "competitor benchmark analysis")
    ar = ctx.analysis_result
    gaps = list(ar.gaps)
    if not gaps:
        return _empty_bundle(
            ChatIntent.GAP_ANALYSIS,
            "No behind-benchmark gaps were identified — the primary company is at "
            "or ahead of parity on the comparable metrics.",
        )
    evidence: List[ChatEvidence] = []
    for g in gaps[:6]:
        unit = g.unit
        evidence.append(
            ChatEvidence(
                label=f"{g.display_name} ({g.priority.value} priority)",
                value=g.percentage_gap,
                display_value=(
                    f"You: {_format_value(g.current_value, unit)}, "
                    f"benchmark: {_format_value(g.benchmark_value, unit)}"
                    + (f", gap: {g.percentage_gap:+.2f}%" if g.percentage_gap is not None else "")
                ),
                metric_id=g.metric_id.value,
                unit=unit.value,
                entity=EntityRef.PRIMARY.value,
                source="benchmark_analyzer.gaps",
                status=AnswerClassification.CALCULATED,
            )
        )
    high = [g for g in gaps if g.priority == Priority.HIGH]
    headline = (
        f"{len(gaps)} behind-benchmark gap(s); "
        f"{len(high)} at high priority."
    )
    return EvidenceBundle(
        intent=ChatIntent.GAP_ANALYSIS,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.HIGH,
        headline=headline,
        evidence=evidence,
    )


def _handle_roadmap(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    if ctx.analysis_mode != AnalysisMode.COMPETITOR_MARKET_BENCHMARK or not ctx.analysis_result:
        return _mode_mismatch(ChatIntent.ROADMAP, "competitor benchmark analysis")
    ar = ctx.analysis_result
    gaps = [g for g in ar.gaps if g.near_term_target is not None]
    if not gaps:
        return _empty_bundle(
            ChatIntent.ROADMAP,
            "There are no behind-benchmark gaps to build a roadmap from.",
        )
    evidence: List[ChatEvidence] = []
    for g in gaps[:6]:
        unit = g.unit
        near_target = _format_value(g.near_term_target, unit)
        long_target = _format_value(g.long_term_target, unit)
        evidence.append(
            ChatEvidence(
                label=g.display_name,
                display_value=(
                    f"Current {_format_value(g.current_value, unit)} → "
                    f"near-term {near_target} → long-term {long_target} "
                    f"(priority {g.priority.value})"
                ),
                metric_id=g.metric_id.value,
                unit=unit.value,
                source="benchmark_analyzer.gaps",
                status=AnswerClassification.CALCULATED,
            )
        )
    return EvidenceBundle(
        intent=ChatIntent.ROADMAP,
        classification=AnswerClassification.CALCULATED,
        confidence=ConfidenceLevel.MEDIUM,
        headline=(
            "Suggested near-term and long-term targets for each behind-benchmark gap. "
            "These are analytical suggestions, not commitments."
        ),
        evidence=evidence,
    )


# ---------------------------------------------------------------------------
# Handlers — fallback
# ---------------------------------------------------------------------------
def _handle_unsupported(query: ClassifiedQuery, ctx: ChatContext) -> EvidenceBundle:
    return EvidenceBundle(
        intent=ChatIntent.UNSUPPORTED,
        classification=AnswerClassification.UNAVAILABLE,
        confidence=ConfidenceLevel.NONE,
        headline=(
            "I couldn't map that to a metric, period, or analysis result "
            "in your dataset. Try asking about a specific metric, a period, "
            "the health score, risks, gaps, or trends."
        ),
    )


# ---------------------------------------------------------------------------
# Metric-value helpers
# ---------------------------------------------------------------------------
def _metric_aggregate(
    metric_id: MetricId,
    entity_ref: EntityRef,
    entity_ctx: EntityContext,
    ctx: ChatContext,
) -> EvidenceBundle:
    ext = entity_ctx.extraction
    if ext is None:
        return _no_entity_data(ChatIntent.METRIC_LOOKUP, entity_ref, ctx)

    labeled = _find(ext.metrics, metric_id)
    if labeled is None or labeled.value is None or labeled.status == MetricStatus.UNAVAILABLE:
        return _missing_metric(metric_id, entity_ref, entity_ctx, ctx)

    unit = labeled.unit
    entity_name = _entity_label(entity_ref, ctx)
    evidence = [
        ChatEvidence(
            label=f"{labeled.display_name} ({entity_name})",
            value=labeled.value,
            display_value=_format_value(labeled.value, unit),
            metric_id=metric_id.value,
            entity=entity_ref.value,
            entity_name=entity_name,
            unit=unit.value,
            source="metric_extractor",
            status=_classification_for_status(labeled.status),
            period=_period_label_for(entity_ctx),
        )
    ]
    period_note = _period_label_for(entity_ctx)
    period_ref = PeriodRef(kind="raw", label=period_note or "aggregate", raw=period_note)
    return EvidenceBundle(
        intent=ChatIntent.METRIC_LOOKUP,
        classification=_classification_for_status(labeled.status),
        confidence=ConfidenceLevel.HIGH if labeled.status == MetricStatus.REPORTED else ConfidenceLevel.MEDIUM,
        headline=(
            f"{labeled.display_name} for {entity_name} is "
            f"{_format_value(labeled.value, unit)}"
            + (f" ({period_note})" if period_note else "") + "."
        ),
        evidence=evidence,
        notes=list(labeled.notes),
        metric_hint=metric_id.value,
        entity_hint=entity_ref,
        period_hint=period_ref,
    )


def _period_label_for(entity_ctx: EntityContext) -> Optional[str]:
    ext = entity_ctx.extraction
    if not ext:
        return None
    if ext.period_start and ext.period_end:
        return f"{ext.period_start[:10]} to {ext.period_end[:10]}"
    if ext.period_end:
        return ext.period_end[:10]
    return None


def _metric_at_period(
    metric_id: MetricId,
    entity_ref: EntityRef,
    entity_ctx: EntityContext,
    ctx: ChatContext,
    period: PeriodRef,
) -> EvidenceBundle:
    value, label, note = _metric_by_period(metric_id, entity_ctx, period)
    unit = _def_unit(metric_id)
    entity_name = _entity_label(entity_ref, ctx)

    if value is None:
        return EvidenceBundle(
            intent=ChatIntent.METRIC_LOOKUP,
            classification=AnswerClassification.UNAVAILABLE,
            confidence=ConfidenceLevel.LOW,
            headline=(
                f"{METRIC_REGISTRY[metric_id].display_name} for {entity_name} in "
                f"{label} is unavailable in this dataset."
            ),
            notes=[note] if note else [],
            metric_hint=metric_id.value,
            entity_hint=entity_ref,
            period_hint=period,
        )
    evidence = [
        ChatEvidence(
            label=f"{METRIC_REGISTRY[metric_id].display_name} — {label}",
            value=value,
            display_value=_format_value(value, unit),
            metric_id=metric_id.value,
            period=label,
            entity=entity_ref.value,
            entity_name=entity_name,
            unit=unit.value,
            source="metric_extractor+period_filter",
            status=AnswerClassification.REPORTED,
        )
    ]
    return EvidenceBundle(
        intent=ChatIntent.METRIC_LOOKUP,
        classification=AnswerClassification.REPORTED,
        confidence=ConfidenceLevel.HIGH,
        headline=(
            f"{METRIC_REGISTRY[metric_id].display_name} for {entity_name} in "
            f"{label}: {_format_value(value, unit)}."
        ),
        evidence=evidence,
        notes=[note] if note else [],
        metric_hint=metric_id.value,
        entity_hint=entity_ref,
        period_hint=period,
    )


def _metric_by_period(
    metric_id: MetricId,
    entity_ctx: EntityContext,
    period: PeriodRef,
) -> Tuple[Optional[float], str, Optional[str]]:
    """Compute value of ``metric_id`` for ``period`` using the DataFrame.

    Returns (value, label, note).
    """
    ext = entity_ctx.extraction
    if ext is None:
        return None, period.label, "No extraction available."

    labeled = _find(ext.metrics, metric_id)
    if labeled is None:
        return None, period.label, (
            f"{METRIC_REGISTRY[metric_id].display_name} is not present in this dataset."
        )
    column = labeled.source_columns[0] if labeled.source_columns else None

    df = entity_ctx.df
    date_col = entity_ctx.date_column

    # If we have no time series, we can only serve "latest" as the aggregate.
    if df is None or df.empty or not column or not date_col or column not in df.columns:
        # Special case: period is "latest" or matches the whole aggregate.
        if period.kind in ("latest", "raw"):
            return labeled.value, period.label, "Aggregate value; per-period breakdown unavailable."
        return None, period.label, (
            "Per-period breakdown is unavailable — the dataset has no time series."
        )

    try:
        dates = pd.to_datetime(df[date_col], errors="coerce")
    except Exception:  # noqa: BLE001
        return None, period.label, "Date column could not be parsed."

    values = pd.to_numeric(df[column], errors="coerce")
    frame = pd.concat([dates, values], axis=1).dropna()
    if frame.empty:
        return None, period.label, "No usable rows for that column."
    frame.columns = ["_date", "_value"]
    frame = frame.sort_values("_date")

    if period.kind == "year":
        year = period.year
        subset = frame[frame["_date"].dt.year == year]
        if subset.empty:
            return None, f"FY{year}", (
                f"No data for FY{year}. Available years: "
                f"{sorted(frame['_date'].dt.year.unique().tolist())}."
            )
        agg = _aggregate_value(metric_id, subset["_value"])
        return agg, f"FY{year}", None

    if period.kind == "quarter":
        year = period.year
        q = period.quarter
        subset = frame[frame["_date"].dt.quarter == q]
        if year is not None:
            subset = subset[subset["_date"].dt.year == year]
        if subset.empty:
            return None, period.label, "No data for that quarter."
        agg = _aggregate_value(metric_id, subset["_value"])
        return agg, period.label, None

    if period.kind == "range":
        start = period.start_year
        end = period.end_year
        subset = frame[
            (frame["_date"].dt.year >= start) & (frame["_date"].dt.year <= end)
        ]
        if subset.empty:
            return None, period.label, "No data in that range."
        agg = _aggregate_value(metric_id, subset["_value"])
        return agg, f"{start}-{end}", None

    if period.kind == "latest":
        last_year = int(frame["_date"].dt.year.max())
        subset = frame[frame["_date"].dt.year == last_year]
        agg = _aggregate_value(metric_id, subset["_value"])
        return agg, f"FY{last_year} (latest)", None

    if period.kind == "previous":
        years = sorted(frame["_date"].dt.year.unique().tolist())
        if len(years) < 2:
            return None, period.label, "Only one year is present in the data."
        prev_year = int(years[-2])
        subset = frame[frame["_date"].dt.year == prev_year]
        agg = _aggregate_value(metric_id, subset["_value"])
        return agg, f"FY{prev_year} (previous)", None

    return None, period.label, "Period kind not supported."


# Which metrics should be summed vs pointed at latest value.
_STOCK_METRICS = {
    MetricId.ASSETS, MetricId.CURRENT_ASSETS, MetricId.NON_CURRENT_ASSETS,
    MetricId.LIABILITIES, MetricId.CURRENT_LIABILITIES, MetricId.EQUITY,
    MetricId.DEBT, MetricId.CASH, MetricId.INVENTORY, MetricId.RECEIVABLES,
    MetricId.WORKING_CAPITAL, MetricId.DEPOSITS, MetricId.CASA,
    MetricId.LOANS, MetricId.GROSS_NPA, MetricId.NET_NPA,
    MetricId.CUSTOMERS, MetricId.EMPLOYEES,
}


def _aggregate_value(metric_id: MetricId, series: pd.Series) -> Optional[float]:
    if series.empty:
        return None
    try:
        if _def_unit(metric_id) == MetricUnit.PERCENT:
            return float(series.mean())
        if metric_id in _STOCK_METRICS:
            # For balance-sheet stocks aggregated over multiple rows in a
            # period, the "latest by index" (already sorted by date) is the
            # least-wrong choice.
            return float(series.iloc[-1])
        return float(series.sum())
    except Exception:  # noqa: BLE001
        return None


def _derive_trend(entity_ctx: EntityContext, metric_id: MetricId) -> Optional[TrendResult]:
    """Compute a trend on the fly if the pre-computed map didn't have it."""
    ext = entity_ctx.extraction
    if ext is None or entity_ctx.df is None or not entity_ctx.date_column:
        return None
    labeled = _find(ext.metrics, metric_id)
    if labeled is None or not labeled.source_columns:
        return None
    column = labeled.source_columns[0]
    if column not in entity_ctx.df.columns:
        return None
    try:
        dates = pd.to_datetime(entity_ctx.df[entity_ctx.date_column], errors="coerce")
    except Exception:  # noqa: BLE001
        return None
    values = pd.to_numeric(entity_ctx.df[column], errors="coerce")
    frame = pd.concat([dates, values], axis=1).dropna()
    frame.columns = ["_date", "_value"]
    frame = frame.sort_values("_date")
    if len(frame) < 2:
        return None

    first = float(frame["_value"].iloc[0])
    last = float(frame["_value"].iloc[-1])
    growth = None if first == 0 else (last - first) / abs(first) * 100.0
    direction = "insufficient_data"
    if growth is not None:
        direction = (
            "improving" if growth > 2.5 else "declining" if growth < -2.5 else "stable"
        )
    period_series: Dict[str, float] = {}
    for ts, value in zip(frame["_date"], frame["_value"]):
        try:
            key = pd.Timestamp(ts).strftime("%Y-%m-%d")
        except Exception:  # noqa: BLE001
            key = str(ts)
        period_series[key] = float(value)

    return TrendResult(
        metric_id=metric_id,
        column=column,
        growth_rate=growth,
        avg_period_growth=None,
        direction=direction,
        period_series=period_series,
        period_count=len(period_series),
    )


# ---------------------------------------------------------------------------
# Ratio helpers
# ---------------------------------------------------------------------------
def _ratio_bundle(
    ratio: LabeledMetric,
    entity_ctx: EntityContext,
    entity_ref: EntityRef,
    ctx: ChatContext,
) -> EvidenceBundle:
    entity_name = _entity_label(entity_ref, ctx)
    unit = ratio.unit
    evidence = [
        ChatEvidence(
            label=f"{ratio.display_name} ({entity_name})",
            value=ratio.value,
            display_value=_format_value(ratio.value, unit),
            metric_id=ratio.metric_id.value,
            entity=entity_ref.value,
            entity_name=entity_name,
            unit=unit.value,
            source="ratio_engine",
            status=_classification_for_status(ratio.status),
        )
    ]
    calc: List[CalculationTrace] = []
    if ratio.notes:
        calc.append(
            CalculationTrace(
                formula=ratio.notes[0],
                result=ratio.value,
                explanation="Derived from the labeled base metrics.",
            )
        )
    return EvidenceBundle(
        intent=ChatIntent.RATIO_LOOKUP,
        classification=_classification_for_status(ratio.status),
        confidence=ConfidenceLevel.HIGH if ratio.status == MetricStatus.CALCULATED else ConfidenceLevel.MEDIUM,
        headline=(
            f"{ratio.display_name} for {entity_name} is "
            f"{_format_value(ratio.value, unit)}."
        ),
        evidence=evidence,
        calculations=calc,
        notes=list(ratio.notes),
        metric_hint=ratio.metric_id.value,
        entity_hint=entity_ref,
    )


def _missing_ratio(
    metric_id: MetricId,
    entity_ctx: EntityContext,
    entity_ref: EntityRef,
    ctx: ChatContext,
) -> EvidenceBundle:
    reason = _explain_missing_ratio(metric_id, entity_ctx)
    return EvidenceBundle(
        intent=ChatIntent.RATIO_LOOKUP,
        classification=AnswerClassification.UNAVAILABLE,
        confidence=ConfidenceLevel.NONE,
        headline=(
            f"{METRIC_REGISTRY[metric_id].display_name} cannot be calculated "
            f"from this dataset."
        ),
        notes=[reason] if reason else [],
        metric_hint=metric_id.value,
        entity_hint=entity_ref,
    )


_RATIO_REQUIREMENTS: Dict[MetricId, Tuple[MetricId, ...]] = {
    MetricId.GROSS_MARGIN: (MetricId.GROSS_PROFIT, MetricId.REVENUE),
    MetricId.OPERATING_MARGIN: (MetricId.OPERATING_PROFIT, MetricId.REVENUE),
    MetricId.NET_MARGIN: (MetricId.NET_PROFIT, MetricId.REVENUE),
    MetricId.ROA: (MetricId.NET_PROFIT, MetricId.ASSETS),
    MetricId.ROE: (MetricId.NET_PROFIT, MetricId.EQUITY),
    MetricId.DEBT_TO_EQUITY: (MetricId.DEBT, MetricId.EQUITY),
    MetricId.CURRENT_RATIO: (MetricId.CURRENT_ASSETS, MetricId.CURRENT_LIABILITIES),
    MetricId.QUICK_RATIO: (MetricId.CURRENT_ASSETS, MetricId.CURRENT_LIABILITIES),
    MetricId.ASSET_TURNOVER: (MetricId.REVENUE, MetricId.ASSETS),
    MetricId.RECEIVABLES_TURNOVER: (MetricId.REVENUE, MetricId.RECEIVABLES),
    MetricId.INVENTORY_TURNOVER: (MetricId.COGS, MetricId.INVENTORY),
    MetricId.INTEREST_COVERAGE: (MetricId.EBIT, MetricId.INTEREST_EXPENSE),
    MetricId.FCF_MARGIN: (MetricId.FREE_CASH_FLOW, MetricId.REVENUE),
    MetricId.COST_TO_INCOME: (MetricId.OPERATING_EXPENSES, MetricId.NET_INTEREST_INCOME),
    MetricId.NIM: (MetricId.NET_INTEREST_INCOME, MetricId.ASSETS),
    MetricId.CREDIT_DEPOSIT_RATIO: (MetricId.LOANS, MetricId.DEPOSITS),
    MetricId.PROVISION_COVERAGE: (MetricId.PROVISIONS, MetricId.GROSS_NPA),
    MetricId.CASA_RATIO: (MetricId.CASA, MetricId.DEPOSITS),
}


def _explain_missing_ratio(metric_id: MetricId, entity_ctx: EntityContext) -> str:
    needed = _RATIO_REQUIREMENTS.get(metric_id, ())
    if not needed or not entity_ctx.extraction:
        return "The required underlying metrics are unavailable."
    missing = [
        METRIC_REGISTRY[mid].display_name
        for mid in needed
        if mid not in entity_ctx.extraction.value_map
    ]
    if missing:
        return f"Missing input(s): {', '.join(missing)}."
    return "The dataset has the inputs but the denominator is zero — ratio undefined."


# ---------------------------------------------------------------------------
# Comparison helpers
# ---------------------------------------------------------------------------
def _comparison_evidence(
    row: ComparisonRow, ctx: ChatContext, *, include_market: bool
) -> List[ChatEvidence]:
    unit = row.unit
    entity_name_primary = ctx.primary.display_name
    entity_name_secondary = ctx.secondary.display_name if ctx.secondary else "Competitor"
    entity_name_market = ctx.market.display_name if ctx.market else "Market"
    out: List[ChatEvidence] = []
    if row.primary_value is not None:
        out.append(
            ChatEvidence(
                label=f"{row.display_name} ({entity_name_primary})",
                value=row.primary_value,
                display_value=_format_value(row.primary_value, unit),
                metric_id=row.metric_id.value,
                unit=unit.value,
                entity=EntityRef.PRIMARY.value,
                entity_name=entity_name_primary,
                source="benchmark_analyzer.comparisons",
                status=AnswerClassification.REPORTED,
            )
        )
    if row.secondary_value is not None:
        out.append(
            ChatEvidence(
                label=f"{row.display_name} ({entity_name_secondary})",
                value=row.secondary_value,
                display_value=_format_value(row.secondary_value, unit),
                metric_id=row.metric_id.value,
                unit=unit.value,
                entity=EntityRef.SECONDARY.value,
                entity_name=entity_name_secondary,
                source="benchmark_analyzer.comparisons",
                status=AnswerClassification.REPORTED,
            )
        )
    if include_market and row.market_value is not None:
        out.append(
            ChatEvidence(
                label=f"{row.display_name} ({entity_name_market})",
                value=row.market_value,
                display_value=_format_value(row.market_value, unit),
                metric_id=row.metric_id.value,
                unit=unit.value,
                entity=EntityRef.MARKET.value,
                entity_name=entity_name_market,
                source="benchmark_analyzer.comparisons",
                status=AnswerClassification.REPORTED,
            )
        )
    if row.percentage_gap is not None:
        out.append(
            ChatEvidence(
                label=f"{row.display_name} — gap",
                value=row.percentage_gap,
                display_value=f"{row.percentage_gap:+.2f}% ({row.status})",
                metric_id=row.metric_id.value,
                unit=MetricUnit.PERCENT.value,
                source="benchmark_analyzer.comparisons",
                status=AnswerClassification.CALCULATED,
            )
        )
    return out


def _comparison_headline(row: ComparisonRow, ctx: ChatContext, *, include_market: bool = False) -> str:
    unit = row.unit
    parts = [
        f"{row.display_name}: "
        f"{ctx.primary.display_name} {_format_value(row.primary_value, unit)}"
    ]
    if row.secondary_value is not None:
        parts.append(
            f"vs {ctx.secondary.display_name if ctx.secondary else 'competitor'} "
            f"{_format_value(row.secondary_value, unit)}"
        )
    if include_market and row.market_value is not None:
        parts.append(
            f"(market {_format_value(row.market_value, unit)})"
        )
    parts.append(f"— {row.status}")
    return " ".join(parts) + "."


# ---------------------------------------------------------------------------
# Fallback bundles
# ---------------------------------------------------------------------------
def _missing_metric(
    metric_id: MetricId,
    entity_ref: EntityRef,
    entity_ctx: EntityContext,
    ctx: ChatContext,
) -> EvidenceBundle:
    return EvidenceBundle(
        intent=ChatIntent.METRIC_LOOKUP,
        classification=AnswerClassification.UNAVAILABLE,
        confidence=ConfidenceLevel.NONE,
        headline=(
            f"{METRIC_REGISTRY[metric_id].display_name} is not available for "
            f"{_entity_label(entity_ref, ctx)} in this dataset."
        ),
        notes=[
            "This metric was not recognised in any column. Rename the column "
            "or add a column with a canonical name to enable it.",
        ],
        metric_hint=metric_id.value,
        entity_hint=entity_ref,
    )


def _no_entity_data(intent: ChatIntent, ref: EntityRef, ctx: ChatContext) -> EvidenceBundle:
    if ref == EntityRef.SECONDARY:
        msg = "No secondary / competitor dataset is loaded for this session."
    elif ref == EntityRef.MARKET:
        msg = "No market benchmark dataset is loaded for this session."
    elif ref == EntityRef.COMBINED:
        msg = "No combined merger scenario is available for this session."
    else:
        msg = "No primary dataset is loaded for this session."
    return EvidenceBundle(
        intent=intent,
        classification=AnswerClassification.UNAVAILABLE,
        confidence=ConfidenceLevel.NONE,
        headline=msg,
        entity_hint=ref,
    )


def _mode_mismatch(intent: ChatIntent, expected: str) -> EvidenceBundle:
    return EvidenceBundle(
        intent=intent,
        classification=AnswerClassification.UNAVAILABLE,
        confidence=ConfidenceLevel.NONE,
        headline=(
            f"That question requires {expected}, which is not the mode you have open. "
            "Switch modes and re-run the analysis to answer it."
        ),
    )


def _empty_bundle(intent: ChatIntent, msg: str) -> EvidenceBundle:
    return EvidenceBundle(
        intent=intent,
        classification=AnswerClassification.UNAVAILABLE,
        confidence=ConfidenceLevel.NONE,
        headline=msg,
    )


def _find(metrics: Iterable[LabeledMetric], mid: MetricId) -> Optional[LabeledMetric]:
    for m in metrics:
        if m.metric_id == mid:
            return m
    return None
