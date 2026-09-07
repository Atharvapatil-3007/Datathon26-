"""Phase 2 - Automatic Data Understanding.

Given a validated `DatasetObject` produced by Phase 1, the profiling engine
computes a structured `ProfilingResult` describing the dataset's schema,
statistics, distributions, outliers, correlations, and quality.

Phase 2 NEVER modifies the source dataset. It only reads.
"""

from app.profiling.types import (
    ColumnClass,
    ColumnProfile,
    CardinalityClass,
    CorrelationSummary,
    DuplicateSummary,
    MissingSummary,
    ProfilingResult,
    QualityScore,
)
from app.profiling.exceptions import ProfilingError

__all__ = [
    "ColumnClass",
    "ColumnProfile",
    "CardinalityClass",
    "CorrelationSummary",
    "DuplicateSummary",
    "MissingSummary",
    "ProfilingResult",
    "QualityScore",
    "ProfilingError",
]
