"""Shared types for the Phase 3 financial intelligence layer.

Design goals:
  * Every numeric surfaces to the client with a *status* label
    (REPORTED / CALCULATED / ESTIMATED / SCENARIO / UNAVAILABLE) so the UI
    can be truthful about provenance.
  * One ``AnalysisResult`` shape covers all three modes; per-mode fields
    are optional. Mirrors the spec's ``result contract``.
  * All dataclasses have a ``to_dict`` that returns JSON-safe primitives.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

PHASE3_VERSION = "3.0"


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------
class AnalysisMode(str, Enum):
    SELF_ANALYSIS = "self_analysis"
    MERGER_PARTNERSHIP_ANALYSIS = "merger_partnership_analysis"
    COMPETITOR_MARKET_BENCHMARK = "competitor_market_benchmark"


class MetricStatus(str, Enum):
    REPORTED = "reported"      # value came directly from a column
    CALCULATED = "calculated"  # derived from other reported values
    ESTIMATED = "estimated"    # rough approximation with assumptions
    SCENARIO = "scenario"      # combined / hypothetical figure
    UNAVAILABLE = "unavailable"


class MetricUnit(str, Enum):
    CURRENCY = "currency"
    PERCENT = "percent"
    RATIO = "ratio"
    COUNT = "count"
    DAYS = "days"
    UNKNOWN = "unknown"


class MetricDirection(str, Enum):
    """When comparing to a benchmark, which direction is 'good'?"""

    HIGHER_BETTER = "higher_better"
    LOWER_BETTER = "lower_better"
    NEUTRAL = "neutral"


class Priority(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class InsightKind(str, Enum):
    OBSERVATION = "observation"      # raw data statement
    ANALYSIS = "analysis"            # what the numbers imply
    RECOMMENDATION = "recommendation"  # what could be investigated / improved


# ---------------------------------------------------------------------------
# MetricId
# ---------------------------------------------------------------------------
class MetricId(str, Enum):
    """Canonical financial metric identifiers.

    The metric registry (``metric_registry.py``) maps user column names
    (via aliases + regex) into these values, so downstream analyzers only
    ever talk about canonical ids.
    """

    # ----- Income statement -----
    REVENUE = "revenue"
    COGS = "cogs"
    GROSS_PROFIT = "gross_profit"
    OPERATING_EXPENSES = "operating_expenses"
    EXPENSES_TOTAL = "expenses_total"
    OPERATING_PROFIT = "operating_profit"
    EBITDA = "ebitda"
    EBIT = "ebit"
    INTEREST_EXPENSE = "interest_expense"
    INTEREST_INCOME = "interest_income"
    TAX = "tax"
    NET_PROFIT = "net_profit"

    # ----- Balance sheet -----
    ASSETS = "assets"
    CURRENT_ASSETS = "current_assets"
    NON_CURRENT_ASSETS = "non_current_assets"
    CASH = "cash"
    INVENTORY = "inventory"
    RECEIVABLES = "receivables"
    LIABILITIES = "liabilities"
    CURRENT_LIABILITIES = "current_liabilities"
    DEBT = "debt"
    EQUITY = "equity"
    WORKING_CAPITAL = "working_capital"

    # ----- Cash flow -----
    CASH_FLOW_OPERATIONS = "cash_flow_operations"
    FREE_CASH_FLOW = "free_cash_flow"
    CAPEX = "capex"

    # ----- Business -----
    CUSTOMERS = "customers"
    TRANSACTIONS = "transactions"
    ORDERS = "orders"
    EMPLOYEES = "employees"

    # ----- Banking-specific -----
    DEPOSITS = "deposits"
    CASA = "casa"
    LOANS = "loans"
    NET_INTEREST_INCOME = "net_interest_income"
    NON_INTEREST_INCOME = "non_interest_income"
    GROSS_NPA = "gross_npa"
    NET_NPA = "net_npa"
    PROVISIONS = "provisions"
    CAPITAL_ADEQUACY = "capital_adequacy"

    # ----- Derived ratios -----
    GROSS_MARGIN = "gross_margin"
    OPERATING_MARGIN = "operating_margin"
    NET_MARGIN = "net_margin"
    ROA = "roa"
    ROE = "roe"
    DEBT_TO_EQUITY = "debt_to_equity"
    CURRENT_RATIO = "current_ratio"
    QUICK_RATIO = "quick_ratio"
    ASSET_TURNOVER = "asset_turnover"
    RECEIVABLES_TURNOVER = "receivables_turnover"
    INVENTORY_TURNOVER = "inventory_turnover"
    INTEREST_COVERAGE = "interest_coverage"
    FCF_MARGIN = "fcf_margin"
    COST_TO_INCOME = "cost_to_income"
    NIM = "nim"
    CREDIT_DEPOSIT_RATIO = "credit_deposit_ratio"
    PROVISION_COVERAGE = "provision_coverage"
    CASA_RATIO = "casa_ratio"


# ---------------------------------------------------------------------------
# Small data classes
# ---------------------------------------------------------------------------
@dataclass
class LabeledMetric:
    """A single metric with full provenance metadata."""

    metric_id: MetricId
    display_name: str
    value: Optional[float]
    unit: MetricUnit
    status: MetricStatus
    direction: MetricDirection = MetricDirection.NEUTRAL
    source_columns: List[str] = field(default_factory=list)
    confidence: float = 1.0
    period_series: Optional[Dict[str, float]] = None  # e.g. {"2024-Q1": 100, ...}
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id.value,
            "display_name": self.display_name,
            "value": _safe_number(self.value),
            "unit": self.unit.value,
            "status": self.status.value,
            "direction": self.direction.value,
            "source_columns": self.source_columns,
            "confidence": round(self.confidence, 4),
            "period_series": self.period_series,
            "notes": self.notes,
        }


@dataclass
class EntitySnapshot:
    """A company / dataset boiled down to labelled metrics."""

    entity_id: str                       # dataset_id
    display_name: str                    # dataset filename or user-provided
    metrics: List[LabeledMetric] = field(default_factory=list)
    period_start: Optional[str] = None
    period_end: Optional[str] = None
    unit_hint: Optional[str] = None      # 'currency' / user-declared
    entity_type: Optional[str] = None    # e.g. "bank", "corporate" — future
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "display_name": self.display_name,
            "metrics": [m.to_dict() for m in self.metrics],
            "period_start": self.period_start,
            "period_end": self.period_end,
            "unit_hint": self.unit_hint,
            "entity_type": self.entity_type,
            "notes": self.notes,
        }


@dataclass
class HealthScore:
    overall_score: float
    grade: str  # A / B / C / D / F
    dimensions: Dict[str, float] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": round(self.overall_score, 2),
            "grade": self.grade,
            "dimensions": {k: round(v, 2) for k, v in self.dimensions.items()},
            "notes": self.notes,
        }


@dataclass
class ComparisonRow:
    """Row of a benchmark-style comparison table."""

    metric_id: MetricId
    display_name: str
    unit: MetricUnit
    direction: MetricDirection
    primary_value: Optional[float]
    secondary_value: Optional[float]
    market_value: Optional[float] = None
    absolute_gap: Optional[float] = None       # primary - secondary
    percentage_gap: Optional[float] = None     # relative to secondary
    status: str = "ok"                         # 'ok' | 'ahead' | 'behind' | 'na'

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id.value,
            "display_name": self.display_name,
            "unit": self.unit.value,
            "direction": self.direction.value,
            "primary_value": _safe_number(self.primary_value),
            "secondary_value": _safe_number(self.secondary_value),
            "market_value": _safe_number(self.market_value),
            "absolute_gap": _safe_number(self.absolute_gap),
            "percentage_gap": _safe_number(self.percentage_gap),
            "status": self.status,
        }


@dataclass
class GapItem:
    """One row of gap analysis with target + priority classification."""

    metric_id: MetricId
    display_name: str
    unit: MetricUnit
    current_value: Optional[float]
    benchmark_value: Optional[float]
    absolute_gap: Optional[float]
    percentage_gap: Optional[float]
    near_term_target: Optional[float]      # midway
    long_term_target: Optional[float]      # match benchmark
    priority: Priority
    importance: str                        # 'high' / 'medium' / 'low' — subjective ranking
    required_improvement: Optional[str] = None
    direction: MetricDirection = MetricDirection.HIGHER_BETTER

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id.value,
            "display_name": self.display_name,
            "unit": self.unit.value,
            "current_value": _safe_number(self.current_value),
            "benchmark_value": _safe_number(self.benchmark_value),
            "absolute_gap": _safe_number(self.absolute_gap),
            "percentage_gap": _safe_number(self.percentage_gap),
            "near_term_target": _safe_number(self.near_term_target),
            "long_term_target": _safe_number(self.long_term_target),
            "priority": self.priority.value,
            "importance": self.importance,
            "required_improvement": self.required_improvement,
            "direction": self.direction.value,
        }


@dataclass
class CombinedScenario:
    """Merger-mode combined view. All values labelled SCENARIO."""

    metrics: List[LabeledMetric] = field(default_factory=list)
    label: str = "Combined Scenario \u2014 Not a Forecast"
    caveats: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "metrics": [m.to_dict() for m in self.metrics],
            "caveats": self.caveats,
        }


@dataclass
class SynergyItem:
    kind: str          # "revenue" | "cost"
    title: str
    description: str
    magnitude_hint: Optional[str] = None  # "insufficient_data" / "small" / "material"
    supporting_metrics: List[str] = field(default_factory=list)  # metric_ids as strings

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "title": self.title,
            "description": self.description,
            "magnitude_hint": self.magnitude_hint,
            "supporting_metrics": self.supporting_metrics,
        }


@dataclass
class RiskItem:
    severity: Priority
    title: str
    description: str
    supporting_metrics: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "supporting_metrics": self.supporting_metrics,
        }


@dataclass
class Insight:
    kind: InsightKind
    text: str
    related_metrics: List[str] = field(default_factory=list)
    priority: Priority = Priority.MEDIUM

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind.value,
            "text": self.text,
            "related_metrics": self.related_metrics,
            "priority": self.priority.value,
        }


@dataclass
class Confidence:
    """How much can we trust this analysis result?"""

    overall: float                       # 0.0 - 1.0
    metric_coverage: float               # fraction of expected metrics we found
    period_coverage: Optional[float] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall": round(self.overall, 4),
            "metric_coverage": round(self.metric_coverage, 4),
            "period_coverage": None
                if self.period_coverage is None
                else round(self.period_coverage, 4),
            "notes": self.notes,
        }


# ---------------------------------------------------------------------------
# Top-level result
# ---------------------------------------------------------------------------
@dataclass
class AnalysisResult:
    """Single response contract for all three analysis modes.

    Only fields relevant to the selected ``mode`` are populated; the rest
    stay empty. Matches the ``result contract`` in the spec.
    """

    mode: AnalysisMode
    primary_entity: Optional[EntitySnapshot] = None
    secondary_entity: Optional[EntitySnapshot] = None
    market_entity: Optional[EntitySnapshot] = None
    financial_health: Optional[HealthScore] = None
    combined_scenario: Optional[CombinedScenario] = None

    metrics: List[LabeledMetric] = field(default_factory=list)      # convenience: primary metrics
    ratios: List[LabeledMetric] = field(default_factory=list)
    comparisons: List[ComparisonRow] = field(default_factory=list)
    gaps: List[GapItem] = field(default_factory=list)
    synergies: List[SynergyItem] = field(default_factory=list)
    risks: List[RiskItem] = field(default_factory=list)

    strengths: List[str] = field(default_factory=list)
    weaknesses: List[str] = field(default_factory=list)
    opportunities: List[str] = field(default_factory=list)

    insights: List[Insight] = field(default_factory=list)
    recommendations: List[Insight] = field(default_factory=list)

    summary_text: str = ""
    warnings: List[str] = field(default_factory=list)
    confidence: Optional[Confidence] = None
    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    version: str = PHASE3_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode.value,
            "primary_entity": self.primary_entity.to_dict() if self.primary_entity else None,
            "secondary_entity": self.secondary_entity.to_dict() if self.secondary_entity else None,
            "market_entity": self.market_entity.to_dict() if self.market_entity else None,
            "financial_health": self.financial_health.to_dict() if self.financial_health else None,
            "combined_scenario": self.combined_scenario.to_dict() if self.combined_scenario else None,
            "metrics": [m.to_dict() for m in self.metrics],
            "ratios": [r.to_dict() for r in self.ratios],
            "comparisons": [c.to_dict() for c in self.comparisons],
            "gaps": [g.to_dict() for g in self.gaps],
            "synergies": [s.to_dict() for s in self.synergies],
            "risks": [r.to_dict() for r in self.risks],
            "strengths": self.strengths,
            "weaknesses": self.weaknesses,
            "opportunities": self.opportunities,
            "insights": [i.to_dict() for i in self.insights],
            "recommendations": [i.to_dict() for i in self.recommendations],
            "summary_text": self.summary_text,
            "warnings": self.warnings,
            "confidence": self.confidence.to_dict() if self.confidence else None,
            "metadata": {
                "version": self.version,
                "generated_at": self.generated_at.isoformat(),
            },
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_number(v: Any) -> Optional[float]:
    """Strip NaN / Inf so the payload stays JSON-safe."""
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
