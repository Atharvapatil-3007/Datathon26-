"""Phase 3 - Financial Intelligence.

Three analysis modes take Phase 2 profiles as input and produce
decision-oriented financial intelligence:

* ``SELF_ANALYSIS`` \u2014 single-company financial health / KPIs / trends
* ``MERGER_PARTNERSHIP_ANALYSIS`` \u2014 two-company combined scenario + synergies
* ``COMPETITOR_MARKET_BENCHMARK`` \u2014 gap analysis vs competitor / market

Every numeric value is labeled REPORTED / CALCULATED / ESTIMATED / SCENARIO /
UNAVAILABLE so the frontend can be honest about what came from data and what
is a model output.
"""

from app.analysis.types import (
    AnalysisMode,
    AnalysisResult,
    ComparisonRow,
    CombinedScenario,
    EntitySnapshot,
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
    RiskItem,
    SynergyItem,
)
from app.analysis.exceptions import (
    AnalysisError,
    AnalysisNotSupportedError,
    IncompatibleDatasetsError,
    InsufficientDataError,
)

__all__ = [
    # types
    "AnalysisMode",
    "AnalysisResult",
    "ComparisonRow",
    "CombinedScenario",
    "EntitySnapshot",
    "GapItem",
    "HealthScore",
    "Insight",
    "InsightKind",
    "LabeledMetric",
    "MetricDirection",
    "MetricId",
    "MetricStatus",
    "MetricUnit",
    "Priority",
    "RiskItem",
    "SynergyItem",
    # exceptions
    "AnalysisError",
    "AnalysisNotSupportedError",
    "IncompatibleDatasetsError",
    "InsufficientDataError",
]
