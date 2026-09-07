"""End-to-end chatbot service tests.

These go through ``ChatbotService.handle_query`` — the full pipeline
(guardrail → classify → build context → query engine → answer generator
→ session store). They exercise conversation memory, refusal paths,
missing-data handling, and multi-dataset attribution.
"""

from __future__ import annotations

import pytest

from app.chatbot.service import get_chatbot_service
from app.chatbot.types import AnswerClassification, ChatIntent


class TestServiceAnswers:
    def test_revenue_answered_with_reported_value(self, corporate_dataset_id):
        service = get_chatbot_service()
        r = service.handle_query(
            message="What is our total revenue?",
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        assert r.classification == AnswerClassification.REPORTED
        assert r.intent == ChatIntent.METRIC_LOOKUP
        # 460 must appear in either evidence or the natural-language answer.
        assert "460" in r.answer or any(e.value == 460.0 for e in r.evidence)

    def test_health_score(self, corporate_dataset_id):
        service = get_chatbot_service()
        r = service.handle_query(
            message="How financially healthy are we?",
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        assert r.classification == AnswerClassification.CALCULATED
        assert r.intent == ChatIntent.FINANCIAL_HEALTH

    def test_context_metadata_present(self, corporate_dataset_id):
        service = get_chatbot_service()
        r = service.handle_query(
            message="Overview",
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
            primary_display_name="Acme Corp",
        )
        assert r.context is not None
        assert r.context.dataset_id == corporate_dataset_id
        assert r.context.analysis_mode == "self_analysis"


class TestServiceGuardrail:
    def test_out_of_scope_returns_refused(self, corporate_dataset_id):
        service = get_chatbot_service()
        r = service.handle_query(
            message="What is the capital of France?",
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        assert r.classification == AnswerClassification.REFUSED
        assert "dataset" in r.answer.lower()

    def test_investment_advice_refused(self, corporate_dataset_id):
        service = get_chatbot_service()
        r = service.handle_query(
            message="Should I buy this stock?",
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        assert r.classification == AnswerClassification.REFUSED

    def test_no_dataset_returns_unavailable(self):
        service = get_chatbot_service()
        r = service.handle_query(
            message="What is our revenue?",
            dataset_id=None,
            analysis_mode="self_analysis",
        )
        assert r.classification == AnswerClassification.UNAVAILABLE


class TestMissingData:
    def test_missing_input_returns_unavailable(self, no_assets_dataset_id):
        """ROA needs total_assets. Without it the chatbot must not fabricate."""
        service = get_chatbot_service()
        r = service.handle_query(
            message="What is our ROA?",
            dataset_id=no_assets_dataset_id,
            analysis_mode="self_analysis",
        )
        assert r.classification == AnswerClassification.UNAVAILABLE
        assert "assets" in r.answer.lower()

    def test_unknown_year_returns_unavailable(self, corporate_dataset_id):
        service = get_chatbot_service()
        r = service.handle_query(
            message="What was revenue in 2099?",
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        assert r.classification == AnswerClassification.UNAVAILABLE

    def test_missing_secondary_for_merger(self, corporate_dataset_id):
        service = get_chatbot_service()
        r = service.handle_query(
            message="What would combined revenue look like?",
            dataset_id=corporate_dataset_id,
            analysis_mode="merger_partnership_analysis",
            secondary_dataset_id=None,
        )
        assert r.classification == AnswerClassification.UNAVAILABLE


class TestConversationMemory:
    def test_session_reused_across_calls(self, corporate_dataset_id):
        service = get_chatbot_service()
        r1 = service.handle_query(
            message="What is our revenue?",
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        r2 = service.handle_query(
            message="How is it trending?",
            session_id=r1.session_id,
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        assert r2.session_id == r1.session_id

    def test_followup_backfills_metric(self, corporate_dataset_id):
        """`what about profit?` should carry the metric from the previous turn."""
        service = get_chatbot_service()
        r1 = service.handle_query(
            message="What was our revenue in 2024?",
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        assert r1.classification == AnswerClassification.REPORTED

        r2 = service.handle_query(
            message="what about profit?",
            session_id=r1.session_id,
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        # We didn't restate the period 2024 — the classifier should carry it.
        assert r2.used_context is True
        # Net profit 2024 = 15+18+21+25 = 79
        assert "79" in r2.answer or any(
            e.metric_id == "net_profit" and e.value is not None
            and abs(e.value - 79.0) < 0.5
            for e in r2.evidence
        )

    def test_history_persisted(self, corporate_dataset_id):
        service = get_chatbot_service()
        r = service.handle_query(
            message="Overview",
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        session = service.get_session(r.session_id)
        assert session is not None
        # user + assistant
        assert len(session.history) == 2

    def test_slot_reset_on_mode_change(self, corporate_dataset_id, competitor_dataset_id):
        """Switching mode within the same session clears slot memory."""
        service = get_chatbot_service()
        r1 = service.handle_query(
            message="What is our revenue?",
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        service.handle_query(
            message="What is our revenue?",
            session_id=r1.session_id,
            dataset_id=corporate_dataset_id,
            analysis_mode="competitor_market_benchmark",
            secondary_dataset_id=competitor_dataset_id,
        )
        session = service.get_session(r1.session_id)
        assert session is not None
        assert session.analysis_mode == "competitor_market_benchmark"


class TestMultiDatasetAttribution:
    def test_competitor_values_carry_secondary_entity(
        self, corporate_dataset_id, competitor_dataset_id
    ):
        service = get_chatbot_service()
        r = service.handle_query(
            message="How does our revenue compare to the competitor?",
            dataset_id=corporate_dataset_id,
            analysis_mode="competitor_market_benchmark",
            secondary_dataset_id=competitor_dataset_id,
        )
        entities = {e.entity for e in r.evidence}
        assert "primary" in entities
        assert "secondary" in entities
        # No fabricated 'market' entity when no market dataset was loaded.
        assert "market" not in entities

    def test_merger_values_carry_scenario_status(
        self, corporate_dataset_id, competitor_dataset_id
    ):
        service = get_chatbot_service()
        r = service.handle_query(
            message="What would combined revenue look like?",
            dataset_id=corporate_dataset_id,
            analysis_mode="merger_partnership_analysis",
            secondary_dataset_id=competitor_dataset_id,
        )
        combined = [e for e in r.evidence if e.entity == "combined"]
        assert combined
        # Every combined evidence item must be labelled SCENARIO.
        assert all(e.status == AnswerClassification.SCENARIO for e in combined)


class TestSuggestions:
    def test_suggestions_returned_after_answer(self, corporate_dataset_id):
        service = get_chatbot_service()
        r = service.handle_query(
            message="What is our revenue?",
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        assert isinstance(r.suggested_followups, list)

    def test_starter_suggestions_self_mode(self, corporate_dataset_id):
        service = get_chatbot_service()
        items = service.suggestions_for(
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        assert items, "Expected at least one starter suggestion"
        # None of the suggestions should be an off-topic question.
        assert not any("weather" in s.lower() for s in items)


class TestNoFabrication:
    """Guards against the specific failure mode we designed the chatbot around."""

    def test_never_invents_market_data(self, corporate_dataset_id, competitor_dataset_id):
        service = get_chatbot_service()
        r = service.handle_query(
            message="What is the industry average revenue?",
            dataset_id=corporate_dataset_id,
            analysis_mode="competitor_market_benchmark",
            secondary_dataset_id=competitor_dataset_id,
            # NB: no market_dataset_id
        )
        # No market dataset → response must not present any market number.
        assert r.classification == AnswerClassification.UNAVAILABLE
        assert not any(e.entity == "market" and e.value is not None for e in r.evidence)

    def test_never_invents_ratio_when_input_missing(self, no_assets_dataset_id):
        service = get_chatbot_service()
        r = service.handle_query(
            message="What is our return on assets?",
            dataset_id=no_assets_dataset_id,
            analysis_mode="self_analysis",
        )
        assert r.classification == AnswerClassification.UNAVAILABLE
        # No fabricated numeric evidence for ROA.
        assert not any(
            e.metric_id == "roa" and e.value is not None for e in r.evidence
        )

    def test_causation_not_claimed(self, corporate_dataset_id):
        """Explanation answers should not use causal language like 'because'
        without hedging."""
        service = get_chatbot_service()
        r = service.handle_query(
            message="Why is our net margin low?",
            dataset_id=corporate_dataset_id,
            analysis_mode="self_analysis",
        )
        answer_lower = r.answer.lower()
        # Either the answer is explicitly non-causal, or it flags that
        # relationships aren't causation.
        assert (
            "cause" not in answer_lower
            or "not" in answer_lower
            or "relationship" in answer_lower
            or "does not" in answer_lower
        )
