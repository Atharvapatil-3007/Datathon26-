"""Thin dispatcher that turns an ``AnalysisMode`` into an ``AnalysisResult``.

Keeps the API layer skinny: routes just receive a payload, forward it here,
and return ``result.to_dict()``.
"""

from __future__ import annotations

from typing import Optional

from app.analysis.benchmark_analyzer import run_benchmark_analysis
from app.analysis.exceptions import AnalysisNotSupportedError
from app.analysis.merger_analyzer import run_merger_analysis
from app.analysis.self_analyzer import run_self_analysis
from app.analysis.types import AnalysisMode, AnalysisResult


def run_self(dataset_id: str, display_name: Optional[str] = None) -> AnalysisResult:
    return run_self_analysis(dataset_id, display_name=display_name)


def run_merger(
    primary_dataset_id: str,
    secondary_dataset_id: str,
    *,
    deal_type: Optional[str] = None,
    primary_display_name: Optional[str] = None,
    secondary_display_name: Optional[str] = None,
) -> AnalysisResult:
    return run_merger_analysis(
        primary_dataset_id,
        secondary_dataset_id,
        deal_type=deal_type,
        primary_display_name=primary_display_name,
        secondary_display_name=secondary_display_name,
    )


def run_benchmark(
    primary_dataset_id: str,
    competitor_dataset_id: str,
    *,
    market_dataset_id: Optional[str] = None,
    primary_display_name: Optional[str] = None,
    competitor_display_name: Optional[str] = None,
    market_display_name: Optional[str] = None,
) -> AnalysisResult:
    return run_benchmark_analysis(
        primary_dataset_id,
        competitor_dataset_id,
        market_dataset_id=market_dataset_id,
        primary_display_name=primary_display_name,
        competitor_display_name=competitor_display_name,
        market_display_name=market_display_name,
    )


def describe_modes() -> list[dict]:
    """Metadata for the frontend "what do you want to analyze?" picker."""
    return [
        {
            "mode": AnalysisMode.SELF_ANALYSIS.value,
            "title": "Self Financial Analysis",
            "description": (
                "Understand your company's financial health, performance, "
                "risks, and opportunities."
            ),
            "requires": ["dataset_id"],
        },
        {
            "mode": AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS.value,
            "title": "Merger / Partnership Analysis",
            "description": (
                "Analyze the potential financial impact of combining with "
                "another company."
            ),
            "requires": ["primary_dataset_id", "secondary_dataset_id"],
        },
        {
            "mode": AnalysisMode.COMPETITOR_MARKET_BENCHMARK.value,
            "title": "Competitor & Market Benchmarking",
            "description": (
                "Compare your performance with competitors and market benchmarks "
                "and identify improvement gaps."
            ),
            "requires": ["primary_dataset_id", "competitor_dataset_id"],
        },
    ]


def run_by_mode(mode: str, payload: dict) -> AnalysisResult:
    """Generic dispatcher \u2014 useful for tests. Not used by the API."""
    try:
        enum_mode = AnalysisMode(mode)
    except ValueError as exc:
        raise AnalysisNotSupportedError(f"Unknown analysis mode: {mode}") from exc

    if enum_mode == AnalysisMode.SELF_ANALYSIS:
        return run_self(payload["dataset_id"], payload.get("display_name"))
    if enum_mode == AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS:
        return run_merger(
            payload["primary_dataset_id"],
            payload["secondary_dataset_id"],
            deal_type=payload.get("deal_type"),
            primary_display_name=payload.get("primary_display_name"),
            secondary_display_name=payload.get("secondary_display_name"),
        )
    if enum_mode == AnalysisMode.COMPETITOR_MARKET_BENCHMARK:
        return run_benchmark(
            payload["primary_dataset_id"],
            payload["competitor_dataset_id"],
            market_dataset_id=payload.get("market_dataset_id"),
            primary_display_name=payload.get("primary_display_name"),
            competitor_display_name=payload.get("competitor_display_name"),
            market_display_name=payload.get("market_display_name"),
        )
    raise AnalysisNotSupportedError(f"Unsupported mode: {mode}")  # pragma: no cover
