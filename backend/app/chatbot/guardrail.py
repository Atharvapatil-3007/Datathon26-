"""Guardrail — decides whether a question is in scope BEFORE any expensive
work (context loading, LLM calls) happens.

The chatbot is finance-first. It should only answer questions about:
  * the currently loaded dataset (Phase 2 profile)
  * the calculated financial metrics / ratios / trends (Phase 3)
  * the selected analysis mode (self / merger / competitor)

Everything else — politics, weather, entertainment, coding help, personal
questions, generic financial advice — is politely refused.

We keep this deliberately simple and *transparent*:
  * an allow-list of finance & dataset keywords
  * a deny-list of out-of-scope topics + advice patterns
  * follow-up questions that reference prior conversation ("what about
    2024?", "and profit?") are allowed even if they don't contain a
    keyword, because the classifier will resolve them from history.

No numbers are trusted from this layer. Its only job is to decide
"answer / refuse".
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, List, Optional, Tuple

from app.chatbot.prompts import (
    INVESTMENT_ADVICE_REFUSAL,
    INVESTMENT_ADVICE_TERMS,
    OUT_OF_SCOPE_MESSAGE,
    OUT_OF_SCOPE_TERMS,
)


# ---------------------------------------------------------------------------
# Vocabulary that keeps a question in scope
# ---------------------------------------------------------------------------
_FINANCE_KEYWORDS: Tuple[str, ...] = (
    # top-level
    "financial", "finance", "financials", "financially",
    "kpi", "kpis",
    # business subjects
    "company", "companies", "business", "our business", "the company",
    "healthy", "unhealthy", "compatible", "compatibility",
    # revenue / sales
    "revenue", "revenues", "sales", "turnover", "topline", "top line",
    "gross revenue", "net revenue", "operating revenue",
    # profit
    "profit", "profits", "profitability", "net profit", "net income",
    "gross profit", "operating profit", "bottom line", "pat", "earnings",
    "ebitda", "ebit",
    # margin
    "margin", "margins", "net margin", "gross margin", "operating margin",
    "profit margin", "fcf margin",
    # expenses
    "expense", "expenses", "cost", "costs", "cogs", "opex", "operating expenses",
    "interest expense", "tax", "depreciation",
    # cash / assets / balance
    "cash", "cash flow", "cashflow", "free cash flow", "fcf", "capex",
    "asset", "assets", "current asset", "non current asset", "fixed assets",
    "inventory", "receivable", "receivables", "payable", "payables",
    "liability", "liabilities", "current liability", "debt", "borrowing",
    "equity", "shareholder", "shareholders equity", "net worth",
    "working capital", "capital",
    # ratios
    "ratio", "ratios", "roa", "roe", "roi", "return on assets", "return on equity",
    "debt to equity", "debt-to-equity", "d/e", "current ratio", "quick ratio",
    "acid test", "asset turnover", "inventory turnover", "receivables turnover",
    "interest coverage", "coverage ratio", "cost to income", "cost-to-income",
    "nim", "net interest margin", "credit deposit", "credit-deposit",
    "provision coverage", "casa ratio",
    # banking
    "deposit", "deposits", "loan", "loans", "advances", "casa",
    "net interest income", "nii", "non interest income", "fee income",
    "npa", "gross npa", "net npa", "provision", "provisions",
    "capital adequacy", "car", "crar",
    # customers / business
    "customer", "customers", "client", "clients", "user", "users",
    "transaction", "transactions", "order", "orders", "employee", "employees",
    "headcount", "staff",
    # trends
    "trend", "trends", "growth", "yoy", "year over year", "year-over-year",
    "quarter over quarter", "qoq", "period over period", "declining",
    "improving", "increasing", "decreasing",
    # analysis modes
    "analysis", "analyze", "analyse", "health", "score", "grade",
    "strengths", "weaknesses", "opportunities", "risks", "swot",
    "recommendation", "recommendations", "recommend",
    "merger", "acquisition", "partnership", "combined", "combine",
    "synergy", "synergies", "compatibility",
    "competitor", "competition", "benchmark", "benchmarks", "benchmarking",
    "peer", "peers", "market", "industry", "gap", "gaps",
    "position", "positioning", "target", "targets", "roadmap",
    # dataset understanding
    "dataset", "data", "column", "columns", "row", "rows", "record",
    "records", "profile", "profiling", "quality", "missing", "duplicate",
    "duplicates", "cardinality", "distribution", "distributions",
    "correlation", "correlations", "outlier", "outliers", "statistics",
    "schema", "type", "types", "field", "fields", "period", "periods",
    "date range", "range",
)


_DATASET_STOPWORD_HINTS: Tuple[str, ...] = (
    # short "meta" nouns that alone might not sound like finance but strongly
    # imply the dataset is the subject.
    "how many", "how much", "when was", "what does the",
)


_FOLLOWUP_PATTERNS: Tuple[re.Pattern, ...] = tuple(
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^\s*(what|how)\s+about\b",
        r"^\s*and\s+(the\s+)?[a-z]",
        r"^\s*and\b\s*[a-z0-9\?]",
        r"^\s*(compared|compare)\s+(with|to)\b",
        r"^\s*(why|how)\s+(is|was|are|were)\b",
        r"^\s*(what|why|which)\s+caused",
        r"^\s*(is|was|are|were)\s+(that|it)\b",
        r"^\s*(show|tell|explain)\s+me\s+(more|why|the)\b",
        r"^\s*(details|more)\s*\??\s*$",
        r"^\s*same\s+for\b",
        r"^\s*for\s+(last|this|next)\s+(year|quarter|month)\b",
    )
)


@dataclass(frozen=True)
class GuardrailVerdict:
    """Outcome of a guardrail check."""

    allowed: bool
    reason: str = ""
    refusal_message: Optional[str] = None
    category: Optional[str] = None  # 'empty' | 'too_long' | 'off_topic' | 'advice'


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------
_MAX_LEN = 2000
_MIN_LEN = 2


def evaluate(question: str, *, has_conversation_history: bool = False) -> GuardrailVerdict:
    """Return whether ``question`` is in scope. Non-raising.

    Parameters
    ----------
    question : str
        Raw user input.
    has_conversation_history : bool
        If True, a follow-up phrase (e.g. "and 2024?") is allowed to bypass
        the keyword allow-list because the classifier will substitute the
        missing slot from prior messages.
    """
    if question is None:
        return GuardrailVerdict(
            allowed=False,
            reason="Empty question.",
            refusal_message="Ask me a question about your dataset or analysis.",
            category="empty",
        )
    text = question.strip()
    if len(text) < _MIN_LEN:
        return GuardrailVerdict(
            allowed=False,
            reason="Question too short.",
            refusal_message="Ask me a question about your dataset or analysis.",
            category="empty",
        )
    if len(text) > _MAX_LEN:
        return GuardrailVerdict(
            allowed=False,
            reason=f"Question exceeds {_MAX_LEN} characters.",
            refusal_message=(
                "That question is too long. Ask a focused question about your "
                "dataset or its analysis and I'll answer it."
            ),
            category="too_long",
        )

    lowered = text.lower()

    # Never allow investment / trading advice, even if it uses finance words.
    if _matches_any(lowered, INVESTMENT_ADVICE_TERMS):
        return GuardrailVerdict(
            allowed=False,
            reason="Investment / autonomous decision request.",
            refusal_message=INVESTMENT_ADVICE_REFUSAL,
            category="advice",
        )

    # Explicit out-of-scope topics.
    if _matches_any(lowered, OUT_OF_SCOPE_TERMS):
        return GuardrailVerdict(
            allowed=False,
            reason="Question is outside the dataset-intelligence domain.",
            refusal_message=OUT_OF_SCOPE_MESSAGE,
            category="off_topic",
        )

    # Positive signals: finance / dataset vocabulary.
    if _matches_any(lowered, _FINANCE_KEYWORDS):
        return GuardrailVerdict(allowed=True)

    # Meta hints (how many rows, etc.)
    if _matches_any(lowered, _DATASET_STOPWORD_HINTS):
        return GuardrailVerdict(allowed=True)

    # Follow-up question relying on prior context.
    if has_conversation_history and _looks_like_followup(text):
        return GuardrailVerdict(allowed=True)

    # Short pleasantries — allowed, will hit the GREETING intent path.
    if _looks_like_greeting(lowered):
        return GuardrailVerdict(allowed=True)

    return GuardrailVerdict(
        allowed=False,
        reason="Question does not mention any dataset, metric, or analysis concept.",
        refusal_message=OUT_OF_SCOPE_MESSAGE,
        category="off_topic",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _matches_any(text: str, terms: Iterable[str]) -> bool:
    """Substring match against a list of lowercase phrases."""
    for term in terms:
        if _has_phrase(text, term):
            return True
    return False


def _has_phrase(text: str, phrase: str) -> bool:
    """True if ``phrase`` occurs as a word-boundary substring.

    We can't use ``\\b`` alone because our phrases may contain punctuation
    (e.g. "debt-to-equity"). Fall back to a simple containment test after
    padding both sides so multi-word phrases still match.
    """
    if " " in phrase or "-" in phrase or "/" in phrase:
        return phrase in f" {text} "
    pattern = rf"\b{re.escape(phrase)}\b"
    return re.search(pattern, text) is not None


def _looks_like_followup(text: str) -> bool:
    return any(p.search(text) for p in _FOLLOWUP_PATTERNS)


_GREETINGS = ("hi", "hello", "hey", "help", "start", "?", "what can you do")


def _looks_like_greeting(lowered: str) -> bool:
    stripped = lowered.strip(" .!?")
    if stripped in _GREETINGS:
        return True
    if len(stripped) <= 12 and any(stripped.startswith(g) for g in ("hi ", "hello", "hey ", "help")):
        return True
    return False
