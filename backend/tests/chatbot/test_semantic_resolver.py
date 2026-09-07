"""Semantic resolver tests — metric / period / entity extraction."""

from __future__ import annotations

import pytest

from app.analysis.types import MetricId
from app.chatbot.semantic_resolver import (
    resolve_entity,
    resolve_metrics,
    resolve_periods,
)
from app.chatbot.types import EntityRef


class TestResolveMetrics:
    @pytest.mark.parametrize(
        "text,metric",
        [
            ("What was our revenue?", MetricId.REVENUE),
            ("What are total sales?", MetricId.REVENUE),
            ("Show me the turnover", MetricId.REVENUE),
            ("What is our net profit?", MetricId.NET_PROFIT),
            ("What is our EBITDA?", MetricId.EBITDA),
            ("Show me operating expenses", MetricId.OPERATING_EXPENSES),
            ("What's total assets?", MetricId.ASSETS),
            ("How much cash do we have?", MetricId.CASH),
            ("What is our equity position?", MetricId.EQUITY),
            ("Show inventory levels", MetricId.INVENTORY),
            ("What are receivables?", MetricId.RECEIVABLES),
            ("How many customers do we have?", MetricId.CUSTOMERS),
            ("What is our headcount?", MetricId.EMPLOYEES),
            ("Show me deposits", MetricId.DEPOSITS),
            ("What are our loans?", MetricId.LOANS),
            ("What is net interest income?", MetricId.NET_INTEREST_INCOME),
            ("How much gross NPA is there?", MetricId.GROSS_NPA),
        ],
    )
    def test_base_metric(self, text, metric):
        ids = [m for m, _c in resolve_metrics(text)]
        assert metric in ids, f"{metric} not detected in {text!r}. Got {ids}"

    @pytest.mark.parametrize(
        "text,metric",
        [
            ("What is our ROE?", MetricId.ROE),
            ("Show return on equity", MetricId.ROE),
            ("What's our ROA?", MetricId.ROA),
            ("Return on assets?", MetricId.ROA),
            ("What is our net margin?", MetricId.NET_MARGIN),
            ("Show net profit margin", MetricId.NET_MARGIN),
            ("What is gross margin?", MetricId.GROSS_MARGIN),
            ("What is operating margin?", MetricId.OPERATING_MARGIN),
            ("Show me debt-to-equity", MetricId.DEBT_TO_EQUITY),
            ("What is our current ratio?", MetricId.CURRENT_RATIO),
            ("Show quick ratio", MetricId.QUICK_RATIO),
            ("What is asset turnover?", MetricId.ASSET_TURNOVER),
            ("What is interest coverage?", MetricId.INTEREST_COVERAGE),
            ("Show cost to income", MetricId.COST_TO_INCOME),
            ("What is CASA ratio?", MetricId.CASA_RATIO),
        ],
    )
    def test_ratio_metric(self, text, metric):
        ids = [m for m, _c in resolve_metrics(text)]
        assert metric in ids

    def test_no_metric_found(self):
        ids = [m for m, _c in resolve_metrics("weather in Paris")]
        assert ids == []

    def test_confidence_prefers_longer_match(self):
        # "net profit margin" should beat "profit" alone
        matches = resolve_metrics("What is our net profit margin?")
        assert matches[0][0] == MetricId.NET_MARGIN


class TestResolvePeriods:
    def test_bare_year(self):
        periods = resolve_periods("Revenue in 2024?")
        assert len(periods) == 1
        assert periods[0].kind == "year"
        assert periods[0].year == 2024

    def test_fy_year(self):
        periods = resolve_periods("Revenue in FY2025?")
        assert any(p.year == 2025 and p.kind == "year" for p in periods)

    def test_quarter_numeric(self):
        periods = resolve_periods("Revenue in Q3 2024?")
        q = [p for p in periods if p.kind == "quarter"]
        assert q
        assert q[0].quarter == 3
        assert q[0].year == 2024

    def test_quarter_ordinal(self):
        periods = resolve_periods("Revenue in the third quarter of 2024?")
        q = [p for p in periods if p.kind == "quarter"]
        assert q
        assert q[0].quarter == 3
        assert q[0].year == 2024

    def test_vs_two_years_produces_two_periods(self):
        periods = resolve_periods("Revenue 2024 vs 2025?")
        years = sorted(p.year for p in periods if p.year is not None)
        assert years == [2024, 2025]
        assert all(p.kind == "year" for p in periods)

    def test_and_two_years_produces_two_periods(self):
        periods = resolve_periods("Revenue between 2023 and 2025")
        years = sorted(p.year for p in periods if p.year is not None)
        assert years == [2023, 2025]

    def test_range_to(self):
        periods = resolve_periods("Revenue from 2023 to 2025")
        assert any(p.kind == "range" and p.start_year == 2023 and p.end_year == 2025 for p in periods)

    def test_last_year(self):
        periods = resolve_periods("what about last year?")
        assert any(p.kind == "previous" for p in periods)

    def test_this_year(self):
        periods = resolve_periods("this year")
        assert any(p.kind == "latest" for p in periods)

    def test_latest_quarter(self):
        periods = resolve_periods("show me the latest quarter")
        assert any(p.kind == "latest" for p in periods)

    def test_no_periods(self):
        assert resolve_periods("Show me the revenue trend") == []


class TestResolveEntity:
    @pytest.mark.parametrize(
        "text,expected",
        [
            ("How does the competitor compare?", EntityRef.SECONDARY),
            ("Show the other company's revenue", EntityRef.SECONDARY),
            ("What are peer averages?", EntityRef.MARKET),
            ("How do we compare to the market benchmark?", EntityRef.MARKET),
            ("What's the industry average?", EntityRef.MARKET),
            ("What would combined revenue look like?", EntityRef.COMBINED),
            ("What are the post-merger financials?", EntityRef.COMBINED),
            ("What is our revenue?", EntityRef.PRIMARY),
        ],
    )
    def test_entity_resolution(self, text, expected):
        assert resolve_entity(text) == expected

    def test_default_primary(self):
        assert resolve_entity("Revenue?") == EntityRef.PRIMARY
