"""SKU-level RQ1 evaluation using reconstructed inventory exposure.

The inventory ledger is used to decide whether a zero can be observed: a
shop-SKU-day is eligible only when reconstructed intraday stock remains
positive. Entire shop-SKU histories with any negative balance are quarantined.
Outputs contain aggregate results only; source data stay outside Git.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import HistGradientBoostingRegressor

SEED = 20261109
START = pd.Timestamp("2023-01-01")
END = pd.Timestamp("2025-12-31")
TRAIN_CUTOFF = pd.Timestamp("2025-09-30")
TEST_START = pd.Timestamp("2025-10-01")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def load_exposure(data_dir: Path):
    movement_path = data_dir / "inventory_movements.csv"
    sale_path = data_dir / "rq1_daily_sku_sales_observed.csv"
    product_path = data_dir / "products.csv"
    movements = pd.read_csv(
        movement_path,
        usecols=["movement_id", "shop_id", "sku_id", "movement_datetime", "movement_type", "quantity_delta"],
        dtype={"movement_id": "string", "shop_id": "string", "sku_id": "string", "movement_type": "string", "quantity_delta": "int32"},
        parse_dates=["movement_datetime"],
    )
    movements["day"] = movements["movement_datetime"].dt.normalize()
    keys = movements[["shop_id", "sku_id"]].drop_duplicates().reset_index(drop=True)
    key_index = pd.MultiIndex.from_frame(keys)
    move_index = key_index.get_indexer(pd.MultiIndex.from_frame(movements[["shop_id", "sku_id"]]))
    if (move_index < 0).any():
        raise AssertionError("Failed to map an inventory movement to its shop-SKU key.")
    movements["sid"] = move_index.astype(np.int32)
    dates = pd.date_range(START, END, freq="D")
    n_series, n_days = len(keys), len(dates)
    movements["day_idx"] = (movements["day"] - START).dt.days.astype(np.int32)

    # Quarantine any series with a negative running inventory balance.
    ordered_all = movements.sort_values(
        ["sid", "movement_datetime", "movement_id"], kind="mergesort"
    )
    running = ordered_all.groupby("sid", sort=False)["quantity_delta"].cumsum()
    bad_sid = np.zeros(n_series, dtype=bool)
    bad_sid[np.unique(ordered_all.loc[running < 0, "sid"].to_numpy(dtype=np.int32))] = True

    before = movements.loc[movements["day_idx"] < 0].groupby("sid", sort=False)["quantity_delta"].sum()
    opening = np.zeros(n_series, dtype=np.float32)
    opening[before.index.to_numpy(dtype=np.int32)] = before.to_numpy(dtype=np.float32)
    during = movements.loc[movements["day_idx"].between(0, n_days - 1)].copy()
    during = during.sort_values(
        ["sid", "day_idx", "movement_datetime", "movement_id"], kind="mergesort"
    )
    during["intra_cum"] = during.groupby(["sid", "day_idx"], sort=False)["quantity_delta"].cumsum()
    daily = during.groupby(["sid", "day_idx"], sort=False).agg(
        delta=("quantity_delta", "sum"),
        min_prefix=("intra_cum", "min"),
    ).reset_index()
    delta_matrix = np.zeros((n_series, n_days), dtype=np.float32)
    min_prefix_matrix = np.zeros((n_series, n_days), dtype=np.float32)
    si = daily["sid"].to_numpy(dtype=np.int32)
    di = daily["day_idx"].to_numpy(dtype=np.int32)
    delta_matrix[si, di] = daily["delta"].to_numpy(dtype=np.float32)
    min_prefix_matrix[si, di] = daily["min_prefix"].to_numpy(dtype=np.float32)
    opening_stock = opening[:, None] + np.cumsum(delta_matrix, axis=1, dtype=np.float32) - delta_matrix
    minimum_intraday_stock = opening_stock + min_prefix_matrix
    exposed = (minimum_intraday_stock > 0) & (~bad_sid[:, None])

    sales = np.zeros((n_series, n_days), dtype=np.float32)
    sku_sales = pd.read_csv(
        sale_path,
        usecols=["shop_id", "sku_id", "date", "units_sold_observed"],
        dtype={"shop_id": "string", "sku_id": "string", "units_sold_observed": "float32"},
        parse_dates=["date"],
    )
    sku_sales["sid"] = key_index.get_indexer(
        pd.MultiIndex.from_frame(sku_sales[["shop_id", "sku_id"]])
    )
    sku_sales["day_idx"] = (sku_sales["date"] - START).dt.days.astype(np.int32)
    if sku_sales["sid"].lt(0).any():
        raise ValueError("A positive-sale SKU key has no inventory-movement history.")
    if sku_sales["day_idx"].lt(0).any() or sku_sales["day_idx"].ge(n_days).any():
        raise ValueError("SKU sales contain a date outside the declared panel.")
    sales[
        sku_sales["sid"].to_numpy(dtype=np.int32),
        sku_sales["day_idx"].to_numpy(dtype=np.int32),
    ] = sku_sales["units_sold_observed"].to_numpy(dtype=np.float32)

    positive = sales > 0
    clean_exposed_positive = int((positive & exposed).sum())
    excluded_positive = int((positive & ~exposed).sum())
    exposure_summary = {
        "inventory_movement_rows": int(len(movements)),
        "shop_sku_series_with_movement_history": int(n_series),
        "series_with_any_negative_running_balance_quarantined": int(bad_sid.sum()),
        "reconstructed_in_stock_days_before_quarantine": int((minimum_intraday_stock > 0).sum()),
        "eligible_shop_sku_days_after_quarantine": int(exposed.sum()),
        "positive_sale_days_in_eligible_exposure": clean_exposed_positive,
        "positive_sale_days_excluded_as_nonpositive_stock_or_quarantined": excluded_positive,
        "zero_targets_created_only_for_eligible_exposed_days": int((exposed & ~positive).sum()),
        "sku_positive_sale_rows": int(len(sku_sales)),
        "sku_positive_sale_units": int(sku_sales["units_sold_observed"].sum()),
    }
    products = pd.read_csv(data_dir / "products.csv", usecols=["sku_id", "category"])
    category_by_sku = products.set_index("sku_id")["category"].to_dict()
    keys["category"] = keys["sku_id"].map(category_by_sku)
    if keys["category"].isna().any():
        raise ValueError("Some inventory-tracked SKU keys have no product category.")
    return keys, dates, sales, exposed, opening_stock, exposure_summary


def historical_priors(keys: pd.DataFrame, sales: np.ndarray, exposed: np.ndarray, dates: pd.DatetimeIndex):
    early = dates < pd.Timestamp("2024-01-01")
    early_exposure = exposed[:, early]
    early_sales = sales[:, early]
    count = early_exposure.sum(axis=1)
    total = (early_sales * early_exposure).sum(axis=1)
    series_mean = np.divide(total, count, out=np.full(len(count), np.nan), where=count > 0)
    base = keys[["shop_id", "sku_id", "category"]].copy()
    base["early_mean"] = series_mean
    sku_mean = base.groupby("sku_id", observed=True)["early_mean"].mean()
    shop_mean = base.groupby("shop_id", observed=True)["early_mean"].mean()
    category_mean = base.groupby("category", observed=True)["early_mean"].mean()
    priors = np.column_stack([
        keys["sku_id"].map(sku_mean).to_numpy(dtype=np.float32),
        keys["shop_id"].map(shop_mean).to_numpy(dtype=np.float32),
        keys["category"].map(category_mean).to_numpy(dtype=np.float32),
    ])
    priors = np.nan_to_num(priors, nan=0.0)
    return priors


def days_since_sale(sales: np.ndarray, exposed: np.ndarray) -> np.ndarray:
    n_series, n_days = sales.shape
    result = np.empty((n_series, n_days), dtype=np.uint16)
    last = np.full(n_series, -1000, dtype=np.int32)
    for day in range(n_days):
        result[:, day] = np.minimum(day - last, 999).astype(np.uint16)
        sold = exposed[:, day] & (sales[:, day] > 0)
        last[sold] = day
    return result


def make_features(
    series_idx: np.ndarray,
    day_idx: np.ndarray,
    sales: np.ndarray,
    exposed: np.ndarray,
    opening_stock: np.ndarray,
    since_sale: np.ndarray,
    priors: np.ndarray,
    dates: pd.DatetimeIndex,
) -> np.ndarray:
    n = len(series_idx)
    columns: list[np.ndarray] = []
    for lag in (1, 7, 14, 28):
        prev = day_idx - lag
        ok = exposed[series_idx, prev]
        value = sales[series_idx, prev].astype(np.float32)
        columns.append(np.where(ok, value, np.nan).astype(np.float32))
    means = {}
    availability = {}
    for window in (7, 28):
        total = np.zeros(n, dtype=np.float32)
        count = np.zeros(n, dtype=np.float32)
        for lag in range(1, window + 1):
            prev = day_idx - lag
            ok = exposed[series_idx, prev]
            total += np.where(ok, sales[series_idx, prev], 0.0).astype(np.float32)
            count += ok.astype(np.float32)
        means[window] = np.divide(
            total, count, out=np.full(n, np.nan, dtype=np.float32), where=count > 0
        )
        availability[window] = count / float(window)
    columns.extend([
        means[7],
        means[28],
        availability[28],
        np.log1p(np.maximum(0, opening_stock[series_idx, day_idx])).astype(np.float32),
        np.minimum(since_sale[series_idx, day_idx], 999).astype(np.float32),
    ])
    day_dates = dates.take(day_idx)
    dow = day_dates.dayofweek.to_numpy()
    month = day_dates.month.to_numpy()
    columns.extend([
        np.sin(2 * np.pi * dow / 7).astype(np.float32),
        np.cos(2 * np.pi * dow / 7).astype(np.float32),
        np.sin(2 * np.pi * (month - 1) / 12).astype(np.float32),
        np.cos(2 * np.pi * (month - 1) / 12).astype(np.float32),
        priors[series_idx, 0],
        priors[series_idx, 1],
        priors[series_idx, 2],
    ])
    return np.column_stack(columns).astype(np.float32, copy=False)


def metric(y: np.ndarray, pred: np.ndarray) -> dict:
    pred = np.maximum(np.asarray(pred, dtype=np.float64), 0.0)
    y = np.asarray(y, dtype=np.float64)
    denom = float(np.abs(y).sum())
    return {
        "n_exposed_shop_sku_days": int(len(y)),
        "actual_units": float(y.sum()),
        "forecast_units": float(pred.sum()),
        "WAPE": float(np.abs(y - pred).sum() / denom) if denom else None,
        "MAE_units_per_exposed_day": float(np.abs(y - pred).mean()),
        "RMSE_units_per_exposed_day": float(np.sqrt(np.square(y - pred).mean())),
        "Bias_pct": float((pred.sum() - y.sum()) / denom) if denom else None,
    }


def shop_cluster_ci(
    y: np.ndarray, predictions: dict[str, np.ndarray], shop_code: np.ndarray, shop_names: list[str]
) -> dict:
    rng = np.random.default_rng(SEED)
    n_shops = len(shop_names)
    actual_total = np.bincount(shop_code, weights=np.abs(y), minlength=n_shops)
    result = {}
    for name, pred in predictions.items():
        err_total = np.bincount(shop_code, weights=np.abs(y - pred), minlength=n_shops)
        wape = err_total.sum() / actual_total.sum()
        result[name] = {"WAPE": float(wape)}
    if "hist_gradient_boosting" in predictions:
        err_by_model = {
            name: np.bincount(
                shop_code, weights=np.abs(y - pred), minlength=n_shops
            )
            for name, pred in predictions.items()
        }
        draws = rng.integers(0, n_shops, size=(2000, n_shops))
        for comparator in ("weekly_naive", "moving_mean_28_exposed_days"):
            if comparator not in err_by_model:
                continue
            hgb_wape = err_by_model["hist_gradient_boosting"][draws].sum(axis=1) / actual_total[draws].sum(axis=1)
            comparator_wape = err_by_model[comparator][draws].sum(axis=1) / actual_total[draws].sum(axis=1)
            delta = hgb_wape - comparator_wape
            result[f"paired_hgb_minus_{comparator}_shop_bootstrap"] = {
                "unit": "shop cluster",
                "shops": n_shops,
                "replicates": 2000,
                "WAPE_difference": float(result["hist_gradient_boosting"]["WAPE"] - result[comparator]["WAPE"]),
                "percentile_95pct_ci": [
                    float(np.quantile(delta, 0.025)), float(np.quantile(delta, 0.975))
                ],
                "interpretation": "Descriptive cluster bootstrap; small number of shops limits precision.",
            }
    return result


def run(data_dir: Path, out: Path) -> None:
    started = time.time()
    out.mkdir(parents=True, exist_ok=True)
    keys, dates, sales, exposed, opening_stock, exposure_summary = load_exposure(data_dir)
    priors = historical_priors(keys, sales, exposed, dates)
    since = days_since_sale(sales, exposed)
    train_days = np.flatnonzero(
        (dates >= pd.Timestamp("2024-01-01")) & (dates <= TRAIN_CUTOFF)
    )
    test_days = np.flatnonzero((dates >= TEST_START) & (dates <= END))
    train_mask = exposed[:, train_days]
    train_target = sales[:, train_days]
    positive_flat = np.flatnonzero(train_mask & (train_target > 0))
    zero_flat = np.flatnonzero(train_mask & (train_target == 0))
    if not len(positive_flat) or not len(zero_flat):
        raise ValueError("Training sample must include both positive and exposed-zero outcomes.")

    # Keep every positive day and sample exposed zero days to control runtime.
    rng = np.random.default_rng(SEED)
    max_zero_sample = 500_000
    zero_count = min(max_zero_sample, len(zero_flat))
    sampled_zero = rng.choice(zero_flat, size=zero_count, replace=False)
    n_train_days = len(train_days)
    pos_series = positive_flat // n_train_days
    pos_day = train_days[positive_flat % n_train_days]
    zero_series = sampled_zero // n_train_days
    zero_day = train_days[sampled_zero % n_train_days]
    train_series = np.concatenate([pos_series, zero_series]).astype(np.int32)
    train_day = np.concatenate([pos_day, zero_day]).astype(np.int32)
    train_y = sales[train_series, train_day].astype(np.float32)
    train_weights = np.concatenate([
        np.ones(len(pos_series), dtype=np.float32),
        np.full(len(zero_series), len(zero_flat) / len(zero_series), dtype=np.float32),
    ])
    X_train = make_features(
        train_series, train_day, sales, exposed, opening_stock, since, priors, dates
    )

    test_mask = exposed[:, test_days]
    test_flat = np.flatnonzero(test_mask)
    n_test_days = len(test_days)
    test_series = (test_flat // n_test_days).astype(np.int32)
    test_day = test_days[test_flat % n_test_days].astype(np.int32)
    y_test = sales[test_series, test_day].astype(np.float32)
    X_test = make_features(
        test_series, test_day, sales, exposed, opening_stock, since, priors, dates
    )
    feature_names = [
        "lag_1", "lag_7", "lag_14", "lag_28", "mean_exposed_7d",
        "mean_exposed_28d", "exposure_ratio_28d", "log_opening_stock",
        "days_since_last_exposed_sale", "dow_sin", "dow_cos", "month_sin",
        "month_cos", "sku_2023_mean", "shop_2023_mean", "category_2023_mean",
    ]
    model = HistGradientBoostingRegressor(
        loss="poisson",
        learning_rate=0.06,
        max_iter=80,
        max_leaf_nodes=15,
        min_samples_leaf=80,
        l2_regularization=5.0,
        early_stopping=False,
        random_state=SEED,
    )
    model.fit(X_train, train_y, sample_weight=train_weights)
    hgb_pred = np.maximum(model.predict(X_test), 0.0).astype(np.float32)

    lag7 = X_test[:, feature_names.index("lag_7")]
    mean28 = X_test[:, feature_names.index("mean_exposed_28d")]
    sku_prior = priors[test_series, 0]
    shop_prior = priors[test_series, 1]
    category_prior = priors[test_series, 2]
    fallback = np.where(np.isfinite(mean28), mean28, sku_prior)
    fallback = np.where(np.isfinite(fallback), fallback, shop_prior)
    fallback = np.where(np.isfinite(fallback), fallback, category_prior)
    fallback = np.nan_to_num(fallback, nan=0.0)
    weekly_pred = np.where(np.isfinite(lag7), lag7, fallback).astype(np.float32)
    mean_pred = np.where(np.isfinite(mean28), mean28, fallback).astype(np.float32)
    predictions = {
        "weekly_naive": weekly_pred,
        "moving_mean_28_exposed_days": mean_pred,
        "hist_gradient_boosting": hgb_pred,
    }
    metrics_rows = [
        {"model": name, **metric(y_test, pred)}
        for name, pred in predictions.items()
    ]
    metric_frame = pd.DataFrame(metrics_rows)
    metric_frame.to_csv(out / "q4_exposure_metrics.csv", index=False)

    test_shops = keys.iloc[test_series]["shop_id"].to_numpy()
    shop_codes, shop_names = pd.factorize(test_shops, sort=True)
    bootstrap = shop_cluster_ci(y_test, predictions, shop_codes, list(shop_names))
    (out / "shop_cluster_bootstrap.json").write_text(
        json.dumps(bootstrap, indent=2), encoding="utf-8"
    )
    exposure_summary.update({
        "development_training_cutoff": str(TRAIN_CUTOFF.date()),
        "evaluation_start": str(TEST_START.date()),
        "evaluation_end": str(END.date()),
        "development_positive_days_used": int(len(pos_series)),
        "development_exposed_zero_days_total": int(len(zero_flat)),
        "development_exposed_zero_days_sampled": int(len(zero_series)),
        "test_exposed_days": int(len(test_flat)),
        "test_positive_days": int((y_test > 0).sum()),
        "test_actual_units": float(y_test.sum()),
        "test_unique_shop_sku_series": int(len(np.unique(test_series))),
        "test_zero_target_fraction": float((y_test == 0).mean()),
        "evaluation_status": "later-period exposure-conditioned diagnostic; Q4 2025 was previously inspected in project work and is not an untouched final holdout",
        "stock_exposure_source": "reconstructed inventory movements; not an independent physical stock audit",
    })
    (out / "exposure_audit_summary.json").write_text(
        json.dumps(exposure_summary, indent=2), encoding="utf-8"
    )
    movement_path = data_dir / "inventory_movements.csv"
    sales_path = data_dir / "rq1_daily_sku_sales_observed.csv"
    manifest = {
        "experiment": "RQ1 exposure-conditioned daily SKU observed-sales evaluation",
        "target": "daily observed units on shop-SKU-days whose reconstructed intraday inventory stayed positive",
        "zero_policy": "set zero only on eligible exposed days; censor nonpositive or quarantined days",
        "temporal_protocol": "train through 2025-09-30; sequential one-day predictions from 2025-10-01 through 2025-12-31; past test outcomes become available to later daily forecasts",
        "preexisting_data_exposure": "Q4 2025 was previously inspected in project work; this is not an untouched final holdout",
        "features": feature_names,
        "model": {
            "class": "sklearn.ensemble.HistGradientBoostingRegressor",
            "loss": "poisson",
            "learning_rate": 0.06,
            "max_iter": 80,
            "max_leaf_nodes": 15,
            "min_samples_leaf": 80,
            "l2_regularization": 5.0,
            "random_state": SEED,
            "zero_sampling": "all positive training days plus up to 500,000 exposed zero days, weighted to represent the full exposed-zero set",
        },
        "input_hashes": {
            movement_path.name: sha256(movement_path),
            sales_path.name: sha256(sales_path),
            "products.csv": sha256(data_dir / "products.csv"),
        },
        "output_files": [
            "exposure_audit_summary.json", "q4_exposure_metrics.csv",
            "shop_cluster_bootstrap.json",
        ],
        "seed": SEED,
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "scikit_learn": sklearn.__version__,
        "elapsed_seconds": round(time.time() - started, 1),
        "raw_data_copied_to_repository": False,
        "provenance_limit": "Drive manifest declares real-world origin but source lineage was not independently verified in this run.",
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({
        "exposure_audit": exposure_summary,
        "metrics": metrics_rows,
        "shop_cluster_bootstrap": bootstrap,
        "elapsed_seconds": manifest["elapsed_seconds"],
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("research/experiments/results/rq1_exposure_aware_20261109"))
    args = parser.parse_args()
    run(args.data_dir, args.output_dir)


if __name__ == "__main__":
    main()
