"""Leakage-safe context-aware multi-horizon shop-category forecasting experiment.

This experiment uses only the supplied complete shop-category observed-sales panel.
It does not treat missing SKU dates as zero and does not use simulated unmet demand.
Raw business files remain in controlled storage; only aggregate evidence is committed.
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
from sklearn.metrics import mean_absolute_error, mean_squared_error

KEYS = ["shop_id", "category"]
HORIZON_ORIGINS = {
    1: pd.date_range("2025-07-01", "2025-09-01", freq="MS"),
    7: pd.date_range("2025-01-01", "2025-09-01", freq="MS"),
    14: pd.date_range("2025-07-01", "2025-09-01", freq="MS"),
    28: pd.date_range("2025-07-01", "2025-09-01", freq="MS"),
}
MIN_HISTORY = 56
TRAIN_STRIDE = 14
MODEL_PARAMS = {
    "objective": "tweedie",
    "tweedie_variance_power": 1.3,
    "n_estimators": 100,
    "learning_rate": 0.035,
    "num_leaves": 31,
    "min_child_samples": 80,
    "subsample": 0.85,
    "subsample_freq": 1,
    "colsample_bytree": 0.85,
    "reg_lambda": 2.0,
    "random_state": 42,
    "n_jobs": 4,
    "verbosity": -1,
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_panel(path: Path):
    frame = pd.read_csv(path, parse_dates=["date"])
    required = set(KEYS + ["date", "units_sold_observed", "is_zero_observed_sales"])
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if frame[list(required)].isna().any().any():
        raise ValueError("Null values exist in required panel fields")
    if frame.duplicated(KEYS + ["date"]).any():
        raise ValueError("Duplicate shop-category-date keys")
    frame["units_sold_observed"] = pd.to_numeric(frame["units_sold_observed"], errors="raise")
    y = frame["units_sold_observed"].to_numpy(dtype=float)
    if not np.isfinite(y).all() or (y < 0).any():
        raise ValueError("Observed sales must be finite and non-negative")
    zero = frame["is_zero_observed_sales"].astype(int).to_numpy()
    if not np.array_equal(zero, (y == 0).astype(int)):
        raise ValueError("Zero-sales flag disagrees with observed quantity")

    dates = pd.date_range(frame.date.min(), frame.date.max(), freq="D")
    pivot = frame.pivot(index=KEYS, columns="date", values="units_sold_observed").reindex(columns=dates)
    if pivot.isna().any().any():
        raise ValueError("Incomplete daily shop-category panel; no missing dates are imputed")
    pivot = pivot.sort_index()
    shops = sorted(frame.shop_id.unique())
    categories = sorted(frame.category.unique())
    if (len(shops), len(categories), len(dates), len(pivot)) != (32, 16, 1096, 512):
        raise ValueError("Panel dimensions differ from the audited 32 x 16 x 1,096 design")
    return frame, pivot, dates, shops, categories


class FeatureStore:
    """Vectorised point-in-time features; every slice ends strictly before origin."""

    def __init__(self, pivot: pd.DataFrame, shops: list[str], categories: list[str]):
        self.keys = list(pivot.index)
        self.y = pivot.to_numpy(dtype=float)
        self.shop_values = np.asarray([key[0] for key in self.keys])
        self.category_values = np.asarray([key[1] for key in self.keys])
        self.shop_idx = np.asarray([shops.index(x) for x in self.shop_values])
        self.category_idx = np.asarray([categories.index(x) for x in self.category_values])
        self.shop_y = np.stack([self.y[self.shop_idx == i].sum(axis=0) for i in range(len(shops))])
        self.category_y = np.stack([self.y[self.category_idx == i].sum(axis=0) for i in range(len(categories))])
        self.network_y = self.y.sum(axis=0)
        self.cum = np.concatenate([np.zeros((len(self.y), 1)), np.cumsum(self.y, axis=1)], axis=1)
        self.cum2 = np.concatenate([np.zeros((len(self.y), 1)), np.cumsum(self.y ** 2, axis=1)], axis=1)
        self.cum_positive = np.concatenate([np.zeros((len(self.y), 1)), np.cumsum(self.y > 0, axis=1)], axis=1)
        self.cum_positive_sum = np.concatenate([np.zeros((len(self.y), 1)), np.cumsum(self.y * (self.y > 0), axis=1)], axis=1)
        self.cum_positive_sq = np.concatenate([np.zeros((len(self.y), 1)), np.cumsum(self.y ** 2 * (self.y > 0), axis=1)], axis=1)
        self.last_positive = np.maximum.accumulate(
            np.where(self.y > 0, np.arange(self.y.shape[1])[None, :], -1), axis=1
        )

    def snapshot(self, index: int, context: bool) -> pd.DataFrame:
        if index < MIN_HISTORY:
            raise ValueError(f"Feature origin {index} is earlier than {MIN_HISTORY}-day history")
        if index > self.y.shape[1] - 1:
            raise ValueError("Feature origin is outside the observed panel")
        features = {}
        for lag in (1, 7, 14, 28, 56):
            features[f"lag_{lag}"] = self.y[:, index - lag]

        for window in (7, 14, 28, 56):
            total = self.cum[:, index] - self.cum[:, index - window]
            square_total = self.cum2[:, index] - self.cum2[:, index - window]
            mean = total / window
            features[f"mean_{window}"] = mean
            features[f"std_{window}"] = np.sqrt(np.maximum(0.0, square_total / window - mean ** 2))
            features[f"sum_{window}"] = total
            features[f"zero_{window}"] = 1.0 - (
                self.cum_positive[:, index] - self.cum_positive[:, index - window]
            ) / window

        positive_count = self.cum_positive[:, index]
        positive_sum = self.cum_positive_sum[:, index]
        positive_square_sum = self.cum_positive_sq[:, index]
        positive_mean = np.divide(
            positive_sum, positive_count, out=np.zeros_like(positive_sum), where=positive_count > 0
        )
        positive_variance = np.maximum(
            0.0,
            np.divide(positive_square_sum, positive_count,
                      out=np.zeros_like(positive_square_sum), where=positive_count > 0)
            - positive_mean ** 2,
        )
        features["days_since_sale"] = np.where(
            self.last_positive[:, index - 1] >= 0,
            (index - 1) - self.last_positive[:, index - 1],
            index,
        )
        features["ADI"] = np.divide(
            index, positive_count, out=np.full_like(positive_sum, index + 1, dtype=float),
            where=positive_count > 0,
        )
        features["positive_mean"] = positive_mean
        features["positive_cv2"] = np.divide(
            positive_variance, positive_mean ** 2, out=np.zeros_like(positive_sum),
            where=positive_mean > 0,
        )

        date = self.dates[index]
        features["dow"] = np.full(len(self.y), date.dayofweek)
        features["day"] = np.full(len(self.y), date.day)
        features["month"] = np.full(len(self.y), date.month)
        features["week"] = np.full(len(self.y), int(date.isocalendar().week))
        features["dow_sin"] = np.full(len(self.y), np.sin(2 * np.pi * date.dayofweek / 7))
        features["dow_cos"] = np.full(len(self.y), np.cos(2 * np.pi * date.dayofweek / 7))
        features["month_sin"] = np.full(len(self.y), np.sin(2 * np.pi * (date.month - 1) / 12))
        features["month_cos"] = np.full(len(self.y), np.cos(2 * np.pi * (date.month - 1) / 12))

        if context:
            for name, matrix, row_index in (
                ("shop", self.shop_y, self.shop_idx),
                ("category", self.category_y, self.category_idx),
            ):
                for window in (7, 28, 56):
                    values = matrix[row_index, index - window:index]
                    features[f"{name}_sum_{window}"] = values.sum(axis=1)
                    features[f"{name}_mean_{window}"] = values.mean(axis=1)
                values = matrix[row_index]
                recent = values[:, index - 28:index].mean(axis=1)
                previous = values[:, index - 56:index - 28].mean(axis=1)
                features[f"{name}_trend_28"] = recent / (previous + 1e-6) - 1.0

            for window in (7, 28):
                features[f"network_sum_{window}"] = np.full(
                    len(self.y), self.network_y[index - window:index].sum()
                )
            features["series_share_shop_28"] = (
                features["sum_28"] / (features["shop_sum_28"] + 1e-6)
            )
            features["series_share_category_28"] = (
                features["sum_28"] / (features["category_sum_28"] + 1e-6)
            )
            features["shop_share_network_28"] = (
                features["shop_sum_28"] / (self.network_y[index - 28:index].sum() + 1e-6)
            )
            features["category_share_network_28"] = (
                features["category_sum_28"] / (self.network_y[index - 28:index].sum() + 1e-6)
            )

        result = pd.DataFrame(features)
        result["shop_id"] = self.shop_values
        result["category"] = self.category_values
        return result

    def build_fold(self, origin_index: int, horizon: int, context: bool):
        train_features, train_targets = [], []
        for train_origin in range(
            MIN_HISTORY, origin_index - horizon + 1, TRAIN_STRIDE
        ):
            train_features.append(self.snapshot(train_origin, context))
            train_targets.append(
                self.y[:, train_origin:train_origin + horizon].sum(axis=1)
            )
        if not train_features:
            raise ValueError("No eligible historical training samples")
        x_train = pd.concat(train_features, ignore_index=True)
        y_train = np.concatenate(train_targets)
        x_test = self.snapshot(origin_index, context)
        y_test = self.y[:, origin_index:origin_index + horizon].sum(axis=1)
        return x_train, y_train, x_test, y_test

    @property
    def dates(self):
        return self._dates

    @dates.setter
    def dates(self, value):
        self._dates = value


def fit_predict(store: FeatureStore, origin: pd.Timestamp, horizon: int, context: bool):
    origin_index = int((origin - store.dates[0]).days)
    x_train, y_train, x_test, y_test = store.build_fold(origin_index, horizon, context)
    categorical = ["shop_id", "category"]
    for column in categorical:
        x_train[column] = x_train[column].astype("category")
        x_test[column] = pd.Categorical(x_test[column], categories=x_train[column].cat.categories)
    model = lgb.LGBMRegressor(**MODEL_PARAMS)
    model.fit(x_train, y_train, categorical_feature=categorical)
    prediction = np.maximum(0.0, model.predict(x_test))
    return y_test, prediction, len(x_train)


def metric(actual: np.ndarray, forecast: np.ndarray):
    actual = np.asarray(actual, dtype=float)
    forecast = np.maximum(0.0, np.asarray(forecast, dtype=float))
    denominator = float(np.abs(actual).sum())
    return {
        "n": int(len(actual)),
        "actual_total": float(actual.sum()),
        "forecast_total": float(forecast.sum()),
        "WAPE": float(np.abs(actual - forecast).sum() / denominator) if denominator else None,
        "MAE": float(mean_absolute_error(actual, forecast)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, forecast))),
        "Bias_pct": float((forecast.sum() - actual.sum()) / denominator) if denominator else None,
    }


def run(input_path: Path, output_path: Path, evidence_status: str):
    started = time.time()
    output_path.mkdir(parents=True, exist_ok=True)
    frame, pivot, dates, shops, categories = read_panel(input_path)
    store = FeatureStore(pivot, shops, categories)
    store.dates = dates
    predictions = []
    folds = []

    for horizon, origins in HORIZON_ORIGINS.items():
        for origin in origins:
            for model_name, use_context in (
                ("LightGBM_base", False),
                ("LightGBM_context", True),
            ):
                actual, forecast, train_rows = fit_predict(
                    store, origin, horizon, use_context
                )
                folds.append({
                    "horizon": horizon,
                    "origin": str(origin.date()),
                    "model": model_name,
                    "train_rows": train_rows,
                    **metric(actual, forecast),
                })
                for index, (shop, category) in enumerate(store.keys):
                    predictions.append({
                        "horizon": horizon,
                        "origin": str(origin.date()),
                        "shop_id": shop,
                        "category": category,
                        "model": model_name,
                        "actual": float(actual[index]),
                        "forecast": float(forecast[index]),
                    })

    pred = pd.DataFrame(predictions)
    fold_frame = pd.DataFrame(folds)
    aggregate = []
    for (horizon, model_name), group in pred.groupby(["horizon", "model"]):
        result = metric(group.actual.to_numpy(), group.forecast.to_numpy())
        fold_wape = fold_frame[
            (fold_frame.horizon == horizon) & (fold_frame.model == model_name)
        ].WAPE
        aggregate.append({
            "horizon": int(horizon),
            "model": model_name,
            **result,
            "mean_origin_WAPE": float(fold_wape.mean()),
            "origins": int(group.origin.nunique()),
        })
    aggregate_frame = pd.DataFrame(aggregate).sort_values(["horizon", "model"])

    # Paired cluster bootstrap: resample independent shop-category series,
    # retaining each sampled series' complete set of validation origins.
    h7 = pred[pred.horizon == 7]
    origins7 = sorted(h7.origin.unique())
    keys = sorted(set(zip(h7.shop_id, h7.category)))
    actual_matrix = np.vstack([
        h7[(h7.shop_id == shop) & (h7.category == category) &
           (h7.model == "LightGBM_base")].sort_values("origin").actual.to_numpy()
        for shop, category in keys
    ])
    base_matrix = np.vstack([
        h7[(h7.shop_id == shop) & (h7.category == category) &
           (h7.model == "LightGBM_base")].sort_values("origin").forecast.to_numpy()
        for shop, category in keys
    ])
    context_matrix = np.vstack([
        h7[(h7.shop_id == shop) & (h7.category == category) &
           (h7.model == "LightGBM_context")].sort_values("origin").forecast.to_numpy()
        for shop, category in keys
    ])
    rng = np.random.default_rng(20261108)
    differences = []
    for _ in range(2000):
        sample = rng.integers(0, len(keys), size=len(keys))
        y = actual_matrix[sample]
        denominator = np.abs(y).sum()
        differences.append(
            np.abs(y - context_matrix[sample]).sum() / denominator
            - np.abs(y - base_matrix[sample]).sum() / denominator
        )
    lower, median, upper = np.quantile(differences, [0.025, 0.5, 0.975])
    bootstrap = pd.DataFrame([{
        "horizon": 7,
        "reference": "LightGBM_base",
        "challenger": "LightGBM_context",
        "series_clusters": len(keys),
        "origins": len(origins7),
        "replicates": 2000,
        "median_WAPE_difference": median,
        "ci_2_5": lower,
        "ci_97_5": upper,
        "difference_definition": "WAPE(context) - WAPE(base); negative favours context",
    }])

    # Prequential conformal-style intervals: calibration residuals are drawn
    # only from earlier validation origins, never from the current fold.
    interval_rows = []
    prior_scores = []
    for origin in origins7:
        current = h7[(h7.origin == origin) & (h7.model == "LightGBM_context")].sort_values(
            ["shop_id", "category"]
        )
        y = current.actual.to_numpy(float)
        p = current.forecast.to_numpy(float)
        if len(prior_scores) and len(prior_scores) >= 3 * len(keys):
            q80 = np.quantile(prior_scores, 0.80, method="higher")
            q90 = np.quantile(prior_scores, 0.90, method="higher")
            scale = np.sqrt(np.maximum(p, 1.0))
            lo80, hi80 = np.maximum(0.0, p - q80 * scale), p + q80 * scale
            lo90, hi90 = np.maximum(0.0, p - q90 * scale), p + q90 * scale
            interval_rows.append({
                "origin": origin,
                "calibration_origins": len(prior_scores) // len(keys),
                "coverage_80": float(np.mean((y >= lo80) & (y <= hi80))),
                "mean_width_80": float(np.mean(hi80 - lo80)),
                "coverage_90": float(np.mean((y >= lo90) & (y <= hi90))),
                "mean_width_90": float(np.mean(hi90 - lo90)),
            })
        prior_scores.extend(
            (np.abs(y - p) / np.sqrt(np.maximum(p, 1.0))).tolist()
        )
    interval_frame = pd.DataFrame(interval_rows)

    # Coherent bottom-up roll-ups: no separate aggregate prediction is created.
    hierarchy_rows = []
    for level, group_columns in (
        ("shop_category", ["shop_id", "category"]),
        ("shop_total", ["shop_id"]),
        ("category_total", ["category"]),
        ("network", []),
    ):
        actual_values, forecast_values = [], []
        for origin in origins7:
            part = h7[(h7.origin == origin) & (h7.model == "LightGBM_context")]
            if group_columns:
                grouped = part.groupby(group_columns)[["actual", "forecast"]].sum()
                actual_values.extend(grouped.actual.to_numpy())
                forecast_values.extend(grouped.forecast.to_numpy())
            else:
                actual_values.append(float(part.actual.sum()))
                forecast_values.append(float(part.forecast.sum()))
        row = metric(np.asarray(actual_values), np.asarray(forecast_values))
        hierarchy_rows.append({"level": level, **row})
    hierarchy_frame = pd.DataFrame(hierarchy_rows)

    # Optional past-fold-only multiplicative bias correction. It is reported
    # as a trade-off, not silently applied to the selected point forecast.
    calibration_rows = []
    prior_actual = prior_forecast = 0.0
    for origin in origins7:
        part = h7[(h7.origin == origin) & (h7.model == "LightGBM_context")]
        y, p = part.actual.to_numpy(float), part.forecast.to_numpy(float)
        factor = float(np.clip(prior_actual / prior_forecast, 0.90, 1.10)) if prior_forecast > 0 else 1.0
        adjusted = p * factor
        calibration_rows.append({
            "origin": origin,
            "factor_from_prior_origins": factor,
            "raw_WAPE": metric(y, p)["WAPE"],
            "adjusted_WAPE": metric(y, adjusted)["WAPE"],
            "raw_Bias_pct": metric(y, p)["Bias_pct"],
            "adjusted_Bias_pct": metric(y, adjusted)["Bias_pct"],
        })
        prior_actual += float(y.sum())
        prior_forecast += float(p.sum())
    calibration_frame = pd.DataFrame(calibration_rows)

    pred.to_csv(output_path / "predictions.csv", index=False)
    fold_frame.to_csv(output_path / "fold_metrics.csv", index=False)
    aggregate_frame.to_csv(output_path / "aggregate_metrics.csv", index=False)
    bootstrap.to_csv(output_path / "cluster_bootstrap_h7.csv", index=False)
    interval_frame.to_csv(output_path / "prequential_intervals_h7.csv", index=False)
    hierarchy_frame.to_csv(output_path / "hierarchy_metrics_h7.csv", index=False)
    calibration_frame.to_csv(output_path / "prequential_bias_calibration_h7.csv", index=False)

    manifest = {
        "pipeline": "bsmart_context_aware_global_tweedie_v1",
        "input_file": input_path.name,
        "input_sha256": sha256(input_path),
        "evidence_status": evidence_status,
        "rows": int(len(frame)),
        "shops": int(frame.shop_id.nunique()),
        "categories": int(frame.category.nunique()),
        "series": int(len(pivot)),
        "date_start": str(dates.min().date()),
        "date_end": str(dates.max().date()),
        "horizon_origins": {
            str(h): [str(x.date()) for x in origins]
            for h, origins in HORIZON_ORIGINS.items()
        },
        "training_stride_days": TRAIN_STRIDE,
        "minimum_history_days": MIN_HISTORY,
        "target": "direct cumulative observed units over the next h days",
        "feature_policy": "all own-series and cross-series features use dates strictly before each origin",
        "base_features": [
            "lags 1/7/14/28/56",
            "rolling mean/std/sum/zero ratio 7/14/28/56",
            "days since last sale, ADI, positive mean, positive CV2",
            "shop/category IDs and weekday/day/month/ISO-week cyclic encodings",
        ],
        "context_features": [
            "shop aggregate sums and means 7/28/56",
            "category aggregate sums and means 7/28/56",
            "shop/category 28-day trend",
            "network aggregate sums 7/28",
            "series share of shop/category and shop/category share of network",
        ],
        "model": "LightGBM Tweedie",
        "model_parameters": MODEL_PARAMS,
        "comparison": "same model parameters and same origins; base features versus added hierarchical context features",
        "bootstrap": {"clusters": "shop-category series", "replicates": 2000, "seed": 20261108},
        "interval_method": "prequential standardised absolute residual quantiles from earlier 7-day origins only",
        "hierarchy_method": "bottom-up summation of the same shop-category forecasts",
        "final_holdout_evaluated": False,
        "legacy_q4_2025_used": False,
        "raw_business_data_committed": False,
        "elapsed_seconds": round(time.time() - started, 2),
        "python": sys.version,
        "platform": platform.platform(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "lightgbm": lgb.__version__,
    }
    (output_path / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )
    print(aggregate_frame.to_string(index=False))
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--evidence-status", default="observed_unverified")
    args = parser.parse_args()
    run(args.input, args.output, args.evidence_status)
