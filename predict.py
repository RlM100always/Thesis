"""
=============================================================
INFERENCE SERVICE LAYER
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
The single place that loads trained artifacts and turns them into
predictions. The API layer talks to this module and never opens a pickle
itself, so serving logic stays testable without an HTTP server running.

THE RULE THAT MATTERS
---------------------
Scalers and encoders are LOADED, never re-fit. Re-fitting on request data
would scale each request against its own min/max instead of the training
distribution, and the predictions would be silently wrong — no error, just
bad answers. Every transform here uses the objects saved during training.

Artifacts consumed (all produced by run_all.py):
    output/customer_splits.pkl      training scaler + feature order
    output/models/v2_xgboost.pkl    segment classifier (leak-free)
    output/models/churn_model.pkl   churn model + its own scaler/features
    output/models/return_model.pkl  return model + its own scaler/features
    output/customer_features.csv    customer lookup
    output/forecast_results.pkl     LSTM / ARIMA / seasonal-naive
"""

from __future__ import annotations

import os
import pickle
from functools import lru_cache
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parent
OUTPUT = BASE_DIR / "output"

SEGMENT_NAMES = ["Low-Engagement", "Moderate-Spender", "High-Value", "VIP-Platinum"]


class ArtifactsMissingError(RuntimeError):
    """Raised when the pipeline has not been run yet."""


def _load_pickle(relpath: str):
    path = OUTPUT / relpath
    if not path.exists():
        raise ArtifactsMissingError(
            f"Missing artifact: {path}\n"
            f"Run the pipeline first:\n"
            f"  PYTHONIOENCODING=utf-8 ./.venv312/Scripts/python.exe run_all.py"
        )
    with open(path, "rb") as f:
        return pickle.load(f)


@lru_cache(maxsize=1)
def get_artifacts() -> dict:
    """Load everything once; cached for the process lifetime."""
    splits = _load_pickle("customer_splits.pkl")
    segment_model = _load_pickle("models/v2_xgboost.pkl")
    churn = _load_pickle("models/churn_model.pkl")
    ret = _load_pickle("models/return_model.pkl")

    customers = pd.read_csv(OUTPUT / "customer_features.csv")
    customers["Churned"] = (customers["Recency"] > churn["churn_days"]).astype(int)

    segments_path = OUTPUT / "customer_segments.csv"
    segments = pd.read_csv(segments_path) if segments_path.exists() else None

    return {
        "segment_model": segment_model,
        "segment_scaler": splits["scaler"],          # fit on TRAIN only in 01b
        "segment_features": splits["feature_names"],
        "churn": churn,
        "return": ret,
        "customers": customers,
        "segments": segments,
        "forecast": _load_pickle("forecast_results.pkl"),
        "classification_v2": _load_pickle("classification_v2_results.pkl"),
        "churn_results": _load_pickle("churn_results.pkl"),
        "return_results": _load_pickle("return_results.pkl"),
    }


def _vectorise(payload: dict, feature_names: list[str]) -> np.ndarray:
    """
    Build a model-ready row from a name->value dict.

    Missing features default to 0.0 rather than raising, so a partial
    payload still returns a prediction; the caller is told which fields
    were defaulted so the answer can be judged.
    """
    row = [float(payload.get(name, 0.0)) for name in feature_names]
    return np.array(row, dtype=float).reshape(1, -1)


def missing_fields(payload: dict, feature_names: list[str]) -> list[str]:
    return [f for f in feature_names if f not in payload]


# ─────────────────────────────────────────────
# PREDICTORS
# ─────────────────────────────────────────────
def predict_segment(payload: dict) -> dict:
    a = get_artifacts()
    features = a["segment_features"]
    X = a["segment_scaler"].transform(_vectorise(payload, features))
    proba = a["segment_model"].predict_proba(X)[0]
    idx = int(np.argmax(proba))
    return {
        "segment": SEGMENT_NAMES[idx],
        "segment_id": idx,
        "confidence": float(proba[idx]),
        "probabilities": {SEGMENT_NAMES[i]: float(p) for i, p in enumerate(proba)},
        "missing_fields": missing_fields(payload, features),
    }


def predict_churn(payload: dict) -> dict:
    a = get_artifacts()["churn"]
    X = a["scaler"].transform(_vectorise(payload, a["features"]))
    p = float(a["model"].predict_proba(X)[0, 1])
    return {
        "churn_probability": p,
        "will_churn": bool(p >= 0.5),
        "risk_band": "High" if p >= 0.66 else "Medium" if p >= 0.33 else "Low",
        "model": a["model_name"],
        "threshold_days": a["churn_days"],
        "missing_fields": missing_fields(payload, a["features"]),
    }


def predict_return(payload: dict) -> dict:
    a = get_artifacts()["return"]
    X = a["scaler"].transform(_vectorise(payload, a["features"]))
    p = float(a["model"].predict_proba(X)[0, 1])
    return {
        "return_probability": p,
        "will_return": bool(p >= 0.5),
        "model": a["model_name"],
        # The model is weak (ROC-AUC ~0.58). Saying so at the point of use
        # stops the number being trusted more than it deserves.
        "reliability": "low",
        "note": "Return signal is weak in this dataset; use for ranking manual "
                "checks only, not for automated decisions.",
        "missing_fields": missing_fields(payload, a["features"]),
    }


# ─────────────────────────────────────────────
# CUSTOMER LOOKUP
# ─────────────────────────────────────────────
def list_customers(query: str = "", page: int = 1, page_size: int = 25) -> dict:
    df = get_artifacts()["customers"]
    if query:
        df = df[df["Customer_ID"].str.contains(query, case=False, na=False)]

    total = len(df)
    start = max(0, (page - 1) * page_size)
    rows = df.iloc[start:start + page_size]

    return {
        "total": int(total),
        "page": page,
        "page_size": page_size,
        "customers": [
            {
                "customer_id": r["Customer_ID"],
                "segment": SEGMENT_NAMES[int(r["Segment_Label"])],
                "monetary": float(r["Monetary"]),
                "recency": int(r["Recency"]),
                "frequency": float(r["Frequency"]),
                "txn_count": int(r["Txn_Count"]),
                "churned": bool(r["Churned"]),
            }
            for _, r in rows.iterrows()
        ],
    }


def get_customer(customer_id: str) -> dict | None:
    a = get_artifacts()
    df = a["customers"]
    match = df[df["Customer_ID"] == customer_id]
    if match.empty:
        return None

    row = match.iloc[0]
    payload = row.to_dict()

    segment = predict_segment(payload)
    churn = predict_churn(payload)

    return {
        "customer_id": customer_id,
        "actual_segment": SEGMENT_NAMES[int(row["Segment_Label"])],
        "predicted_segment": segment,
        "churn": churn,
        "profile": {
            "recency": int(row["Recency"]),
            "frequency": float(row["Frequency"]),
            "monetary": float(row["Monetary"]),
            "txn_count": int(row["Txn_Count"]),
            "avg_order_value": float(row["Avg_Order_Value"]),
            "total_profit": float(row["Total_Profit"]),
            "avg_discount": float(row["Avg_Discount"]),
            "avg_csat": float(row["Avg_CSAT"]),
            "return_rate": float(row["Return_Rate"]),
            "tenure_days": int(row["Tenure_Days"]),
            "age": int(row["Customer_Age"]),
        },
        "explanation": explain_customer(customer_id),
    }


# ─────────────────────────────────────────────
# EXPLAINABILITY
# ─────────────────────────────────────────────
def explain_customer(customer_id: str, top_n: int = 8) -> list[dict] | None:
    """
    Per-customer SHAP contributions for the predicted segment.

    Returns the features that pushed this particular prediction, signed:
    positive means the feature argued FOR the predicted class.
    """
    a = get_artifacts()
    df = a["customers"]
    match = df[df["Customer_ID"] == customer_id]
    if match.empty:
        return None

    try:
        import shap
    except ImportError:
        return None

    features = a["segment_features"]
    X = a["segment_scaler"].transform(_vectorise(match.iloc[0].to_dict(), features))

    explainer = shap.TreeExplainer(a["segment_model"])
    values = explainer.shap_values(X)

    # Multiclass SHAP: newer versions give (samples, features, classes)
    pred_class = int(a["segment_model"].predict(X)[0])
    if isinstance(values, list):
        contrib = values[pred_class][0]
    elif values.ndim == 3:
        contrib = values[0, :, pred_class]
    else:
        contrib = values[0]

    order = np.argsort(np.abs(contrib))[::-1][:top_n]
    return [
        {
            "feature": features[i].replace("_", " "),
            "contribution": float(contrib[i]),
            "direction": "increases" if contrib[i] > 0 else "decreases",
            "value": float(match.iloc[0][features[i]]),
        }
        for i in order
    ]


# ─────────────────────────────────────────────
# AGGREGATE VIEWS
# ─────────────────────────────────────────────
def get_overview() -> dict:
    a = get_artifacts()
    df = a["customers"]
    fc = a["forecast"]

    monthly = None
    processed = OUTPUT / "processed_dataset.csv"
    if processed.exists():
        tx = pd.read_csv(processed, usecols=["Transaction_Date", "Net_Amount_BDT"])
        tx["Transaction_Date"] = pd.to_datetime(tx["Transaction_Date"])
        series = (
            tx.set_index("Transaction_Date")["Net_Amount_BDT"]
            .resample("MS").sum().reset_index()
        )
        monthly = [
            {"month": d.strftime("%Y-%m"), "sales": float(v)}
            for d, v in zip(series["Transaction_Date"], series["Net_Amount_BDT"])
        ]

    return {
        "total_customers": int(len(df)),
        "total_revenue": float(df["Monetary"].sum()),
        "total_transactions": int(df["Txn_Count"].sum()),
        "avg_order_value": float(df["Avg_Order_Value"].mean()),
        "churn_rate": float(df["Churned"].mean()),
        "avg_csat": float(df["Avg_CSAT"].mean()),
        "monthly_sales": monthly or [],
        "best_forecast_model": fc.get("best_model", "Seasonal-Naive"),
    }


def get_segments() -> dict:
    a = get_artifacts()
    df = a["customers"]

    profiles = []
    for label in range(4):
        sub = df[df["Segment_Label"] == label]
        if sub.empty:
            continue
        profiles.append({
            "segment": SEGMENT_NAMES[label],
            "count": int(len(sub)),
            "share": float(len(sub) / len(df)),
            "avg_recency": float(sub["Recency"].mean()),
            "avg_frequency": float(sub["Frequency"].mean()),
            "avg_monetary": float(sub["Monetary"].mean()),
            "avg_txn_count": float(sub["Txn_Count"].mean()),
            "churn_rate": float(sub["Churned"].mean()),
        })

    clusters = []
    if a["segments"] is not None and "Cluster" in a["segments"].columns:
        seg = a["segments"]
        for cid, sub in seg.groupby("Cluster"):
            entry = {"cluster": int(cid), "count": int(len(sub))}
            if "Segment" in sub.columns:
                entry["label"] = str(sub["Segment"].iloc[0])
            clusters.append(entry)

    return {"supervised_profiles": profiles, "kmeans_clusters": clusters}


def get_forecast() -> dict:
    fc = get_artifacts()["forecast"]
    actual = list(map(float, fc["actual"]))
    points = [
        {
            "period": f"T+{i+1}",
            "actual": actual[i],
            "lstm": float(fc["lstm_pred"][i]),
            "arima": float(fc["arima_pred"][i]),
            "seasonal_naive": float(fc["snaive_pred"][i]),
        }
        for i in range(len(actual))
    ]
    return {
        "points": points,
        "metrics": {
            k: {m: float(v) for m, v in fc[k].items()}
            for k in ("lstm", "arima", "seasonal_naive")
        },
        "best_model": fc.get("best_model"),
        "note": "The seasonal-naive baseline outperforms both trained models, "
                "which is direct evidence the series is strongly seasonal.",
    }


def get_model_report() -> dict:
    """Everything the Model Report page needs, including the leakage ablation."""
    a = get_artifacts()
    v2 = a["classification_v2"]

    return {
        "segment": {
            "models": {
                name: {
                    "accuracy": r["accuracy"],
                    "ci_low": r["acc_ci"][0], "ci_high": r["acc_ci"][1],
                    "f1_macro": r["f1_macro"], "f1_weighted": r["f1_weighted"],
                    "cv_mean": v2["cv"][name]["mean"], "cv_std": v2["cv"][name]["std"],
                }
                for name, r in v2["test"].items()
            },
            "mcnemar": v2["mcnemar"],
            "n_features": v2["n_features"],
            "n_test": v2["n_test"],
        },
        "ablation": [
            {"variant": "Transaction-level + CLV (both leaks)",
             "accuracy": 0.9481, "mcnemar_p": None},
            {"variant": "Customer-level + CLV (CLV leak only)",
             "accuracy": 0.9453, "mcnemar_p": 0.5235},
            {"variant": "Customer-level, no CLV (honest)",
             "accuracy": v2["test"]["XGBoost"]["accuracy"],
             "mcnemar_p": v2["mcnemar"]["pvalue"]},
        ],
        "churn": {
            "best_model": a["churn_results"]["best_model"],
            "churn_rate": a["churn_results"]["churn_rate"],
            "threshold_days": a["churn_results"]["churn_days"],
            "models": a["churn_results"]["results"],
        },
        "returns": {
            "best_model": a["return_results"]["best_model"],
            "models": a["return_results"]["results"],
        },
        "forecast": get_forecast()["metrics"],
    }
