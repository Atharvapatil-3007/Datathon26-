"""Data-quality scoring.

Four dimensions, each scored 0-100:

* **Completeness** — how much of the data is present.
* **Uniqueness** — how much of the data is not repeated where it shouldn't be.
* **Validity** — how many columns look genuinely typed vs unknown / mixed.
* **Consistency** — how uniform textual / categorical values look.

The overall score is a weighted average. Weights are configurable via
`QualityWeights` so we don't have to touch the module to tune them.

The scorer also produces a per-column `quality_score` on each
`ColumnProfile` — the caller applies that in `engine.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Tuple

import pandas as pd
from pandas.api import types as ptypes

from app.profiling.types import (
    ColumnClass,
    ColumnProfile,
    DuplicateSummary,
    MissingSummary,
    QualityGrade,
    QualityScore,
    SectionStatus,
)


# ---------------------------------------------------------------------------
# Tunable weights + column-level penalty knobs
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class QualityWeights:
    completeness: float = 0.35
    uniqueness: float = 0.20
    validity: float = 0.25
    consistency: float = 0.20

    def as_dict(self) -> Dict[str, float]:
        return {
            "completeness": self.completeness,
            "uniqueness": self.uniqueness,
            "validity": self.validity,
            "consistency": self.consistency,
        }


DEFAULT_WEIGHTS = QualityWeights()

# Column quality penalties (in percentage points, deducted from 100)
_MISSING_PENALTY_WEIGHT = 40.0
_OUTLIER_PENALTY_WEIGHT = 15.0
_DUPLICATE_ID_PENALTY_WEIGHT = 25.0
_UNKNOWN_TYPE_PENALTY = 25.0


# ---------------------------------------------------------------------------
# Public entrypoints
# ---------------------------------------------------------------------------
def score_dataset(
    df: pd.DataFrame,
    profiles: List[ColumnProfile],
    missing: MissingSummary,
    duplicates: DuplicateSummary,
    *,
    weights: QualityWeights = DEFAULT_WEIGHTS,
) -> QualityScore:
    """Compute dataset-wide quality score."""
    completeness = _completeness_score(missing)
    uniqueness = _uniqueness_score(duplicates, profiles)
    validity = _validity_score(profiles)
    consistency = _consistency_score(df, profiles)

    dims = {
        "completeness": completeness,
        "uniqueness": uniqueness,
        "validity": validity,
        "consistency": consistency,
    }

    overall = _weighted_average(dims, weights)
    notes = _generate_notes(dims, missing, duplicates, profiles)

    return QualityScore(
        overall_score=overall,
        grade=_grade_for(overall),
        dimensions=dims,
        notes=notes,
    )


def score_column(profile: ColumnProfile) -> float:
    """0-100 quality for a single column. Applied in engine.py."""
    score = 100.0
    score -= profile.missing_ratio * _MISSING_PENALTY_WEIGHT

    if profile.column_class == ColumnClass.NUMERICAL and profile.outliers:
        ratio = float(profile.outliers.get("ratio") or 0.0)
        score -= min(ratio, 0.5) * _OUTLIER_PENALTY_WEIGHT

    if profile.column_class == ColumnClass.ID:
        id_stats = profile.statistics or {}
        total = int(id_stats.get("count") or 0)
        duplicate = int(id_stats.get("duplicate_count") or 0)
        if total > 0:
            dup_ratio = duplicate / total
            score -= min(dup_ratio, 1.0) * _DUPLICATE_ID_PENALTY_WEIGHT

    if profile.column_class == ColumnClass.UNKNOWN:
        score -= _UNKNOWN_TYPE_PENALTY

    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# Dimension scorers
# ---------------------------------------------------------------------------
def _completeness_score(missing: MissingSummary) -> float:
    if missing.status != SectionStatus.OK or missing.total_cells == 0:
        return 100.0
    return max(0.0, 100.0 * (1.0 - missing.missing_ratio))


def _uniqueness_score(
    duplicates: DuplicateSummary,
    profiles: List[ColumnProfile],
) -> float:
    base = 100.0
    if duplicates.status == SectionStatus.OK:
        base -= duplicates.duplicate_ratio * 100.0

    # ID duplication penalty on top of row dupes.
    id_penalty = 0.0
    for report in duplicates.duplicate_ids or []:
        dup_rows = int(report.get("duplicate_row_count") or 0)
        matching_profile = next(
            (p for p in profiles if p.name == report.get("column")), None
        )
        if not matching_profile:
            continue
        total = matching_profile.non_null
        if total > 0 and dup_rows > 0:
            id_penalty += min(1.0, dup_rows / total) * 10.0  # up to 10 pts per ID column

    return max(0.0, base - id_penalty)


def _validity_score(profiles: List[ColumnProfile]) -> float:
    if not profiles:
        return 100.0
    unknown = sum(1 for p in profiles if p.column_class == ColumnClass.UNKNOWN)
    ratio = unknown / len(profiles)
    # A single unknown column already knocks off noticeable points; five+ unknown
    # columns bottom out the dimension.
    return max(0.0, 100.0 - ratio * 100.0)


def _consistency_score(df: pd.DataFrame, profiles: List[ColumnProfile]) -> float:
    """Consistency proxy: penalize text/categorical columns whose string values
    have leading/trailing whitespace or case-variant duplicates (e.g. 'UPI'
    vs 'upi'). Very fast — samples the first N unique values per column.
    """
    if not profiles or df.empty:
        return 100.0

    inconsistency_ratio_sum = 0.0
    considered = 0

    for p in profiles:
        if p.column_class not in (ColumnClass.CATEGORICAL, ColumnClass.TEXT):
            continue
        try:
            col = df[p.name]
        except KeyError:
            continue
        if isinstance(col, pd.DataFrame):
            col = col.iloc[:, 0]
        if not (ptypes.is_object_dtype(col) or ptypes.is_string_dtype(col)):
            continue
        considered += 1
        inconsistency_ratio_sum += _string_inconsistency_ratio(col)

    if considered == 0:
        return 100.0
    avg = inconsistency_ratio_sum / considered
    return max(0.0, 100.0 - avg * 100.0)


def _string_inconsistency_ratio(col: pd.Series) -> float:
    sample = col.dropna().astype(str).head(500)
    if sample.empty:
        return 0.0

    total = len(sample)
    stripped = sample.str.strip()

    # Leading/trailing whitespace.
    whitespace = int((stripped != sample).sum())

    # Case-variant duplicates: values that differ only by casing/whitespace.
    lowered = stripped.str.lower()
    duplicates_via_case = 0
    for group in lowered.unique():
        variants = stripped[lowered == group].unique()
        if len(variants) > 1:
            duplicates_via_case += int((lowered == group).sum()) - 1

    penalty = whitespace + duplicates_via_case
    return min(1.0, penalty / total)


def _weighted_average(dims: Dict[str, float], w: QualityWeights) -> float:
    total_w = w.completeness + w.uniqueness + w.validity + w.consistency
    if total_w == 0:
        return 0.0
    return (
        dims["completeness"] * w.completeness
        + dims["uniqueness"] * w.uniqueness
        + dims["validity"] * w.validity
        + dims["consistency"] * w.consistency
    ) / total_w


def _grade_for(score: float) -> QualityGrade:
    if score >= 90:
        return QualityGrade.A
    if score >= 80:
        return QualityGrade.B
    if score >= 70:
        return QualityGrade.C
    if score >= 60:
        return QualityGrade.D
    return QualityGrade.F


def _generate_notes(
    dims: Dict[str, float],
    missing: MissingSummary,
    duplicates: DuplicateSummary,
    profiles: List[ColumnProfile],
) -> List[str]:
    notes: List[str] = []
    if dims["completeness"] < 90 and missing.status == SectionStatus.OK:
        notes.append(
            f"{round(missing.missing_ratio * 100, 2)}% of cells are missing"
            f" across {missing.columns_with_missing} column(s)."
        )
    if dims["uniqueness"] < 95 and duplicates.status == SectionStatus.OK:
        notes.append(
            f"{duplicates.duplicate_rows} duplicate row(s) detected"
            f" ({round(duplicates.duplicate_ratio * 100, 2)}%)."
        )
    unknown_cols = [p.name for p in profiles if p.column_class == ColumnClass.UNKNOWN]
    if unknown_cols:
        notes.append(
            f"{len(unknown_cols)} column(s) could not be classified: "
            f"{', '.join(unknown_cols[:3])}"
            f"{'...' if len(unknown_cols) > 3 else ''}."
        )
    if dims["consistency"] < 90:
        notes.append(
            "Text/categorical columns contain whitespace or case-variant duplicates."
        )
    return notes
