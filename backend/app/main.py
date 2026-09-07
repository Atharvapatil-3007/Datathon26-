"""FastAPI application entrypoint.

Run locally with:

    uvicorn app.main:app --reload --port 8000

The app exposes a versioned API under `/api/v1` and installs a global
exception handler that converts `IngestionError` into a structured JSON
response — the frontend never sees a raw Python traceback.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__
from app.api.analysis import router_analysis
from app.api.chat import router_chat
from app.api.ingestion import router_datasets, router_ingestion
from app.config.settings import get_settings
from app.database.supabase import get_supabase_service
from app.ingestion.exceptions import IngestionError
from app.utils.logging import configure_logging, get_logger


configure_logging()
log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Lifespan (replaces deprecated on_event handlers)
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    service = get_supabase_service()
    log.info(
        "app_startup",
        app_name=settings.app_name,
        env=settings.app_env,
        version=__version__,
        supabase_configured=settings.supabase_configured,
        local_fallback=service.is_local_fallback,
    )
    yield
    log.info("app_shutdown")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
def _build_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description=(
            "Financial Intelligence & Decision-Support Platform.\n\n"
            "Phase 1 — Data Ingestion: uploads CSV / Excel / JSON / JSONL / "
            "Parquet / SQLite / ZIP, detects format, validates.\n\n"
            "Phase 2 — Automatic Data Understanding: column types, missing / "
            "duplicates / cardinality, statistics, distributions, correlations, "
            "quality score.\n\n"
            "Phase 3 — Financial Intelligence: Self Analysis, "
            "Merger / Partnership Analysis, Competitor & Market Benchmarking.\n\n"
            "Chatbot — Dataset Intelligence Assistant grounded in the uploaded "
            "dataset, its Phase 2 profile and its Phase 3 analysis results."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # ---- CORS --------------------------------------------------------------
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list or ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ---- Routes -------------------------------------------------------------
    app.include_router(router_ingestion, prefix="/api/v1")
    app.include_router(router_datasets, prefix="/api/v1")
    app.include_router(router_analysis, prefix="/api/v1")
    app.include_router(router_chat, prefix="/api/v1")

    # ---- Health -------------------------------------------------------------
    @app.get("/", tags=["meta"])
    async def root():
        return {
            "app": settings.app_name,
            "version": __version__,
            "phases": [
                "1 - Data Ingestion",
                "2 - Data Understanding",
                "3 - Financial Intelligence",
                "Chatbot - Dataset Intelligence Assistant",
            ],
            "docs": "/docs",
        }

    @app.get("/health", tags=["meta"])
    async def health():
        service = get_supabase_service()
        return {
            "status": "ok",
            "supabase_configured": settings.supabase_configured,
            "local_fallback": service.is_local_fallback,
        }

    # ---- Exception handlers -------------------------------------------------
    _install_error_handlers(app)

    return app


def _install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(IngestionError)
    async def _ingestion_error_handler(request: Request, exc: IngestionError):
        log.warning(
            "ingestion_error",
            path=request.url.path,
            code=exc.code,
            status=exc.http_status,
            message=exc.message,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content={"success": False, "error": exc.to_dict()},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(request: Request, exc: RequestValidationError):
        log.info("request_validation_error", path=request.url.path)
        return JSONResponse(
            status_code=422,
            content={
                "success": False,
                "error": {
                    "code": "REQUEST_VALIDATION_ERROR",
                    "message": "Request payload failed validation",
                    "details": exc.errors(),
                },
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled_exception_handler(request: Request, exc: Exception):
        log.exception("unhandled_exception", path=request.url.path)
        return JSONResponse(
            status_code=500,
            content={
                "success": False,
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected error occurred.",
                },
            },
        )


app = _build_app()


# ---------------------------------------------------------------------------
# Enable `python -m app.main` for quick local dev
# ---------------------------------------------------------------------------
if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_env == "development",
    )
