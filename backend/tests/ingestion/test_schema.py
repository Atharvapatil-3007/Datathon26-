"""Tests for schema inference."""

from __future__ import annotations

import pandas as pd

from app.ingestion.dataset import InferredType
from app.ingestion.schema import infer_schema


def test_schema_flags_customer_id_as_identifier(rich_dataframe: pd.DataFrame) -> None:
    columns = {c.name: c for c in infer_schema(rich_dataframe)}
    cid = columns["customer_id"]
    assert cid.is_identifier is True
    assert cid.is_categorical is False


def test_schema_flags_age_income_as_numerical(rich_dataframe: pd.DataFrame) -> None:
    columns = {c.name: c for c in infer_schema(rich_dataframe)}
    assert columns["age"].is_numerical is True
    assert columns["income"].is_numerical is True
    assert columns["age"].inferred_type == InferredType.INTEGER


def test_schema_flags_city_as_categorical(rich_dataframe: pd.DataFrame) -> None:
    columns = {c.name: c for c in infer_schema(rich_dataframe)}
    assert columns["city"].is_categorical is True


def test_schema_flags_signup_date_as_datetime(rich_dataframe: pd.DataFrame) -> None:
    columns = {c.name: c for c in infer_schema(rich_dataframe)}
    assert columns["signup_date"].is_datetime is True
    assert columns["signup_date"].inferred_type == InferredType.DATETIME


def test_schema_flags_feedback_as_text(rich_dataframe: pd.DataFrame) -> None:
    columns = {c.name: c for c in infer_schema(rich_dataframe)}
    # long-form strings should be flagged as text, not categorical
    assert columns["feedback"].is_text is True


def test_schema_flags_low_cardinality_integer_as_categorical(rich_dataframe: pd.DataFrame) -> None:
    columns = {c.name: c for c in infer_schema(rich_dataframe)}
    # rating column has only 5 distinct values in 20 rows
    assert columns["rating"].is_categorical is True


def test_schema_captures_missing_counts() -> None:
    df = pd.DataFrame({"a": [1, 2, None, 4, None]})
    schema = infer_schema(df)
    (col,) = schema
    assert col.missing_count == 2
    assert col.nullable is True
    assert 0.39 < col.missing_ratio < 0.41
