"""HTTP API for Phase 3 — Financial Intelligence Analysis.

Three analysis modes are exposed after Phase 2 profiling completes:

    POST /api/v1/analysis/self
    POST /api/v1/analysis/merger
    POST /api/v1/analysis/benchmark

There is also a metadata endpoint the frontend uses to render the
"What do you want to analyze?" selection screen:

    GET  /api/v1/analysis/options

Each mode is a **selection**, not an automatic pipeline: only the requested
analyzer runs. The heavy lifting lives in ``app.analysis.*`` — this file is a
thin translation layer between JSON payloads and the analyzer functions.

Every ``AnalysisError`` (see ``app.analysis.exceptions``) inherits from
``IngestionError`` so the existing global FastAPI exception handler already
serializes them into the standard ``{"success": false, "error": {...}}``
error envelope.

Response contract for the three analyze endpoints: the response body IS the
JSON-safe ``AnalysisResult.to_dict()`` (flat — no wrapping envelope) so
``body["mode"]``, ``body["primary_entity"]``, ``body["gaps"]``, etc. are
directly readable. This is what the frontend and tests expect.
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from fastapi import APIRouter, status
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from app.analysis.benchmark_analyzer import run_benchmark_analysis
from app.analysis.merger_analyzer import run_merger_analysis
from app.analysis.self_analyzer import run_self_analysis
from app.analysis.types import AnalysisMode
from app.utils.logging import get_logger

log = get_logger(__name__)


# ============================================================================
# Request bodies
# ============================================================================
class SelfAnalysisRequest(BaseModel):
    """Body for POST /analysis/self."""

    dataset_id: str = Field(..., description="Phase 2-profiled dataset id")
    display_name: Optional[str] = Field(
        default=None,
        description="User-friendly label for the entity (e.g. 'Our Company')",
        max_length=200,
    )


class MergerAnalysisRequest(BaseModel):
    """Body for POST /analysis/merger."""

    primary_dataset_id: str = Field(..., description="Our company dataset")
    secondary_dataset_id: str = Field(..., description="Other company dataset")
    deal_type: Optional[Literal["merger", "acquisition", "partnership"]] = None
    primary_display_name: Optional[str] = Field(default=None, max_length=200)
    secondary_display_name: Optional[str] = Field(default=None, max_length=200)


class BenchmarkAnalysisRequest(BaseModel):
    """Body for POST /analysis/benchmark."""

    primary_dataset_id: str = Field(..., description="Our company dataset")
    competitor_dataset_id: str = Field(..., description="Competitor dataset")
    market_dataset_id: Optional[str] = Field(
        default=None,
        description="Optional market / industry benchmark dataset",
    )
    primary_display_name: Optional[str] = Field(default=None, max_length=200)
    competitor_display_name: Optional[str] = Field(default=None, max_length=200)
    market_display_name: Optional[str] = Field(default=None, max_length=200)


# ============================================================================
# Response models (advisory — the analyzer produces the actual payload)
# ============================================================================
class ModeDescriptor(BaseModel):
    """One row of the ``GET /analysis/options`` catalog.

    ``requires`` is a flat list of the datasets the user must provide. Items
    prefixed with ``optional:`` are optional; everything else is mandatory.
    A single field keeps the frontend rendering trivially simple — the
    picker just shows the list as-is.
    """

    mode: str                                  # matches AnalysisMode.value
    title: str
    description: str
    requires: List[str]                        # human-readable dataset labels


class ModeCatalog(BaseModel):
    """Envelope for the options endpoint."""

    modes: List[ModeDescriptor]


# ============================================================================
# Router
# ============================================================================
router_analysis = APIRouter(prefix="/analysis", tags=["analysis"])


# ----------------------------------------------------------------------------
# Metadata: available modes (drives the selection screen)
# ----------------------------------------------------------------------------
@router_analysis.get(
    "/options",
    response_model=ModeCatalog,
    summary="List the available Phase 3 analysis modes and their requirements",
)
async def list_options() -> ModeCatalog:
    return ModeCatalog(
        modes=[
            ModeDescriptor(
                mode=AnalysisMode.SELF_ANALYSIS.value,
                title="Self Financial Analysis",
                description=(
                    "Understand your company's financial health, performance, "
                    "risks, and opportunities using the dataset you just uploaded."
                ),
                requires=["Your Company"],
            ),
            ModeDescriptor(
                mode=AnalysisMode.MERGER_PARTNERSHIP_ANALYSIS.value,
                title="Merger / Partnership Analysis",
                description=(
                    "Analyze the potential financial impact of combining with "
                    "another company. Upload a second dataset for the other party."
                ),
                requires=["Your Company", "Other Company"],
            ),
            ModeDescriptor(
                mode=AnalysisMode.COMPETITOR_MARKET_BENCHMARK.value,
                title="Competitor & Market Benchmarking",
                description=(
                    "Compare your financial performance with a competitor and, "
                    "optionally, a market / industry benchmark."
                ),
                requires=[
                    "Your Company",
                    "Competitor",
                    "optional:Market / Industry Benchmark",
                ],
            ),
        ]
    )


# ----------------------------------------------------------------------------
# Self Financial Analysis
# ----------------------------------------------------------------------------
@router_analysis.post(
    "/self",
    status_code=status.HTTP_200_OK,
    summary="Run Self Financial Analysis on a single Phase 2-profiled dataset",
)
async def analyze_self(payload: SelfAnalysisRequest) -> Dict[str, Any]:
    log.info(
        "analysis_self_requested",
        dataset_id=payload.dataset_id,
        display_name=payload.display_name,
    )
    result = await run_in_threadpool(
        run_self_analysis,
        payload.dataset_id,
        display_name=payload.display_name,
    )
    return result.to_dict()


# ----------------------------------------------------------------------------
# Merger / Partnership
# ----------------------------------------------------------------------------
@router_analysis.post(
    "/merger",
    status_code=status.HTTP_200_OK,
    summary="Run Merger / Partnership Analysis on two Phase 2-profiled datasets",
)
async def analyze_merger(payload: MergerAnalysisRequest) -> Dict[str, Any]:
    log.info(
        "analysis_merger_requested",
        primary=payload.primary_dataset_id,
        secondary=payload.secondary_dataset_id,
        deal_type=payload.deal_type,
    )
    result = await run_in_threadpool(
        run_merger_analysis,
        payload.primary_dataset_id,
        payload.secondary_dataset_id,
        deal_type=payload.deal_type,
        primary_display_name=payload.primary_display_name,
        secondary_display_name=payload.secondary_display_name,
    )
    return result.to_dict()


# ----------------------------------------------------------------------------
# Competitor & Market Benchmarking
# ----------------------------------------------------------------------------
@router_analysis.post(
    "/benchmark",
    status_code=status.HTTP_200_OK,
    summary="Run Competitor & Market Benchmarking",
)
async def analyze_benchmark(payload: BenchmarkAnalysisRequest) -> Dict[str, Any]:
    log.info(
        "analysis_benchmark_requested",
        primary=payload.primary_dataset_id,
        competitor=payload.competitor_dataset_id,
        market=payload.market_dataset_id,
    )
    result = await run_in_threadpool(
        run_benchmark_analysis,
        payload.primary_dataset_id,
        payload.competitor_dataset_id,
        market_dataset_id=payload.market_dataset_id,
        primary_display_name=payload.primary_display_name,
        competitor_display_name=payload.competitor_display_name,
        market_display_name=payload.market_display_name,
    )
    return result.to_dict()
