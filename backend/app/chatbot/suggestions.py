"""Context-aware suggested follow-up questions.

Suggestions are generated *from the actual data*, not from a static list:
we only surface a question when the underlying metric / ratio / gap is
present. That way the UI never shows a follow-up that the chatbot can't
answer.
"""

from __future__ import annotations

from typing import List

from app.analysis.metric_registry import METRIC_REGISTRY
from app.analysis.types import AnalysisMode, MetricId, MetricStatus
from app.chatbot.context_builder import ChatContext


def suggest_starter_questions(ctx: ChatContext, *, limit: int = 6) -> List[str]:
    """Return a short list of high-signal questions the user can start with."""
    if ctx.analysis_mode == AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS:
        return _merger_suggestions(ctx, limit)
    if ctx.analysis_mode == AnalysisMode.COMPETITOR_MARKET_BENCHMARK:
        return _benchmark_suggestions(ctx, limit)
    return _self_suggestions(ctx, limit)


def suggest_followups(ctx: ChatContext, last_intent: str, *, limit: int = 4) -> List[str]:
    """Return follow-up suggestions that make sense after ``last_intent``."""
    if last_intent in ("metric_lookup", "period_comparison", "trend_analysis"):
        return _followups_after_metric(ctx, limit)
    if last_intent == "financial_health":
        return _followups_after_health(ctx, limit)
    if last_intent in ("risk_analysis", "weakness_analysis"):
        return _followups_after_risk(ctx, limit)
    if last_intent in ("gap_analysis", "competitor_comparison", "market_benchmark"):
        return _followups_after_gap(ctx, limit)
    if last_intent in ("merger_overview", "merger_metric", "merger_synergy"):
        return _followups_after_merger(ctx, limit)
    return suggest_starter_questions(ctx, limit=limit)


# ---------------------------------------------------------------------------
# Mode-specific starters
# ---------------------------------------------------------------------------
def _self_suggestions(ctx: ChatContext, limit: int) -> List[str]:
    out: List[str] = []
    present = _present_metric_ids(ctx)
    ratios_present = _present_ratio_ids(ctx)

    if ctx.analysis_result and ctx.analysis_result.financial_health:
        out.append("How financially healthy are we?")
    if MetricId.REVENUE in present:
        out.append("What is our revenue trend?")
    if MetricId.NET_MARGIN in ratios_present or MetricId.NET_PROFIT in present:
        out.append("What is our net profit margin?")
    if ctx.analysis_result and ctx.analysis_result.risks:
        out.append("What are our biggest financial risks?")
    if ctx.analysis_result and ctx.analysis_result.opportunities:
        out.append("Which metrics look like opportunities?")
    if ctx.analysis_result and ctx.analysis_result.recommendations:
        out.append("What should we improve first?")
    if MetricId.DEBT_TO_EQUITY in ratios_present:
        out.append("How high is our leverage?")
    return out[:limit]


def _merger_suggestions(ctx: ChatContext, limit: int) -> List[str]:
    ar = ctx.analysis_result
    out: List[str] = []
    if ar and ar.combined_scenario and ar.combined_scenario.metrics:
        out.append("What would combined revenue look like?")
    if ar and ar.synergies:
        out.append("What synergies could exist?")
    if ar and ar.risks:
        out.append("What are the biggest merger risks?")
    out.append("How compatible are the two companies?")
    if ar and ar.financial_health:
        out.append("What's the combined financial health score?")
    out.append("How does combined debt-to-equity look?")
    return out[:limit]


def _benchmark_suggestions(ctx: ChatContext, limit: int) -> List[str]:
    ar = ctx.analysis_result
    out: List[str] = []
    if ar and ar.gaps:
        out.append("Where are we behind the competitor?")
        out.append("What is our biggest benchmark gap?")
    if ar and ar.comparisons:
        out.append("How does our net margin compare?")
    if ar and ar.market_entity:
        out.append("How do we compare to the market?")
    out.append("What should we improve first?")
    out.append("Show me our strengths and weaknesses.")
    return out[:limit]


# ---------------------------------------------------------------------------
# Follow-up templates
# ---------------------------------------------------------------------------
def _followups_after_metric(ctx: ChatContext, limit: int) -> List[str]:
    out = [
        "What about the previous year?",
        "How is this metric trending?",
        "Is that good?",
    ]
    if ctx.analysis_mode == AnalysisMode.COMPETITOR_MARKET_BENCHMARK:
        out.append("How does that compare to the competitor?")
    if ctx.analysis_mode == AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS:
        out.append("What does that look like combined?")
    return out[:limit]


def _followups_after_health(ctx: ChatContext, limit: int) -> List[str]:
    return [
        "Which dimension is dragging our score down?",
        "What are our biggest risks?",
        "What should we improve first?",
    ][:limit]


def _followups_after_risk(ctx: ChatContext, limit: int) -> List[str]:
    return [
        "What are our strengths?",
        "What opportunities exist?",
        "What should we improve first?",
    ][:limit]


def _followups_after_gap(ctx: ChatContext, limit: int) -> List[str]:
    return [
        "What is the near-term target for that gap?",
        "Which gaps are highest priority?",
        "Where are we ahead of the competitor?",
    ][:limit]


def _followups_after_merger(ctx: ChatContext, limit: int) -> List[str]:
    return [
        "What are the biggest risks?",
        "How compatible are the two companies?",
        "What would combined margins look like?",
    ][:limit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _present_metric_ids(ctx: ChatContext):
    ext = ctx.primary.extraction
    if ext is None:
        return set()
    return set(ext.value_map.keys())


def _present_ratio_ids(ctx: ChatContext):
    return {
        r.metric_id
        for r in ctx.primary.ratios
        if r.status != MetricStatus.UNAVAILABLE and r.value is not None
    }
