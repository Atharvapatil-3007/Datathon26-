"""ProfilingEngine — the Phase 2 orchestrator.

Given a Phase 1 `DatasetObject`, run every analyzer and stitch the results
into a single `ProfilingResult`. Every section is wrapped in try/except so
one failure never nukes the entire report — bad sections come back marked
`status: "unavailable"` with a human-readable reason.

Rules of engagement:
  * We never mutate the source DataFrame. We work off a copy produced by
    `normalization.normalize_missing`.
  * Timings are recorded end-to-end in ms.
  * Column ordering in the response matches the source dataframe column
    order — deterministic output makes the dashboard sortable.
"""

from __future__ import annotations

import time
from typing import List, Optional

import pandas as pd

from app.ingestion.dataset import DatasetObject, InferredType
from app.profiling import (
    cardinality as _card,
    correlations as _corr,
    distributions as _dist,
    duplicates as _dup,
    missing as _miss,
    outliers as _out,
    quality as _quality,
    statistics as _stats,
)
from app.profiling.normalization import normalize_missing
from app.profiling.type_detector import detect_column_type
from app.profiling.types import (
    ColumnClass,
    ColumnProfile,
    CorrelationSummary,
    CardinalityBreakdown,
    DatasetOverview,
    DuplicateSummary,
    MissingSummary,
    ProfilingResult,
    QualityScore,
    SectionStatus,
)
from app.utils.logging import get_logger


log = get_logger(__name__)


class ProfilingEngine:
    """Composes every analyzer into a single `ProfilingResult`."""

    def profile(self, dataset: DatasetObject) -> ProfilingResult:
        started = time.perf_counter()
        result = ProfilingResult(
            dataset_id=dataset.dataset_id,
            overview=DatasetOverview(rows=0, columns=0),
        )

        df = dataset.data
        if df is None or df.empty and df.shape[1] == 0:
            result.warnings.append("Dataset is empty; no profiling performed")
            result.profiling_time_ms = _elapsed_ms(started)
            result.summary_text = _summary_for_empty(dataset)
            return result

        # 1. Normalize missing tokens ONCE for the whole pipeline.
        working = normalize_missing(df)

        # 2. Per-column profiles.
        profiles = self._profile_columns(working)

        # 3. Dataset-level sections. Each is fault-isolated.
        missing = self._safe(_miss.analyze_missing, working, section="missing")
        id_columns = [p.name for p in profiles if p.column_class == ColumnClass.ID]
        duplicates = self._safe(
            _dup.analyze_duplicates,
            working,
            id_columns,
            section="duplicates",
        )
        cardinality_summary = self._safe(
            _card.summarize_cardinality, profiles, section="cardinality"
        )
        correlations = self._safe(
            _corr.analyze_correlations, working, profiles, section="correlations"
        )

        # 4. Quality — depends on everything above.
        quality = self._safe(
            _quality.score_dataset,
            working,
            profiles,
            missing,
            duplicates,
            section="quality",
        )
        # Apply per-column quality scores after the dataset-level score exists.
        for p in profiles:
            try:
                p.quality_score = _quality.score_column(p)
            except Exception as exc:  # noqa: BLE001
                log.warning("column_quality_failed", column=p.name, error=str(exc))
                p.quality_score = 0.0

        # 5. Assemble
        overview = self._build_overview(working, profiles, dataset)

        result.overview = overview
        result.column_profiles = profiles
        result.missing = missing or MissingSummary(status=SectionStatus.UNAVAILABLE, reason="missing analyzer failed")
        result.duplicates = duplicates or DuplicateSummary(status=SectionStatus.UNAVAILABLE, reason="duplicate analyzer failed")
        result.cardinality = cardinality_summary or CardinalityBreakdown(status=SectionStatus.UNAVAILABLE, reason="cardinality analyzer failed")
        result.correlations = correlations or CorrelationSummary(status=SectionStatus.UNAVAILABLE, reason="correlation analyzer failed")
        result.quality = quality or QualityScore()
        result.summary_text = _build_summary_text(dataset, overview, missing, duplicates, quality)
        result.profiling_time_ms = _elapsed_ms(started)

        log.info(
            "profile_completed",
            dataset_id=dataset.dataset_id,
            rows=overview.rows,
            columns=overview.columns,
            duration_ms=result.profiling_time_ms,
            quality=(quality.overall_score if quality else None),
        )
        return result

    # ------------------------------------------------------------------
    # Column-level
    # ------------------------------------------------------------------
    def _profile_columns(self, df: pd.DataFrame) -> List[ColumnProfile]:
        total = len(df)
        # Identify the first date / datetime column ONCE; every numerical
        # column will use it as its temporal anchor for `latest_value` (F-05).
        date_series = self._first_date_series(df)

        profiles: List[ColumnProfile] = []
        for i in range(df.shape[1]):
            name = str(df.columns[i])
            col = df.iloc[:, i]
            try:
                profile = self._profile_one(name, col, total, date_series=date_series)
            except Exception as exc:  # noqa: BLE001
                log.warning("column_profile_failed", column=name, error=str(exc))
                profile = _minimal_profile(name, col, total)
            profiles.append(profile)
        return profiles

    def _first_date_series(self, df: pd.DataFrame) -> Optional[pd.Series]:
        """Return the first column that looks date/datetime-shaped."""
        from pandas.api import types as ptypes

        for i in range(df.shape[1]):
            col = df.iloc[:, i]
            if ptypes.is_datetime64_any_dtype(col):
                return col
        # No native datetime dtype \u2014 try a lightweight sniff on object cols.
        for i in range(df.shape[1]):
            col = df.iloc[:, i]
            if not ptypes.is_object_dtype(col) and not ptypes.is_string_dtype(col):
                continue
            sample = col.dropna().head(20)
            if sample.empty:
                continue
            try:
                parsed = pd.to_datetime(sample, errors="coerce", format="mixed")
            except Exception:  # noqa: BLE001
                continue
            if parsed.notna().mean() >= 0.9:
                return pd.to_datetime(col, errors="coerce", format="mixed")
        return None

    def _profile_one(
        self,
        name: str,
        series: pd.Series,
        total_rows: int,
        *,
        date_series: Optional[pd.Series] = None,
    ) -> ColumnProfile:
        detection = detect_column_type(name, series)
        non_null = series.dropna()
        missing_count = int(total_rows - len(non_null))
        missing_ratio = float(missing_count / total_rows) if total_rows else 0.0

        # Sample + mode
        sample_values = [_json_safe(v) for v in non_null.head(5).tolist()]
        mode_value = None
        mode_count = 0
        if not non_null.empty:
            counts = non_null.value_counts()
            mode_value = _json_safe(counts.index[0])
            mode_count = int(counts.iloc[0])

        # Type-specific stats + distribution + outliers
        stats_payload: dict = {}
        dist_payload: dict = {}
        outliers_payload = None
        top_values: list = []

        cls = detection.column_class
        if cls == ColumnClass.NUMERICAL:
            stats_payload = _stats.numerical_stats(series, date_series=date_series)
            dist_payload = _dist.numerical_distribution(series)
            outliers_payload = _out.detect_outliers(series)
        elif cls == ColumnClass.CATEGORICAL:
            stats_payload = _stats.categorical_stats(series)
            dist = _dist.categorical_distribution(series)
            dist_payload = dist
            top_values = dist["top_values"]
        elif cls == ColumnClass.TEXT:
            stats_payload = _stats.text_stats(series)
            top_values = _dist.top_values(series, k=5)  # short list for text
        elif cls in (ColumnClass.DATE, ColumnClass.DATETIME):
            stats_payload = _stats.datetime_stats(series)
        elif cls == ColumnClass.BOOLEAN:
            stats_payload = _stats.boolean_stats(series)
            top_values = _dist.top_values(series, k=2)
        elif cls == ColumnClass.ID:
            stats_payload = _stats.id_stats(series)

        return ColumnProfile(
            name=name,
            dtype=str(series.dtype),
            column_class=cls,
            inferred_type=detection.inferred_type,
            total=int(total_rows),
            non_null=int(len(non_null)),
            missing_count=missing_count,
            missing_ratio=round(missing_ratio, 6),
            unique_count=detection.unique_count,
            unique_ratio=round(detection.unique_ratio, 6),
            cardinality_class=detection.cardinality_class,
            sample_values=sample_values,
            most_frequent_value=mode_value,
            most_frequent_count=mode_count,
            statistics=stats_payload,
            distribution=dist_payload,
            outliers=outliers_payload,
            top_values=top_values,
        )

    # ------------------------------------------------------------------
    # Overview
    # ------------------------------------------------------------------
    def _build_overview(
        self,
        df: pd.DataFrame,
        profiles: List[ColumnProfile],
        dataset: DatasetObject,
    ) -> DatasetOverview:
        counts = {c: 0 for c in ColumnClass}
        for p in profiles:
            counts[p.column_class] += 1

        size_bytes = None
        try:
            size_bytes = int(df.memory_usage(deep=True).sum())
        except Exception:  # noqa: BLE001
            size_bytes = None

        return DatasetOverview(
            rows=int(len(df)),
            columns=int(df.shape[1]),
            size_bytes=size_bytes,
            numerical_columns=counts[ColumnClass.NUMERICAL],
            categorical_columns=counts[ColumnClass.CATEGORICAL],
            text_columns=counts[ColumnClass.TEXT],
            date_columns=counts[ColumnClass.DATE],
            datetime_columns=counts[ColumnClass.DATETIME],
            id_columns=counts[ColumnClass.ID],
            boolean_columns=counts[ColumnClass.BOOLEAN],
            unknown_columns=counts[ColumnClass.UNKNOWN],
        )

    # ------------------------------------------------------------------
    # Fault isolation
    # ------------------------------------------------------------------
    def _safe(self, fn, *args, section: str, **kwargs):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001
            log.warning("phase2_section_failed", section=section, error=str(exc))
            return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _summary_for_empty(dataset: DatasetObject) -> str:
    return (
        f"Dataset '{dataset.source_name}' contains no rows or columns; "
        "profiling produced no analytical results."
    )


def _build_summary_text(
    dataset: DatasetObject,
    overview: DatasetOverview,
    missing: Optional[MissingSummary],
    duplicates: Optional[DuplicateSummary],
    quality: Optional[QualityScore],
) -> str:
    parts: List[str] = []

    parts.append(
        f"Dataset '{dataset.source_name}' contains {overview.rows:,} rows and "
        f"{overview.columns} columns."
    )

    class_parts: List[str] = []
    for label, count in (
        ("numerical", overview.numerical_columns),
        ("categorical", overview.categorical_columns),
        ("text", overview.text_columns),
        ("date", overview.date_columns + overview.datetime_columns),
        ("boolean", overview.boolean_columns),
        ("identifier", overview.id_columns),
    ):
        if count > 0:
            class_parts.append(f"{count} {label}")
    if class_parts:
        parts.append(f"Detected: {', '.join(class_parts)}.")

    if missing and missing.status == SectionStatus.OK:
        parts.append(
            f"{round(missing.missing_ratio * 100, 2)}% of values are missing"
            f" across {missing.columns_with_missing} column(s)."
        )
    if duplicates and duplicates.status == SectionStatus.OK:
        parts.append(
            f"{duplicates.duplicate_rows} duplicate row(s) detected"
            f" ({round(duplicates.duplicate_ratio * 100, 2)}%)."
        )
    if quality:
        parts.append(
            f"Overall data quality score: {round(quality.overall_score, 1)}/100 (grade {quality.grade.value})."
        )
    return " ".join(parts)


def _json_safe(v):
    """Small local copy — avoids depending on any single analyzer."""
    import math

    import numpy as np

    if v is None:
        return None
    if isinstance(v, (str, bool, int)):
        return v
    if isinstance(v, float):
        return None if (math.isnan(v) or math.isinf(v)) else v
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    if isinstance(v, (np.bool_,)):
        return bool(v)
    if isinstance(v, pd.Timestamp):
        return v.isoformat()
    return str(v)


def _minimal_profile(name: str, series: pd.Series, total: int) -> ColumnProfile:
    return ColumnProfile(
        name=name,
        dtype=str(series.dtype),
        column_class=ColumnClass.UNKNOWN,
        inferred_type=InferredType.UNKNOWN,
        total=int(total),
        non_null=int(len(series.dropna())),
        missing_count=int(total - len(series.dropna())),
        missing_ratio=0.0,
        unique_count=0,
        unique_ratio=0.0,
        cardinality_class=_card.CardinalityClass.LOW,
    )


# ---------------------------------------------------------------------------
# Singleton accessor
# ---------------------------------------------------------------------------
_engine: Optional[ProfilingEngine] = None


def get_profiling_engine() -> ProfilingEngine:
    global _engine
    if _engine is None:
        _engine = ProfilingEngine()
    return _engine


def reset_profiling_engine_for_tests() -> None:
    global _engine
    _engine = None
