"""Intent classifier for chatbot queries.

Rule-based on purpose: predictable, transparent, testable, and free of any
network dependency. Each rule inspects the normalized question plus the
slots already extracted by the semantic resolver.

Slot back-filling — for follow-ups such as "what about 2024?" — is done
here by pulling ``last_metric`` / ``last_period`` / ``last_entity`` from a
short-term conversation state (see ``session_store``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Optional

from app.analysis.metric_registry import METRIC_REGISTRY
from app.analysis.types import MetricId
from app.chatbot.semantic_resolver import (
    resolve_entity,
    resolve_metrics,
    resolve_periods,
)
from app.chatbot.types import (
    ChatIntent,
    ClassifiedQuery,
    EntityRef,
    PeriodRef,
    QuerySlots,
)


# ---------------------------------------------------------------------------
# Conversation state input (what we read from the session, if any).
# ---------------------------------------------------------------------------
@dataclass
class ConversationState:
    last_metric_id: Optional[str] = None
    last_period: Optional[PeriodRef] = None
    last_entity: Optional[EntityRef] = None
    last_intent: Optional[ChatIntent] = None


# ---------------------------------------------------------------------------
# Rule patterns
# ---------------------------------------------------------------------------
_GREETINGS = re.compile(
    r"^\s*(hi|hello|hey|yo|good\s+(morning|afternoon|evening))\b",
    re.IGNORECASE,
)

_HELP_PATTERNS = re.compile(
    r"\b(help|what\s+can\s+you\s+do|what\s+do\s+you\s+know|what\s+can\s+i\s+ask)\b",
    re.IGNORECASE,
)

_DATASET_OVERVIEW = re.compile(
    r"\b(overview|summary|describe\s+the\s+data|tell\s+me\s+about\s+(the|this)\s+dataset|"
    r"summari[sz]e|what('| i)s\s+in\s+(the|this)\s+dataset)\b",
    re.IGNORECASE,
)

_ROW_COUNT = re.compile(
    r"\b(how\s+many\s+(rows|records|entries|transactions|periods)|"
    r"(number|count)\s+of\s+(rows|records|entries|transactions|periods)|"
    r"row\s+count|record\s+count)\b",
    re.IGNORECASE,
)

_COLUMN_COUNT = re.compile(
    r"\b(how\s+many\s+(columns|fields|variables|attributes)|"
    r"(number|count)\s+of\s+(columns|fields|variables)|"
    r"column\s+count|which\s+columns|what\s+columns|list\s+(the\s+)?columns|"
    r"columns\s+do\s+(we|i|the\s+dataset)\s+have|"
    r"show\s+(me\s+)?(the\s+)?columns)\b",
    re.IGNORECASE,
)

_DATA_QUALITY = re.compile(
    r"\b(data\s+quality|quality\s+(score|grade)|missing(\s+values)?|"
    r"nulls?|duplicates?|duplicate\s+rows|outliers?|cardinality|"
    r"quality\s+of\s+(the|this)\s+data)\b",
    re.IGNORECASE,
)

_PERIOD_RANGE = re.compile(
    r"\b(date\s+range|time\s+range|period\s+range|reporting\s+period|"
    r"what\s+periods|what\s+years|which\s+years|which\s+periods|"
    r"time\s+span|coverage|from\s+when|earliest|latest\s+(period|date))\b",
    re.IGNORECASE,
)

_TREND_PATTERNS = re.compile(
    r"\b(trend|trending|over\s+time|yoy|year[- ]over[- ]year|"
    r"quarter[- ]over[- ]quarter|growth|growing|declining|going\s+up|"
    r"going\s+down|history|historical|movement)\b",
    re.IGNORECASE,
)

_PERIOD_COMPARISON = re.compile(
    r"\b(vs\.?|versus|compared\s+to|compare\s+with|change\s+(between|from|"
    r"in)|difference\s+between|delta\s+between)\b",
    re.IGNORECASE,
)

_HEALTH_PATTERNS = re.compile(
    r"\b(health(y)?|health\s+score|overall\s+score|grade|financial\s+"
    r"condition|how\s+are\s+we\s+doing|how\s+healthy)\b",
    re.IGNORECASE,
)

_RISK_PATTERNS = re.compile(
    r"\b(risk|risks|risky|risk\s+factor|weakness|weaknesses|threats?|"
    r"vulnerability|red\s+flag|biggest\s+risk|main\s+risks?)\b",
    re.IGNORECASE,
)

_STRENGTH_PATTERNS = re.compile(
    r"\b(strength|strengths|strong\s+point|advantage|advantages)\b",
    re.IGNORECASE,
)

_OPPORTUNITY_PATTERNS = re.compile(
    r"\b(opportunit(y|ies)|upside|potential|room\s+to\s+grow)\b",
    re.IGNORECASE,
)

_RECO_PATTERNS = re.compile(
    r"\b(recommend|recommendation|advice|what\s+should\s+(we|i)|next\s+"
    r"steps?|priorit(y|ies)|what\s+to\s+improve|where\s+should\s+we\s+"
    r"focus)\b",
    re.IGNORECASE,
)

_EXPLANATION_PATTERNS = re.compile(
    r"\b(why(\s+is|\s+are)?|explain|what\s+caused|driver|reason)\b",
    re.IGNORECASE,
)

_MERGER_SYNERGY = re.compile(
    r"\b(synerg(y|ies)|cross[- ]sell|cost\s+saving|revenue\s+uplift)\b",
    re.IGNORECASE,
)

_MERGER_RISK = re.compile(
    r"\b(merger\s+risk|integration\s+risk|dilution|deal\s+risk)\b",
    re.IGNORECASE,
)

_MERGER_COMPAT = re.compile(
    r"\b(compatib(le|ility)|fit|match|suitable\s+partner)\b",
    re.IGNORECASE,
)

_MERGER_HINTS = re.compile(
    r"\b(merger|acquisition|acquire|acquiring|combined|consolidat(e|ed|ion)|"
    r"post[- ]merger|merged\s+entity|partnership)\b",
    re.IGNORECASE,
)

_COMPETITOR_HINTS = re.compile(
    r"\b(competitor|competition|rival|peer|the\s+other\s+company|"
    r"how\s+(do|does|are)\s+we\s+compare)\b",
    re.IGNORECASE,
)

_MARKET_HINTS = re.compile(
    r"\b(market|industry|market\s+benchmark|industry\s+benchmark|market\s+average|"
    r"peer\s+(average|median|median))\b",
    re.IGNORECASE,
)

_GAP_HINTS = re.compile(
    r"\b(gap|gaps|behind|falling\s+short|below\s+the\s+benchmark|catch\s+up|"
    r"where\s+are\s+we\s+behind)\b",
    re.IGNORECASE,
)

_ROADMAP_HINTS = re.compile(
    r"\b(roadmap|action\s+plan|plan\s+to\s+(close|match)|near\s+term\s+"
    r"target|long\s+term\s+target|milestone)\b",
    re.IGNORECASE,
)

_FOLLOWUP_STARTS = re.compile(
    r"^\s*(what|how)\s+about\b|^\s*and\s+(what|how|the)?|^\s*same\s+for\b",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
def classify(
    text: str,
    *,
    state: Optional[ConversationState] = None,
    analysis_mode: Optional[str] = None,
) -> ClassifiedQuery:
    """Return a ``ClassifiedQuery`` for ``text``.

    ``state`` supplies short-term memory (last metric / period / entity) so
    a follow-up like "what about 2024?" gets the previous metric and
    intent back-filled. ``analysis_mode`` is the current UI mode; it
    influences intent resolution ties (e.g. "how do we compare?" is a
    competitor comparison when benchmark mode is open).
    """
    original = text or ""
    normalized = _normalize(original)
    is_followup = _FOLLOWUP_STARTS.search(normalized) is not None
    used_context = False

    # ---- Slot extraction ---------------------------------------------------
    metric_matches = resolve_metrics(normalized)
    periods = resolve_periods(normalized)
    entity = resolve_entity(normalized, default=EntityRef.PRIMARY)

    # Back-fill from conversation state.
    if state is not None:
        if not metric_matches and state.last_metric_id:
            metric_matches = [(_metric_from_id(state.last_metric_id), 0.75)]  # type: ignore[list-item]
            used_context = True
        if not periods and state.last_period is not None and is_followup:
            periods = [state.last_period]
            used_context = True
        if (
            entity == EntityRef.PRIMARY
            and state.last_entity is not None
            and state.last_entity != EntityRef.PRIMARY
            and _entity_missing_in_text(normalized)
        ):
            entity = state.last_entity
            used_context = True

    slots = QuerySlots(
        metric_ids=[
            mid.value for mid, _score in metric_matches if isinstance(mid, MetricId)
        ],
        periods=periods,
        entity=entity,
    )

    # ---- Intent -----------------------------------------------------------
    intent = _pick_intent(
        original,
        normalized,
        slots,
        is_followup=is_followup,
        state=state,
        analysis_mode=analysis_mode,
    )

    # Subject hints for downstream generators
    if _HEALTH_PATTERNS.search(normalized):
        slots.subject_hints.append("health")
    if _RISK_PATTERNS.search(normalized):
        slots.subject_hints.append("risk")
    if _STRENGTH_PATTERNS.search(normalized):
        slots.subject_hints.append("strength")
    if _OPPORTUNITY_PATTERNS.search(normalized):
        slots.subject_hints.append("opportunity")
    if _RECO_PATTERNS.search(normalized):
        slots.subject_hints.append("recommendation")

    # Aggregation hints
    if _TREND_PATTERNS.search(normalized):
        slots.aggregation = "trend"
    elif "growth" in normalized:
        slots.aggregation = "growth"
    elif _PERIOD_COMPARISON.search(normalized) and len(periods) >= 2:
        slots.aggregation = "delta"
    elif "average" in normalized or "avg" in normalized or "mean" in normalized:
        slots.aggregation = "mean"
    elif "sum" in normalized or "total" in normalized:
        slots.aggregation = "sum"

    if _GAP_HINTS.search(normalized):
        slots.comparison = "gap"
    elif _PERIOD_COMPARISON.search(normalized):
        slots.comparison = "vs"

    return ClassifiedQuery(
        original_text=original,
        normalized_text=normalized,
        intent=intent,
        slots=slots,
        used_context=used_context,
    )


# ---------------------------------------------------------------------------
# Intent resolution
# ---------------------------------------------------------------------------
def _pick_intent(
    original: str,
    normalized: str,
    slots: QuerySlots,
    *,
    is_followup: bool,
    state: Optional[ConversationState],
    analysis_mode: Optional[str],
) -> ChatIntent:
    # Meta intents first
    if _GREETINGS.match(normalized):
        return ChatIntent.GREETING
    if _HELP_PATTERNS.search(normalized):
        return ChatIntent.HELP

    # Dataset understanding
    if _ROW_COUNT.search(normalized):
        return ChatIntent.DATASET_OVERVIEW
    if _COLUMN_COUNT.search(normalized):
        return ChatIntent.COLUMN_LOOKUP
    if _DATA_QUALITY.search(normalized):
        return ChatIntent.DATA_QUALITY
    if _PERIOD_RANGE.search(normalized):
        return ChatIntent.PERIOD_RANGE
    if _DATASET_OVERVIEW.search(normalized):
        return ChatIntent.DATASET_OVERVIEW

    # Roadmap / gap have to beat generic comparisons
    if _ROADMAP_HINTS.search(normalized):
        return ChatIntent.ROADMAP
    if _GAP_HINTS.search(normalized):
        return ChatIntent.GAP_ANALYSIS

    # Merger cluster (only when mode allows or hint is present)
    if _MERGER_SYNERGY.search(normalized):
        return ChatIntent.MERGER_SYNERGY
    if _MERGER_RISK.search(normalized):
        return ChatIntent.MERGER_RISK
    if _MERGER_COMPAT.search(normalized):
        return ChatIntent.MERGER_COMPATIBILITY
    if _MERGER_HINTS.search(normalized) or slots.entity == EntityRef.COMBINED:
        # Metric-specific under merger scenario
        if slots.metric_ids or "revenue" in normalized or "profit" in normalized:
            return ChatIntent.MERGER_METRIC
        return ChatIntent.MERGER_OVERVIEW

    # Benchmark cluster
    if _COMPETITOR_HINTS.search(normalized) or slots.entity == EntityRef.SECONDARY:
        if _MARKET_HINTS.search(normalized) or slots.entity == EntityRef.MARKET:
            return ChatIntent.MARKET_BENCHMARK
        return ChatIntent.COMPETITOR_COMPARISON
    if _MARKET_HINTS.search(normalized) or slots.entity == EntityRef.MARKET:
        return ChatIntent.MARKET_BENCHMARK

    # Financial health & SWOT
    if _RECO_PATTERNS.search(normalized):
        return ChatIntent.RECOMMENDATION
    if _RISK_PATTERNS.search(normalized) and "weakness" not in normalized:
        return ChatIntent.RISK_ANALYSIS
    if _STRENGTH_PATTERNS.search(normalized):
        return ChatIntent.STRENGTH_ANALYSIS
    if _OPPORTUNITY_PATTERNS.search(normalized):
        return ChatIntent.OPPORTUNITY_ANALYSIS
    if "weakness" in normalized or "weaknesses" in normalized:
        return ChatIntent.WEAKNESS_ANALYSIS
    if _HEALTH_PATTERNS.search(normalized):
        return ChatIntent.FINANCIAL_HEALTH

    # Trend & period comparisons need metric context. An explicit
    # two-period question ("2024 vs 2025") wins over a generic trend keyword.
    if slots.metric_ids and len(slots.periods) >= 2:
        return ChatIntent.PERIOD_COMPARISON

    if _TREND_PATTERNS.search(normalized) and slots.metric_ids:
        return ChatIntent.TREND_ANALYSIS

    if slots.metric_ids and _PERIOD_COMPARISON.search(normalized):
        return ChatIntent.PERIOD_COMPARISON

    # Ratio lookup: metric present that is one of the derived ratios
    if slots.metric_ids and _is_ratio_metric(slots.metric_ids[0]):
        return ChatIntent.RATIO_LOOKUP

    if slots.metric_ids:
        return ChatIntent.METRIC_LOOKUP

    if _EXPLANATION_PATTERNS.search(normalized):
        return ChatIntent.EXPLANATION

    # Follow-up with no new slots and history is available.
    if is_followup and state is not None and (state.last_intent or state.last_metric_id):
        return state.last_intent or ChatIntent.METRIC_LOOKUP

    return ChatIntent.UNSUPPORTED


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _normalize(text: str) -> str:
    """Trim + collapse whitespace. Keeps punctuation for regexes."""
    if not text:
        return ""
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned


def _is_ratio_metric(metric_id_value: str) -> bool:
    try:
        mid = MetricId(metric_id_value)
    except ValueError:
        return False
    defn = METRIC_REGISTRY.get(mid)
    return bool(defn and defn.is_derived)


def _metric_from_id(value: str) -> MetricId:
    return MetricId(value)


def _entity_missing_in_text(normalized: str) -> bool:
    """True if the text doesn't explicitly override entity (so we can
    inherit)."""
    lowered = f" {normalized.lower()} "
    hint_words = (
        " our ", " we ", " us ", " my company ",
        " competitor ", " market ", " combined ",
    )
    return not any(w in lowered for w in hint_words)
