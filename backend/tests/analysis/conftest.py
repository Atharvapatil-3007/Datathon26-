"""Fixtures for Phase 3 analysis tests.

We reuse the existing local-storage fallback (via the top-level
``_isolate_supabase`` autouse fixture) so every test writes to a
throw-away directory. Datasets are uploaded through the real ingestion
manager, meaning Phase 1 + Phase 2 both run before Phase 3 sees anything.
"""

from __future__ import annotations

import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import pytest


# ---------------------------------------------------------------------------
# CSV builders
# ---------------------------------------------------------------------------
def _write_csv(path: Path, header: List[str], rows: List[List]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


@pytest.fixture
def corporate_pnl_csv(tmp_path: Path) -> Path:
    """A tiny 4-period quarterly income statement + balance sheet."""
    p = tmp_path / "corporate_pnl.csv"
    start = datetime(2024, 1, 1)
    rows = []
    for i, (rev, cogs, opex, net, assets, liab, eq, debt, cash) in enumerate(
        [
            (100.0, 55.0, 25.0, 15.0, 400.0, 180.0, 220.0, 90.0, 60.0),
            (110.0, 58.0, 26.0, 18.0, 420.0, 190.0, 230.0, 92.0, 65.0),
            (120.0, 62.0, 27.0, 21.0, 435.0, 195.0, 240.0, 90.0, 68.0),
            (130.0, 66.0, 28.0, 25.0, 450.0, 195.0, 255.0, 88.0, 72.0),
        ]
    ):
        rows.append(
            [
                (start + timedelta(days=90 * i)).strftime("%Y-%m-%d"),
                rev,
                cogs,
                opex,
                net,
                assets,
                liab,
                eq,
                debt,
                cash,
            ]
        )
    _write_csv(
        p,
        [
            "period_date",
            "revenue",
            "cogs",
            "operating_expenses",
            "net_profit",
            "total_assets",
            "total_liabilities",
            "equity",
            "debt",
            "cash",
        ],
        rows,
    )
    return p


@pytest.fixture
def competitor_pnl_csv(tmp_path: Path) -> Path:
    """A competitor with slightly different (better) financials."""
    p = tmp_path / "competitor_pnl.csv"
    start = datetime(2024, 1, 1)
    rows = []
    for i, (rev, cogs, opex, net, assets, liab, eq, debt, cash) in enumerate(
        [
            (140.0, 70.0, 32.0, 28.0, 500.0, 200.0, 300.0, 110.0, 85.0),
            (150.0, 74.0, 33.0, 32.0, 520.0, 205.0, 315.0, 108.0, 92.0),
            (162.0, 78.0, 34.0, 37.0, 540.0, 210.0, 330.0, 105.0, 98.0),
            (175.0, 82.0, 35.0, 42.0, 560.0, 215.0, 345.0, 102.0, 105.0),
        ]
    ):
        rows.append(
            [
                (start + timedelta(days=90 * i)).strftime("%Y-%m-%d"),
                rev,
                cogs,
                opex,
                net,
                assets,
                liab,
                eq,
                debt,
                cash,
            ]
        )
    _write_csv(
        p,
        [
            "period_date",
            "revenue",
            "cogs",
            "operating_expenses",
            "net_profit",
            "total_assets",
            "total_liabilities",
            "equity",
            "debt",
            "cash",
        ],
        rows,
    )
    return p


@pytest.fixture
def bank_dataset_csv(tmp_path: Path) -> Path:
    """A tiny bank-shaped dataset with banking metrics."""
    p = tmp_path / "bank.csv"
    start = datetime(2023, 1, 1)
    rows = []
    for i in range(4):
        rows.append(
            [
                (start + timedelta(days=90 * i)).strftime("%Y-%m-%d"),
                10_000.0 + i * 500,    # deposits
                8_000.0 + i * 400,     # loans
                4_500.0 + i * 200,     # casa
                180.0 + i * 5,         # net_interest_income
                40.0 + i * 2,          # non_interest_income
                80.0 + i * 3,          # operating_expenses
                200.0 - i * 5,         # gross_npa
                50.0 + i,              # provisions
                60.0 + i * 2,          # net_profit
                12_000.0 + i * 250,    # total_assets
                1_500.0 + i * 40,      # equity
            ]
        )
    _write_csv(
        p,
        [
            "period_date",
            "deposits",
            "loans",
            "casa",
            "net_interest_income",
            "non_interest_income",
            "operating_expenses",
            "gross_npa",
            "provisions",
            "net_profit",
            "total_assets",
            "equity",
        ],
        rows,
    )
    return p


# ---------------------------------------------------------------------------
# Upload helpers \u2014 push a CSV through the real ingestion manager so both
# Phase 1 and Phase 2 run, producing a persisted profile.
# ---------------------------------------------------------------------------
def _ingest(path: Path) -> str:
    from app.ingestion.manager import get_ingestion_manager

    manager = get_ingestion_manager()
    result, _status = manager.ingest_file(
        temp_path=str(path),
        filename=path.name,
        mime_type="text/csv",
    )
    return result.dataset.dataset_id


@pytest.fixture
def corporate_dataset_id(corporate_pnl_csv: Path) -> str:
    return _ingest(corporate_pnl_csv)


@pytest.fixture
def competitor_dataset_id(competitor_pnl_csv: Path) -> str:
    return _ingest(competitor_pnl_csv)


@pytest.fixture
def bank_dataset_id(bank_dataset_csv: Path) -> str:
    return _ingest(bank_dataset_csv)
