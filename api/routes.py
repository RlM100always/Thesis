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

from fastapi import APIRouter, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

# predict.py sits at the project root, one level above api/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import predict as service  # noqa: E402
import upload_service  # noqa: E402

from .schemas import (  # noqa: E402
    ChurnPrediction, ColumnMapping, CustomerList, FeaturePayload, ForecastResponse,
    Overview, ReturnPrediction, SegmentPrediction, ShapContribution,
    UploadParsed, UploadScore,
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


@router.get("/research/real-data-validation", tags=["dashboard"])
def real_data_validation():
    """
    Real-data validation study, read-only.

    Reports the pre-computed results of `python -m ml.real_data_validation`
    (a one-off study, not something to retrain on every request) — real
    forecast/churn metrics from UCI Online Retail II and a real Bangladeshi
    retailer's demand series, run through the same leak-free training code
    a B-SMART business's own data uses. Supplements, never replaces, the
    synthetic thesis pipeline's results reported by /models/metrics.
    """
    path = Path("artifacts/real_public/real_data_validation.json")
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="Not generated yet. Run: python -m ml.real_data_validation",
        )
    import json
    return json.loads(path.read_text(encoding="utf-8"))


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
# Bring-your-own-data: upload, map, score
# ─────────────────────────────────────────────
# Scoring only. No model is retrained, so the thesis artifacts in output/
# are never written by any of these handlers.
@router.post("/upload", response_model=UploadParsed, tags=["upload"])
async def upload(file: UploadFile = File(...)):
    """Parse an uploaded CSV/Excel and suggest a column mapping."""
    try:
        return upload_service.parse_upload(await file.read(), file.filename or "upload.csv")
    except upload_service.UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/upload/{token}/score", response_model=UploadScore, tags=["upload"])
def upload_score(token: str, mapping: ColumnMapping):
    """Rebuild customer features from the mapping and rank by churn risk."""
    try:
        return upload_service.score_upload(token, mapping.model_dump())
    except upload_service.UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/upload/{token}/export", tags=["upload"])
def upload_export(token: str, mapping: ColumnMapping):
    """The same scored rows as a downloadable CSV."""
    try:
        csv_text = upload_service.export_csv(token, mapping.model_dump())
    except upload_service.UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # utf-8-sig so Excel renders it without mojibake — repo CSV convention.
    return StreamingResponse(
        iter([csv_text.encode("utf-8-sig")]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="scored_customers.csv"'},
    )


@router.delete("/upload/{token}", tags=["upload"])
def upload_delete(token: str):
    return {"deleted": upload_service.drop_session(token)}


# The four views below are plain arithmetic over the user's own rows — no
# trained model is involved, so unlike /score they carry no transfer caveat.
@router.post("/upload/{token}/overview", tags=["upload"])
def upload_overview(token: str, mapping: ColumnMapping):
    """Headline KPIs and the monthly sales series for the uploaded file."""
    try:
        return upload_service.overview_for(token, mapping.model_dump())
    except upload_service.UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/upload/{token}/forecast", tags=["upload"])
def upload_forecast(token: str, mapping: ColumnMapping, horizon: int = Query(3, ge=1, le=12)):
    """
    Seasonal-naive forecast for the uploaded file.

    Responds `available: false` with a reason when the file has under 13 months
    of history, rather than extrapolating from too little data.
    """
    try:
        return upload_service.forecast_for(token, mapping.model_dump(), horizon=horizon)
    except upload_service.UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/upload/{token}/segments", tags=["upload"])
def upload_segments(token: str, mapping: ColumnMapping, k: int = Query(4, ge=2, le=6)):
    """K-Means re-fitted on the uploaded customers, with silhouette reported."""
    try:
        return upload_service.segments_for(token, mapping.model_dump(), k=k)
    except upload_service.UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/upload/{token}/train-churn", tags=["upload"])
def upload_train_churn(token: str, mapping: ColumnMapping, horizon: int = Query(90, ge=30, le=180)):
    """
    Train a brand-new future-repeat model on nothing but this upload's own
    rows and report its held-out performance (PR-AUC, ROC-AUC, Brier, lift).

    Unlike /score, which scores against the fixed churn_model.pkl trained on
    the synthetic thesis dataset, this fits a fresh model from scratch on
    whatever was uploaded — genuinely dynamic, same training code the
    B-SMART "AI মডেল প্রশিক্ষণ" button uses for a business's own database.
    """
    try:
        return upload_service.train_dynamic_churn(token, mapping.model_dump(), horizon_days=horizon)
    except upload_service.UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/upload/{token}/products", tags=["upload"])
def upload_products(token: str, mapping: ColumnMapping):
    """Best sellers. Returns `available: false` when no product column was mapped."""
    try:
        return upload_service.products_for(token, mapping.model_dump())
    except upload_service.UploadError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


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
