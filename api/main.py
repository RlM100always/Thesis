"""
=============================================================
FastAPI APPLICATION
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
HOW TO RUN:
    PYTHONIOENCODING=utf-8 ./.venv312/Scripts/python.exe -m uvicorn api.main:app --reload

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

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import predict as service  # noqa: E402

from .routes import router  # noqa: E402
from .schemas import Health  # noqa: E402

app = FastAPI(
    title="AI-Powered Business Analytics API",
    description=(
        "Customer segmentation, churn and return prediction, sales forecasting "
        "and per-customer SHAP explanations for Bangladeshi retail data.\n\n"
        "**Note on reported accuracy.** The segment model scores 67.07%, not the "
        "94.81% an earlier version of this project reported. The higher figure came "
        "from data leakage (customer-level labels split at transaction level, plus a "
        "CLV feature that nearly determined the label). See `/api/models/metrics` "
        "for the full ablation."
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
