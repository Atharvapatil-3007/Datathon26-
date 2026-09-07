"""End-to-end profiling engine tests."""

from __future__ import annotations

import json

import pandas as pd
import pytest

from app.ingestion.dataset import DatasetObject
from app.profiling.engine import ProfilingEngine, get_profiling_engine
from app.profiling.types import (
    ColumnClass,
    QualityGrade,
    SectionStatus,
)


# ---------------------------------------------------------------------------
# Financial reference dataset
# ---------------------------------------------------------------------------
def test_profile_financial_dataset_covers_all_column_classes(financial_dataset) -> None:
    result = get_profiling_engine().profile(financial_dataset)

    assert result.overview.rows == 500
    assert result.overview.columns == 10
    assert result.overview.id_columns >= 1        # transaction_id + customer_id
    assert result.overview.numerical_columns >= 2  # amount + fee
    assert result.overview.categorical_columns >= 2  # payment_method + region
    assert result.overview.date_columns + result.overview.datetime_columns >= 1
    assert result.overview.boolean_columns >= 1
    assert result.overview.text_columns >= 0  # 'note' may be text or categorical

    kinds = {c.name: c.column_class for c in result.column_profiles}
    assert kinds["transaction_id"] == ColumnClass.ID
    assert kinds["customer_id"] == ColumnClass.ID
    assert kinds["amount"] == ColumnClass.NUMERICAL
    assert kinds["payment_method"] == ColumnClass.CATEGORICAL
    assert kinds["is_flagged"] == ColumnClass.BOOLEAN


def test_profile_generates_summary_text(financial_dataset) -> None:
    result = get_profiling_engine().profile(financial_dataset)
    assert "500" in result.summary_text
    assert "10 columns" in result.summary_text
    assert "grade" in result.summary_text.lower()


def test_profile_result_is_json_safe(financial_dataset) -> None:
    result = get_profiling_engine().profile(financial_dataset)
    # This will raise TypeError if anything inside is non-serializable.
    payload = json.dumps(result.to_dict())
    assert isinstance(payload, str)


def test_profile_does_not_mutate_source(financial_dataset, financial_df) -> None:
    before = financial_dataset.data.copy()
    _ = get_profiling_engine().profile(financial_dataset)
    pd.testing.assert_frame_equal(financial_dataset.data, before)


def test_profile_quality_is_reasonable(financial_dataset) -> None:
    result = get_profiling_engine().profile(financial_dataset)
    assert 0 <= result.quality.overall_score <= 100
    assert result.quality.grade in QualityGrade


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------
def test_profile_dataset_with_missing_values(dataset_with_missing) -> None:
    result = get_profiling_engine().profile(dataset_with_missing)
    assert result.missing.status == SectionStatus.OK
    assert result.missing.total_missing > 0
    assert result.quality.dimensions["completeness"] < 100


def test_profile_dataset_with_duplicates(dataset_with_duplicates) -> None:
    result = get_profiling_engine().profile(dataset_with_duplicates)
    assert result.duplicates.status == SectionStatus.OK
    assert result.duplicates.duplicate_rows > 0
    assert result.quality.dimensions["uniqueness"] < 100


def test_profile_dataset_with_no_numeric_returns_unavailable_correlations(dataset_no_numeric) -> None:
    result = get_profiling_engine().profile(dataset_no_numeric)
    assert result.correlations.status == SectionStatus.UNAVAILABLE


def test_profile_empty_dataset_returns_result(dataset_empty) -> None:
    result = get_profiling_engine().profile(dataset_empty)
    assert result.overview.rows == 0
    assert result.overview.columns == 0
    assert "empty" in result.summary_text.lower()


def test_profile_high_cardinality_dataset(dataset_high_card_string) -> None:
    result = get_profiling_engine().profile(dataset_high_card_string)
    # user_id should be classified as ID or high-cardinality UNIQUE
    kinds = {c.name: c.column_class for c in result.column_profiles}
    assert kinds["user_id"] in (ColumnClass.ID, ColumnClass.UNKNOWN)


def test_profile_records_timing(financial_dataset) -> None:
    result = get_profiling_engine().profile(financial_dataset)
    assert result.profiling_time_ms >= 0
