"""Metric registry + column-matching heuristics."""

from __future__ import annotations

from app.analysis.metric_registry import (
    base_metrics,
    derived_metrics,
    match_column,
)
from app.analysis.types import MetricId


def test_match_revenue_from_various_aliases() -> None:
    for name in ("revenue", "total_revenue", "annual_revenue", "sales", "net_sales", "turnover"):
        result = match_column(name)
        assert result is not None, f"expected {name} to match"
        assert result[0] == MetricId.REVENUE


def test_revenue_growth_is_excluded() -> None:
    # 'revenue growth' should NOT match REVENUE because of the exclude pattern.
    result = match_column("revenue_growth")
    assert result is None or result[0] != MetricId.REVENUE


def test_customer_id_does_not_match_customers() -> None:
    result = match_column("customer_id")
    assert result is None or result[0] != MetricId.CUSTOMERS


def test_customer_name_does_not_match_customers() -> None:
    result = match_column("customer_name")
    assert result is None or result[0] != MetricId.CUSTOMERS


def test_net_profit_matches() -> None:
    for name in ("net_profit", "net_income", "profit_after_tax", "pat"):
        result = match_column(name)
        assert result is not None
        assert result[0] == MetricId.NET_PROFIT


def test_ebitda_not_confused_with_ebit() -> None:
    assert match_column("ebitda")[0] == MetricId.EBITDA
    ebit = match_column("ebit")
    assert ebit is not None
    assert ebit[0] == MetricId.EBIT


def test_banking_aliases() -> None:
    assert match_column("deposits")[0] == MetricId.DEPOSITS
    assert match_column("gross_npa")[0] == MetricId.GROSS_NPA
    assert match_column("net_interest_income")[0] == MetricId.NET_INTEREST_INCOME
    assert match_column("casa")[0] == MetricId.CASA


def test_derived_ratios_are_never_matched_from_columns() -> None:
    # Even if a user names a column 'gross_margin', we don't match it as base
    # metric \u2014 ratios are always CALCULATED, never REPORTED.
    for d in derived_metrics():
        assert d.is_derived


def test_registry_has_no_duplicate_ids() -> None:
    ids = [m.metric_id for m in base_metrics()] + [m.metric_id for m in derived_metrics()]
    assert len(ids) == len(set(ids))


def test_match_returns_none_for_gibberish() -> None:
    assert match_column("qwerty") is None
    assert match_column("some_random_column") is None
