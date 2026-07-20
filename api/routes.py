"""
API route handlers.

Every handler delegates to predict.py. No pickle is opened here and no
model logic lives here — the HTTP layer only translates between JSON and
the service layer, which keeps the serving logic testable without a
running server.
"""

from __future__ import annotations

import sys
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query

# predict.py sits at the project root, one level above api/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import predict as service  # noqa: E402

from .schemas import (  # noqa: E402
    ChurnPrediction, CustomerList, FeaturePayload, ForecastResponse,
    Overview, ReturnPrediction, SegmentPrediction, ShapContribution,
)

router = APIRouter(prefix="/api")


# ─────────────────────────────────────────────
# Dashboard aggregates
# ─────────────────────────────────────────────
@router.get("/overview", response_model=Overview, tags=["dashboard"])
def overview():
    """Headline KPIs and the 48-month sales series."""
    return service.get_overview()


@router.get("/segments", tags=["dashboard"])
def segments():
    """Supervised segment profiles plus the K-Means cluster distribution."""
    return service.get_segments()


@router.get("/forecast", response_model=ForecastResponse, tags=["dashboard"])
def forecast():
    """Held-out months with LSTM, ARIMA and seasonal-naive predictions."""
    return service.get_forecast()


@router.get("/models/metrics", tags=["dashboard"])
def model_metrics():
    """
    Full model report, including the leakage ablation.

    The ablation is exposed deliberately: the discovery that CLV leaked
    the label is a result of this project, not an embarrassment to hide
    behind the dashboard.
    """
    return service.get_model_report()


# ─────────────────────────────────────────────
# Customers
# ─────────────────────────────────────────────
@router.get("/customers", response_model=CustomerList, tags=["customers"])
def customers(
    q: str = Query("", description="Substring match on Customer_ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
):
    return service.list_customers(query=q, page=page, page_size=page_size)


@router.get("/customers/{customer_id}", tags=["customers"])
def customer_detail(customer_id: str):
    """Profile, segment prediction, churn risk and per-customer SHAP reasons."""
    result = service.get_customer(customer_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Unknown customer: {customer_id}")
    return result


@router.get(
    "/customers/{customer_id}/explain",
    response_model=list[ShapContribution],
    tags=["customers"],
)
def customer_explain(customer_id: str, top_n: int = Query(8, ge=1, le=30)):
    result = service.explain_customer(customer_id, top_n=top_n)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown customer, or the shap package is not installed: {customer_id}",
        )
    return result


# ─────────────────────────────────────────────
# Ad-hoc prediction
# ─────────────────────────────────────────────
@router.post("/predict/segment", response_model=SegmentPrediction, tags=["predict"])
def predict_segment(payload: FeaturePayload):
    return service.predict_segment(payload.features)


@router.post("/predict/churn", response_model=ChurnPrediction, tags=["predict"])
def predict_churn(payload: FeaturePayload):
    return service.predict_churn(payload.features)


@router.post("/predict/return", response_model=ReturnPrediction, tags=["predict"])
def predict_return(payload: FeaturePayload):
    """
    Note the `reliability: low` field in the response. The return model
    scores ROC-AUC ~0.58, so it is served with that caveat attached rather
    than presented as a confident answer.
    """
    return service.predict_return(payload.features)


# ─────────────────────────────────────────────
# Feature discovery — what does each model expect?
# ─────────────────────────────────────────────
@router.get("/features/{model}", tags=["predict"])
def model_features(model: str):
    a = service.get_artifacts()
    mapping = {
        "segment": a["segment_features"],
        "churn": a["churn"]["features"],
        "return": a["return"]["features"],
    }
    if model not in mapping:
        raise HTTPException(
            status_code=404,
            detail=f"Unknown model '{model}'. Expected one of: {list(mapping)}",
        )
    return {"model": model, "features": mapping[model], "count": len(mapping[model])}
