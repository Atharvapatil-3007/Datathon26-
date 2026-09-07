"""Type-detector heuristic coverage."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.profiling.type_detector import detect_column_type
from app.profiling.types import CardinalityClass, ColumnClass


def test_numerical_column() -> None:
    s = pd.Series(np.random.default_rng(0).normal(size=200), name="amount")
    r = detect_column_type("amount", s)
    assert r.column_class == ColumnClass.NUMERICAL


def test_categorical_column_from_low_card_strings() -> None:
    s = pd.Series(["UPI", "Card", "Cash"] * 50, name="payment_method")
    r = detect_column_type("payment_method", s)
    assert r.column_class == ColumnClass.CATEGORICAL


def test_text_column_from_long_strings() -> None:
    long = "This is a longer piece of free-form text that clearly exceeds the text-length threshold."
    s = pd.Series([long] * 20, name="note")
    r = detect_column_type("note", s)
    assert r.column_class == ColumnClass.TEXT


def test_date_column_iso_strings() -> None:
    s = pd.Series(
        [f"2024-01-{d:02d}" for d in range(1, 21)],
        name="transaction_date",
    )
    r = detect_column_type("transaction_date", s)
    assert r.column_class in (ColumnClass.DATE, ColumnClass.DATETIME)


def test_identifier_from_name_hint_and_sequential_ints() -> None:
    s = pd.Series(range(100_001, 100_101), name="customer_id")
    r = detect_column_type("customer_id", s)
    assert r.column_class == ColumnClass.ID


def test_identifier_from_uuid_pattern() -> None:
    import uuid

    values = [str(uuid.uuid4()) for _ in range(50)]
    s = pd.Series(values, name="ref")
    r = detect_column_type("ref", s)
    assert r.column_class == ColumnClass.ID


def test_boolean_column_from_bool_dtype() -> None:
    s = pd.Series([True, False, True, False, True], name="is_flagged")
    r = detect_column_type("is_flagged", s)
    assert r.column_class == ColumnClass.BOOLEAN


def test_boolean_column_from_yes_no_strings() -> None:
    s = pd.Series(["yes", "no", "yes", "no"] * 10, name="active")
    r = detect_column_type("active", s)
    assert r.column_class == ColumnClass.BOOLEAN


def test_low_card_integer_becomes_categorical_not_numerical() -> None:
    s = pd.Series([1, 2, 3, 4, 5] * 20, name="rating")
    r = detect_column_type("rating", s)
    assert r.column_class == ColumnClass.CATEGORICAL


def test_empty_column_is_unknown() -> None:
    s = pd.Series([None] * 20, name="empty", dtype="object")
    r = detect_column_type("empty", s)
    assert r.column_class == ColumnClass.UNKNOWN


def test_cardinality_class_unique() -> None:
    s = pd.Series([f"user-{i}" for i in range(50)], name="user")
    r = detect_column_type("user", s)
    assert r.cardinality_class == CardinalityClass.UNIQUE


def test_cardinality_class_low() -> None:
    s = pd.Series(["A", "B", "C"] * 40, name="grade")
    r = detect_column_type("grade", s)
    assert r.cardinality_class == CardinalityClass.LOW
