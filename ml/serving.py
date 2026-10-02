"""Serving layer for real-data models trained by ml/real_pipeline.py.

The only module that opens a joblib artifact for the B-SMART live API,
mirroring predict.py's rule for the thesis pipeline: load what was trained,
never re-fit, and never fabricate a prediction when a model or the history
it needs isn't there — return None and let the caller fall back to a
transparent baseline instead.
"""

from __future__ import annotations

from pathlib import Path

import joblib
import pandas as pd

from .real_pipeline import churn_snapshots, customer_rfm, demand_features, return_features

ARTIFACTS_ROOT = Path("artifacts/real")

_cache: dict[str, tuple[float, dict]] = {}


def _artifact_path(organization_id: str, name: str) -> Path:
    return ARTIFACTS_ROOT / organization_id / name


def _load(organization_id: str, name: str) -> dict | None:
    path = _artifact_path(organization_id, name)
    if not path.is_file():
        return None
    mtime = path.stat().st_mtime
    key = f"{organization_id}/{name}"
    cached = _cache.get(key)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    artifact = joblib.load(path)
    _cache[key] = (mtime, artifact)
    return artifact


def load_demand_model(organization_id: str) -> dict | None:
    return _load(organization_id, "demand_model.joblib")


def load_churn_model(organization_id: str) -> dict | None:
    return _load(organization_id, "future_repeat_model.joblib")


def load_segment_model(organization_id: str) -> dict | None:
    return _load(organization_id, "segment_model.joblib")


def load_return_risk_model(organization_id: str) -> dict | None:
    return _load(organization_id, "return_risk_model.joblib")


def predict_daily_rates(
    organization_id: str, sales: pd.DataFrame,
) -> dict[tuple[str, str], float]:
    """Predict tomorrow's expected daily units for every (branch, sku) pair.

    `sales` must carry the org's full canonical sales history (branch_id,
    sku, sold_at, quantity, unit_price, discount_amount, line_total) — not
    just a recent window, since demand_features() needs each branch/sku
    pair's own history to build lag/rolling features. Pairs with fewer than
    28 days of history are silently absent from the result (dropped by
    demand_features' own dropna), never given a guessed rate.

    Returns an empty dict if there's no trained model for this organization.
    """
    artifact = load_demand_model(organization_id)
    if artifact is None or sales.empty:
        return {}
    features = demand_features(sales)
    if features.empty:
        return {}
    latest = features.sort_values("date").groupby(["branch_id", "sku"], as_index=False).last()
    predictions = artifact["pipeline"].predict(latest[artifact["features"]])
    return {
        (row.branch_id, row.sku): max(0.0, float(rate))
        for row, rate in zip(latest.itertuples(), predictions)
    }


def predict_churn_proba(organization_id: str, sales: pd.DataFrame) -> dict[str, float]:
    """Probability each real customer WILL return within the trained horizon
    (so churn risk = 1 - this). Empty dict when no model or no real customers."""
    artifact = load_churn_model(organization_id)
    if artifact is None or sales.empty:
        return {}
    horizon = artifact.get("horizon_days", 90)
    snapshot = churn_snapshots(sales, horizon_days=horizon, history_days=180)
    if snapshot.empty:
        return {}
    latest = snapshot.sort_values("cutoff").groupby("customer", as_index=False).last()
    probability = artifact["pipeline"].predict_proba(latest[artifact["features"]])[:, 1]
    return {row.customer: float(p) for row, p in zip(latest.itertuples(), probability)}


def predict_segments(organization_id: str, sales: pd.DataFrame) -> dict | None:
    """Live K-Means tier per customer plus the cluster profile. None when no
    trained segment model exists for this organization yet."""
    artifact = load_segment_model(organization_id)
    if artifact is None or sales.empty:
        return None
    rfm = customer_rfm(sales)
    if rfm.empty:
        return None
    X = artifact["scaler"].transform(rfm[artifact["features"]])
    labels = artifact["model"].predict(X)
    rfm["tier"] = [artifact["tier_map"].get(c, "Unclassified") for c in labels]
    return {
        "customer_tier": dict(zip(rfm.customer_pseudo_id, rfm.tier)),
        "k": artifact["k"],
    }


def predict_return_risk(organization_id: str, sales: pd.DataFrame) -> dict[tuple[str, str], float]:
    """Mean predicted return probability per (branch, sku), from the most
    recent sold lines. Empty dict when no model is trained for this org."""
    artifact = load_return_risk_model(organization_id)
    if artifact is None or sales.empty:
        return {}
    data = return_features(sales)
    if data.empty:
        return {}
    recent = data.sort_values("sold_at").groupby(["branch_id", "sku"]).tail(20)
    probability = artifact["pipeline"].predict_proba(recent[artifact["features"]])[:, 1]
    recent = recent.assign(_p=probability)
    grouped = recent.groupby(["branch_id", "sku"])._p.mean()
    return {(branch, sku): float(p) for (branch, sku), p in grouped.items()}
