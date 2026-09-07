"""Canonical financial-metric registry.

Every ``MetricId`` gets a ``MetricDefinition`` describing its display name,
unit, "which direction is good?" hint, and the alias patterns used by
``semantic_matcher.py`` to turn arbitrary user column names into a single
canonical metric.

The registry is deliberately *narrow* on aliases:
  * ambiguous strings ("income", "cost", "balance") are avoided as
    standalone keywords \u2014 they must be paired with a qualifier
    ("net_income", "cost_of_goods", "cash_balance") to trigger a match
  * word-boundary regexes prevent "revenue" matching "irrelevant_venue"
  * ``exclude`` patterns rule out common look-alikes
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Pattern, Tuple

from app.analysis.types import MetricDirection, MetricId, MetricUnit


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class MetricDefinition:
    metric_id: MetricId
    display_name: str
    unit: MetricUnit
    direction: MetricDirection

    #: Regex patterns (case-insensitive) whose match on a *normalized* column
    #: name means "this column is (probably) this metric".
    patterns: Tuple[Pattern[str], ...] = field(default_factory=tuple)

    #: Patterns whose match on the column name *disqualifies* this metric
    #: (useful for keyword collisions e.g. "revenue_growth" is NOT REVENUE).
    exclude: Tuple[Pattern[str], ...] = field(default_factory=tuple)

    #: A metric produced from other reported metrics by the ratio engine.
    #: These are never matched against columns directly.
    is_derived: bool = False

    #: Rough category, useful for grouping in the UI.
    category: str = "general"


# ---------------------------------------------------------------------------
# Pattern-compilation helper
# ---------------------------------------------------------------------------
def _pat(*terms: str) -> Tuple[Pattern[str], ...]:
    """Compile a list of *word-boundary* substrings into regex patterns.

    A term like ``"gross profit"`` becomes ``r"\\bgross[\\s_-]*profit\\b"``,
    so both ``gross_profit`` and ``gross-profit`` and ``Gross Profit`` match.
    """
    compiled: List[Pattern[str]] = []
    for t in terms:
        parts = re.split(r"\s+", t.strip())
        joined = r"[\s_\-]*".join(re.escape(p) for p in parts)
        compiled.append(re.compile(rf"(?:^|[\s_\-]){joined}(?:$|[\s_\-])", re.IGNORECASE))
    return tuple(compiled)


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------
def _build_registry() -> Dict[MetricId, MetricDefinition]:
    m = MetricId
    return {
        # ================== Income statement (base metrics) ==================
        m.REVENUE: MetricDefinition(
            m.REVENUE, "Revenue", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat(
                "revenue", "revenues", "total revenue", "gross revenue", "net revenue",
                "sales", "gross sales", "net sales", "total sales", "annual sales",
                "turnover", "top line", "total income", "gross income", "operating income",
            ),
            exclude=_pat(
                "revenue growth", "sales growth", "cost of sales", "sales tax",
            ),
            category="income_statement",
        ),
        m.COGS: MetricDefinition(
            m.COGS, "Cost of Goods Sold", MetricUnit.CURRENCY, MetricDirection.LOWER_BETTER,
            patterns=_pat(
                "cogs", "cost of goods sold", "cost of goods", "cost of sales",
                "cost of revenue", "direct costs",
            ),
            category="income_statement",
        ),
        m.GROSS_PROFIT: MetricDefinition(
            m.GROSS_PROFIT, "Gross Profit", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("gross profit", "gross margin absolute"),
            category="income_statement",
        ),
        m.OPERATING_EXPENSES: MetricDefinition(
            m.OPERATING_EXPENSES, "Operating Expenses", MetricUnit.CURRENCY, MetricDirection.LOWER_BETTER,
            patterns=_pat(
                "operating expenses", "opex", "operating expense",
                "sga", "selling general and administrative",
            ),
            category="income_statement",
        ),
        m.EXPENSES_TOTAL: MetricDefinition(
            m.EXPENSES_TOTAL, "Total Expenses", MetricUnit.CURRENCY, MetricDirection.LOWER_BETTER,
            patterns=_pat(
                "total expenses", "total costs", "expenses total", "all expenses",
            ),
            category="income_statement",
        ),
        m.OPERATING_PROFIT: MetricDefinition(
            m.OPERATING_PROFIT, "Operating Profit", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat(
                "operating profit", "operating income", "operating earnings",
            ),
            category="income_statement",
        ),
        m.EBITDA: MetricDefinition(
            m.EBITDA, "EBITDA", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("ebitda"),
            category="income_statement",
        ),
        m.EBIT: MetricDefinition(
            m.EBIT, "EBIT", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("ebit"),
            exclude=_pat("ebitda"),
            category="income_statement",
        ),
        m.INTEREST_EXPENSE: MetricDefinition(
            m.INTEREST_EXPENSE, "Interest Expense", MetricUnit.CURRENCY, MetricDirection.LOWER_BETTER,
            patterns=_pat("interest expense", "interest paid", "finance cost"),
            category="income_statement",
        ),
        m.INTEREST_INCOME: MetricDefinition(
            m.INTEREST_INCOME, "Interest Income", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("interest income", "interest earned"),
            exclude=_pat("net interest income", "non interest income"),
            category="income_statement",
        ),
        m.TAX: MetricDefinition(
            m.TAX, "Tax", MetricUnit.CURRENCY, MetricDirection.NEUTRAL,
            patterns=_pat("tax", "income tax", "tax expense"),
            exclude=_pat("tax rate"),
            category="income_statement",
        ),
        m.NET_PROFIT: MetricDefinition(
            m.NET_PROFIT, "Net Profit", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat(
                "net profit", "net income", "profit after tax", "pat",
                "net earnings", "bottom line",
            ),
            exclude=_pat("net profit margin"),
            category="income_statement",
        ),

        # ================== Balance sheet ==================
        m.ASSETS: MetricDefinition(
            m.ASSETS, "Total Assets", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("total assets", "assets total", "assets"),
            exclude=_pat("current assets", "non current assets", "asset turnover"),
            category="balance_sheet",
        ),
        m.CURRENT_ASSETS: MetricDefinition(
            m.CURRENT_ASSETS, "Current Assets", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("current assets"),
            category="balance_sheet",
        ),
        m.NON_CURRENT_ASSETS: MetricDefinition(
            m.NON_CURRENT_ASSETS, "Non-Current Assets", MetricUnit.CURRENCY, MetricDirection.NEUTRAL,
            patterns=_pat("non current assets", "long term assets", "fixed assets"),
            category="balance_sheet",
        ),
        m.CASH: MetricDefinition(
            m.CASH, "Cash", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat(
                "cash", "cash and equivalents", "cash on hand", "cash balance",
            ),
            exclude=_pat("cash flow", "free cash flow"),
            category="balance_sheet",
        ),
        m.INVENTORY: MetricDefinition(
            m.INVENTORY, "Inventory", MetricUnit.CURRENCY, MetricDirection.NEUTRAL,
            patterns=_pat("inventory", "inventories", "stock"),
            category="balance_sheet",
        ),
        m.RECEIVABLES: MetricDefinition(
            m.RECEIVABLES, "Receivables", MetricUnit.CURRENCY, MetricDirection.NEUTRAL,
            patterns=_pat(
                "receivables", "accounts receivable", "trade receivables", "debtors",
            ),
            category="balance_sheet",
        ),
        m.LIABILITIES: MetricDefinition(
            m.LIABILITIES, "Total Liabilities", MetricUnit.CURRENCY, MetricDirection.LOWER_BETTER,
            patterns=_pat("total liabilities", "liabilities total", "liabilities"),
            exclude=_pat("current liabilities", "non current liabilities"),
            category="balance_sheet",
        ),
        m.CURRENT_LIABILITIES: MetricDefinition(
            m.CURRENT_LIABILITIES, "Current Liabilities", MetricUnit.CURRENCY, MetricDirection.LOWER_BETTER,
            patterns=_pat("current liabilities"),
            category="balance_sheet",
        ),
        m.DEBT: MetricDefinition(
            m.DEBT, "Debt", MetricUnit.CURRENCY, MetricDirection.LOWER_BETTER,
            patterns=_pat(
                "debt", "total debt", "long term debt", "borrowings", "loans payable",
            ),
            exclude=_pat("debt to equity", "debt ratio"),
            category="balance_sheet",
        ),
        m.EQUITY: MetricDefinition(
            m.EQUITY, "Equity", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat(
                "equity", "shareholders equity", "stockholders equity",
                "total equity", "net worth",
            ),
            exclude=_pat("return on equity", "debt to equity"),
            category="balance_sheet",
        ),
        m.WORKING_CAPITAL: MetricDefinition(
            m.WORKING_CAPITAL, "Working Capital", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("working capital"),
            category="balance_sheet",
        ),

        # ================== Cash flow ==================
        m.CASH_FLOW_OPERATIONS: MetricDefinition(
            m.CASH_FLOW_OPERATIONS, "Operating Cash Flow", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("operating cash flow", "cash flow from operations", "cfo"),
            category="cash_flow",
        ),
        m.FREE_CASH_FLOW: MetricDefinition(
            m.FREE_CASH_FLOW, "Free Cash Flow", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("free cash flow", "fcf"),
            category="cash_flow",
        ),
        m.CAPEX: MetricDefinition(
            m.CAPEX, "Capital Expenditure", MetricUnit.CURRENCY, MetricDirection.NEUTRAL,
            patterns=_pat("capex", "capital expenditure", "capital expenditures"),
            category="cash_flow",
        ),

        # ================== Business ==================
        m.CUSTOMERS: MetricDefinition(
            m.CUSTOMERS, "Customers", MetricUnit.COUNT, MetricDirection.HIGHER_BETTER,
            patterns=_pat(
                "customers", "customer count", "number of customers",
                "total customers", "active customers",
            ),
            exclude=_pat("customer id"),
            category="business",
        ),
        m.TRANSACTIONS: MetricDefinition(
            m.TRANSACTIONS, "Transactions", MetricUnit.COUNT, MetricDirection.HIGHER_BETTER,
            patterns=_pat(
                "transactions", "transaction count", "number of transactions",
                "total transactions",
            ),
            exclude=_pat("transaction id"),
            category="business",
        ),
        m.ORDERS: MetricDefinition(
            m.ORDERS, "Orders", MetricUnit.COUNT, MetricDirection.HIGHER_BETTER,
            patterns=_pat("orders", "order count", "total orders"),
            exclude=_pat("order id"),
            category="business",
        ),
        m.EMPLOYEES: MetricDefinition(
            m.EMPLOYEES, "Employees", MetricUnit.COUNT, MetricDirection.NEUTRAL,
            patterns=_pat("employees", "headcount", "staff count", "workforce"),
            category="business",
        ),

        # ================== Banking-specific ==================
        m.DEPOSITS: MetricDefinition(
            m.DEPOSITS, "Total Deposits", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("deposits", "total deposits", "customer deposits"),
            exclude=_pat("deposit growth"),
            category="banking",
        ),
        m.CASA: MetricDefinition(
            m.CASA, "CASA Deposits", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("casa", "casa deposits", "current and savings"),
            exclude=_pat("casa ratio"),
            category="banking",
        ),
        m.LOANS: MetricDefinition(
            m.LOANS, "Loans / Advances", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("loans", "advances", "gross loans", "net loans", "total loans"),
            exclude=_pat("loan growth", "loans payable", "loans to deposits"),
            category="banking",
        ),
        m.NET_INTEREST_INCOME: MetricDefinition(
            m.NET_INTEREST_INCOME, "Net Interest Income", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("net interest income", "nii"),
            category="banking",
        ),
        m.NON_INTEREST_INCOME: MetricDefinition(
            m.NON_INTEREST_INCOME, "Non-Interest Income", MetricUnit.CURRENCY, MetricDirection.HIGHER_BETTER,
            patterns=_pat("non interest income", "other income", "fee income"),
            category="banking",
        ),
        m.GROSS_NPA: MetricDefinition(
            m.GROSS_NPA, "Gross NPA", MetricUnit.CURRENCY, MetricDirection.LOWER_BETTER,
            patterns=_pat("gross npa", "gross non performing", "gnpa"),
            category="banking",
        ),
        m.NET_NPA: MetricDefinition(
            m.NET_NPA, "Net NPA", MetricUnit.CURRENCY, MetricDirection.LOWER_BETTER,
            patterns=_pat("net npa", "net non performing", "nnpa"),
            category="banking",
        ),
        m.PROVISIONS: MetricDefinition(
            m.PROVISIONS, "Provisions", MetricUnit.CURRENCY, MetricDirection.NEUTRAL,
            patterns=_pat("provisions", "loan loss provisions", "provision expense"),
            category="banking",
        ),
        m.CAPITAL_ADEQUACY: MetricDefinition(
            m.CAPITAL_ADEQUACY, "Capital Adequacy Ratio", MetricUnit.PERCENT, MetricDirection.HIGHER_BETTER,
            patterns=_pat("capital adequacy", "car", "crar", "capital ratio"),
            category="banking",
        ),

        # ================== Derived ratios (never matched from columns) ==================
        m.GROSS_MARGIN: MetricDefinition(
            m.GROSS_MARGIN, "Gross Margin", MetricUnit.PERCENT, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.OPERATING_MARGIN: MetricDefinition(
            m.OPERATING_MARGIN, "Operating Margin", MetricUnit.PERCENT, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.NET_MARGIN: MetricDefinition(
            m.NET_MARGIN, "Net Profit Margin", MetricUnit.PERCENT, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.ROA: MetricDefinition(
            m.ROA, "Return on Assets", MetricUnit.PERCENT, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.ROE: MetricDefinition(
            m.ROE, "Return on Equity", MetricUnit.PERCENT, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.DEBT_TO_EQUITY: MetricDefinition(
            m.DEBT_TO_EQUITY, "Debt-to-Equity", MetricUnit.RATIO, MetricDirection.LOWER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.CURRENT_RATIO: MetricDefinition(
            m.CURRENT_RATIO, "Current Ratio", MetricUnit.RATIO, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.QUICK_RATIO: MetricDefinition(
            m.QUICK_RATIO, "Quick Ratio", MetricUnit.RATIO, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.ASSET_TURNOVER: MetricDefinition(
            m.ASSET_TURNOVER, "Asset Turnover", MetricUnit.RATIO, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.RECEIVABLES_TURNOVER: MetricDefinition(
            m.RECEIVABLES_TURNOVER, "Receivables Turnover", MetricUnit.RATIO, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.INVENTORY_TURNOVER: MetricDefinition(
            m.INVENTORY_TURNOVER, "Inventory Turnover", MetricUnit.RATIO, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.INTEREST_COVERAGE: MetricDefinition(
            m.INTEREST_COVERAGE, "Interest Coverage", MetricUnit.RATIO, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.FCF_MARGIN: MetricDefinition(
            m.FCF_MARGIN, "Free Cash Flow Margin", MetricUnit.PERCENT, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio",
        ),
        m.COST_TO_INCOME: MetricDefinition(
            m.COST_TO_INCOME, "Cost-to-Income", MetricUnit.PERCENT, MetricDirection.LOWER_BETTER,
            is_derived=True, category="ratio_banking",
        ),
        m.NIM: MetricDefinition(
            m.NIM, "Net Interest Margin", MetricUnit.PERCENT, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio_banking",
        ),
        m.CREDIT_DEPOSIT_RATIO: MetricDefinition(
            m.CREDIT_DEPOSIT_RATIO, "Credit-to-Deposit Ratio", MetricUnit.PERCENT, MetricDirection.NEUTRAL,
            is_derived=True, category="ratio_banking",
        ),
        m.PROVISION_COVERAGE: MetricDefinition(
            m.PROVISION_COVERAGE, "Provision Coverage Ratio", MetricUnit.PERCENT, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio_banking",
        ),
        m.CASA_RATIO: MetricDefinition(
            m.CASA_RATIO, "CASA Ratio", MetricUnit.PERCENT, MetricDirection.HIGHER_BETTER,
            is_derived=True, category="ratio_banking",
        ),
    }


METRIC_REGISTRY: Dict[MetricId, MetricDefinition] = _build_registry()


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------
def get_definition(metric_id: MetricId) -> MetricDefinition:
    return METRIC_REGISTRY[metric_id]


def base_metrics() -> List[MetricDefinition]:
    """Metrics that can be matched from column names."""
    return [d for d in METRIC_REGISTRY.values() if not d.is_derived]


def derived_metrics() -> List[MetricDefinition]:
    return [d for d in METRIC_REGISTRY.values() if d.is_derived]


def match_column(name: str) -> Optional[Tuple[MetricId, float]]:
    """Return the best matching metric id for a column name, or None.

    Confidence starts at 1.0 for word-boundary matches; longer/more-specific
    aliases beat generic ones. If an ``exclude`` pattern also matches, the
    candidate is dropped even if a positive pattern hit.
    """
    if not name:
        return None
    key = f" {name} "  # sentinel so ^ / $ anchors don't matter
    best: Optional[Tuple[MetricId, float]] = None
    best_specificity = -1

    for definition in base_metrics():
        # Disqualify if any exclude pattern matches.
        if any(p.search(key) for p in definition.exclude):
            continue

        for pat in definition.patterns:
            match = pat.search(key)
            if not match:
                continue
            # Longer matched substring => more specific => higher confidence.
            specificity = len(match.group(0))
            confidence = min(1.0, 0.65 + specificity * 0.04)
            if specificity > best_specificity:
                best = (definition.metric_id, round(confidence, 4))
                best_specificity = specificity
            break  # first pattern hit is enough per definition

    return best
