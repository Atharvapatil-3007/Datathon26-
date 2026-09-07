"""Chatbot data types.

Everything here is a plain dataclass with a ``to_dict()`` returning JSON-safe
primitives. The types are deliberately narrow so the frontend contract stays
readable.

Design goals:
  * Every numerical answer carries an ``AnswerClassification`` so the UI can
    honestly distinguish reported / calculated / scenario / estimated /
    unavailable results.
  * Every response carries an ``evidence`` list — the atomic facts that back
    the answer — so users (and tests) can verify what the model saw.
  * Every calculation surfaces its formula so nothing is a black box.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from app.analysis.types import AnalysisMode  # re-exported for callers


CHATBOT_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class ChatRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


class ChatIntent(str, Enum):
    """Coarse-grained classification of what the user is asking for."""

    # ---- Dataset understanding ---------------------------------------------
    DATASET_OVERVIEW = "dataset_overview"
    COLUMN_LOOKUP = "column_lookup"
    DATA_QUALITY = "data_quality"
    PERIOD_RANGE = "period_range"

    # ---- Financial metrics -------------------------------------------------
    METRIC_LOOKUP = "metric_lookup"
    RATIO_LOOKUP = "ratio_lookup"
    PERIOD_COMPARISON = "period_comparison"
    TREND_ANALYSIS = "trend_analysis"

    # ---- Financial health --------------------------------------------------
    FINANCIAL_HEALTH = "financial_health"
    RISK_ANALYSIS = "risk_analysis"
    STRENGTH_ANALYSIS = "strength_analysis"
    OPPORTUNITY_ANALYSIS = "opportunity_analysis"
    WEAKNESS_ANALYSIS = "weakness_analysis"
    RECOMMENDATION = "recommendation"
    EXPLANATION = "explanation"

    # ---- Merger mode -------------------------------------------------------
    MERGER_OVERVIEW = "merger_overview"
    MERGER_METRIC = "merger_metric"
    MERGER_SYNERGY = "merger_synergy"
    MERGER_RISK = "merger_risk"
    MERGER_COMPATIBILITY = "merger_compatibility"

    # ---- Benchmark mode ----------------------------------------------------
    COMPETITOR_COMPARISON = "competitor_comparison"
    MARKET_BENCHMARK = "market_benchmark"
    GAP_ANALYSIS = "gap_analysis"
    ROADMAP = "roadmap"

    # ---- Meta --------------------------------------------------------------
    GREETING = "greeting"
    HELP = "help"
    UNRELATED = "unrelated"
    UNSUPPORTED = "unsupported"


class AnswerClassification(str, Enum):
    """How the value should be understood by the user."""

    REPORTED = "reported"
    CALCULATED = "calculated"
    ESTIMATED = "estimated"
    SCENARIO = "scenario"
    UNAVAILABLE = "unavailable"
    INFORMATIONAL = "informational"  # descriptive, non-numeric answers
    REFUSED = "refused"              # out-of-scope guardrail refusal


class ConfidenceLevel(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    NONE = "none"


class EntityRef(str, Enum):
    """Which entity the question refers to."""

    PRIMARY = "primary"           # our company
    SECONDARY = "secondary"       # other company / competitor
    MARKET = "market"             # market/industry benchmark
    COMBINED = "combined"         # merger combined scenario
    UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Query slots and classification
# ---------------------------------------------------------------------------
@dataclass
class PeriodRef:
    """A resolved period reference.

    ``kind`` describes the shape:
      * ``year``     -> ``value = "2024"``
      * ``quarter``  -> ``value = "Q1 2024"``, ``year=2024``, ``quarter=1``
      * ``latest``   -> most recent period in the data
      * ``previous`` -> period immediately before ``latest``
      * ``range``    -> ``start_year`` / ``end_year`` populated
      * ``raw``      -> free text; unresolved
    """

    kind: str                 # 'year' | 'quarter' | 'latest' | 'previous' | 'range' | 'raw'
    label: str
    year: Optional[int] = None
    quarter: Optional[int] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    raw: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "label": self.label,
            "year": self.year,
            "quarter": self.quarter,
            "start_year": self.start_year,
            "end_year": self.end_year,
            "raw": self.raw,
        }


@dataclass
class QuerySlots:
    """The structured facts we could pull from a natural-language question."""

    metric_ids: List[str] = field(default_factory=list)  # canonical MetricId .value strings
    ratio_hints: List[str] = field(default_factory=list)
    periods: List[PeriodRef] = field(default_factory=list)
    entity: EntityRef = EntityRef.PRIMARY
    aggregation: Optional[str] = None      # 'sum' | 'mean' | 'growth' | 'yoy' | etc.
    comparison: Optional[str] = None       # 'gap' | 'vs' | 'trend' | 'growth'
    subject_hints: List[str] = field(default_factory=list)  # 'health', 'risk', 'strength', ...

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_ids": self.metric_ids,
            "ratio_hints": self.ratio_hints,
            "periods": [p.to_dict() for p in self.periods],
            "entity": self.entity.value,
            "aggregation": self.aggregation,
            "comparison": self.comparison,
            "subject_hints": self.subject_hints,
        }


@dataclass
class ClassifiedQuery:
    """The classifier's output. Sent to the query engine."""

    original_text: str
    normalized_text: str
    intent: ChatIntent
    slots: QuerySlots = field(default_factory=QuerySlots)
    used_context: bool = False              # true if we back-filled slots from history

    def to_dict(self) -> Dict[str, Any]:
        return {
            "original_text": self.original_text,
            "normalized_text": self.normalized_text,
            "intent": self.intent.value,
            "slots": self.slots.to_dict(),
            "used_context": self.used_context,
        }


# ---------------------------------------------------------------------------
# Evidence & calculation
# ---------------------------------------------------------------------------
@dataclass
class ChatEvidence:
    """One atomic fact used to back an answer.

    Not every field is populated for every evidence item — a data-quality
    observation, for example, only has ``label`` and ``value``.
    """

    label: str                                          # human-readable
    value: Optional[float] = None                       # numeric, when applicable
    display_value: Optional[str] = None                 # pre-formatted string
    unit: Optional[str] = None                          # 'currency' | 'percent' | ...
    metric_id: Optional[str] = None                     # canonical id, if any
    period: Optional[str] = None                        # e.g. '2024' | 'Q3 2024'
    entity: Optional[str] = None                        # 'primary' | 'secondary' | 'market' | 'combined'
    entity_name: Optional[str] = None                   # display name for the entity
    source: Optional[str] = None                        # 'profile' | 'metric_extractor' | 'ratio_engine' | ...
    status: AnswerClassification = AnswerClassification.INFORMATIONAL

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "value": _safe_number(self.value),
            "display_value": self.display_value,
            "unit": self.unit,
            "metric_id": self.metric_id,
            "period": self.period,
            "entity": self.entity,
            "entity_name": self.entity_name,
            "source": self.source,
            "status": self.status.value,
        }


@dataclass
class CalculationTrace:
    """How a derived value was computed."""

    formula: str
    result: Optional[float]
    inputs: Dict[str, float] = field(default_factory=dict)
    explanation: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "formula": self.formula,
            "result": _safe_number(self.result),
            "inputs": {k: _safe_number(v) for k, v in self.inputs.items()},
            "explanation": self.explanation,
        }


@dataclass
class EvidenceBundle:
    """Everything the query engine could produce for a single question.

    The answer generator turns this into natural language. Keeping this
    separate makes it trivial to test the engine independently from the
    prose layer.
    """

    intent: ChatIntent
    classification: AnswerClassification
    confidence: ConfidenceLevel
    headline: str = ""                                     # one-line summary text (raw)
    evidence: List[ChatEvidence] = field(default_factory=list)
    calculations: List[CalculationTrace] = field(default_factory=list)
    notes: List[str] = field(default_factory=list)         # explanations / caveats
    warnings: List[str] = field(default_factory=list)      # data caveats
    entity_hint: Optional[EntityRef] = None                # for follow-up context
    metric_hint: Optional[str] = None                      # for follow-up context
    period_hint: Optional[PeriodRef] = None                # for follow-up context

    def to_dict(self) -> Dict[str, Any]:
        return {
            "intent": self.intent.value,
            "classification": self.classification.value,
            "confidence": self.confidence.value,
            "headline": self.headline,
            "evidence": [e.to_dict() for e in self.evidence],
            "calculations": [c.to_dict() for c in self.calculations],
            "notes": self.notes,
            "warnings": self.warnings,
            "entity_hint": self.entity_hint.value if self.entity_hint else None,
            "metric_hint": self.metric_hint,
            "period_hint": self.period_hint.to_dict() if self.period_hint else None,
        }


# ---------------------------------------------------------------------------
# Chat messages & response
# ---------------------------------------------------------------------------
@dataclass
class ChatMessage:
    role: ChatRole
    text: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # Assistant messages only:
    intent: Optional[ChatIntent] = None
    classification: Optional[AnswerClassification] = None
    confidence: Optional[ConfidenceLevel] = None
    evidence: List[ChatEvidence] = field(default_factory=list)
    calculations: List[CalculationTrace] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "text": self.text,
            "timestamp": self.timestamp.isoformat(),
            "intent": self.intent.value if self.intent else None,
            "classification": self.classification.value if self.classification else None,
            "confidence": self.confidence.value if self.confidence else None,
            "evidence": [e.to_dict() for e in self.evidence],
            "calculations": [c.to_dict() for c in self.calculations],
        }


@dataclass
class ChatContextInfo:
    """Static metadata about what the assistant is seeing right now."""

    dataset_id: Optional[str]
    dataset_name: Optional[str]
    analysis_mode: Optional[str]           # 'self_analysis' | 'merger_partnership_analysis' | ...
    secondary_dataset_id: Optional[str] = None
    secondary_dataset_name: Optional[str] = None
    market_dataset_id: Optional[str] = None
    market_dataset_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "dataset_id": self.dataset_id,
            "dataset_name": self.dataset_name,
            "analysis_mode": self.analysis_mode,
            "secondary_dataset_id": self.secondary_dataset_id,
            "secondary_dataset_name": self.secondary_dataset_name,
            "market_dataset_id": self.market_dataset_id,
            "market_dataset_name": self.market_dataset_name,
        }


@dataclass
class ChatResponse:
    """The full response sent to the client."""

    session_id: str
    message_id: str
    answer: str
    intent: ChatIntent
    classification: AnswerClassification
    confidence: ConfidenceLevel
    evidence: List[ChatEvidence] = field(default_factory=list)
    calculations: List[CalculationTrace] = field(default_factory=list)
    context: Optional[ChatContextInfo] = None
    suggested_followups: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    used_context: bool = False
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = CHATBOT_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "session_id": self.session_id,
            "message_id": self.message_id,
            "answer": self.answer,
            "intent": self.intent.value,
            "classification": self.classification.value,
            "confidence": self.confidence.value,
            "evidence": [e.to_dict() for e in self.evidence],
            "calculations": [c.to_dict() for c in self.calculations],
            "context": self.context.to_dict() if self.context else None,
            "suggested_followups": self.suggested_followups,
            "warnings": self.warnings,
            "used_context": self.used_context,
            "generated_at": self.generated_at.isoformat(),
            "version": self.version,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_number(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
    except (TypeError, ValueError):
        return None
    import math

    if math.isnan(f) or math.isinf(f):
        return None
    return f
