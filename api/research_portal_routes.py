"""
api/research_portal_routes.py
Research Portal backend — dynamic experiment registry, ML training pipeline,
comparison, and thesis export endpoints.

Architecture
────────────
- Any logged-in user can create experiments (no org required).
- Experiments are stored as JSON files under artifacts/research_portal/.
- run_experiment uses a background thread so the HTTP response returns
  immediately with status="running"; poll /experiments/{id}/status.
- EXP-001 is the locked pharmacy baseline; it is seeded and run once.

Endpoints
─────────
GET  /api/research/portal/datasets              — list built-in datasets
GET  /api/research/portal/vertical-schema       — describe vertical schemas
GET  /api/research/portal/experiments           — list all experiments
POST /api/research/portal/experiments           — create new experiment
GET  /api/research/portal/experiments/{id}      — get full experiment JSON
GET  /api/research/portal/experiments/{id}/status — lightweight status poll
POST /api/research/portal/experiments/{id}/run  — start run (returns immediately)
DELETE /api/research/portal/experiments/{id}    — delete + clean up artifacts
POST /api/research/portal/compare               — compare N experiments
POST /api/research/portal/upload-dataset        — upload custom CSV/XLSX
"""
from __future__ import annotations

import json
import shutil
import sys
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

router = APIRouter(prefix="/api/research/portal", tags=["research-portal"])

ARTIFACTS_DIR = Path("artifacts/research_portal")
ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)

DATASETS_DIR = Path("normalized_data/verticals")
UPLOAD_DIR   = ARTIFACTS_DIR / "uploads"
MODELS_DIR   = ARTIFACTS_DIR / "models"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MODELS_DIR.mkdir(parents=True, exist_ok=True)

BASELINE_ID = "EXP-001"

# ── Vertical schema registry ──────────────────────────────────────────────────

VERTICAL_SCHEMAS: dict[str, dict] = {
    "pharmacy": {
        "description": "Retail pharmacy — medicines, OTC, vitamins",
        "universal_columns": ["Transaction_ID", "Customer_ID", "Transaction_Date",
                              "Product_Name", "Category", "Quantity",
                              "Unit_Price_BDT", "Total_Amount_BDT"],
        "vertical_columns": {
            "Expiry_Date":           "Medicine expiry date (YYYY-MM-DD)",
            "Batch_No":              "Batch / lot number",
            "Drug_Class":            "Drug classification (antibiotic, otc, …)",
            "Prescription_Required": "1 if prescription needed, 0 otherwise",
        },
        "vertical_analyses": ["near_expiry_alert", "drug_class_distribution",
                              "prescription_ratio"],
    },
    "grocery": {
        "description": "General grocery / kirana store",
        "universal_columns": ["Transaction_ID", "Customer_ID", "Transaction_Date",
                              "Product_Name", "Category", "Quantity",
                              "Unit_Price_BDT", "Total_Amount_BDT"],
        "vertical_columns": {
            "Weight_Unit":     "kg / g / pcs / litre / ml / dozen",
            "Perishable":      "1 if perishable, 0 otherwise",
            "Shelf_Life_Days": "Days before spoilage",
        },
        "vertical_analyses": ["perishable_turnover", "short_shelf_life_reorder"],
    },
    "clothing": {
        "description": "Ready-made garments & clothing boutique",
        "universal_columns": ["Transaction_ID", "Customer_ID", "Transaction_Date",
                              "Product_Name", "Category", "Quantity",
                              "Unit_Price_BDT", "Total_Amount_BDT"],
        "vertical_columns": {
            "Size":   "XS / S / M / L / XL / XXL",
            "Gender": "male / female / kids / unisex",
            "Season": "summer / winter / eid / all-season",
            "Fabric": "cotton / polyester / linen / silk / denim / georgette",
        },
        "vertical_analyses": ["size_distribution", "season_demand", "gender_split"],
    },
    "restaurant": {
        "description": "Food & beverage — dine-in and takeaway",
        "universal_columns": ["Transaction_ID", "Customer_ID", "Transaction_Date",
                              "Product_Name", "Category", "Quantity",
                              "Unit_Price_BDT", "Total_Amount_BDT"],
        "vertical_columns": {
            "Meal_Time":  "morning / lunch / afternoon / evening / dinner",
            "Order_Type": "dine_in / takeaway / delivery",
        },
        "vertical_analyses": ["peak_hour_analysis", "order_type_split"],
    },
    "electronics": {
        "description": "Mobile accessories & consumer electronics",
        "universal_columns": ["Transaction_ID", "Customer_ID", "Transaction_Date",
                              "Product_Name", "Category", "Quantity",
                              "Unit_Price_BDT", "Total_Amount_BDT"],
        "vertical_columns": {
            "Brand":             "Product brand",
            "Warranty_Months":   "Warranty period in months",
            "Product_Condition": "new / refurbished",
        },
        "vertical_analyses": ["brand_performance", "warranty_distribution"],
    },
    "auto_parts": {
        "description": "Motorbike / CNG auto-rickshaw spare parts shop",
        "universal_columns": ["Transaction_ID", "Customer_ID", "Transaction_Date",
                              "Product_Name", "Category", "Quantity",
                              "Unit_Price_BDT", "Total_Amount_BDT"],
        "vertical_columns": {
            "Vehicle_Type":      "motorbike / CNG_auto / car / bicycle",
            "Brand":             "Honda / Bajaj / Yamaha / TVS / Hero etc.",
            "Part_Number":       "Manufacturer part number",
            "Product_Condition": "new / reconditioned",
            "Warranty_Days":     "Warranty in days (0 = no warranty)",
        },
        "vertical_analyses": ["vehicle_type_split", "brand_performance",
                              "condition_mix", "warranty_distribution"],
    },
    "stationery": {
        "description": "School & office stationery, books, art supplies",
        "universal_columns": ["Transaction_ID", "Customer_ID", "Transaction_Date",
                              "Product_Name", "Category", "Quantity",
                              "Unit_Price_BDT", "Total_Amount_BDT"],
        "vertical_columns": {
            "Customer_Type": "student / office / institution",
            "Season_Tag":    "new_year_term / exam_season / new_term / vacation etc.",
            "Paper_Size":    "A4 / A3 / legal / custom / N/A",
        },
        "vertical_analyses": ["customer_type_split", "season_demand", "paper_size_dist"],
    },
    "generic": {
        "description": "Any SME dataset — universal analysis only",
        "universal_columns": ["Transaction_ID", "Customer_ID", "Transaction_Date",
                              "Product_Name", "Category", "Quantity",
                              "Unit_Price_BDT", "Total_Amount_BDT"],
        "vertical_columns": {},
        "vertical_analyses": [],
    },
}

# ── Vertical detection ────────────────────────────────────────────────────────

def detect_vertical(cols: list[str]) -> str:
    col_set = {c.lower() for c in cols}
    if "expiry_date" in col_set or "batch_no" in col_set:
        return "pharmacy"
    if "size" in col_set and "fabric" in col_set:
        return "clothing"
    if "meal_time" in col_set or "order_type" in col_set:
        return "restaurant"
    if "part_number" in col_set or "vehicle_type" in col_set:
        return "auto_parts"
    if "season_tag" in col_set or "customer_type" in col_set:
        return "stationery"
    if "brand" in col_set and ("warranty_months" in col_set or "warranty_days" in col_set):
        return "electronics"
    if "perishable" in col_set or "shelf_life_days" in col_set:
        return "grocery"
    return "generic"

# ── Numeric helpers ───────────────────────────────────────────────────────────

def _safe_float(v) -> float | None:
    try:
        f = float(v)
        return None if (f != f) or f == float("inf") or f == float("-inf") else round(f, 4)
    except Exception:
        return None

def _lift_at_10(actual: np.ndarray, proba: np.ndarray) -> float:
    n = max(1, int(np.ceil(len(actual) * 0.1)))
    base = float(actual.mean())
    return float(actual[np.argsort(proba)[::-1][:n]].mean() / base) if base > 0 else float("nan")

# ── Universal pipeline ────────────────────────────────────────────────────────

def run_universal_pipeline(df: pd.DataFrame, config: dict) -> dict:
    results: dict[str, Any] = {}
    date_col = "Transaction_Date" if "Transaction_Date" in df.columns else None

    results["dataset_summary"] = {
        "rows":      len(df),
        "customers": df["Customer_ID"].nunique() if "Customer_ID" in df.columns else 0,
        "products":  df["Product_Name"].nunique() if "Product_Name" in df.columns else 0,
        "date_range": [
            str(df[date_col].min())[:10] if date_col else None,
            str(df[date_col].max())[:10] if date_col else None,
        ],
        "vertical": detect_vertical(list(df.columns)),
    }

    # RFM
    if date_col and "Customer_ID" in df.columns and "Total_Amount_BDT" in df.columns:
        try:
            df = df.copy()
            df[date_col] = pd.to_datetime(df[date_col])
            ref = df[date_col].max()
            tx_col = "Transaction_ID" if "Transaction_ID" in df.columns else date_col
            rfm = df.groupby("Customer_ID").agg(
                Recency   = (date_col,          lambda x: (ref - x.max()).days),
                Frequency = (tx_col,            "count"),
                Monetary  = ("Total_Amount_BDT", "sum"),
            )
            results["rfm"] = {
                "recency_mean":   _safe_float(rfm["Recency"].mean()),
                "frequency_mean": _safe_float(rfm["Frequency"].mean()),
                "monetary_mean":  _safe_float(rfm["Monetary"].mean()),
                "recency_median": _safe_float(rfm["Recency"].median()),
                "n_customers":    int(len(rfm)),
            }
        except Exception as e:
            results["rfm"] = {"error": str(e)}

    # Churn estimate (recency-threshold)
    churn_days = int(config.get("churn_threshold_days", 90))
    if "rfm" in results and "error" not in results["rfm"]:
        try:
            results["churn"] = {
                "threshold_days": churn_days,
                "churn_rate":     round(float((rfm["Recency"] > churn_days).mean()), 4),
                "churned_count":  int((rfm["Recency"] > churn_days).sum()),
                "active_count":   int((rfm["Recency"] <= churn_days).sum()),
            }
        except Exception as e:
            results["churn"] = {"error": str(e)}

    # Monthly revenue + seasonal-naive WAPE
    if date_col and "Total_Amount_BDT" in df.columns:
        try:
            df[date_col] = pd.to_datetime(df[date_col])
            monthly = (
                df.set_index(date_col)
                  .resample("ME")["Total_Amount_BDT"]
                  .sum()
                  .reset_index()
            )
            monthly.columns = ["month", "revenue"]
            sn_wape = None
            if len(monthly) >= 13:
                actual   = monthly["revenue"].values[12:]
                baseline = monthly["revenue"].values[:-12]
                denom = float(np.abs(actual).sum())
                sn_wape = _safe_float(np.abs(actual - baseline).sum() / denom if denom > 0 else None)
            results["forecast"] = {
                "monthly_points":      len(monthly),
                "seasonal_naive_wape": sn_wape,
                "monthly_revenue":     [
                    {"month": str(r.month)[:7], "revenue": _safe_float(r.revenue)}
                    for r in monthly.itertuples()
                ],
            }
        except Exception as e:
            results["forecast"] = {"error": str(e)}

    # Customer segmentation (spend quartiles)
    if "Customer_ID" in df.columns and "Total_Amount_BDT" in df.columns:
        try:
            spend = df.groupby("Customer_ID")["Total_Amount_BDT"].sum()
            q = spend.quantile([0.35, 0.65, 0.85]).values
            def tier(s):
                if s <= q[0]: return "Low"
                if s <= q[1]: return "Moderate"
                if s <= q[2]: return "High"
                return "VIP"
            tier_counts = spend.map(tier).value_counts().to_dict()
            results["segmentation"] = {
                "method":    "spend_quartile",
                "segments":  tier_counts,
                "thresholds": {
                    "low_max":      _safe_float(q[0]),
                    "moderate_max": _safe_float(q[1]),
                    "high_max":     _safe_float(q[2]),
                },
            }
        except Exception as e:
            results["segmentation"] = {"error": str(e)}

    # ABC product analysis
    if "Product_Name" in df.columns and "Total_Amount_BDT" in df.columns:
        try:
            prod_rev = df.groupby("Product_Name")["Total_Amount_BDT"].sum().sort_values(ascending=False)
            total  = prod_rev.sum()
            cumsum = prod_rev.cumsum() / total
            results["abc_analysis"] = {
                "A_products": int((cumsum <= 0.80).sum()),
                "B_products": int(((cumsum > 0.80) & (cumsum <= 0.95)).sum()),
                "C_products": int((cumsum > 0.95).sum()),
                "top_5": [{"name": k, "revenue": _safe_float(v)}
                          for k, v in list(prod_rev.head(5).items())],
            }
        except Exception as e:
            results["abc_analysis"] = {"error": str(e)}

    return results


# ── Vertical-specific pipeline ────────────────────────────────────────────────

def run_vertical_pipeline(df: pd.DataFrame, vertical: str) -> dict:
    results: dict[str, Any] = {}

    if vertical == "pharmacy":
        if "Expiry_Date" in df.columns:
            try:
                df = df.copy()
                df["Expiry_Date"] = pd.to_datetime(df["Expiry_Date"])
                today = pd.Timestamp.today()
                df["days_to_expiry"] = (df["Expiry_Date"] - today).dt.days
                ne = df[df["days_to_expiry"] <= 90]
                results["near_expiry"] = {
                    "count_within_90_days": int(len(ne)),
                    "pct_of_stock":         round(len(ne) / len(df) * 100, 2),
                }
            except Exception as e:
                results["near_expiry"] = {"error": str(e)}
        if "Drug_Class" in df.columns:
            results["drug_class_distribution"] = df["Drug_Class"].value_counts().to_dict()
        if "Prescription_Required" in df.columns:
            results["prescription_ratio"] = round(float(df["Prescription_Required"].mean()) * 100, 2)

    elif vertical == "clothing":
        for col in ["Size", "Gender", "Season", "Fabric"]:
            if col in df.columns:
                results[f"{col.lower()}_distribution"] = df[col].value_counts().to_dict()

    elif vertical == "restaurant":
        if "Meal_Time" in df.columns:
            results["peak_hours"] = df["Meal_Time"].value_counts().to_dict()
        if "Order_Type" in df.columns:
            results["order_type_split"] = df["Order_Type"].value_counts().to_dict()

    elif vertical == "electronics":
        if "Brand" in df.columns:
            br = df.groupby("Brand")["Total_Amount_BDT"].sum()
            results["brand_performance"] = br.sort_values(ascending=False).head(10).to_dict()
        if "Product_Condition" in df.columns:
            results["condition_mix"] = df["Product_Condition"].value_counts().to_dict()

    elif vertical == "grocery":
        if "Perishable" in df.columns:
            results["perishable_ratio"] = round(float(df["Perishable"].mean()) * 100, 2)
        if "Shelf_Life_Days" in df.columns:
            results["avg_shelf_life_days"] = _safe_float(df["Shelf_Life_Days"].mean())

    elif vertical == "auto_parts":
        if "Vehicle_Type" in df.columns:
            results["vehicle_type_split"] = df["Vehicle_Type"].value_counts().to_dict()
        if "Brand" in df.columns:
            br = df.groupby("Brand")["Total_Amount_BDT"].sum()
            results["brand_performance"] = br.sort_values(ascending=False).head(10).to_dict()
        if "Product_Condition" in df.columns:
            results["condition_mix"] = df["Product_Condition"].value_counts().to_dict()
        if "Warranty_Days" in df.columns:
            results["warranty_distribution"] = {
                "no_warranty": int((df["Warranty_Days"] == 0).sum()),
                "with_warranty": int((df["Warranty_Days"] > 0).sum()),
                "avg_warranty_days": _safe_float(df[df["Warranty_Days"] > 0]["Warranty_Days"].mean()),
            }

    elif vertical == "stationery":
        if "Customer_Type" in df.columns:
            results["customer_type_split"] = df["Customer_Type"].value_counts().to_dict()
        if "Season_Tag" in df.columns:
            results["season_demand"] = df["Season_Tag"].value_counts().to_dict()
        if "Paper_Size" in df.columns:
            valid = df[df["Paper_Size"] != "N/A"]
            if len(valid):
                results["paper_size_distribution"] = valid["Paper_Size"].value_counts().to_dict()

    return results


# ── Thesis-aligned ML models ──────────────────────────────────────────────────

def _train_portal_churn_model(df: pd.DataFrame, config: dict) -> dict:
    """
    Customer-level churn classifier — thesis methodology (08_churn_prediction.py).

    Label   : Recency > churn_threshold_days (the customer has not returned).
    Features: Frequency, Monetary, avg_order_value, unique_products,
              tenure_days, purchase_frequency_monthly.
    Split   : Stratified 5-fold CV (customer-level, no temporal leakage because
              recency is NOT a feature — it IS the label by construction).
    Models  : XGBoost + Random Forest.
    Metrics : ROC-AUC, PR-AUC, Lift@10% — all out-of-fold via cross_val_predict.
    """
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import StratifiedKFold, cross_val_predict
    from sklearn.metrics import roc_auc_score, average_precision_score
    try:
        from xgboost import XGBClassifier
        _HAS_XGB = True
    except ImportError:
        _HAS_XGB = False

    threshold = int(config.get("churn_threshold_days", 90))
    date_col  = "Transaction_Date"
    if date_col not in df.columns or "Customer_ID" not in df.columns:
        raise ValueError("Need Transaction_Date and Customer_ID columns")

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    ref_date = df[date_col].max()
    tx_col = "Transaction_ID" if "Transaction_ID" in df.columns else date_col

    # One row per customer
    rfm = df.groupby("Customer_ID").agg(
        recency       = (date_col,          lambda x: (ref_date - x.max()).days),
        frequency     = (tx_col,            "count"),
        monetary      = ("Total_Amount_BDT", "sum"),
        first_purchase= (date_col,          "min"),
        unique_prods  = ("Product_Name",    "nunique") if "Product_Name" in df.columns
                        else (tx_col,       "count"),
    ).reset_index()

    rfm["avg_order_value"]           = rfm["monetary"] / rfm["frequency"].clip(lower=1)
    rfm["tenure_days"]               = (ref_date - rfm["first_purchase"]).dt.days
    rfm["purchase_frequency_monthly"]= rfm["frequency"] / (rfm["tenure_days"] / 30).clip(lower=1)
    rfm["churn"]                     = (rfm["recency"] > threshold).astype(int)

    base_rate = float(rfm["churn"].mean())

    # Require at least 100 customers with both classes present
    n_pos = int(rfm["churn"].sum())
    n_neg = len(rfm) - n_pos
    if len(rfm) < 100 or n_pos < 15 or n_neg < 15:
        raise ValueError(
            f"Insufficient data: {len(rfm)} customers, "
            f"{n_pos} churned, {n_neg} active. Need ≥100 customers with ≥15 in each class."
        )

    # Features (no recency — that IS the label)
    features = ["frequency", "monetary", "avg_order_value",
                "unique_prods", "tenure_days", "purchase_frequency_monthly"]
    X = rfm[features].fillna(0).values
    y = rfm["churn"].values

    results: dict[str, Any] = {}
    cv = StratifiedKFold(n_splits=int(config.get("cv_folds", 5)), shuffle=True, random_state=42)

    model_specs: list[tuple[str, Any]] = [
        ("random_forest", RandomForestClassifier(
            n_estimators=200, max_depth=10, class_weight="balanced",
            random_state=42, n_jobs=2)),
    ]
    if _HAS_XGB:
        scale_pw = n_neg / n_pos if n_pos > 0 else 1.0
        model_specs.append(("xgboost", XGBClassifier(
            n_estimators=200, max_depth=5, learning_rate=0.05,
            scale_pos_weight=scale_pw, random_state=42,
            eval_metric="logloss", verbosity=0,
        )))

    for name, model in model_specs:
        try:
            proba = cross_val_predict(model, X, y, cv=cv, method="predict_proba")[:, 1]
            results[name] = {
                "roc_auc":   round(float(roc_auc_score(y, proba)), 4),
                "pr_auc":    round(float(average_precision_score(y, proba)), 4),
                "lift_at_10": round(_lift_at_10(y, proba), 3),
            }
        except Exception as e:
            results[name] = {"error": str(e)}

    winner = max(
        (k for k in results if "roc_auc" in results[k]),
        key=lambda k: results[k]["roc_auc"],
        default=None,
    )
    return {
        "method":           "customer_level_stratified_cv",
        "customers":        len(rfm),
        "churn_rate":       round(base_rate, 4),
        "threshold_days":   threshold,
        "cv_folds":         int(config.get("cv_folds", 5)),
        "features_used":    features,
        "models":           results,
        "winner_by_roc_auc": winner,
    }


def _train_portal_forecast_model(df: pd.DataFrame, config: dict) -> dict:
    """
    Monthly-level forecast — thesis methodology (04_forecasting.py):
      seasonal-naive vs ARIMA(2,1,2).
    Needs ≥ 13 monthly data points.  Holdout = last 20% (≥ 3 months).
    """
    date_col = "Transaction_Date"
    if date_col not in df.columns or "Total_Amount_BDT" not in df.columns:
        raise ValueError("Need Transaction_Date and Total_Amount_BDT columns")

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    monthly = df.set_index(date_col).resample("ME")["Total_Amount_BDT"].sum()

    if len(monthly) < 13:
        raise ValueError(
            f"Forecasting needs ≥13 months of data; got {len(monthly)}. "
            "Upload at least 13 months of transactions."
        )

    n_test = max(3, int(len(monthly) * 0.20))
    train  = monthly.iloc[:-n_test]
    test   = monthly.iloc[-n_test:]
    actual = test.values

    def _wape(a, p):
        d = float(np.abs(a).sum())
        return round(float(np.abs(a - p).sum() / d), 4) if d > 0 else None

    def _mae(a, p):
        return round(float(np.abs(a - p).mean()), 2)

    results: dict[str, Any] = {}

    # Seasonal naive (same month, 1 year ago)
    if len(train) >= 12:
        sn_pred = np.array([
            train.values[-(12 - i % 12)] if len(train) >= 12 else train.values[-1]
            for i in range(n_test)
        ])
        results["seasonal_naive"] = {"wape": _wape(actual, sn_pred), "mae": _mae(actual, sn_pred)}
    else:
        mean_pred = np.full(n_test, train.mean())
        results["mean_baseline"] = {"wape": _wape(actual, mean_pred), "mae": _mae(actual, mean_pred)}

    # ARIMA(2,1,2)
    try:
        from statsmodels.tsa.arima.model import ARIMA
        arima = ARIMA(train.values, order=(2, 1, 2)).fit()
        arima_pred = arima.forecast(n_test)
        results["arima_2_1_2"] = {"wape": _wape(actual, arima_pred), "mae": _mae(actual, arima_pred)}
    except Exception as e:
        results["arima_2_1_2"] = {"error": str(e)}

    winner = min(
        (k for k in results if isinstance(results[k], dict) and results[k].get("wape") is not None),
        key=lambda k: results[k]["wape"],
        default=None,
    )

    return {
        "method":       "monthly_holdout",
        "train_months": int(len(train)),
        "test_months":  int(n_test),
        "models":       results,
        "winner":       winner,
        "monthly_totals": {str(k)[:7]: round(float(v), 2) for k, v in monthly.tail(36).items()},
    }


def _train_portal_segments(df: pd.DataFrame, config: dict) -> dict:
    """
    K-Means segmentation on RFM features — thesis methodology (03_clustering.py).
    Returns silhouette + per-cluster profile.
    """
    from sklearn.cluster import KMeans
    from sklearn.preprocessing import StandardScaler
    from sklearn.metrics import silhouette_score

    date_col = "Transaction_Date"
    if "Customer_ID" not in df.columns or "Total_Amount_BDT" not in df.columns:
        raise ValueError("Need Customer_ID and Total_Amount_BDT columns")

    df = df.copy()
    if date_col in df.columns:
        df[date_col] = pd.to_datetime(df[date_col])
        ref = df[date_col].max()
        tx_col = "Transaction_ID" if "Transaction_ID" in df.columns else date_col
        rfm = df.groupby("Customer_ID").agg(
            recency   = (date_col,           lambda x: (ref - x.max()).days),
            frequency = (tx_col,             "count"),
            monetary  = ("Total_Amount_BDT", "sum"),
        ).reset_index()
    else:
        rfm = df.groupby("Customer_ID").agg(
            frequency = ("Transaction_ID",   "count") if "Transaction_ID" in df.columns
                        else ("Total_Amount_BDT", "count"),
            monetary  = ("Total_Amount_BDT", "sum"),
        ).reset_index()
        rfm["recency"] = 0

    k = min(int(config.get("segment_k", 4)), len(rfm) - 1)
    if len(rfm) < 20:
        raise ValueError(f"Only {len(rfm)} customers — need ≥20 for segmentation.")
    if k < 2:
        raise ValueError("Need ≥ 2 clusters (segment_k ≥ 2).")

    features = ["recency", "frequency", "monetary"]
    X = StandardScaler().fit_transform(rfm[features])
    km = KMeans(n_clusters=k, random_state=42, n_init=10).fit(X)
    rfm["cluster"] = km.labels_

    sil = float(silhouette_score(X, km.labels_)) if k > 1 else float("nan")

    # Name clusters by monetary rank
    ranking = rfm.groupby("cluster")["monetary"].mean().sort_values().index.tolist()
    tier_names = ["Low value", "Moderate value", "High value", "VIP"][-k:]
    tier_map   = {c: tier_names[i] for i, c in enumerate(ranking)}

    profile: dict[str, Any] = {}
    for c, grp in rfm.groupby("cluster"):
        tier = tier_map[c]
        profile[tier] = {
            "count":              int(len(grp)),
            "avg_monetary":       round(float(grp["monetary"].mean()), 2),
            "avg_recency_days":   round(float(grp["recency"].mean()), 1),
            "avg_frequency":      round(float(grp["frequency"].mean()), 2),
        }

    return {
        "method":    "kmeans_rfm",
        "customers": len(rfm),
        "k":         k,
        "silhouette": round(sil, 4),
        "profile":   profile,
    }


# ── ML training dispatcher ────────────────────────────────────────────────────

def _run_ml_training(df: pd.DataFrame, config: dict, exp_id: str) -> dict:
    """
    Run ML training in the calling thread, writing progress to the experiment JSON.
    Called from the background thread started by run_experiment_bg.
    """
    results: dict[str, Any] = {}

    if config.get("run_churn", True):
        _update_progress(exp_id, "churn", "running")
        try:
            results["churn_model"] = _train_portal_churn_model(df, config)
            _update_progress(exp_id, "churn", "done")
        except Exception as e:
            results["churn_model"] = {"error": str(e)}
            _update_progress(exp_id, "churn", f"failed: {e}")

    if config.get("run_segments", True):
        _update_progress(exp_id, "segmentation", "running")
        try:
            results["segments_model"] = _train_portal_segments(df, config)
            _update_progress(exp_id, "segmentation", "done")
        except Exception as e:
            results["segments_model"] = {"error": str(e)}
            _update_progress(exp_id, "segmentation", f"failed: {e}")

    if config.get("run_forecast", False):
        _update_progress(exp_id, "forecast", "running")
        try:
            results["forecast_model"] = _train_portal_forecast_model(df, config)
            _update_progress(exp_id, "forecast", "done")
        except Exception as e:
            results["forecast_model"] = {"error": str(e)}
            _update_progress(exp_id, "forecast", f"failed: {e}")

    return results


# ── Experiment storage helpers ────────────────────────────────────────────────

def _exp_path(exp_id: str) -> Path:
    return ARTIFACTS_DIR / f"{exp_id}.json"

def _load_exp(exp_id: str) -> dict:
    p = _exp_path(exp_id)
    if not p.exists():
        raise HTTPException(404, f"Experiment {exp_id} not found")
    return json.loads(p.read_text(encoding="utf-8"))

def _save_exp(exp: dict):
    _exp_path(exp["id"]).write_text(
        json.dumps(exp, ensure_ascii=False, indent=2), encoding="utf-8"
    )

def _update_progress(exp_id: str, step: str, status: str):
    """Update experiment JSON with current step/status while running."""
    try:
        p = _exp_path(exp_id)
        if not p.exists():
            return
        exp = json.loads(p.read_text(encoding="utf-8"))
        progress = exp.get("progress", [])
        # Update existing step or append
        for item in progress:
            if item["step"] == step:
                item["status"] = status
                item["ts"] = time.time()
                break
        else:
            progress.append({"step": step, "status": status, "ts": time.time()})
        exp["progress"] = progress
        p.write_text(json.dumps(exp, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass  # progress updates are best-effort


def _seed_baseline():
    p = _exp_path(BASELINE_ID)
    if p.exists():
        return
    baseline = {
        "id":           BASELINE_ID,
        "name":         "Pharmacy Baseline (Thesis — Locked)",
        "description":  "BD_Pharmacy_Dataset — fixed reference, locked",
        "vertical":     "pharmacy",
        "dataset_source": "built-in",
        "dataset_path": str(DATASETS_DIR / "pharmacy" / "pharmacy_dataset.csv"),
        "config": {
            "train_ratio": 0.70, "val_ratio": 0.15, "test_ratio": 0.15,
            "cv_folds": 5, "random_seed": 42, "churn_threshold_days": 90,
            "stratified": True, "run_churn": True, "run_segments": True,
            "run_forecast": False, "segment_k": 4,
        },
        "locked":     True,
        "status":     "pending",
        "progress":   [],
        "results":    None,
        "created_at": time.time(),
        "run_at":     None,
    }
    _save_exp(baseline)

_seed_baseline()


# ── Background runner ─────────────────────────────────────────────────────────

def _run_experiment_bg(exp_id: str):
    """Run the full pipeline in a background thread, updating the JSON as it goes."""
    try:
        exp = _load_exp(exp_id)
        dataset_path = Path(exp["dataset_path"])
        if not dataset_path.exists():
            exp["status"]       = "failed"
            exp["error"]        = f"Dataset not found: {dataset_path}"
            _save_exp(exp)
            return

        try:
            df = pd.read_csv(dataset_path, encoding="utf-8-sig")
        except Exception as e:
            exp["status"] = "failed"
            exp["error"]  = f"Cannot read dataset: {e}"
            _save_exp(exp)
            return

        config   = exp.get("config", {})
        vertical = detect_vertical(list(df.columns))

        _update_progress(exp_id, "universal_pipeline", "running")
        universal = run_universal_pipeline(df, config)
        specific  = run_vertical_pipeline(df, vertical)
        _update_progress(exp_id, "universal_pipeline", "done")

        ml_results = _run_ml_training(df, config, exp_id)

        exp = _load_exp(exp_id)   # re-read (progress may have updated it)
        exp["status"]  = "completed"
        exp["run_at"]  = time.time()
        exp["results"] = {
            "detected_vertical": vertical,
            "universal":         universal,
            "vertical_specific": specific,
            "ml_models":         ml_results,
        }
        _save_exp(exp)

    except Exception:
        try:
            exp = _load_exp(exp_id)
            exp["status"] = "failed"
            exp["error"]  = traceback.format_exc()[-500:]
            _save_exp(exp)
        except Exception:
            pass


# ── Routes ────────────────────────────────────────────────────────────────────

@router.get("/datasets")
def list_datasets():
    built_in = []
    for v in VERTICAL_SCHEMAS:
        if v == "generic":
            continue
        path = DATASETS_DIR / v / f"{v}_dataset.csv"
        built_in.append({
            "id":          f"builtin_{v}",
            "name":        f"{v.replace('_', ' ').title()} — Bangladesh SME",
            "vertical":    v,
            "description": VERTICAL_SCHEMAS[v]["description"],
            "available":   path.exists(),
            "rows":        30000,
        })
    return {"datasets": built_in}


@router.get("/vertical-schema")
def vertical_schema():
    return VERTICAL_SCHEMAS


@router.get("/experiments")
def list_experiments():
    exps = []
    for p in sorted(ARTIFACTS_DIR.glob("EXP-*.json")):
        try:
            e = json.loads(p.read_text(encoding="utf-8"))
            exps.append({k: e.get(k) for k in
                         ["id", "name", "vertical", "status", "locked",
                          "created_at", "run_at", "config", "progress"]})
        except Exception:
            pass
    return {"experiments": exps}


class CreateExperimentBody(BaseModel):
    name:           str
    description:    str   = ""
    vertical:       str   = "pharmacy"
    dataset_source: str   = "built-in"   # "built-in" | "upload"
    dataset_id:     str | None = None
    upload_path:    str | None = None
    config:         dict  = {}


@router.post("/experiments")
def create_experiment(body: CreateExperimentBody):
    exp_id = f"EXP-{str(uuid.uuid4())[:8].upper()}"
    default_config = {
        "train_ratio": 0.70, "val_ratio": 0.15, "test_ratio": 0.15,
        "cv_folds": 5, "random_seed": 42, "churn_threshold_days": 90,
        "stratified": True, "run_churn": True, "run_segments": True,
        "run_forecast": False, "segment_k": 4,
    }
    default_config.update(body.config)

    if body.dataset_source == "built-in":
        v = body.vertical if body.vertical in VERTICAL_SCHEMAS else "pharmacy"
        dataset_path = str(DATASETS_DIR / v / f"{v}_dataset.csv")
    elif body.dataset_source == "upload" and body.upload_path:
        dataset_path = body.upload_path
    else:
        raise HTTPException(400, "Provide dataset_id for built-in or upload_path for uploaded datasets")

    exp = {
        "id":             exp_id,
        "name":           body.name,
        "description":    body.description,
        "vertical":       body.vertical,
        "dataset_source": body.dataset_source,
        "dataset_path":   dataset_path,
        "config":         default_config,
        "locked":         False,
        "status":         "pending",
        "progress":       [],
        "results":        None,
        "created_at":     time.time(),
        "run_at":         None,
    }
    _save_exp(exp)
    return exp


@router.get("/experiments/{exp_id}")
def get_experiment(exp_id: str):
    return _load_exp(exp_id)


@router.get("/experiments/{exp_id}/status")
def experiment_status(exp_id: str):
    exp = _load_exp(exp_id)
    return {
        "id":       exp["id"],
        "status":   exp.get("status"),
        "progress": exp.get("progress", []),
        "run_at":   exp.get("run_at"),
        "error":    exp.get("error"),
    }


@router.post("/experiments/{exp_id}/run")
def run_experiment(exp_id: str):
    exp = _load_exp(exp_id)
    if exp.get("status") == "running":
        return exp

    # Mark as running immediately, clear old results
    exp["status"]   = "running"
    exp["progress"] = []
    exp["error"]    = None
    exp["run_at"]   = time.time()
    _save_exp(exp)

    # Start background thread — returns immediately to the HTTP client
    t = threading.Thread(target=_run_experiment_bg, args=(exp_id,), daemon=True)
    t.start()

    return exp


@router.delete("/experiments/{exp_id}")
def delete_experiment(exp_id: str):
    exp = _load_exp(exp_id)
    if exp.get("locked"):
        raise HTTPException(403, "Baseline experiment is locked and cannot be deleted")

    # Clean up model artifacts
    model_dir = MODELS_DIR / exp_id
    if model_dir.exists():
        shutil.rmtree(model_dir, ignore_errors=True)

    # Clean up uploaded dataset if it came from an upload
    if exp.get("dataset_source") == "upload" and exp.get("dataset_path"):
        up = Path(exp["dataset_path"])
        if up.exists() and str(up).startswith(str(UPLOAD_DIR)):
            up.unlink(missing_ok=True)

    _exp_path(exp_id).unlink(missing_ok=True)
    return {"deleted": exp_id}


class CompareBody(BaseModel):
    experiment_ids: list[str]


@router.post("/compare")
def compare_experiments(body: CompareBody):
    if len(body.experiment_ids) < 2:
        raise HTTPException(400, "Provide at least 2 experiment IDs to compare")
    rows = []
    for eid in body.experiment_ids:
        exp = _load_exp(eid)
        if exp.get("status") != "completed" or not exp.get("results"):
            raise HTTPException(400, f"Experiment {eid} has not completed yet")

        u  = exp["results"].get("universal", {})
        ml = exp["results"].get("ml_models", {})

        churn_m  = ml.get("churn_model",   {})
        seg_m    = ml.get("segments_model",{})
        fc_m     = ml.get("forecast_model",{})

        cm = churn_m.get("models", {}) if isinstance(churn_m, dict) else {}
        best_roc = max((v.get("roc_auc", 0) for v in cm.values() if "roc_auc" in v), default=None) if cm else None
        best_prc = max((v.get("pr_auc",  0) for v in cm.values() if "pr_auc"  in v), default=None) if cm else None

        rows.append({
            "id":               exp["id"],
            "name":             exp["name"],
            "vertical":         exp["results"].get("detected_vertical"),
            "rows":             u.get("dataset_summary", {}).get("rows"),
            "customers":        u.get("dataset_summary", {}).get("customers"),
            "churn_rate":       u.get("churn", {}).get("churn_rate"),
            "recency_mean":     u.get("rfm", {}).get("recency_mean"),
            "frequency_mean":   u.get("rfm", {}).get("frequency_mean"),
            "monetary_mean":    u.get("rfm", {}).get("monetary_mean"),
            "seasonal_naive_wape": u.get("forecast", {}).get("seasonal_naive_wape"),
            "top_segment":      max(u.get("segmentation", {}).get("segments", {}).items(),
                                    key=lambda x: x[1])[0]
                                if u.get("segmentation", {}).get("segments") else None,
            "churn_roc_auc":    round(best_roc, 4) if best_roc is not None else None,
            "churn_pr_auc":     round(best_prc, 4) if best_prc is not None else None,
            "seg_silhouette":   round(seg_m.get("silhouette", 0), 4)
                                if isinstance(seg_m, dict) and "silhouette" in seg_m else None,
            "seg_customers":    seg_m.get("customers") if isinstance(seg_m, dict) else None,
            "forecast_wape":    round(min(
                                    (v.get("wape", 1) for v in fc_m.get("models", {}).values()
                                     if isinstance(v, dict) and v.get("wape") is not None),
                                    default=1.0), 4)
                                if isinstance(fc_m, dict) and fc_m.get("models") else None,
        })
    return {"comparison": rows}


@router.post("/upload-dataset")
async def upload_dataset(file: UploadFile = File(...)):
    if not (file.filename or "").endswith((".csv", ".xlsx")):
        raise HTTPException(400, "Only .csv and .xlsx files are accepted")
    content = await file.read()
    safe_name = f"{uuid.uuid4().hex}_{file.filename}"
    dest = UPLOAD_DIR / safe_name
    dest.write_bytes(content)

    try:
        df = (pd.read_csv(dest, encoding="utf-8-sig")
              if (file.filename or "").endswith(".csv")
              else pd.read_excel(dest))
    except Exception as e:
        dest.unlink(missing_ok=True)
        raise HTTPException(422, f"Cannot parse file: {e}")

    vertical = detect_vertical(list(df.columns))
    schema   = VERTICAL_SCHEMAS.get(vertical, VERTICAL_SCHEMAS["generic"])
    missing  = [c for c in schema["universal_columns"] if c not in df.columns]

    return {
        "upload_path":       str(dest),
        "filename":          file.filename,
        "rows":              len(df),
        "columns":           list(df.columns),
        "detected_vertical": vertical,
        "missing_required":  missing,
        "valid":             len(missing) == 0,
    }
