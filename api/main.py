"""
=============================================================
FastAPI APPLICATION
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
HOW TO RUN:
    python run_api.py

Use the launcher rather than calling uvicorn directly. `python -m uvicorn
api.main:app` resolves "api.main" against the current directory, so it
only works from the project root and fails from inside api/ with
`ModuleNotFoundError: No module named 'api'`. run_api.py pins the working
directory first and checks that the pipeline artifacts exist.

Then open:
    http://127.0.0.1:8000/docs    interactive Swagger UI
    http://127.0.0.1:8000/health  liveness probe

ARCHITECTURE
------------
    React (Vite, :5173)
        │  fetch / JSON
        ▼
    FastAPI (:8000)  ── api/routes.py ── api/schemas.py
        │
        ▼
    predict.py                     ← the only module that loads artifacts
        │
        ▼
    output/models/*.pkl, output/*.csv

The layers are separated so the serving logic can be tested without HTTP
and the HTTP layer can be inspected without loading a single model.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import utf8_console  # noqa: E402,F401  — UTF-8 stdout before any printing

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import predict as service  # noqa: E402

from .routes import router  # noqa: E402
from .app_routes import router as app_router  # noqa: E402
from .auth_routes import router as auth_router  # noqa: E402
from .commerce_routes import router as commerce_router  # noqa: E402
from .directory_routes import router as directory_router  # noqa: E402
from .finance_routes import router as finance_router  # noqa: E402
from .data_import_routes import router as data_import_router  # noqa: E402
from .analytics_routes import router as analytics_router  # noqa: E402
from .bsmart_routes import router as bsmart_router  # noqa: E402
from .audit_routes import router as audit_router  # noqa: E402
from .batch_routes import router as batch_router  # noqa: E402
from .insights_routes import router as insights_router  # noqa: E402
from .bulk_import_routes import router as bulk_import_router  # noqa: E402
from .planning_routes import router as planning_router  # noqa: E402
from .receivables_routes import router as receivables_router  # noqa: E402
from .insights_advanced_routes import router as insights_advanced_router  # noqa: E402
from .accounting_routes import router as accounting_router  # noqa: E402
from .approval_routes import router as approval_router  # noqa: E402
from .stock_count_routes import router as stock_count_router  # noqa: E402
from .database import create_schema  # noqa: E402
from .schemas import Health  # noqa: E402

app = FastAPI(
    title="AI-Powered Business Analytics API",
    description=(
        "B-SMART: constraint-aware strategy recommendation for Bangladeshi retail "
        "pharmacy SMEs, plus the supporting analytics (demand forecasting, customer "
        "inactivity risk, RFM segmentation) it consumes.\n\n"
        "**Note on reported accuracy.** The segment model scores ~51% leak-free "
        "against a 35.2% majority baseline, not the 85.27% a transaction-level split "
        "with a CLV feature reports. That gap is data leakage, and it is published "
        "rather than hidden — see `/api/models/metrics` for the full ablation.\n\n"
        "**Architecture.** See `docs/BSMART_ARCHITECTURE.md`. Layer 5 (Algorithm 1) "
        "is served read-only at `/api/research/bsmart/latest`; layers 9 and 10 "
        "(owner decision, outcome and monitoring) live under `/api/app/bsmart/*`."
    ),
    version="2.0.0",
)

# The Vite dev server runs on a different origin, so the browser needs
# explicit permission. Ports 5173/5174 are Vite's default and its fallback.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
app.include_router(auth_router)
app.include_router(app_router)
app.include_router(commerce_router)
app.include_router(directory_router)
app.include_router(finance_router)
app.include_router(data_import_router)
app.include_router(analytics_router)
app.include_router(bsmart_router)
app.include_router(audit_router)
app.include_router(batch_router)
app.include_router(insights_router)
app.include_router(bulk_import_router)
app.include_router(planning_router)
app.include_router(receivables_router)
app.include_router(insights_advanced_router)
app.include_router(accounting_router)
app.include_router(approval_router)
app.include_router(stock_count_router)


@app.on_event("startup")
def initialize_application_database():
    """Create the development schema; Alembic will own production upgrades."""
    create_schema()


@app.get("/health", response_model=Health, tags=["system"])
def health():
    """
    Liveness plus an artifact check.

    Reports unhealthy rather than crashing when the pipeline has not been
    run, so the frontend can show a useful message instead of a blank page.
    """
    try:
        service.get_artifacts()
        return {"status": "ok", "artifacts_loaded": True, "detail": None}
    except service.ArtifactsMissingError as e:
        return {"status": "degraded", "artifacts_loaded": False, "detail": str(e)}


@app.get("/", tags=["system"])
def root():
    return {
        "name": "AI-Powered Business Analytics API",
        "docs": "/docs",
        "health": "/health",
    }
