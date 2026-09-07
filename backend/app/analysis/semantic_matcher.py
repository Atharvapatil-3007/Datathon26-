"""Semantic column matcher.

Wraps ``metric_registry.match_column`` with the extra logic needed when a
dataset has *multiple* candidate columns for the same metric (e.g. both
``sales`` and ``net_sales``). The matcher keeps the best column and marks
the rest as duplicates on the resulting ``LabeledMetric.notes``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from app.analysis.metric_registry import match_column
from app.analysis.types import MetricId


@dataclass(frozen=True)
class ColumnMatch:
    column: str
    metric_id: MetricId
    confidence: float


def match_columns(column_names: List[str]) -> Dict[MetricId, List[ColumnMatch]]:
    """For every column, find the best metric candidate.

    Returns ``{metric_id: [ColumnMatch, ...]}``. Each list is sorted by
    descending confidence so the caller can pick the top one and treat the
    rest as ambiguous duplicates.
    """
    grouped: Dict[MetricId, List[ColumnMatch]] = {}
    for name in column_names:
        result = match_column(name)
        if not result:
            continue
        metric_id, confidence = result
        grouped.setdefault(metric_id, []).append(
            ColumnMatch(column=name, metric_id=metric_id, confidence=confidence)
        )

    for metric_id, matches in grouped.items():
        matches.sort(key=lambda m: m.confidence, reverse=True)
    return grouped


def pick_best(match_groups: Dict[MetricId, List[ColumnMatch]]) -> Dict[MetricId, ColumnMatch]:
    """Reduce each metric to its single best-matching column."""
    return {mid: matches[0] for mid, matches in match_groups.items() if matches}


def matched_summary(match_groups: Dict[MetricId, List[ColumnMatch]]) -> List[Dict[str, Any]]:
    """Debug-friendly summary for the API response / logs."""
    out: List[Dict[str, Any]] = []
    for mid, matches in match_groups.items():
        out.append(
            {
                "metric_id": mid.value,
                "picked": matches[0].column,
                "picked_confidence": matches[0].confidence,
                "other_candidates": [m.column for m in matches[1:]],
            }
        )
    return out
