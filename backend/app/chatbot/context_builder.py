"""ChatContext builder.

We pull every piece of analytical evidence the chatbot could possibly need
before touching the query engine, and cache it per
(mode, primary_id, secondary_id, market_id). That way a follow-up question
in the same session doesn't re-run profiling, extraction, or analysis.

We deliberately reuse the existing Phase 3 building blocks:
  * ``dataset_loader.load_dataset_bundle`` — reads Supabase row + optional
    DataFrame from storage
  * ``metric_extractor.extract_metrics`` — canonical metrics from a profile
  * ``ratio_engine.compute_ratios`` — derived ratios from a value map
  * ``trend_analyzer.analyze_trends`` — period-series growth
  * ``run_self_analysis / run_merger_analysis / run_benchmark_analysis`` —
    the assembled AnalysisResult with health / insights / gaps / risks
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import pandas as pd

from app.analysis.benchmark_analyzer import run_benchmark_analysis
from app.analysis.dataset_loader import load_dataset_bundle
from app.analysis.merger_analyzer import run_merger_analysis
from app.analysis.metric_extractor import ExtractionResult, extract_metrics
from app.analysis.ratio_engine import compute_ratios
from app.analysis.self_analyzer import run_self_analysis
from app.analysis.trend_analyzer import TrendResult, analyze_trends
from app.analysis.types import (
    AnalysisMode,
    AnalysisResult,
    LabeledMetric,
    MetricId,
)
from app.chatbot.exceptions import ChatbotError
from app.utils.logging import get_logger


log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_CACHE_TTL_SECONDS = 15 * 60


@dataclass
class _CacheEntry:
    context: "ChatContext"
    expires_at: float


class _ContextCache:
    def __init__(self) -> None:
        self._entries: Dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional["ChatContext"]:
        with self._lock:
            entry = self._entries.get(key)
            if not entry:
                return None
            if entry.expires_at < time.time():
                self._entries.pop(key, None)
                return None
            return entry.context

    def set(self, key: str, ctx: "ChatContext") -> None:
        with self._lock:
            self._entries[key] = _CacheEntry(
                context=ctx, expires_at=time.time() + _CACHE_TTL_SECONDS
            )

    def invalidate(self, dataset_id: str) -> None:
        """Drop any cache entry that references ``dataset_id``."""
        with self._lock:
            for key in list(self._entries):
                if dataset_id in key:
                    self._entries.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_cache = _ContextCache()


def clear_context_cache() -> None:
    """Test helper to reset the cache between runs."""
    _cache.clear()


# ---------------------------------------------------------------------------
# ChatContext
# ---------------------------------------------------------------------------
@dataclass
class EntityContext:
    """One dataset's analytical view, minus the ``AnalysisResult`` wrapper."""

    dataset_id: str
    display_name: str
    profile: Dict[str, Any] = field(default_factory=dict)
    extraction: Optional[ExtractionResult] = None
    ratios: List[LabeledMetric] = field(default_factory=list)
    trends: Dict[MetricId, TrendResult] = field(default_factory=dict)
    df: Optional[pd.DataFrame] = None
    date_column: Optional[str] = None
    row: Dict[str, Any] = field(default_factory=dict)

    def has_data(self) -> bool:
        return bool(self.extraction and self.extraction.metrics)


@dataclass
class ChatContext:
    """Everything the query engine needs to answer a question.

    Fields not applicable to the current mode are simply ``None``.
    """

    analysis_mode: AnalysisMode
    primary: EntityContext
    secondary: Optional[EntityContext] = None
    market: Optional[EntityContext] = None
    analysis_result: Optional[AnalysisResult] = None      # cached full Phase 3 output
    warnings: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Public builders
# ---------------------------------------------------------------------------
def build_context(
    *,
    analysis_mode: str,
    dataset_id: str,
    secondary_dataset_id: Optional[str] = None,
    market_dataset_id: Optional[str] = None,
    primary_display_name: Optional[str] = None,
    secondary_display_name: Optional[str] = None,
    market_display_name: Optional[str] = None,
    force_refresh: bool = False,
) -> ChatContext:
    """Return a ``ChatContext`` for the requested (mode, dataset) combination.

    Uses an in-process cache. Set ``force_refresh=True`` to bust it.
    """
    mode = _normalise_mode(analysis_mode)
    key = _cache_key(mode, dataset_id, secondary_dataset_id, market_dataset_id)
    if not force_refresh:
        cached = _cache.get(key)
        if cached:
            log.info("chatbot_context_cache_hit", key=key)
            return cached

    log.info(
        "chatbot_context_build",
        mode=mode.value,
        primary=dataset_id,
        secondary=secondary_dataset_id,
        market=market_dataset_id,
    )

    primary_entity = _build_entity_context(dataset_id, primary_display_name)
    secondary_entity: Optional[EntityContext] = None
    market_entity: Optional[EntityContext] = None
    analysis_result: Optional[AnalysisResult] = None
    warnings: List[str] = []

    if mode == AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS:
        if not secondary_dataset_id:
            raise ChatbotError(
                "Merger mode requires a secondary dataset. Provide "
                "'secondary_dataset_id'.",
                code="MISSING_SECONDARY_DATASET",
            )
        secondary_entity = _build_entity_context(secondary_dataset_id, secondary_display_name)
        try:
            analysis_result = run_merger_analysis(
                dataset_id,
                secondary_dataset_id,
                primary_display_name=primary_display_name or primary_entity.display_name,
                secondary_display_name=secondary_display_name or secondary_entity.display_name,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("chatbot_merger_analysis_failed_soft", error=str(exc))
            warnings.append(f"Merger analysis could not be assembled: {exc}")

    elif mode == AnalysisMode.COMPETITOR_MARKET_BENCHMARK:
        if not secondary_dataset_id:
            raise ChatbotError(
                "Competitor benchmark mode requires a competitor dataset. "
                "Provide 'secondary_dataset_id'.",
                code="MISSING_COMPETITOR_DATASET",
            )
        secondary_entity = _build_entity_context(secondary_dataset_id, secondary_display_name)
        if market_dataset_id:
            market_entity = _build_entity_context(market_dataset_id, market_display_name)
        try:
            analysis_result = run_benchmark_analysis(
                dataset_id,
                secondary_dataset_id,
                market_dataset_id=market_dataset_id,
                primary_display_name=primary_display_name or primary_entity.display_name,
                competitor_display_name=secondary_display_name or secondary_entity.display_name,
                market_display_name=market_display_name
                or (market_entity.display_name if market_entity else None),
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("chatbot_benchmark_analysis_failed_soft", error=str(exc))
            warnings.append(f"Benchmark analysis could not be assembled: {exc}")

    else:
        # Self analysis
        try:
            analysis_result = run_self_analysis(
                dataset_id,
                display_name=primary_display_name or primary_entity.display_name,
            )
        except Exception as exc:  # noqa: BLE001
            log.warning("chatbot_self_analysis_failed_soft", error=str(exc))
            warnings.append(f"Self analysis could not be assembled: {exc}")

    ctx = ChatContext(
        analysis_mode=mode,
        primary=primary_entity,
        secondary=secondary_entity,
        market=market_entity,
        analysis_result=analysis_result,
        warnings=warnings,
    )
    _cache.set(key, ctx)
    return ctx


# ---------------------------------------------------------------------------
# Per-entity build
# ---------------------------------------------------------------------------
def _build_entity_context(
    dataset_id: str, display_name: Optional[str] = None
) -> EntityContext:
    row, df = load_dataset_bundle(dataset_id)
    profile = row.get("profile") or {}
    label = display_name or row.get("original_filename") or dataset_id

    extraction = extract_metrics(profile, df=df)
    ratios = compute_ratios(extraction.value_map) if extraction.value_map else []

    date_column = _find_date_column(profile)
    numerical_names = _numerical_column_names(profile)
    trends: Dict[MetricId, TrendResult] = {}
    if df is not None and date_column:
        try:
            trends = analyze_trends(df, date_column, numerical_names)
        except Exception as exc:  # noqa: BLE001
            log.warning("chatbot_trend_soft_failure", dataset_id=dataset_id, error=str(exc))

    return EntityContext(
        dataset_id=dataset_id,
        display_name=label,
        profile=profile,
        extraction=extraction,
        ratios=ratios,
        trends=trends,
        df=df,
        date_column=date_column,
        row=row,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _find_date_column(profile: Dict[str, Any]) -> Optional[str]:
    for c in profile.get("column_profiles") or []:
        if c.get("column_class") in ("date", "datetime"):
            return c.get("name")
    return None


def _numerical_column_names(profile: Dict[str, Any]) -> List[str]:
    return [
        c.get("name")
        for c in profile.get("column_profiles") or []
        if c.get("column_class") == "numerical" and c.get("name")
    ]


def _cache_key(
    mode: AnalysisMode,
    primary: str,
    secondary: Optional[str],
    market: Optional[str],
) -> str:
    return f"{mode.value}|{primary}|{secondary or ''}|{market or ''}"


def _normalise_mode(value: Optional[str]) -> AnalysisMode:
    if value is None:
        return AnalysisMode.SELF_ANALYSIS
    if isinstance(value, AnalysisMode):
        return value
    try:
        return AnalysisMode(value)
    except ValueError:
        raise ChatbotError(
            f"Unknown analysis mode: {value}",
            code="UNKNOWN_ANALYSIS_MODE",
        )
