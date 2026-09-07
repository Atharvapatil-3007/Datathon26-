"""Fixtures for chatbot tests.

We reuse the corporate / competitor / bank ingestion fixtures defined in
``tests/analysis/conftest.py``. Pytest doesn't automatically inherit
sibling conftests, so we import them here as ordinary fixtures.

Each test starts with fresh chatbot state — session store, context cache
and service singleton are reset so cross-test bleeding cannot happen.
"""

from __future__ import annotations

import pytest

from tests.analysis.conftest import (  # noqa: F401 — re-exported fixtures
    corporate_pnl_csv,
    corporate_dataset_id,
    competitor_pnl_csv,
    competitor_dataset_id,
    bank_dataset_csv,
    bank_dataset_id,
)


@pytest.fixture(autouse=True)
def _reset_chatbot_state():
    """Clear session store, context cache, and service singleton per test."""
    from app.chatbot.context_builder import clear_context_cache
    from app.chatbot.service import reset_chatbot_service_for_tests
    from app.chatbot.session_store import reset_session_store_for_tests

    clear_context_cache()
    reset_session_store_for_tests()
    reset_chatbot_service_for_tests()
    yield
    clear_context_cache()
    reset_session_store_for_tests()
    reset_chatbot_service_for_tests()


@pytest.fixture
def no_assets_dataset_id(tmp_path):
    """A CSV with revenue + net_profit but no balance-sheet columns.

    Useful for testing "missing data" responses — ROA / ROE / D-E cannot be
    computed and the chatbot must say so cleanly.
    """
    from tests.analysis.conftest import _write_csv
    from app.ingestion.manager import get_ingestion_manager

    p = tmp_path / "no_assets.csv"
    _write_csv(
        p,
        ["period_date", "revenue", "net_profit", "operating_expenses"],
        [
            ["2024-01-01", 100.0, 15.0, 25.0],
            ["2024-04-01", 110.0, 18.0, 26.0],
            ["2024-07-01", 120.0, 21.0, 27.0],
            ["2024-10-01", 130.0, 25.0, 28.0],
        ],
    )
    result, _ = get_ingestion_manager().ingest_file(
        temp_path=str(p),
        filename="no_assets.csv",
        mime_type="text/csv",
    )
    return result.dataset.dataset_id
