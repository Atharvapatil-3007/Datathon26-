"""Static text constants used by the chatbot.

Kept in one file so the tone stays consistent and so future translations
have a single place to change. No dataset values are hardcoded here.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# Assistant identity — used if an LLM paraphraser is enabled.
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """You are the Dataset Intelligence Assistant for a
financial analytics platform. You may only answer using the verified dataset
context and analytical evidence supplied by the backend.

Rules:
- Never invent numeric values. Every number in your answer must appear in
  the provided evidence exactly as written.
- Never assume information that was not provided. If a required field is
  missing, say so explicitly.
- Never use external knowledge or claim knowledge of the internet.
- Never claim causation without direct data evidence.
- Never present merger or scenario values as guaranteed forecasts.
- Never provide guaranteed investment returns, autonomous trading decisions,
  or loan / credit approvals.
- Refuse politely if the question is unrelated to the dataset.
- Distinguish reported / calculated / scenario / estimated / unavailable
  values in your prose.
- Be concise. Prefer a short direct answer followed by evidence lines and a
  confidence label.
"""


# ---------------------------------------------------------------------------
# Refusal & fallback prose
# ---------------------------------------------------------------------------
OUT_OF_SCOPE_MESSAGE = (
    "I can only answer questions related to your uploaded dataset and its "
    "financial analysis. Ask me about your financial metrics, trends, ratios, "
    "risks, benchmarks, or analysis results."
)

INVESTMENT_ADVICE_REFUSAL = (
    "I can't provide investment recommendations, guaranteed returns, or "
    "autonomous financial decisions. I can help you analyze your dataset's "
    "financial metrics, ratios, trends, and health so you can make your own "
    "informed decisions."
)

EMPTY_QUERY_MESSAGE = (
    "Ask me a question about your dataset, its metrics, ratios, trends, or "
    "the financial analysis you have open."
)

NO_DATASET_MESSAGE = (
    "I need an uploaded dataset to answer this. Upload one and open it in "
    "the dashboard, then come back to chat."
)

MISSING_ANALYSIS_MESSAGE = (
    "Run an analysis on this dataset first (Self, Merger, or Competitor). "
    "Once it completes I can answer questions about the results."
)

UNSUPPORTED_MODE_MESSAGE = (
    "That question relates to a different analysis mode than the one you "
    "have open. Switch to the matching mode or ask something available in "
    "the current mode."
)

INSUFFICIENT_DATA_TEMPLATE = (
    "I can't calculate {metric} from this dataset because the required "
    "information is unavailable{needed}."
)

CAUSATION_DISCLAIMER = (
    "The dataset shows a relationship between these values but does not by "
    "itself establish that one caused the other."
)

SCENARIO_DISCLAIMER = (
    "Combined figures are a hypothetical scenario, not a forecast."
)

COMPETITOR_DISCLAIMER = (
    "This comparison uses the competitor dataset you uploaded — competitor "
    "strategy, plans, and non-financial context are not inferred."
)


# ---------------------------------------------------------------------------
# Deny-list keywords for the guardrail.
# ---------------------------------------------------------------------------
INVESTMENT_ADVICE_TERMS = (
    "should i buy",
    "should i sell",
    "should i invest",
    "guaranteed return",
    "guaranteed returns",
    "stock recommendation",
    "stock recommendations",
    "stock tip",
    "stock tips",
    "stock pick",
    "stock picks",
    "trading signal",
    "trading strategy",
    "trade for me",
    "invest for me",
    "loan approval",
    "credit approval",
    "approve my loan",
    "approve my credit",
    "approve loan",
    "approve credit",
    "loan application",
    "credit application",
    "which stock",
    "hot stock",
    "best stock",
    "recommend a stock",
    "recommend stocks",
    "pick a stock",
    "suggest a stock",
)


OUT_OF_SCOPE_TERMS = (
    # weather
    "weather",
    "temperature outside",
    # politics
    "president",
    "prime minister",
    "election",
    "political party",
    # sports
    "football",
    "cricket score",
    "world cup",
    "nba",
    "fifa",
    "olympics",
    # entertainment
    "movie",
    "netflix",
    "tv show",
    "song",
    "spotify",
    "actor",
    "actress",
    "celebrity",
    # general knowledge
    "capital of",
    "population of",
    "who invented",
    "who wrote",
    # personal
    "my age",
    "my birthday",
    "girlfriend",
    "boyfriend",
    "recipe",
    "cook",
    "restaurant",
    # tech unrelated
    "javascript",
    "typescript",
    "python code",
    "html",
    "css",
    "kubernetes",
    "docker",
    "leetcode",
    "algorithm question",
)
