"""Seven-day LightGBM ablation: baseline history versus historical price/activity features.

All transaction-derived covariates are calculated from records dated strictly
before each forecast origin. No future price, promotion, inventory or outcome
fields are used. Raw business files remain outside this repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

HORIZON = 7
ORIGINS = pd.date_range("2025-01-01", "2025-09-01", freq="MS")
LAGS = [1, 7, 14, 28, 56]
WINDOWS = [7, 14, 28, 56]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def features_at(arr: dict, idx: int, date: pd.Timestamp, shop: str, category: str,
                include_transaction_features: bool = False) -> dict:
    """Create a point-in-time feature snapshot using only array positions < idx."""
    y = arr["y"][:idx]
    if len(y) < 56:
        raise ValueError("At least 56 historical days are required")
    features = {f"lag_{lag}": float(y[-lag]) for lag in LAGS}
    for window in WINDOWS:
        recent = y[-window:]
        features[f"mean_{window}"] = float(recent.mean())
        features[f"std_{window}"] = float(recent.std())
        features[f"sum_{window}"] = float(recent.sum())
        features[f"zero_{window}"] = float((recent == 0).mean())

    positive = y[y > 0]
    positive_idx = np.flatnonzero(y > 0)
    features["days_since_sale"] = float(len(y) - 1 - positive_idx[-1]) if len(positive) else float(len(y))
    features["adi"] = float(len(y) / len(positive)) if len(positive) else float(len(y) + 1)
    features["positive_mean"] = float(positive.mean()) if len(positive) else 0.0
    features["positive_cv2"] = float((positive.std() / positive.mean()) ** 2) if len(positive) and positive.mean() else 0.0

    features.update(
        shop_id=str(shop),
        category=str(category),
        dow=date.dayofweek,
        day=date.day,
        month=date.month,
        week=int(date.isocalendar().week),
        dow_sin=np.sin(2 * np.pi * date.dayofweek / 7),
        dow_cos=np.cos(2 * np.pi * date.dayofweek / 7),
        month_sin=np.sin(2 * np.pi * (date.month - 1) / 12),
        month_cos=np.cos(2 * np.pi * (date.month - 1) / 12),
    )

    if include_transaction_features:
        price = arr["price"][:idx]
        discount_rate = arr["discount_rate"][:idx]
        gross = arr["gross"][:idx]
        discount = arr["discount"][:idx]
        orders = arr["orders"][:idx]
        customer_days = arr["customer_days"][:idx]

        valid_price = price[np.isfinite(price) & (price > 0)]
        last_price = float(valid_price[-1]) if len(valid_price) else np.nan
        features["last_observed_unit_price"] = last_price

        for window in (7, 28, 56):
            p = price[-window:]
            p = p[np.isfinite(p) & (p > 0)]
            features[f"mean_unit_price_{window}"] = float(p.mean()) if len(p) else np.nan
            features[f"price_cv_{window}"] = float(p.std() / p.mean()) if len(p) and p.mean() > 0 else np.nan
            features[f"price_observations_{window}"] = int(len(p))
            features[f"orders_{window}"] = float(orders[-window:].sum())
            features[f"customer_days_{window}"] = float(customer_days[-window:].sum())
            features[f"revenue_{window}"] = float(gross[-window:].sum())
            features[f"discount_value_{window}"] = float(discount[-window:].sum())
            gross_sum = float(gross[-window:].sum())
            features[f"discount_rate_{window}"] = float(discount[-window:].sum() / gross_sum) if gross_sum > 0 else 0.0
            order_sum = float(orders[-window:].sum())
            features[f"units_per_order_{window}"] = float(y[-window:].sum() / order_sum) if order_sum > 0 else 0.0

        price_28 = price[-28:]
        price_28 = price_28[np.isfinite(price_28) & (price_28 > 0)]
        features["last_price_change_vs_28d_mean"] = (
            float(last_price / price_28.mean() - 1)
            if len(price_28) and np.isfinite(last_price) and price_28.mean() > 0 else np.nan
        )
        valid_price_idx = np.flatnonzero(np.isfinite(price) & (price > 0))
        features["days_since_price_observation"] = (
            float(idx - 1 - valid_price_idx[-1]) if len(valid_price_idx) else float(idx)
        )
    return features


def load_series(data_dir: Path):
    panel = pd.read_csv(data_dir / "rq1_daily_shop_category.csv", parse_dates=["date"])
    lines = pd.read_csv(data_dir / "sales_lines.csv", dtype={"order_id": "string", "shop_id": "string", "sku_id": "string"})
    orders = pd.read_csv(
        data_dir / "sales_orders.csv",
        usecols=["order_id", "shop_id", "customer_id", "order_datetime"],
        dtype={"order_id": "string", "shop_id": "string", "customer_id": "string"},
        parse_dates=["order_datetime"],
    )
    products = pd.read_csv(data_dir / "products.csv", dtype={"sku_id": "string"})

    joined = lines.merge(
        orders, on="order_id", how="left", validate="many_to_one",
        suffixes=("_line", "_order"), indicator=True,
    )
    if (joined["_merge"] != "both").any():
        raise ValueError("Sales lines contain unmatched order references")
    if (joined["shop_id_line"] != joined["shop_id_order"]).any():
        raise ValueError("Sales-line shop IDs do not match their parent orders")
    joined["shop_id"] = joined["shop_id_line"]
    joined["date"] = joined["order_datetime"].dt.normalize()
    joined = joined.merge(products[["sku_id", "category"]], on="sku_id", how="left", validate="many_to_one")
    if joined["category"].isna().any():
        raise ValueError("Sales lines contain SKU IDs absent from the product master")

    joined["gross_line_bdt"] = joined["quantity"] * joined["unit_price_bdt"]
    joined["discount_line_bdt"] = joined["line_discount_bdt"].fillna(0)
    exog = joined.groupby(["shop_id", "category", "date"], as_index=False).agg(
        gross_bdt=("gross_line_bdt", "sum"),
        discount_bdt=("discount_line_bdt", "sum"),
        orders=("order_id", "nunique"),
        customer_days=("customer_id", "nunique"),
        units=("quantity", "sum"),
    )
    exog["avg_unit_price"] = exog["gross_bdt"] / exog["units"].replace(0, np.nan)
    exog["discount_rate"] = exog["discount_bdt"] / exog["gross_bdt"].replace(0, np.nan)

    panel["date"] = panel["date"].dt.normalize()
    panel_exog = panel.merge(exog, on=["shop_id", "category", "date"], how="left", validate="one_to_one")
    for column in ["gross_bdt", "discount_bdt", "orders", "customer_days", "units"]:
        panel_exog[column] = panel_exog[column].fillna(0)
    if not np.array_equal(panel_exog["units"].to_numpy(), panel_exog["units_sold_observed"].to_numpy()):
        raise ValueError("Transaction-derived shop-category quantities do not reproduce the daily panel")

    series = {}
    for (shop, category), group in panel_exog.sort_values(["shop_id", "category", "date"]).groupby(
        ["shop_id", "category"], sort=True
    ):
        group = group.sort_values("date")
        series[(str(shop), str(category))] = {
            "y": group["units_sold_observed"].to_numpy(dtype=float),
            "price": group["avg_unit_price"].to_numpy(dtype=float),
            "discount_rate": group["discount_rate"].to_numpy(dtype=float),
            "gross": group["gross_bdt"].to_numpy(dtype=float),
            "discount": group["discount_bdt"].to_numpy(dtype=float),
            "orders": group["orders"].to_numpy(dtype=float),
            "customer_days": group["customer_days"].to_numpy(dtype=float),
            "dates": pd.DatetimeIndex(group["date"]),
        }
    return panel, series, {
        "rq1_daily_shop_category.csv": sha256(data_dir / "rq1_daily_shop_category.csv"),
        "sales_lines.csv": sha256(data_dir / "sales_lines.csv"),
        "sales_orders.csv": sha256(data_dir / "sales_orders.csv"),
        "products.csv": sha256(data_dir / "products.csv"),
    }


def fit_lightgbm(train_rows, test_rows, target):
    x_train = pd.DataFrame(train_rows)
    x_test = pd.DataFrame(test_rows)
    for column in ["shop_id", "category"]:
        x_train[column] = x_train[column].astype("category")
        x_test[column] = pd.Categorical(x_test[column], categories=x_train[column].cat.categories)
    model = lgb.LGBMRegressor(
        objective="tweedie", tweedie_variance_power=1.3,
        n_estimators=100, learning_rate=0.035, num_leaves=31,
        min_child_samples=80, subsample=0.85, subsample_freq=1,
        colsample_bytree=0.85, reg_lambda=2.0, random_state=42,
        n_jobs=4, verbosity=-1,
    )
    model.fit(x_train, target, categorical_feature=["shop_id", "category"])
    return np.maximum(0, model.predict(x_test))


def run(data_dir: Path, output_dir: Path):
    started = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    panel, series, checksums = load_series(data_dir)
    start_date = panel["date"].min()
    max_origin = ORIGINS.max()
    max_idx = int((max_origin - start_date).days)
    rows_by_series = {}

    # Precompute historical snapshots once; each origin selects only labels ending before it.
    for (shop, category), arr in series.items():
        cached = []
        y = arr["y"]
        for idx in range(56, max_idx - HORIZON + 1, 28):
            cached.append((
                idx,
                float(y[idx:idx + HORIZON].sum()),
                features_at(arr, idx, arr["dates"][idx], shop, category, False),
                features_at(arr, idx, arr["dates"][idx], shop, category, True),
            ))
        rows_by_series[(shop, category)] = cached

    results = []
    for origin in ORIGINS:
        origin_idx = int((origin - start_date).days)
        train_base, train_extended, target = [], [], []
        test_base, test_extended, actual = [], [], []
        for (shop, category), arr in series.items():
            for idx, label, base_features, extended_features in rows_by_series[(shop, category)]:
                if idx + HORIZON <= origin_idx:
                    train_base.append(base_features)
                    train_extended.append(extended_features)
                    target.append(label)
            test_base.append(features_at(arr, origin_idx, origin, shop, category, False))
            test_extended.append(features_at(arr, origin_idx, origin, shop, category, True))
            actual.append(float(arr["y"][origin_idx:origin_idx + HORIZON].sum()))

        y_train = np.asarray(target, dtype=float)
        y_actual = np.asarray(actual, dtype=float)
        if len(y_actual) != 512:
            raise ValueError(f"Expected 512 series at {origin.date()}, found {len(y_actual)}")

        for model_name, train_rows, test_rows in [
            ("LightGBM_base", train_base, test_base),
            ("LightGBM_price_activity", train_extended, test_extended),
        ]:
            forecast = fit_lightgbm(train_rows, test_rows, y_train)
            absolute_error = np.abs(y_actual - forecast)
            actual_total = float(y_actual.sum())
            forecast_total = float(forecast.sum())
            results.append({
                "origin": str(origin.date()), "model": model_name, "n": int(len(y_actual)),
                "train_rows": int(len(y_train)), "actual_total": actual_total,
                "forecast_total": forecast_total, "absolute_error_total": float(absolute_error.sum()),
                "WAPE": float(absolute_error.sum() / actual_total) if actual_total else np.nan,
                "Bias": float((forecast_total - actual_total) / actual_total) if actual_total else np.nan,
                "MAE": float(absolute_error.mean()),
                "RMSE": float(np.sqrt(np.mean((y_actual - forecast) ** 2))),
            })

    result = pd.DataFrame(results)
    aggregate = []
    for model_name, group in result.groupby("model"):
        actual_total = float(group["actual_total"].sum())
        aggregate.append({
            "model": model_name,
            "origins": int(group["origin"].nunique()),
            "series_origin_forecasts": int(group["n"].sum()),
            "actual_total": actual_total,
            "forecast_total": float(group["forecast_total"].sum()),
            "pooled_WAPE": float(group["absolute_error_total"].sum() / actual_total),
            "mean_origin_WAPE": float(group["WAPE"].mean()),
            "aggregate_Bias": float((group["forecast_total"].sum() - actual_total) / actual_total),
            "mean_origin_MAE": float(group["MAE"].mean()),
            "mean_origin_RMSE": float(group["RMSE"].mean()),
        })
    aggregate = pd.DataFrame(aggregate)
    result.to_csv(output_dir / "origin_metrics.csv", index=False)
    aggregate.to_csv(output_dir / "aggregate_metrics.csv", index=False)

    manifest = {
        "experiment": "seven_day_historical_price_activity_ablation_v1",
        "horizon_days": HORIZON,
        "origins": [str(x.date()) for x in ORIGINS],
        "series_per_origin": 512,
        "series_origin_forecasts_per_model": int(result["n"].sum() // result["model"].nunique()),
        "training_stride_days": 28,
        "minimum_history_days": 56,
        "models": ["LightGBM Tweedie baseline", "LightGBM Tweedie + historical price/activity"],
        "feature_policy": "All transaction covariates use records strictly before the forecast origin; no future price, promotion, inventory, or customer outcomes.",
        "transaction_features": [
            "last observed unit price", "7/28/56-day mean unit price and price CV",
            "7/28/56-day orders and customer-days", "7/28/56-day revenue and discount",
            "7/28/56-day discount rate and units per order", "price change versus 28-day mean",
            "days since price observation"
        ],
        "input_sha256": checksums,
        "provenance_status": "provenance_conflict",
        "final_holdout_evaluated": False,
        "python": sys.version,
        "platform": platform.platform(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "lightgbm": lgb.__version__,
        "elapsed_seconds": round(time.time() - started, 2),
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(aggregate.to_string(index=False))
    return result, aggregate, manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.data_dir, args.output_dir)
