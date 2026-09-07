"""Guardrail tests — the finance-first scope gate.

Every allow / refuse rule the guardrail advertises has an assertion here.
The goal is to be able to change the vocabulary lists in the future and
find out quickly whether the guardrail still admits the right questions
and refuses the wrong ones.
"""

from __future__ import annotations

import pytest

from app.chatbot.guardrail import evaluate


# ---------------------------------------------------------------------------
# Positive cases — must be allowed
# ---------------------------------------------------------------------------
class TestGuardrailAllows:
    @pytest.mark.parametrize(
        "question",
        [
            "What was our revenue in 2024?",
            "Show me our net profit margin",
            "How financially healthy are we?",
            "What is our debt-to-equity ratio?",
            "What is our ROE?",
            "How is revenue trending?",
            "What are the biggest financial risks?",
            "What would combined revenue look like?",
            "Where are we behind the competitor?",
            "What is our biggest gap?",
            "How many rows are in the dataset?",
            "What columns do we have?",
            "Show me the data quality score",
            "What synergies could exist?",
            "How compatible are the two companies?",
        ],
    )
    def test_finance_question_allowed(self, question):
        v = evaluate(question)
        assert v.allowed, f"Expected {question!r} to be allowed. Reason: {v.reason}"

    def test_followup_with_history_allowed(self):
        v = evaluate("what about 2024?", has_conversation_history=True)
        assert v.allowed is True

    def test_greeting_allowed(self):
        assert evaluate("hi").allowed is True
        assert evaluate("hello").allowed is True

    def test_help_allowed(self):
        assert evaluate("help").allowed is True
        assert evaluate("what can you do?").allowed is True


# ---------------------------------------------------------------------------
# Negative cases — must be refused
# ---------------------------------------------------------------------------
class TestGuardrailRejects:
    @pytest.mark.parametrize(
        "question",
        [
            "What is the capital of France?",
            "What is the weather today?",
            "Who is the president of the United States?",
            "Tell me a joke",
            "What is the population of India?",
            "Who wrote Hamlet?",
            "Recommend a good movie on Netflix",
            "What is my age?",
            "Give me a chicken recipe",
            "Write a Python program to sort an array",
            "Explain kubernetes to me",
        ],
    )
    def test_out_of_scope_rejected(self, question):
        v = evaluate(question)
        assert v.allowed is False, f"Expected {question!r} to be refused"
        assert v.category in ("off_topic", "advice")

    @pytest.mark.parametrize(
        "question",
        [
            "Should I buy Tesla stock?",
            "Should I sell my portfolio?",
            "Give me a guaranteed return investment",
            "Which stock should I buy tomorrow?",
            "Give me a hot stock tip",
            "What's the best stock pick right now?",
            "Approve my loan application",
        ],
    )
    def test_investment_advice_rejected(self, question):
        v = evaluate(question)
        assert v.allowed is False
        assert v.category == "advice"

    def test_empty_rejected(self):
        assert evaluate("").allowed is False
        assert evaluate("  ").allowed is False

    def test_none_rejected(self):
        assert evaluate(None).allowed is False  # type: ignore[arg-type]

    def test_too_long_rejected(self):
        v = evaluate("a" * 3000)
        assert v.allowed is False
        assert v.category == "too_long"

    def test_followup_without_history_still_rejected_if_no_keywords(self):
        # "what about 2024" isn't a finance question — with no prior context
        # we should not silently pass it through.
        v = evaluate("what about 2024?", has_conversation_history=False)
        assert v.allowed is False


# ---------------------------------------------------------------------------
# Refusal message quality
# ---------------------------------------------------------------------------
class TestGuardrailMessages:
    def test_refusal_has_helpful_message(self):
        v = evaluate("What is the capital of France?")
        assert v.refusal_message
        assert "dataset" in v.refusal_message.lower()

    def test_advice_refusal_mentions_own_decisions(self):
        v = evaluate("Should I buy Tesla stock?")
        assert v.refusal_message
        assert "recommend" in v.refusal_message.lower() or "advice" in v.refusal_message.lower() or "guaranteed" in v.refusal_message.lower()
