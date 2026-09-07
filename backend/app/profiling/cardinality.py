"""Cardinality bucketing at the dataset level.

Per-column cardinality already lives on each `ColumnProfile.cardinality_class`.
This module produces the aggregate {low: [...], medium: [...], high: [...],
unique: [...]} breakdown for the dashboard.
"""

from __future__ import annotations

from typing import List

from app.profiling.types import (
    CardinalityBreakdown,
    CardinalityClass,
    ColumnProfile,
    SectionStatus,
)


def summarize_cardinality(profiles: List[ColumnProfile]) -> CardinalityBreakdown:
    if not profiles:
        return CardinalityBreakdown(
            status=SectionStatus.UNAVAILABLE,
            reason="No columns to analyze",
        )

    low: List[str] = []
    medium: List[str] = []
    high: List[str] = []
    unique: List[str] = []

    for c in profiles:
        bucket = c.cardinality_class
        if bucket == CardinalityClass.UNIQUE:
            unique.append(c.name)
        elif bucket == CardinalityClass.HIGH:
            high.append(c.name)
        elif bucket == CardinalityClass.MEDIUM:
            medium.append(c.name)
        else:
            low.append(c.name)

    return CardinalityBreakdown(
        status=SectionStatus.OK,
        low=low,
        medium=medium,
        high=high,
        unique=unique,
    )
