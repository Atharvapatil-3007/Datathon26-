"""Intent classifier tests.

Covers every intent branch that the query engine can dispatch on, plus
the conversation-state back-fill for follow-up questions.
"""

from __future__ import annotations

import pytest

from app.chatbot.classifier import ConversationState, classify
from app.chatbot.types import ChatIntent, EntityRef, PeriodRef


class TestIntentDetection:
    @pytest.mark.parametrize(
        "text,intent",
        [
            # Meta
            ("hi", ChatIntent.GREETING),
            ("hello there", ChatIntent.GREETING),
            ("help", ChatIntent.HELP),
            ("what can you do?", ChatIntent.HELP),
            # Dataset understanding
            ("How many rows are in the dataset?", ChatIntent.DATASET_OVERVIEW),
            ("Give me an overview of the dataset", ChatIntent.DATASET_OVERVIEW),
            ("What columns do we have?", ChatIntent.COLUMN_LOOKUP),
            ("List the columns", ChatIntent.COLUMN_LOOKUP),
            ("How many missing values?", ChatIntent.DATA_QUALITY),
            ("Show me the data quality score", ChatIntent.DATA_QUALITY),
            ("What date range does the dataset cover?", ChatIntent.PERIOD_RANGE),
            ("What years are in the dataset?", ChatIntent.PERIOD_RANGE),
            # Metric & ratio lookup
            ("What is our revenue?", ChatIntent.METRIC_LOOKUP),
            ("Show me net profit", ChatIntent.METRIC_LOOKUP),
            ("What is our debt to equity?", ChatIntent.RATIO_LOOKUP),
            ("What is our net margin?", ChatIntent.RATIO_LOOKUP),
            ("What's our ROE?", ChatIntent.RATIO_LOOKUP),
            # Trend & comparison
            ("What is our revenue trend?", ChatIntent.TREND_ANALYSIS),
            ("How is net profit trending?", ChatIntent.TREND_ANALYSIS),
            ("Revenue in 2024 vs 2025?", ChatIntent.PERIOD_COMPARISON),
            # Health
            ("How financially healthy are we?", ChatIntent.FINANCIAL_HEALTH),
            ("What's our health score?", ChatIntent.FINANCIAL_HEALTH),
            # SWOT
            ("What are our biggest risks?", ChatIntent.RISK_ANALYSIS),
            ("Show me strengths", ChatIntent.STRENGTH_ANALYSIS),
            ("What are our weaknesses?", ChatIntent.WEAKNESS_ANALYSIS),
            ("What opportunities exist?", ChatIntent.OPPORTUNITY_ANALYSIS),
            ("What should we improve?", ChatIntent.RECOMMENDATION),
            ("What do you recommend?", ChatIntent.RECOMMENDATION),
            # Merger
            ("What synergies could exist?", ChatIntent.MERGER_SYNERGY),
            ("How compatible are the two companies?", ChatIntent.MERGER_COMPATIBILITY),
            # Benchmark
            ("Where are we behind the competitor?", ChatIntent.GAP_ANALYSIS),
            ("How do we compare to the competitor?", ChatIntent.COMPETITOR_COMPARISON),
            ("What is our biggest gap?", ChatIntent.GAP_ANALYSIS),
            ("What is the roadmap to close the gap?", ChatIntent.ROADMAP),
        ],
    )
    def test_intent(self, text, intent):
        q = classify(text)
        assert q.intent == intent, (
            f"{text!r} classified as {q.intent} instead of {intent}"
        )


class TestSlotExtraction:
    def test_metric_slot(self):
        q = classify("What is our revenue?")
        assert "revenue" in q.slots.metric_ids

    def test_period_slot(self):
        q = classify("Revenue in 2024?")
        assert any(p.year == 2024 for p in q.slots.periods)

    def test_entity_secondary(self):
        q = classify("What's the competitor's revenue?")
        assert q.slots.entity == EntityRef.SECONDARY

    def test_entity_combined(self):
        q = classify("What would combined revenue look like?")
        assert q.slots.entity == EntityRef.COMBINED

    def test_subject_hints(self):
        q = classify("What are our biggest risks?")
        assert "risk" in q.slots.subject_hints

    def test_aggregation_trend(self):
        q = classify("How is revenue trending?")
        assert q.slots.aggregation == "trend"

    def test_comparison_gap(self):
        q = classify("What is our biggest gap?")
        assert q.slots.comparison == "gap"


class TestFollowUpContext:
    def test_no_metric_backfill_from_state(self):
        """`what about 2024?` after asking about revenue should reuse revenue."""
        state = ConversationState(
            last_metric_id="revenue",
            last_intent=ChatIntent.METRIC_LOOKUP,
            last_period=PeriodRef(kind="year", label="FY2023", year=2023),
        )
        q = classify("what about 2024?", state=state)
        assert q.used_context is True
        assert "revenue" in q.slots.metric_ids
        assert any(p.year == 2024 for p in q.slots.periods)

    def test_period_backfill_when_followup_and_no_period(self):
        """`what about profit?` should carry the previous period."""
        state = ConversationState(
            last_metric_id="revenue",
            last_intent=ChatIntent.METRIC_LOOKUP,
            last_period=PeriodRef(kind="year", label="FY2024", year=2024),
        )
        q = classify("what about profit?", state=state)
        assert "net_profit" in q.slots.metric_ids
        assert any(p.year == 2024 for p in q.slots.periods)
        assert q.used_context is True

    def test_no_backfill_when_slots_present(self):
        state = ConversationState(
            last_metric_id="net_profit",
            last_intent=ChatIntent.METRIC_LOOKUP,
        )
        q = classify("What is our revenue?", state=state)
        # New metric takes precedence over state.
        assert "revenue" in q.slots.metric_ids
        assert "net_profit" not in q.slots.metric_ids

    def test_no_backfill_when_not_followup(self):
        state = ConversationState(
            last_metric_id="revenue",
            last_intent=ChatIntent.METRIC_LOOKUP,
            last_period=PeriodRef(kind="year", label="FY2023", year=2023),
        )
        # No "what about" or "and" — regular new question.
        q = classify("How many rows?", state=state)
        # We didn't back-fill any hint because this isn't a follow-up phrasing.
        assert q.slots.periods == []
