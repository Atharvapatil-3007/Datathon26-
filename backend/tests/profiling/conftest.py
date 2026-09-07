"""Fixtures for the Phase 2 profiling test suite.

Reuses the top-level `_isolate_supabase` autouse fixture (defined in
`tests/conftest.py`) so every test runs against the local storage fallback.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from app.ingestion.dataset import DatasetObject, FileFormat, SourceType


# ---------------------------------------------------------------------------
# Synthetic financial dataset — the reference "clean" corpus
# ---------------------------------------------------------------------------
@pytest.fixture
def financial_df() -> pd.DataFrame:
    """A realistic-looking transactions frame.

    500 rows, mixed types: 1 ID, 3 numerical, 2 categorical, 1 date,
    1 boolean, 1 text.
    """
    rng = np.random.default_rng(seed=42)
    n = 500

    return pd.DataFrame(
        {
            "transaction_id": [f"TXN-{100000 + i}" for i in range(n)],
            "customer_id": rng.integers(low=1, high=120, size=n),
            "amount": rng.normal(loc=250.0, scale=90.0, size=n).round(2),
            "fee": np.clip(rng.normal(loc=2.5, scale=1.0, size=n).round(2), 0, None),
            "quantity": rng.integers(low=1, high=10, size=n),
            "payment_method": rng.choice(
                ["UPI", "Card", "Cash", "NetBank", "Other"],
                size=n,
                p=[0.42, 0.31, 0.18, 0.06, 0.03],
            ),
            "region": rng.choice(["North", "South", "East", "West"], size=n),
            "transaction_date": [
                datetime(2024, 1, 1) + timedelta(days=int(d))
                for d in rng.integers(0, 365, size=n)
            ],
            "is_flagged": rng.choice([True, False], size=n, p=[0.05, 0.95]),
            "note": rng.choice(
                [
                    "Routine transfer between accounts",
                    "Merchant refund following support ticket",
                    "Recurring subscription payment",
                    "Manual reconciliation entry",
                ],
                size=n,
            ),
        }
    )


@pytest.fixture
def financial_dataset(financial_df: pd.DataFrame) -> DatasetObject:
    return DatasetObject(
        dataset_id="dataset-financial",
        data=financial_df,
        source_type=SourceType.FILE,
        source_name="transactions.csv",
        format=FileFormat.CSV,
    )


# ---------------------------------------------------------------------------
# Edge-case datasets
# ---------------------------------------------------------------------------
@pytest.fixture
def dataset_with_missing() -> DatasetObject:
    df = pd.DataFrame(
        {
            "id": range(100),
            "amount": [float(i) if i % 5 else None for i in range(100)],
            "region": ["North" if i % 4 else None for i in range(100)],
        }
    )
    return DatasetObject(
        dataset_id="dataset-missing",
        data=df,
        source_name="missing.csv",
        format=FileFormat.CSV,
    )


@pytest.fixture
def dataset_with_duplicates() -> DatasetObject:
    df = pd.DataFrame(
        {
            "customer_id": [1, 2, 3, 4, 5, 1, 2],
            "amount": [100, 200, 300, 400, 500, 100, 200],
        }
    )
    return DatasetObject(
        dataset_id="dataset-duplicates",
        data=df,
        source_name="dupes.csv",
        format=FileFormat.CSV,
    )


@pytest.fixture
def dataset_no_numeric() -> DatasetObject:
    df = pd.DataFrame(
        {
            "region": ["North", "South", "East", "West"] * 10,
            "note": ["free text"] * 40,
        }
    )
    return DatasetObject(
        dataset_id="dataset-non-numeric",
        data=df,
        source_name="strings.csv",
        format=FileFormat.CSV,
    )


@pytest.fixture
def dataset_empty() -> DatasetObject:
    return DatasetObject(
        dataset_id="dataset-empty",
        data=pd.DataFrame(),
        source_name="empty.csv",
        format=FileFormat.CSV,
    )


@pytest.fixture
def dataset_high_card_string() -> DatasetObject:
    """A dataset where every string value is unique — should trigger the
    UNIQUE / high-cardinality behaviour of the detector.
    """
    df = pd.DataFrame(
        {
            "user_id": [f"user-{i:04d}" for i in range(200)],
            "amount": np.linspace(10, 200, 200),
        }
    )
    return DatasetObject(
        dataset_id="dataset-high-card",
        data=df,
        source_name="highcard.csv",
        format=FileFormat.CSV,
    )
