"""
Pydantic request/response models for the analytics API.

These do double duty: FastAPI validates against them at runtime, and it
generates the OpenAPI schema from them, so this file is effectively the
API specification chapter of the thesis.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


# ─────────────────────────────────────────────
# Requests
# ─────────────────────────────────────────────
class FeaturePayload(BaseModel):
    """
    Free-form feature map. Keys must match the trained model's feature
    names; anything missing defaults to 0.0 and is reported back in
    `missing_fields` so a partial payload is never silently trusted.
    """

    features: dict[str, float] = Field(
        ...,
        description="Feature name to value, e.g. {'Monetary': 500000, 'Frequency': 12}",
        json_schema_extra={
            "example": {
                "Monetary": 1024778.07,
                "Frequency": 18.0,
                "Txn_Count": 5,
                "Avg_Order_Value": 204955.61,
                "Customer_Age": 40,
            }
        },
    )


# ─────────────────────────────────────────────
# Responses
# ─────────────────────────────────────────────
class SegmentPrediction(BaseModel):
    segment: str
    segment_id: int
    confidence: float
    probabilities: dict[str, float]
    missing_fields: list[str]


class ChurnPrediction(BaseModel):
    churn_probability: float
    will_churn: bool
    risk_band: str
    model: str
    threshold_days: int
    missing_fields: list[str]


class ReturnPrediction(BaseModel):
    return_probability: float
    will_return: bool
    model: str
    reliability: str
    note: str
    missing_fields: list[str]


class CustomerSummary(BaseModel):
    customer_id: str
    segment: str
    monetary: float
    recency: int
    frequency: float
    txn_count: int
    churned: bool


class CustomerList(BaseModel):
    total: int
    page: int
    page_size: int
    customers: list[CustomerSummary]


class ShapContribution(BaseModel):
    feature: str
    contribution: float
    direction: str
    value: float


class MonthlyPoint(BaseModel):
    month: str
    sales: float


class Overview(BaseModel):
    total_customers: int
    total_revenue: float
    total_transactions: int
    avg_order_value: float
    churn_rate: float
    avg_csat: float
    monthly_sales: list[MonthlyPoint]
    best_forecast_model: str


class ForecastPoint(BaseModel):
    period: str
    actual: float
    lstm: float
    arima: float
    seasonal_naive: float


class ForecastResponse(BaseModel):
    points: list[ForecastPoint]
    metrics: dict[str, dict[str, float]]
    best_model: str
    note: str


class Health(BaseModel):
    status: str
    artifacts_loaded: bool
    detail: str | None = None
