"""Query engine numerical & structural correctness.

These tests run the full pipeline `classify → build_context → answer` and
assert on the resulting ``EvidenceBundle``. Values are cross-checked
against the corporate / competitor / bank fixtures so any drift in
extraction or ratio math trips a test.

Corporate fixture reminder (quarterly 2024):
    revenue  = 100 + 110 + 120 + 130   = 460
    cogs     =  55 +  58 +  62 +  66   = 241
    opex     =  25 +  26 +  27 +  28   = 106
    net_profit = 15 + 18 + 21 + 25     = 79
    assets(latest)      = 450
    equity(latest)      = 255
    debt(latest)        = 88
    cash(latest)        = 72

Competitor fixture reminder (quarterly 2024):
    revenue = 140 + 150 + 162 + 175 = 627
    net_profit = 28 + 32 + 37 + 42 = 139
    assets(latest) = 560
    equity(latest) = 345
"""

from __future__ import annotations

import pytest

from app.chatbot.classifier import classify
from app.chatbot.context_builder import build_context
from app.chatbot.query_engine import answer
from app.chatbot.types import (
    AnswerClassification,
    ChatIntent,
    EntityRef,
)


# ---------------------------------------------------------------------------
# Dataset-understanding intents
# ---------------------------------------------------------------------------
class TestDatasetIntents:
    def test_overview_reports_row_and_column_counts(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        q = classify("Give me an overview of the dataset")
        b = answer(q, ctx)
        assert b.intent == ChatIntent.DATASET_OVERVIEW
        assert b.classification == AnswerClassification.REPORTED
        by_label = {e.label: e for e in b.evidence}
        assert by_label["Rows"].value == 4
        # 10 columns in the corporate fixture: period_date + 9 numerics.
        assert by_label["Columns"].value == 10

    def test_columns_lookup(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        q = classify("What columns do we have?")
        b = answer(q, ctx)
        assert b.intent == ChatIntent.COLUMN_LOOKUP
        # Every evidence item should be a column with a name in its label.
        assert len(b.evidence) >= 5
        assert all(e.label for e in b.evidence)

    def test_data_quality(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        q = classify("What is the data quality score?")
        b = answer(q, ctx)
        assert b.intent == ChatIntent.DATA_QUALITY
        assert b.classification == AnswerClassification.CALCULATED

    def test_period_range(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        q = classify("What date range does the dataset cover?")
        b = answer(q, ctx)
        assert b.intent == ChatIntent.PERIOD_RANGE
        assert b.classification == AnswerClassification.REPORTED


# ---------------------------------------------------------------------------
# Metric lookup — aggregate values
# ---------------------------------------------------------------------------
class TestMetricLookup:
    def test_revenue_aggregate(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What is our total revenue?"), ctx)
        assert b.intent == ChatIntent.METRIC_LOOKUP
        assert b.classification == AnswerClassification.REPORTED
        revenue = _extract_value(b, metric_id="revenue")
        assert abs(revenue - 460.0) < 0.5

    def test_net_profit_aggregate(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What is our net profit?"), ctx)
        assert abs(_extract_value(b, metric_id="net_profit") - 79.0) < 0.5

    def test_equity_uses_latest(self, corporate_dataset_id):
        """Balance-sheet stock metric — periodic data → latest value."""
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What is our equity?"), ctx)
        assert abs(_extract_value(b, metric_id="equity") - 255.0) < 0.5

    def test_debt_uses_latest(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What is our debt?"), ctx)
        assert abs(_extract_value(b, metric_id="debt") - 88.0) < 0.5

    def test_metric_in_year_2024(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What was our revenue in 2024?"), ctx)
        assert b.classification == AnswerClassification.REPORTED
        # All 4 rows are 2024 → sum is 460 regardless of year filter.
        assert abs(_extract_value(b, metric_id="revenue") - 460.0) < 0.5

    def test_metric_in_year_2099_unavailable(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What was our revenue in 2099?"), ctx)
        assert b.classification == AnswerClassification.UNAVAILABLE
        # Must tell the user which years exist.
        assert any("2024" in (n or "") for n in b.notes)

    def test_unknown_metric_returns_empty_bundle(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        # 'CASA' isn't in the corporate fixture — banking-specific.
        b = answer(classify("What is our CASA?"), ctx)
        assert b.classification == AnswerClassification.UNAVAILABLE


# ---------------------------------------------------------------------------
# Ratio lookup — calculated values
# ---------------------------------------------------------------------------
class TestRatioLookup:
    def test_net_margin(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What is our net profit margin?"), ctx)
        assert b.classification == AnswerClassification.CALCULATED
        expected = 79.0 / 460.0 * 100.0
        assert abs(_extract_value(b, metric_id="net_margin") - expected) < 0.05

    def test_roa(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What is our ROA?"), ctx)
        assert b.classification == AnswerClassification.CALCULATED
        expected = 79.0 / 450.0 * 100.0
        assert abs(_extract_value(b, metric_id="roa") - expected) < 0.05

    def test_roe(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What is our ROE?"), ctx)
        expected = 79.0 / 255.0 * 100.0
        assert abs(_extract_value(b, metric_id="roe") - expected) < 0.05

    def test_debt_to_equity(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What is our debt-to-equity ratio?"), ctx)
        expected = 88.0 / 255.0
        assert abs(_extract_value(b, metric_id="debt_to_equity") - expected) < 0.01

    def test_ratio_unavailable_when_input_missing(self, no_assets_dataset_id):
        """ROA needs total assets; if it's missing we must say so, not guess."""
        ctx = build_context(analysis_mode="self_analysis", dataset_id=no_assets_dataset_id)
        b = answer(classify("What is our ROA?"), ctx)
        assert b.classification == AnswerClassification.UNAVAILABLE
        # Explanation must mention what's missing.
        assert any("assets" in (n or "").lower() for n in b.notes)


# ---------------------------------------------------------------------------
# Trend analysis
# ---------------------------------------------------------------------------
class TestTrend:
    def test_revenue_trend(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("How is revenue trending?"), ctx)
        assert b.intent == ChatIntent.TREND_ANALYSIS
        assert b.classification == AnswerClassification.CALCULATED
        # Growth should be positive (100 -> 130 = 30%).
        assert b.calculations
        result = b.calculations[0].result
        assert result is not None and result > 0


# ---------------------------------------------------------------------------
# Health / SWOT / recommendation
# ---------------------------------------------------------------------------
class TestHealthAndSwot:
    def test_financial_health(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("How financially healthy are we?"), ctx)
        assert b.intent == ChatIntent.FINANCIAL_HEALTH
        assert b.classification == AnswerClassification.CALCULATED
        # Score & grade come from health_scorer.
        assert len(b.evidence) >= 1

    def test_risks(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What are our biggest risks?"), ctx)
        assert b.intent == ChatIntent.RISK_ANALYSIS

    def test_recommendations(self, corporate_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What should we improve?"), ctx)
        assert b.intent == ChatIntent.RECOMMENDATION


# ---------------------------------------------------------------------------
# Merger mode
# ---------------------------------------------------------------------------
class TestMergerMode:
    def test_merger_overview(self, corporate_dataset_id, competitor_dataset_id):
        ctx = build_context(
            analysis_mode="merger_partnership_analysis",
            dataset_id=corporate_dataset_id,
            secondary_dataset_id=competitor_dataset_id,
        )
        b = answer(classify("What is the combined scenario?"), ctx)
        assert b.classification == AnswerClassification.SCENARIO
        # Every combined evidence item must be entity=combined.
        combined = [e for e in b.evidence if e.entity == EntityRef.COMBINED.value]
        assert combined
        for e in combined:
            assert e.status == AnswerClassification.SCENARIO

    def test_merger_metric_combined_revenue(
        self, corporate_dataset_id, competitor_dataset_id
    ):
        ctx = build_context(
            analysis_mode="merger_partnership_analysis",
            dataset_id=corporate_dataset_id,
            secondary_dataset_id=competitor_dataset_id,
        )
        b = answer(classify("What would combined revenue look like?"), ctx)
        assert b.classification == AnswerClassification.SCENARIO
        # Combined revenue = 460 + 627 = 1087.
        combined = [
            e for e in b.evidence
            if e.entity == EntityRef.COMBINED.value and e.metric_id == "revenue"
        ]
        assert combined, "Expected a combined revenue evidence item"
        assert abs(combined[0].value - 1087.0) < 1.0

    def test_merger_synergies(self, corporate_dataset_id, competitor_dataset_id):
        ctx = build_context(
            analysis_mode="merger_partnership_analysis",
            dataset_id=corporate_dataset_id,
            secondary_dataset_id=competitor_dataset_id,
        )
        b = answer(classify("What synergies could exist?"), ctx)
        assert b.intent == ChatIntent.MERGER_SYNERGY
        assert b.classification == AnswerClassification.SCENARIO

    def test_merger_mode_required_for_synergy(self, corporate_dataset_id):
        """Asking about synergies in self mode should be UNAVAILABLE, not fabricated."""
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What synergies could exist?"), ctx)
        assert b.classification == AnswerClassification.UNAVAILABLE


# ---------------------------------------------------------------------------
# Competitor / benchmark mode
# ---------------------------------------------------------------------------
class TestBenchmarkMode:
    def test_competitor_comparison_has_both_entities(
        self, corporate_dataset_id, competitor_dataset_id
    ):
        ctx = build_context(
            analysis_mode="competitor_market_benchmark",
            dataset_id=corporate_dataset_id,
            secondary_dataset_id=competitor_dataset_id,
        )
        b = answer(classify("How do we compare to the competitor?"), ctx)
        assert b.intent == ChatIntent.COMPETITOR_COMPARISON
        entities = {e.entity for e in b.evidence}
        assert EntityRef.PRIMARY.value in entities
        assert EntityRef.SECONDARY.value in entities

    def test_competitor_revenue_attribution(
        self, corporate_dataset_id, competitor_dataset_id
    ):
        """Values must be attributed to the correct dataset — no cross-contamination."""
        ctx = build_context(
            analysis_mode="competitor_market_benchmark",
            dataset_id=corporate_dataset_id,
            secondary_dataset_id=competitor_dataset_id,
        )
        b = answer(classify("How do our revenue and the competitor's compare?"), ctx)
        primary_rev = [
            e for e in b.evidence
            if e.metric_id == "revenue" and e.entity == EntityRef.PRIMARY.value
        ]
        secondary_rev = [
            e for e in b.evidence
            if e.metric_id == "revenue" and e.entity == EntityRef.SECONDARY.value
        ]
        assert primary_rev and secondary_rev
        assert abs(primary_rev[0].value - 460.0) < 1.0
        assert abs(secondary_rev[0].value - 627.0) < 1.0

    def test_gap_analysis(self, corporate_dataset_id, competitor_dataset_id):
        ctx = build_context(
            analysis_mode="competitor_market_benchmark",
            dataset_id=corporate_dataset_id,
            secondary_dataset_id=competitor_dataset_id,
        )
        b = answer(classify("Where are we behind?"), ctx)
        assert b.intent == ChatIntent.GAP_ANALYSIS
        # Corporate has lower revenue than competitor, so at least one gap exists.
        assert b.evidence

    def test_market_benchmark_unavailable_without_market_dataset(
        self, corporate_dataset_id, competitor_dataset_id
    ):
        ctx = build_context(
            analysis_mode="competitor_market_benchmark",
            dataset_id=corporate_dataset_id,
            secondary_dataset_id=competitor_dataset_id,
        )
        b = answer(classify("How do we compare to the market benchmark?"), ctx)
        assert b.classification == AnswerClassification.UNAVAILABLE
        assert "market" in b.headline.lower()

    def test_gap_mode_required(self, corporate_dataset_id):
        """Gap questions in self mode should refuse rather than fabricate."""
        ctx = build_context(analysis_mode="self_analysis", dataset_id=corporate_dataset_id)
        b = answer(classify("What is our biggest gap?"), ctx)
        assert b.classification == AnswerClassification.UNAVAILABLE


# ---------------------------------------------------------------------------
# Banking data — a different metric shape
# ---------------------------------------------------------------------------
class TestBankingDataset:
    def test_bank_deposits_latest(self, bank_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=bank_dataset_id)
        b = answer(classify("What are our deposits?"), ctx)
        # Deposits are a stock; latest = 11500.
        assert abs(_extract_value(b, metric_id="deposits") - 11500.0) < 1.0

    def test_bank_casa_ratio(self, bank_dataset_id):
        ctx = build_context(analysis_mode="self_analysis", dataset_id=bank_dataset_id)
        b = answer(classify("What is our CASA ratio?"), ctx)
        # casa 5100 / deposits 11500 * 100 = 44.348%
        assert b.classification == AnswerClassification.CALCULATED
        expected = 5100.0 / 11500.0 * 100.0
        assert abs(_extract_value(b, metric_id="casa_ratio") - expected) < 0.05


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _extract_value(bundle, *, metric_id: str) -> float:
    for e in bundle.evidence:
        if e.metric_id == metric_id and e.value is not None:
            return float(e.value)
    raise AssertionError(
        f"No evidence with metric_id={metric_id!r} in bundle. "
        f"Got: {[(e.metric_id, e.value) for e in bundle.evidence]}"
    )
