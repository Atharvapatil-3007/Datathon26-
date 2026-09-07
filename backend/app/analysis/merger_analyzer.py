"""Merger / partnership analysis.

Assembles the ``AnalysisResult`` for ``AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS``.

Pipeline:
    (primary_id, secondary_id, deal_type?)
      \u2193
    load both bundles (profile + optional DataFrame)
      \u2193
    metric_extractor for each
      \u2193
    _check_compatibility  (schema overlap, unit / period sanity)
      \u2193
    _build_combined_scenario
        \u2192 sum matching *base* metrics, recalculate ratios from combined base
        \u2192 every combined metric labelled MetricStatus.SCENARIO
      \u2193
    _identify_synergies + _identify_risks
      \u2193
    _attractiveness_score
      \u2193
    insight_engine.generate_merger_insights
      \u2193
    AnalysisResult
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

from app.analysis.dataset_loader import load_dataset_bundle
from app.analysis.exceptions import (
    IncompatibleDatasetsError,
    InsufficientDataError,
)
from app.analysis.health_scorer import HealthInputs, score_health
from app.analysis.insight_engine import generate_merger_insights
from app.analysis.metric_extractor import ExtractionResult, extract_metrics
from app.analysis.metric_registry import get_definition
from app.analysis.ratio_engine import compute_ratios
from app.analysis.types import (
    AnalysisMode,
    AnalysisResult,
    CombinedScenario,
    Confidence,
    EntitySnapshot,
    HealthScore,
    LabeledMetric,
    MetricDirection,
    MetricId,
    MetricStatus,
    Priority,
    RiskItem,
    SynergyItem,
)
from app.utils.logging import get_logger


log = get_logger(__name__)


# Base metrics that are *additive* under a merger scenario (flow + stock).
_ADDITIVE_METRICS: Tuple[MetricId, ...] = (
    MetricId.REVENUE,
    MetricId.COGS,
    MetricId.GROSS_PROFIT,
    MetricId.OPERATING_EXPENSES,
    MetricId.EXPENSES_TOTAL,
    MetricId.OPERATING_PROFIT,
    MetricId.EBITDA,
    MetricId.EBIT,
    MetricId.INTEREST_EXPENSE,
    MetricId.INTEREST_INCOME,
    MetricId.TAX,
    MetricId.NET_PROFIT,
    MetricId.ASSETS,
    MetricId.CURRENT_ASSETS,
    MetricId.NON_CURRENT_ASSETS,
    MetricId.CASH,
    MetricId.INVENTORY,
    MetricId.RECEIVABLES,
    MetricId.LIABILITIES,
    MetricId.CURRENT_LIABILITIES,
    MetricId.DEBT,
    MetricId.EQUITY,
    MetricId.WORKING_CAPITAL,
    MetricId.CASH_FLOW_OPERATIONS,
    MetricId.FREE_CASH_FLOW,
    MetricId.CAPEX,
    MetricId.CUSTOMERS,
    MetricId.TRANSACTIONS,
    MetricId.ORDERS,
    MetricId.EMPLOYEES,
    MetricId.DEPOSITS,
    MetricId.CASA,
    MetricId.LOANS,
    MetricId.NET_INTEREST_INCOME,
    MetricId.NON_INTEREST_INCOME,
    MetricId.GROSS_NPA,
    MetricId.NET_NPA,
    MetricId.PROVISIONS,
)


def run_merger_analysis(
    primary_dataset_id: str,
    secondary_dataset_id: str,
    *,
    deal_type: Optional[str] = None,
    primary_display_name: Optional[str] = None,
    secondary_display_name: Optional[str] = None,
) -> AnalysisResult:
    started = time.perf_counter()

    if primary_dataset_id == secondary_dataset_id:
        raise IncompatibleDatasetsError(
            "Primary and secondary datasets must be different.",
        )

    a_row, a_df = load_dataset_bundle(primary_dataset_id)
    b_row, b_df = load_dataset_bundle(secondary_dataset_id)

    a_profile = a_row.get("profile") or {}
    b_profile = b_row.get("profile") or {}

    a_name = primary_display_name or a_row.get("original_filename") or primary_dataset_id
    b_name = secondary_display_name or b_row.get("original_filename") or secondary_dataset_id
    log.info(
        "merger_analysis_started",
        primary=primary_dataset_id,
        secondary=secondary_dataset_id,
        deal_type=deal_type,
    )

    # --- Extract both --------------------------------------------------------
    a_extract = extract_metrics(a_profile, df=a_df)
    b_extract = extract_metrics(b_profile, df=b_df)

    if not a_extract.metrics or not b_extract.metrics:
        raise InsufficientDataError(
            "Both datasets need at least one recognized financial metric.",
        )

    a_ratios = compute_ratios(a_extract.value_map)
    b_ratios = compute_ratios(b_extract.value_map)

    # --- Compatibility check -------------------------------------------------
    warnings = _check_compatibility(a_extract, b_extract, a_row, b_row, deal_type)

    # --- Build combined scenario --------------------------------------------
    combined_scenario, combined_value_map, combined_ratios = _build_combined_scenario(
        a_extract.value_map, b_extract.value_map
    )

    # --- Health scores -------------------------------------------------------
    combined_health = score_health(
        HealthInputs(value_map=combined_value_map, ratios=combined_ratios, trends={})
    )

    # --- Synergies + risks ---------------------------------------------------
    synergies = _identify_synergies(a_extract.value_map, b_extract.value_map)
    risks = _identify_risks(
        a_value_map=a_extract.value_map,
        b_value_map=b_extract.value_map,
        combined_value_map=combined_value_map,
        combined_ratios=combined_ratios,
    )

    # --- Attractiveness score -----------------------------------------------
    attractiveness = _attractiveness_score(
        combined_health=combined_health,
        combined_ratios=combined_ratios,
        primary_value_map=a_extract.value_map,
        secondary_value_map=b_extract.value_map,
        synergies=synergies,
        risks=risks,
    )

    # --- Insights ------------------------------------------------------------
    metrics_a_by_id = _metrics_by_id(a_extract.metrics + a_ratios)
    metrics_b_by_id = _metrics_by_id(b_extract.metrics + b_ratios)
    metrics_c_by_id = _metrics_by_id(combined_scenario.metrics + combined_ratios)

    bundle = generate_merger_insights(
        primary_metrics=metrics_a_by_id,
        secondary_metrics=metrics_b_by_id,
        combined_metrics=metrics_c_by_id,
        synergies=synergies,
        risks=risks,
    )

    # --- Assemble ------------------------------------------------------------
    primary_entity = EntitySnapshot(
        entity_id=primary_dataset_id,
        display_name=a_name,
        metrics=a_extract.metrics + a_ratios,
        period_start=a_extract.period_start,
        period_end=a_extract.period_end,
    )
    secondary_entity = EntitySnapshot(
        entity_id=secondary_dataset_id,
        display_name=b_name,
        metrics=b_extract.metrics + b_ratios,
        period_start=b_extract.period_start,
        period_end=b_extract.period_end,
    )

    result = AnalysisResult(
        mode=AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS,
        primary_entity=primary_entity,
        secondary_entity=secondary_entity,
        combined_scenario=combined_scenario,
        financial_health=combined_health,
        metrics=[],  # metrics live in the entity snapshots
        ratios=combined_ratios,
        synergies=synergies,
        risks=risks,
        strengths=bundle.strengths,
        weaknesses=bundle.weaknesses,
        opportunities=bundle.opportunities,
        insights=bundle.insights,
        recommendations=bundle.recommendations,
        summary_text=_summary_text(
            a_name, b_name, deal_type, combined_health, attractiveness
        ),
        warnings=warnings,
        confidence=_confidence(a_extract, b_extract),
    )

    # Extend recommendations with a top-line attractiveness note.
    result.warnings.append(
        f"Combination Attractiveness Score: {attractiveness:.1f}/100 "
        f"\u2014 analytical support only, not investment advice."
    )

    log.info(
        "merger_analysis_completed",
        primary=primary_dataset_id,
        secondary=secondary_dataset_id,
        synergies=len(synergies),
        risks=len(risks),
        attractiveness=attractiveness,
        duration_ms=int((time.perf_counter() - started) * 1000),
    )
    return result


# ---------------------------------------------------------------------------
# Compatibility
# ---------------------------------------------------------------------------
def _check_compatibility(
    a: ExtractionResult,
    b: ExtractionResult,
    a_row: Dict[str, Any],
    b_row: Dict[str, Any],
    deal_type: Optional[str],
) -> List[str]:
    warnings: List[str] = []

    # Metric overlap
    overlap = set(a.value_map) & set(b.value_map)
    if not overlap:
        warnings.append(
            "No overlapping financial metrics between the two datasets \u2014 "
            "combined view will be very limited."
        )
    elif len(overlap) < 3:
        warnings.append(
            f"Only {len(overlap)} overlapping metric(s) between the datasets \u2014 "
            "combined figures should be interpreted cautiously."
        )

    # Time-period compatibility
    if a.period_start and b.period_start:
        if a.period_start[:4] != b.period_start[:4]:
            warnings.append(
                f"Period start differs (primary begins {a.period_start[:10]}, "
                f"secondary begins {b.period_start[:10]}) \u2014 combined figures "
                "may mix different reporting periods."
            )

    # Row-scale sanity: massively different data volumes are a heuristic warning.
    a_rows = int((a_row.get("row_count") or 0))
    b_rows = int((b_row.get("row_count") or 0))
    if a_rows and b_rows:
        ratio = max(a_rows, b_rows) / max(1, min(a_rows, b_rows))
        if ratio > 100:
            warnings.append(
                f"Datasets differ by ~{ratio:.0f}x in row count \u2014 they may "
                "represent very different granularities (e.g. quarterly vs transactional)."
            )

    # Unit / currency \u2014 we don't infer, but we flag if there's an explicit hint mismatch.
    a_unit = (a_row.get("metadata") or {}).get("unit_hint")
    b_unit = (b_row.get("metadata") or {}).get("unit_hint")
    if a_unit and b_unit and a_unit != b_unit:
        warnings.append(
            f"Declared unit hint differs (primary: {a_unit}, secondary: {b_unit}) "
            "\u2014 verify that both datasets use the same currency / scale before "
            "trusting combined figures."
        )

    if deal_type and deal_type.lower() not in ("merger", "acquisition", "partnership"):
        warnings.append(
            f"Unrecognised deal_type '{deal_type}' \u2014 defaulting to a generic combination."
        )

    return warnings


# ---------------------------------------------------------------------------
# Combined scenario
# ---------------------------------------------------------------------------
def _build_combined_scenario(
    a: Dict[MetricId, float], b: Dict[MetricId, float]
) -> Tuple[CombinedScenario, Dict[MetricId, float], List[LabeledMetric]]:
    combined_map: Dict[MetricId, float] = {}
    combined_metrics: List[LabeledMetric] = []

    for mid in _ADDITIVE_METRICS:
        va = a.get(mid)
        vb = b.get(mid)
        if va is None and vb is None:
            continue
        combined_val = (va or 0.0) + (vb or 0.0)
        combined_map[mid] = combined_val
        definition = get_definition(mid)

        note_bits: List[str] = []
        if va is None:
            note_bits.append("primary company value unavailable \u2014 treated as 0")
        if vb is None:
            note_bits.append("secondary company value unavailable \u2014 treated as 0")
        if not note_bits:
            note_bits.append(f"primary + secondary = {va:,.2f} + {vb:,.2f}")

        combined_metrics.append(
            LabeledMetric(
                metric_id=mid,
                display_name=definition.display_name,
                value=combined_val,
                unit=definition.unit,
                status=MetricStatus.SCENARIO,
                direction=definition.direction,
                confidence=0.85 if (va is not None and vb is not None) else 0.55,
                notes=note_bits,
            )
        )

    # Recalculate ratios from combined *base* values \u2014 never sum ratios.
    combined_ratios_raw = compute_ratios(combined_map)
    combined_ratios: List[LabeledMetric] = []
    for r in combined_ratios_raw:
        r.status = MetricStatus.SCENARIO
        r.notes.insert(0, "Recalculated from combined base metrics.")
        combined_ratios.append(r)

    caveats = [
        "Combined figures are a hypothetical scenario, not a forecast.",
        "Every value is the arithmetic sum of the two standalone datasets.",
        "Overlap between customer bases, product lines, and geographies is not adjusted for.",
        "Ratios have been recalculated from combined base metrics rather than averaged.",
    ]

    scenario = CombinedScenario(
        label="Combined Scenario \u2014 Not a Forecast",
        metrics=combined_metrics,
        caveats=caveats,
    )
    return scenario, combined_map, combined_ratios


# ---------------------------------------------------------------------------
# Synergy identification (conservative)
# ---------------------------------------------------------------------------
def _identify_synergies(
    a: Dict[MetricId, float], b: Dict[MetricId, float]
) -> List[SynergyItem]:
    out: List[SynergyItem] = []

    # ---- Revenue synergies ------------------------------------------------
    if MetricId.CUSTOMERS in a and MetricId.CUSTOMERS in b:
        combined = (a[MetricId.CUSTOMERS] or 0) + (b[MetricId.CUSTOMERS] or 0)
        out.append(
            SynergyItem(
                kind="revenue",
                title="Expanded customer base",
                description=(
                    f"Combined customer count could reach {combined:,.0f} \u2014 "
                    "opens cross-sell opportunities across both books, "
                    "subject to overlap."
                ),
                magnitude_hint="material" if combined >= 1_000_000 else "small",
                supporting_metrics=[MetricId.CUSTOMERS.value],
            )
        )

    if MetricId.REVENUE in a and MetricId.REVENUE in b:
        out.append(
            SynergyItem(
                kind="revenue",
                title="Revenue scale",
                description=(
                    "Combining top lines could support higher fixed-cost absorption, "
                    "increased bargaining power with suppliers, and greater investment capacity."
                ),
                magnitude_hint="material",
                supporting_metrics=[MetricId.REVENUE.value],
            )
        )

    # ---- Cost synergies ---------------------------------------------------
    if MetricId.OPERATING_EXPENSES in a and MetricId.OPERATING_EXPENSES in b:
        out.append(
            SynergyItem(
                kind="cost",
                title="Overlapping operating overhead",
                description=(
                    "Both companies incur operating expenses; overlap in administrative, "
                    "technology, and back-office functions may be consolidatable, "
                    "though the magnitude cannot be quantified from the data alone."
                ),
                magnitude_hint="insufficient_data",
                supporting_metrics=[MetricId.OPERATING_EXPENSES.value],
            )
        )

    if MetricId.EMPLOYEES in a and MetricId.EMPLOYEES in b:
        out.append(
            SynergyItem(
                kind="cost",
                title="Workforce optimization",
                description=(
                    "Combined headcount opens the possibility of consolidating "
                    "duplicated roles, particularly in support functions. "
                    "The size of savings depends on business overlap."
                ),
                magnitude_hint="insufficient_data",
                supporting_metrics=[MetricId.EMPLOYEES.value],
            )
        )

    # ---- Bank-specific ----------------------------------------------------
    if MetricId.DEPOSITS in a and MetricId.DEPOSITS in b:
        combined_dep = (a[MetricId.DEPOSITS] or 0) + (b[MetricId.DEPOSITS] or 0)
        out.append(
            SynergyItem(
                kind="revenue",
                title="Deposit base scale",
                description=(
                    f"Combined deposit base of {combined_dep:,.0f} increases funding "
                    "capacity and stability, potentially enabling further loan growth."
                ),
                magnitude_hint="material",
                supporting_metrics=[MetricId.DEPOSITS.value],
            )
        )

    return out


# ---------------------------------------------------------------------------
# Risk identification
# ---------------------------------------------------------------------------
def _identify_risks(
    *,
    a_value_map: Dict[MetricId, float],
    b_value_map: Dict[MetricId, float],
    combined_value_map: Dict[MetricId, float],
    combined_ratios: List[LabeledMetric],
) -> List[RiskItem]:
    risks: List[RiskItem] = []
    ratios_by_id = {r.metric_id: r for r in combined_ratios}

    # Combined leverage
    de = ratios_by_id.get(MetricId.DEBT_TO_EQUITY)
    if de and de.value is not None and de.value > 2.0:
        risks.append(
            RiskItem(
                severity=Priority.HIGH,
                title="High combined leverage",
                description=(
                    f"Combined debt-to-equity of {de.value:.2f} exceeds 2.0, indicating "
                    "the merged balance sheet would carry significant refinancing "
                    "and interest-rate risk."
                ),
                supporting_metrics=[MetricId.DEBT_TO_EQUITY.value, MetricId.DEBT.value],
            )
        )

    # Margin dilution
    combined_net_margin = ratios_by_id.get(MetricId.NET_MARGIN)
    if combined_net_margin and combined_net_margin.value is not None and combined_net_margin.value < 5:
        risks.append(
            RiskItem(
                severity=Priority.MEDIUM,
                title="Thin combined profitability",
                description=(
                    f"Combined net margin of {combined_net_margin.value:.2f}% leaves "
                    "little cushion for integration costs, market shocks, or one-off "
                    "impairments."
                ),
                supporting_metrics=[MetricId.NET_MARGIN.value],
            )
        )

    # Either party loss-making
    for label, vm in (("primary", a_value_map), ("secondary", b_value_map)):
        np_val = vm.get(MetricId.NET_PROFIT)
        if np_val is not None and np_val < 0:
            risks.append(
                RiskItem(
                    severity=Priority.HIGH,
                    title=f"{label.capitalize()} company is loss-making",
                    description=(
                        f"The {label} company shows negative net profit "
                        f"({np_val:,.0f}) \u2014 combined profitability inherits this drag."
                    ),
                    supporting_metrics=[MetricId.NET_PROFIT.value],
                )
            )

    # High combined liabilities relative to equity
    combined_liab = combined_value_map.get(MetricId.LIABILITIES)
    combined_eq = combined_value_map.get(MetricId.EQUITY)
    if combined_liab is not None and combined_eq is not None and combined_eq > 0:
        ratio = combined_liab / combined_eq
        if ratio > 3.0:
            risks.append(
                RiskItem(
                    severity=Priority.HIGH,
                    title="Elevated combined liabilities",
                    description=(
                        f"Combined liabilities are {ratio:.1f}x combined equity \u2014 "
                        "the consolidated capital structure would be aggressive."
                    ),
                    supporting_metrics=[MetricId.LIABILITIES.value, MetricId.EQUITY.value],
                )
            )

    # Loan-book concentration (banking)
    combined_loans = combined_value_map.get(MetricId.LOANS)
    combined_gnpa = combined_value_map.get(MetricId.GROSS_NPA)
    if combined_loans and combined_gnpa and combined_loans > 0:
        gnpa_pct = combined_gnpa / combined_loans * 100
        if gnpa_pct > 6:
            risks.append(
                RiskItem(
                    severity=Priority.HIGH,
                    title="Elevated combined NPA ratio",
                    description=(
                        f"Combined gross NPA would be {gnpa_pct:.2f}% of the loan book "
                        "\u2014 asset-quality integration will require close attention."
                    ),
                    supporting_metrics=[MetricId.GROSS_NPA.value, MetricId.LOANS.value],
                )
            )

    # Data limitations always flagged
    risks.append(
        RiskItem(
            severity=Priority.LOW,
            title="Data-limitation risk",
            description=(
                "Combined figures assume no overlap in customers, products, or "
                "geographies. Real-world integration adjustments, one-off costs, "
                "and regulatory considerations are not modelled."
            ),
        )
    )
    return risks


# ---------------------------------------------------------------------------
# Attractiveness score
# ---------------------------------------------------------------------------
def _attractiveness_score(
    *,
    combined_health: HealthScore,
    combined_ratios: List[LabeledMetric],
    primary_value_map: Dict[MetricId, float],
    secondary_value_map: Dict[MetricId, float],
    synergies: List[SynergyItem],
    risks: List[RiskItem],
) -> float:
    """0-100 score. Explainable + bounded. Never presented as advice."""
    score = 50.0  # neutral starting point

    # Health of the combined balance sheet is the biggest driver.
    score += (combined_health.overall_score - 50) * 0.4  # up to \u00b120 pts

    # Revenue scale uplift for the primary company.
    rev_a = primary_value_map.get(MetricId.REVENUE)
    rev_b = secondary_value_map.get(MetricId.REVENUE)
    if rev_a and rev_b and rev_a > 0:
        uplift_pct = rev_b / rev_a * 100
        # +12 pts for a 100 % uplift, capped
        score += min(15.0, uplift_pct * 0.12)

    # Penalise if either company is loss-making.
    for vm in (primary_value_map, secondary_value_map):
        np = vm.get(MetricId.NET_PROFIT)
        if np is not None and np < 0:
            score -= 8

    # Reward material synergies.
    material = sum(1 for s in synergies if s.magnitude_hint == "material")
    score += min(10.0, material * 3.0)

    # Penalise high-severity risks.
    high_risks = sum(1 for r in risks if r.severity == Priority.HIGH)
    score -= min(20.0, high_risks * 6.0)

    return max(0.0, min(100.0, score))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _metrics_by_id(metrics: List[LabeledMetric]) -> Dict[MetricId, LabeledMetric]:
    return {m.metric_id: m for m in metrics if m.value is not None}


def _confidence(a: ExtractionResult, b: ExtractionResult) -> Confidence:
    overlap = set(a.value_map) & set(b.value_map)
    total = set(a.value_map) | set(b.value_map)
    metric_coverage = len(overlap) / max(1, len(total))
    return Confidence(
        overall=metric_coverage,
        metric_coverage=metric_coverage,
        notes=[
            f"{len(overlap)} metric(s) overlap; {len(total) - len(overlap)} "
            "appear in only one of the two datasets.",
        ],
    )


def _summary_text(
    a_name: str,
    b_name: str,
    deal_type: Optional[str],
    combined_health: HealthScore,
    attractiveness: float,
) -> str:
    verb = {
        "merger": "merging with",
        "acquisition": "acquiring",
        "partnership": "partnering with",
    }.get((deal_type or "").lower(), "combining with")

    return (
        f"Hypothetical scenario: {a_name} {verb} {b_name}. "
        f"Combined financial health score: {combined_health.overall_score:.1f}/100 "
        f"(grade {combined_health.grade}). "
        f"Combination Attractiveness Score: {attractiveness:.1f}/100. "
        "This is analytical support based on standalone data \u2014 not a forecast or advice."
    )
