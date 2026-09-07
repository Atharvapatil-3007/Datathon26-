"""Semantic resolution helpers.

Given a natural-language question we need to figure out:
  * which canonical ``MetricId`` values it references
  * which time period(s)
  * which entity (primary / secondary / market / combined)

We deliberately reuse the metric registry (word-boundary regex patterns)
that Phase 3 already uses to match columns — extended with a small set of
chat-friendly aliases like "roe" or "return on equity". That way the
chatbot honours the same taxonomy as the analytical engine and never
invents metric identifiers.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Pattern, Sequence, Tuple

from app.analysis.metric_registry import METRIC_REGISTRY
from app.analysis.types import MetricId
from app.chatbot.types import EntityRef, PeriodRef


# ---------------------------------------------------------------------------
# Extra chat-friendly aliases beyond what the registry uses for columns.
# These are matched *in addition* to the registry patterns.
# ---------------------------------------------------------------------------
def _pat(*terms: str) -> Tuple[Pattern[str], ...]:
    compiled: List[Pattern[str]] = []
    for t in terms:
        parts = re.split(r"\s+", t.strip())
        joined = r"[\s_\-]*".join(re.escape(p) for p in parts)
        compiled.append(re.compile(rf"(?:^|[\s_\-]){joined}(?:$|[\s_\-\?\.\!,])", re.IGNORECASE))
    return tuple(compiled)


_CHAT_ALIASES: Dict[MetricId, Tuple[Pattern[str], ...]] = {
    MetricId.REVENUE: _pat(
        "revenue", "sales", "top line", "topline", "turnover",
    ),
    MetricId.NET_PROFIT: _pat(
        "net profit", "net income", "profit after tax", "pat", "bottom line",
        "profit", "profits", "earnings",
    ),
    MetricId.OPERATING_PROFIT: _pat("operating profit", "operating income"),
    MetricId.EBITDA: _pat("ebitda"),
    MetricId.EBIT: _pat("ebit"),
    MetricId.GROSS_PROFIT: _pat("gross profit"),
    MetricId.OPERATING_EXPENSES: _pat("operating expenses", "opex"),
    MetricId.EXPENSES_TOTAL: _pat("total expenses", "expenses", "costs"),
    MetricId.INTEREST_EXPENSE: _pat("interest expense", "interest cost", "finance cost"),
    MetricId.INTEREST_INCOME: _pat("interest income"),
    MetricId.TAX: _pat("tax", "taxes", "tax expense"),
    MetricId.COGS: _pat("cogs", "cost of goods", "cost of goods sold", "cost of sales"),
    MetricId.ASSETS: _pat("total assets", "assets"),
    MetricId.CURRENT_ASSETS: _pat("current assets"),
    MetricId.NON_CURRENT_ASSETS: _pat("non current assets", "fixed assets"),
    MetricId.LIABILITIES: _pat("total liabilities", "liabilities"),
    MetricId.CURRENT_LIABILITIES: _pat("current liabilities"),
    MetricId.EQUITY: _pat("equity", "shareholders equity", "net worth"),
    MetricId.DEBT: _pat("debt", "borrowings", "total debt", "long term debt"),
    MetricId.CASH: _pat("cash", "cash balance", "cash on hand", "cash and equivalents"),
    MetricId.INVENTORY: _pat("inventory", "inventories", "stock"),
    MetricId.RECEIVABLES: _pat("receivables", "accounts receivable", "trade receivables"),
    MetricId.WORKING_CAPITAL: _pat("working capital"),
    MetricId.FREE_CASH_FLOW: _pat("free cash flow", "fcf"),
    MetricId.CASH_FLOW_OPERATIONS: _pat("operating cash flow", "cash from operations"),
    MetricId.CAPEX: _pat("capex", "capital expenditure"),
    MetricId.CUSTOMERS: _pat(
        "customers", "customer count", "number of customers", "active customers",
        "clients", "client count",
    ),
    MetricId.TRANSACTIONS: _pat("transactions", "transaction count"),
    MetricId.ORDERS: _pat("orders", "order count"),
    MetricId.EMPLOYEES: _pat("employees", "headcount", "staff"),
    MetricId.DEPOSITS: _pat("deposits"),
    MetricId.CASA: _pat("casa", "casa deposits"),
    MetricId.LOANS: _pat("loans", "advances"),
    MetricId.NET_INTEREST_INCOME: _pat("net interest income", "nii"),
    MetricId.NON_INTEREST_INCOME: _pat("non interest income", "fee income"),
    MetricId.GROSS_NPA: _pat("gross npa", "gnpa"),
    MetricId.NET_NPA: _pat("net npa", "nnpa"),
    MetricId.PROVISIONS: _pat("provisions"),
    MetricId.CAPITAL_ADEQUACY: _pat("capital adequacy", "car", "crar"),
    # ratios
    MetricId.GROSS_MARGIN: _pat("gross margin"),
    MetricId.OPERATING_MARGIN: _pat("operating margin"),
    MetricId.NET_MARGIN: _pat(
        "net margin", "net profit margin", "profit margin",
    ),
    MetricId.ROA: _pat("roa", "return on assets"),
    MetricId.ROE: _pat("roe", "return on equity"),
    MetricId.DEBT_TO_EQUITY: _pat("debt to equity", "debt-to-equity", "d/e", "d e ratio"),
    MetricId.CURRENT_RATIO: _pat("current ratio"),
    MetricId.QUICK_RATIO: _pat("quick ratio", "acid test"),
    MetricId.ASSET_TURNOVER: _pat("asset turnover"),
    MetricId.RECEIVABLES_TURNOVER: _pat("receivables turnover"),
    MetricId.INVENTORY_TURNOVER: _pat("inventory turnover"),
    MetricId.INTEREST_COVERAGE: _pat("interest coverage"),
    MetricId.FCF_MARGIN: _pat("fcf margin", "free cash flow margin"),
    MetricId.COST_TO_INCOME: _pat("cost to income", "cost-to-income", "cir"),
    MetricId.NIM: _pat("nim", "net interest margin"),
    MetricId.CREDIT_DEPOSIT_RATIO: _pat("credit deposit", "credit-deposit", "cd ratio"),
    MetricId.PROVISION_COVERAGE: _pat("provision coverage"),
    MetricId.CASA_RATIO: _pat("casa ratio"),
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def resolve_metrics(text: str) -> List[Tuple[MetricId, float]]:
    """Return every canonical metric mentioned in ``text``.

    Uses the union of registry patterns and chat-friendly aliases. Each
    match is scored by the length of the matched substring, then converted
    to a confidence in [0, 1]. Ties are broken by raw match length so a
    longer, more specific phrase ("net profit margin") always wins against
    a shorter one that also fits ("profit").

    The list is deduplicated and sorted by descending confidence, with
    length as the tie-breaker.
    """
    if not text:
        return []
    key = f" {text} "
    # metric_id -> best (specificity_length, longest matched substring)
    best_length: Dict[MetricId, int] = {}

    for metric_id, defn in METRIC_REGISTRY.items():
        if defn.is_derived and metric_id not in _CHAT_ALIASES:
            # ratios that we don't chat about won't be extractable
            continue

        # Exclude patterns still block
        if any(p.search(key) for p in defn.exclude):
            continue

        patterns = _combined_patterns(metric_id, defn.patterns)
        longest = 0
        for pat in patterns:
            m = pat.search(key)
            if not m:
                continue
            length = len(m.group(0))
            if length > longest:
                longest = length
        if longest > 0:
            best_length[metric_id] = longest

    ranked = sorted(best_length.items(), key=lambda kv: kv[1], reverse=True)
    return [(mid, min(1.0, round(0.6 + length * 0.03, 4))) for mid, length in ranked]


def _combined_patterns(
    metric_id: MetricId, registry_patterns: Sequence[Pattern[str]]
) -> Tuple[Pattern[str], ...]:
    chat = _CHAT_ALIASES.get(metric_id, ())
    return tuple(list(registry_patterns) + list(chat))


# ---------------------------------------------------------------------------
# Period resolution
# ---------------------------------------------------------------------------
_YEAR_RE = re.compile(r"\b(?:fy|fiscal\s+year\s+)?(\d{4})\b", re.IGNORECASE)
_QUARTER_RE = re.compile(r"\bq([1-4])\s*[-\s/]?\s*(?:fy\s*)?(\d{4})?\b", re.IGNORECASE)
_QUARTER_OF_RE = re.compile(
    r"\b(first|second|third|fourth|1st|2nd|3rd|4th)\s+quarter\s+(?:of\s+)?(\d{4})?\b",
    re.IGNORECASE,
)
# "from 2023 to 2025", "2023 through 2025" — one continuous span
_RANGE_RE = re.compile(
    r"\b(?:fy)?(\d{4})\s*(?:to|through|thru|until)\s*(?:fy)?(\d{4})\b",
    re.IGNORECASE,
)
# "2024 vs 2025", "2024 and 2025", "2024-2025" — two distinct periods
_COMPARISON_PAIR_RE = re.compile(
    r"\b(?:fy)?(\d{4})\s*(?:vs\.?|versus|and|-)\s*(?:fy)?(\d{4})\b",
    re.IGNORECASE,
)

_RELATIVE_PATTERNS: Tuple[Tuple[str, str], ...] = (
    ("last year", "previous"),
    ("previous year", "previous"),
    ("prior year", "previous"),
    ("year before", "previous"),
    ("this year", "latest"),
    ("current year", "latest"),
    ("latest year", "latest"),
    ("most recent", "latest"),
    ("last quarter", "previous"),
    ("previous quarter", "previous"),
    ("this quarter", "latest"),
    ("current quarter", "latest"),
    ("latest quarter", "latest"),
)


_ORDINAL_QUARTER = {
    "first": 1, "1st": 1,
    "second": 2, "2nd": 2,
    "third": 3, "3rd": 3,
    "fourth": 4, "4th": 4,
}


def resolve_periods(text: str) -> List[PeriodRef]:
    """Extract every distinct period mention in ``text``.

    Handles years (``2024``, ``FY2024``), quarters (``Q3 2024``, ``third
    quarter 2024``), relative phrasings (``last year`` / ``this quarter``),
    and simple ranges (``2023 to 2025``).
    """
    if not text:
        return []
    lower = text.lower()
    out: List[PeriodRef] = []
    seen_years: set = set()

    # 1. Comparison pairs first — "2024 vs 2025" means "two separate periods".
    for m in _COMPARISON_PAIR_RE.finditer(lower):
        y1, y2 = int(m.group(1)), int(m.group(2))
        for y in (y1, y2):
            if y in seen_years:
                continue
            if not (1970 <= y <= 2100):
                continue
            out.append(PeriodRef(kind="year", label=f"FY{y}", year=y, raw=str(y)))
            seen_years.add(y)

    # 2. Explicit "from X to Y" spans — one continuous range.
    for m in _RANGE_RE.finditer(lower):
        y1, y2 = int(m.group(1)), int(m.group(2))
        if y1 in seen_years and y2 in seen_years:
            continue
        if y1 > y2:
            y1, y2 = y2, y1
        out.append(
            PeriodRef(
                kind="range",
                label=f"{y1}-{y2}",
                start_year=y1,
                end_year=y2,
                raw=m.group(0),
            )
        )
        seen_years.update({y1, y2})

    # 2. quarters (numeric)
    for m in _QUARTER_RE.finditer(lower):
        q = int(m.group(1))
        y_raw = m.group(2)
        year = int(y_raw) if y_raw else None
        label = f"Q{q}" + (f" {year}" if year else "")
        out.append(
            PeriodRef(
                kind="quarter",
                label=label,
                year=year,
                quarter=q,
                raw=m.group(0),
            )
        )

    # 3. quarters (ordinal, e.g. "third quarter of 2024")
    for m in _QUARTER_OF_RE.finditer(lower):
        q = _ORDINAL_QUARTER.get(m.group(1).lower())
        if not q:
            continue
        y_raw = m.group(2)
        year = int(y_raw) if y_raw else None
        label = f"Q{q}" + (f" {year}" if year else "")
        out.append(
            PeriodRef(kind="quarter", label=label, year=year, quarter=q, raw=m.group(0))
        )

    # 4. bare years
    for m in _YEAR_RE.finditer(lower):
        year = int(m.group(1))
        if year in seen_years:
            continue
        if not (1970 <= year <= 2100):
            continue
        out.append(PeriodRef(kind="year", label=f"FY{year}", year=year, raw=m.group(0)))
        seen_years.add(year)

    # 5. relative phrases
    for phrase, kind in _RELATIVE_PATTERNS:
        if phrase in lower:
            out.append(PeriodRef(kind=kind, label=phrase, raw=phrase))

    return out


# ---------------------------------------------------------------------------
# Entity resolution
# ---------------------------------------------------------------------------
_SECONDARY_TERMS = (
    "competitor", "competitor's", "competition", "peer", "rival",
    "the other", "other company", "target", "target company",
    "acquiree", "acquirer", "partner", "partnership target", "them", "theirs",
)

_MARKET_TERMS = (
    "market", "industry", "benchmark",
    "peer average", "peer averages", "peer median", "peer medians",
    "market average", "market averages",
    "industry average", "industry averages", "industry benchmark",
)

_COMBINED_TERMS = (
    "combined", "merged", "post merger", "post-merger", "after the merger",
    "after merger", "combined entity", "merged entity", "combined company",
    "combined revenue", "combined profit", "consolidated",
)

_PRIMARY_TERMS = (
    "our", "we", "us", "ours", "my company", "our company",
    "the primary", "primary company",
)


def resolve_entity(text: str, default: EntityRef = EntityRef.PRIMARY) -> EntityRef:
    """Return which entity the question is asking about."""
    if not text:
        return default
    lower = f" {text.lower()} "

    if _contains_any(lower, _COMBINED_TERMS):
        return EntityRef.COMBINED
    if _contains_any(lower, _MARKET_TERMS):
        return EntityRef.MARKET
    if _contains_any(lower, _SECONDARY_TERMS):
        return EntityRef.SECONDARY
    if _contains_any(lower, _PRIMARY_TERMS):
        return EntityRef.PRIMARY
    return default


def _contains_any(padded_lower: str, terms: Sequence[str]) -> bool:
    for t in terms:
        if f" {t} " in padded_lower or f" {t}." in padded_lower or f" {t}?" in padded_lower or f" {t}," in padded_lower:
            return True
    return False
