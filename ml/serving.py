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

from .real_pipeline import demand_features

ARTIFACTS_ROOT = Path("artifacts/real")

_cache: dict[str, tuple[float, dict]] = {}


def _artifact_path(organization_id: str) -> Path:
    return ARTIFACTS_ROOT / organization_id / "demand_model.joblib"


def load_demand_model(organization_id: str) -> dict | None:
    path = _artifact_path(organization_id)
    if not path.is_file():
        return None
    mtime = path.stat().st_mtime
    cached = _cache.get(organization_id)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    artifact = joblib.load(path)
    _cache[organization_id] = (mtime, artifact)
    return artifact


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
