"""Leakage-aware adaptive daily-demand forecasting research pipeline.

Input is an explicit daily panel: date, shop_id, category_id, demand.
Demand must be a non-negative quantity (not revenue). Missing dates are not
silently interpreted as zero. This module does not contain or generate research
data; use synthetic fixtures only for software tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import platform
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OrdinalEncoder
from sklearn.metrics import mean_absolute_error, mean_squared_error

KEYS = ["shop_id", "category_id"]
REQUIRED = ["date", *KEYS, "demand"]
HORIZONS = (1, 7, 14, 28)
LAGS = (1, 7, 14, 28, 56)


class DataContractError(ValueError):
    """Raised when input data cannot support a defensible daily panel."""


@dataclass
class DemandProfile:
    adi: float
    cv2: float
    zero_ratio: float
    positive_days: int
    total_days: int
    regime: str


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_input_frame(path: Path) -> pd.DataFrame:
    if path.suffix.lower() in {".xlsx", ".xls"}:
        return pd.read_excel(path)
    return pd.read_csv(path)


def load_daily_panel(path: str | Path, fill_missing_as_zero: bool = False) -> pd.DataFrame:
    """Load a daily shop-category panel, including the supplied RQ1 column names.

    Accepted source aliases: category -> category_id and
    units_sold_observed -> demand. Excel serial dates are converted explicitly.
    Missing dates are never silently treated as zero.
    """
    path = Path(path)
    frame = _read_input_frame(path)
    if "category_id" not in frame.columns and "category" in frame.columns:
        frame = frame.rename(columns={"category": "category_id"})
    if "demand" not in frame.columns and "units_sold_observed" in frame.columns:
        frame = frame.rename(columns={"units_sold_observed": "demand"})
    missing = sorted(set(REQUIRED) - set(frame.columns))
    if missing:
        raise DataContractError(f"Missing required columns: {missing}")

    raw_dates = frame["date"]
    if pd.api.types.is_datetime64_any_dtype(raw_dates):
        parsed_dates = pd.to_datetime(raw_dates, errors="coerce")
    elif pd.api.types.is_numeric_dtype(raw_dates):
        parsed_dates = pd.to_datetime(raw_dates, unit="D", origin="1899-12-30", errors="coerce")
    else:
        numeric_dates = pd.to_numeric(raw_dates, errors="coerce")
        if numeric_dates.notna().all():
            parsed_dates = pd.to_datetime(numeric_dates, unit="D", origin="1899-12-30", errors="coerce")
        else:
            parsed_dates = pd.to_datetime(raw_dates, errors="coerce")
    if parsed_dates.isna().any():
        raise DataContractError("Invalid or missing dates are present.")

    frame = frame.copy()
    frame["date"] = parsed_dates.dt.normalize()
    frame = frame[["date", *KEYS, "demand"] + (["is_zero_observed_sales"] if "is_zero_observed_sales" in frame.columns else [])]
    if frame[KEYS].isna().any().any():
        raise DataContractError("shop_id and category/category_id must be non-null.")
    frame[KEYS] = frame[KEYS].astype(str)
    frame["demand"] = pd.to_numeric(frame["demand"], errors="coerce")
    if frame["demand"].isna().any() or not np.isfinite(frame["demand"]).all():
        raise DataContractError("Demand must be finite numeric values.")
    if (frame["demand"] < 0).any():
        raise DataContractError("Negative demand found; returns/cancellations must be reconciled upstream.")
    if "is_zero_observed_sales" in frame.columns:
        supplied_flag = pd.to_numeric(frame["is_zero_observed_sales"], errors="coerce")
        expected_flag = (frame["demand"] == 0).astype(int)
        if supplied_flag.isna().any() or not supplied_flag.astype(int).equals(expected_flag):
            mismatch = int((supplied_flag.fillna(-1).astype(int) != expected_flag).sum())
            raise DataContractError(f"is_zero_observed_sales disagrees with demand on {mismatch} rows.")
        frame = frame.drop(columns=["is_zero_observed_sales"])

    duplicate = frame.duplicated(["date", *KEYS], keep=False)
    if duplicate.any():
        sample = frame.loc[duplicate, ["date", *KEYS]].head(5).to_dict("records")
        raise DataContractError(f"Duplicate daily keys found; aggregate or resolve upstream: {sample}")

    panels = []
    for key, group in frame.groupby(KEYS, sort=False):
        group = group.sort_values("date").set_index("date")
        if fill_missing_as_zero:
            full_index = pd.date_range(group.index.min(), group.index.max(), freq="D")
            group = group.reindex(full_index)
            group[KEYS[0]], group[KEYS[1]] = key
            group["demand"] = group["demand"].fillna(0.0)
            group.index.name = "date"
            group = group.reset_index()
        else:
            expected = pd.date_range(group.index.min(), group.index.max(), freq="D")
            if not group.index.equals(expected):
                absent = expected.difference(group.index)
                raise DataContractError(
                    f"Missing dates for shop/category {key}: {len(absent)} gaps. "
                    "Confirm closed days vs missing records; only then use --fill-missing-dates-as-zero."
                )
            group = group.reset_index()
        panels.append(group[["date", *KEYS, "demand"]])
    result = pd.concat(panels, ignore_index=True).sort_values([*KEYS, "date"])
    if result.empty:
        raise DataContractError("No usable observations.")
    return result.reset_index(drop=True)

def demand_profile(values: np.ndarray) -> DemandProfile:
    x = np.asarray(values, dtype=float)
    positive = x[x > 0]
    n = len(x)
    zero_ratio = float(np.mean(x == 0)) if n else 1.0
    adi = float(n / len(positive)) if len(positive) else math.inf
    mean = float(positive.mean()) if len(positive) else 0.0
    cv2 = float((positive.std(ddof=0) / mean) ** 2) if mean > 0 else math.inf
    # Syntetos-Boylan demand classes; retain metrics so the threshold decision is auditable.
    if len(positive) == 0:
        regime = "no_observed_demand"
    elif adi >= 1.32 and cv2 >= 0.49:
        regime = "lumpy"
    elif adi >= 1.32:
        regime = "intermittent"
    elif cv2 >= 0.49:
        regime = "erratic"
    else:
        regime = "smooth"
    return DemandProfile(adi, cv2, zero_ratio, int(len(positive)), int(n), regime)


def _features(history: pd.DataFrame, origin: pd.Timestamp) -> dict:
    """Features use observations strictly before origin."""
    y = history.loc[history["date"] < origin, "demand"].to_numpy(dtype=float)
    if len(y) < max(LAGS):
        raise DataContractError(f"At least {max(LAGS)} historical days are required.")
    out: dict[str, float | str] = {}
    last = history.loc[history["date"] < origin].iloc[-1]
    out["shop_id"] = str(last["shop_id"])
    out["category_id"] = str(last["category_id"])
    for lag in LAGS:
        out[f"lag_{lag}"] = float(y[-lag])
    for window in (7, 14, 28, 56):
        w = y[-window:]
        out[f"mean_{window}"] = float(w.mean())
        out[f"std_{window}"] = float(w.std(ddof=0))
        out[f"zero_ratio_{window}"] = float(np.mean(w == 0))
        out[f"sum_{window}"] = float(w.sum())
    nz = np.flatnonzero(y > 0)
    out["days_since_sale"] = float(len(y) - 1 - nz[-1]) if len(nz) else float(len(y))
    profile = demand_profile(y)
    out["adi"] = profile.adi if np.isfinite(profile.adi) else float(len(y) + 1)
    out["cv2"] = profile.cv2 if np.isfinite(profile.cv2) else 0.0
    out["zero_ratio_all"] = profile.zero_ratio
    out["day_of_week"] = int(origin.day_of_week)
    out["day_of_month"] = int(origin.day)
    out["month"] = int(origin.month)
    out["week_of_year"] = int(origin.isocalendar().week)
    out["is_month_start"] = int(origin.is_month_start)
    out["is_month_end"] = int(origin.is_month_end)
    out["dow_sin"] = math.sin(2 * math.pi * origin.day_of_week / 7)
    out["dow_cos"] = math.cos(2 * math.pi * origin.day_of_week / 7)
    out["month_sin"] = math.sin(2 * math.pi * (origin.month - 1) / 12)
    out["month_cos"] = math.cos(2 * math.pi * (origin.month - 1) / 12)
    return out


def make_supervised(panel: pd.DataFrame, horizon: int, min_history: int = 56, stride: int = 7) -> pd.DataFrame:
    """Build direct-horizon examples with vectorised, strictly historical features."""
    if min_history < max(LAGS):
        raise DataContractError(f"min_history must be at least {max(LAGS)} days for the configured lag features.")
    if horizon < 1:
        raise DataContractError("Forecast horizon must be a positive number of days.")
    if stride < 1:
        raise DataContractError("Training stride must be a positive number of days.")
    rows = []
    for key, group in panel.groupby(KEYS, sort=False):
        group = group.sort_values("date")
        values = group["demand"].to_numpy(dtype=np.float64)
        dates = pd.DatetimeIndex(group["date"])
        indices = np.arange(min_history, len(values) - horizon + 1, stride, dtype=np.int32)
        if not len(indices):
            continue

        cumulative = np.concatenate(([0.0], np.cumsum(values, dtype=np.float64)))
        cumulative_sq = np.concatenate(([0.0], np.cumsum(values * values, dtype=np.float64)))
        positive = (values > 0).astype(np.int32)
        positive_count = np.concatenate(([0], np.cumsum(positive)))
        positive_values = np.where(values > 0, values, 0.0)
        positive_sum = np.concatenate(([0.0], np.cumsum(positive_values)))
        positive_sq = np.concatenate(([0.0], np.cumsum(positive_values * positive_values)))
        last_positive = np.maximum.accumulate(np.where(positive > 0, np.arange(len(values)), -1))

        features: dict[str, object] = {
            "shop_id": np.repeat(str(key[0]), len(indices)),
            "category_id": np.repeat(str(key[1]), len(indices)),
        }
        for lag in LAGS:
            features[f"lag_{lag}"] = values[indices - lag].astype(np.float32)

        for window in (7, 14, 28, 56):
            rolling_sum = cumulative[indices] - cumulative[indices - window]
            rolling_sq = cumulative_sq[indices] - cumulative_sq[indices - window]
            rolling_mean = rolling_sum / window
            rolling_var = np.maximum(0.0, rolling_sq / window - rolling_mean * rolling_mean)
            rolling_positive = positive_count[indices] - positive_count[indices - window]
            features[f"mean_{window}"] = rolling_mean.astype(np.float32)
            features[f"std_{window}"] = np.sqrt(rolling_var).astype(np.float32)
            features[f"zero_ratio_{window}"] = (1.0 - rolling_positive / window).astype(np.float32)
            features[f"sum_{window}"] = rolling_sum.astype(np.float32)

        last_sale_index = last_positive[indices - 1]
        features["days_since_sale"] = np.where(
            last_sale_index >= 0, indices - 1 - last_sale_index, indices
        ).astype(np.float32)

        all_positive_count = positive_count[indices]
        all_positive_sum = positive_sum[indices]
        all_positive_sq = positive_sq[indices]
        positive_mean = np.divide(
            all_positive_sum, all_positive_count,
            out=np.zeros_like(all_positive_sum), where=all_positive_count > 0
        )
        positive_var = np.maximum(
            0.0,
            np.divide(all_positive_sq, all_positive_count,
                      out=np.zeros_like(all_positive_sq), where=all_positive_count > 0)
            - positive_mean * positive_mean
        )
        cv2 = np.divide(
            positive_var, positive_mean * positive_mean,
            out=np.zeros_like(positive_var), where=positive_mean > 0
        )
        features["adi"] = np.divide(
            indices, all_positive_count,
            out=np.full(len(indices), len(values) + 1, dtype=np.float64),
            where=all_positive_count > 0
        ).astype(np.float32)
        features["cv2"] = cv2.astype(np.float32)
        features["zero_ratio_all"] = (1.0 - all_positive_count / indices).astype(np.float32)

        origin_dates = dates.take(indices)
        features["day_of_week"] = origin_dates.day_of_week.to_numpy(dtype=np.int8)
        features["day_of_month"] = origin_dates.day.to_numpy(dtype=np.int8)
        features["month"] = origin_dates.month.to_numpy(dtype=np.int8)
        features["week_of_year"] = origin_dates.isocalendar().week.to_numpy(dtype=np.int16)
        features["is_month_start"] = origin_dates.is_month_start.astype(np.int8)
        features["is_month_end"] = origin_dates.is_month_end.astype(np.int8)
        features["dow_sin"] = np.sin(2 * np.pi * origin_dates.day_of_week.to_numpy() / 7).astype(np.float32)
        features["dow_cos"] = np.cos(2 * np.pi * origin_dates.day_of_week.to_numpy() / 7).astype(np.float32)
        features["month_sin"] = np.sin(2 * np.pi * (origin_dates.month.to_numpy() - 1) / 12).astype(np.float32)
        features["month_cos"] = np.cos(2 * np.pi * (origin_dates.month.to_numpy() - 1) / 12).astype(np.float32)

        features["target"] = (cumulative[indices + horizon] - cumulative[indices]).astype(np.float32)
        features["origin"] = origin_dates
        rows.append(pd.DataFrame(features))
    if not rows:
        return pd.DataFrame()
    return pd.concat(rows, ignore_index=True)

def croston_forecast(values: np.ndarray, horizon: int, method: str = "croston") -> float:
    """Croston, SBA and TSB daily-rate forecasts multiplied by horizon."""
    x = np.asarray(values, dtype=float)
    if len(x) == 0 or not np.any(x > 0):
        return 0.0
    alpha = 0.1
    if method in {"croston", "sba"}:
        demand_sizes = []
        intervals = []
        last = None
        for i, value in enumerate(x):
            if value > 0:
                demand_sizes.append(float(value))
                intervals.append(float(i + 1 if last is None else i - last))
                last = i
        z, p = demand_sizes[0], intervals[0]
        for size, interval in zip(demand_sizes[1:], intervals[1:]):
            z = alpha * size + (1 - alpha) * z
            p = alpha * interval + (1 - alpha) * p
        rate = z / max(p, 1e-9)
        if method == "sba":
            rate *= (1 - alpha / 2)
    elif method == "tsb":
        p = float(x[0] > 0)
        z = float(x[x > 0][0])
        for value in x[1:]:
            p = alpha * float(value > 0) + (1 - alpha) * p
            if value > 0:
                z = alpha * float(value) + (1 - alpha) * z
        rate = p * z
    else:
        raise ValueError(f"Unknown intermittent method: {method}")
    return max(0.0, float(rate * horizon))


def _estimator(name: str):
    if name == "hist_gradient_boosting":
        return Pipeline([
            ("encode", ColumnTransformer([
                ("ids", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                 ["shop_id", "category_id"])
            ], remainder="passthrough", verbose_feature_names_out=False)),
            ("model", HistGradientBoostingRegressor(
                max_iter=160, learning_rate=0.06, max_leaf_nodes=15,
                l2_regularization=1.0, random_state=42
            ))
        ])
    if name == "two_stage_hist":
        raise ValueError("two_stage_hist uses a dedicated classifier-regressor fitting path.")
    if name == "lightgbm":
        from lightgbm import LGBMRegressor
        return Pipeline([
            ("encode", ColumnTransformer([
                ("ids", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
                 ["shop_id", "category_id"])
            ], remainder="passthrough", verbose_feature_names_out=False)),
            ("model", LGBMRegressor(
                n_estimators=500, learning_rate=0.025, num_leaves=15,
                max_depth=-1, min_child_samples=30, reg_lambda=2.0,
                subsample=0.85, colsample_bytree=0.85, random_state=42,
                verbosity=-1
            ))
        ])
    if name == "catboost":
        from catboost import CatBoostRegressor
        # Tweedie is appropriate for non-negative, right-skewed cumulative demand.
        return CatBoostRegressor(
            iterations=500, depth=6, learning_rate=0.03,
            loss_function="Tweedie:variance_power=1.3",
            l2_leaf_reg=5.0, random_seed=42, verbose=False, allow_writing_files=False
        )
    raise ValueError(name)


def _fit_predict(model_name: str, train: pd.DataFrame, predict_rows: pd.DataFrame) -> np.ndarray:
    feature_cols = [c for c in train.columns if c not in {"target", "origin"}]
    X_train = train[feature_cols].copy()
    X_pred = predict_rows[feature_cols].copy()
    y_train = train["target"].to_numpy(dtype=float)
    if model_name == "two_stage_hist":
        if np.unique(y_train > 0).size < 2:
            raise DataContractError("Two-stage classifier requires both zero and positive horizon targets.")
        encoder = ColumnTransformer([
            ("ids", OrdinalEncoder(handle_unknown="use_encoded_value", unknown_value=-1),
             ["shop_id", "category_id"])
        ], remainder="passthrough", verbose_feature_names_out=False)
        X_encoded = encoder.fit_transform(X_train)
        X_pred_encoded = encoder.transform(X_pred)
        classifier = HistGradientBoostingClassifier(
            max_iter=140, learning_rate=0.06, max_leaf_nodes=15,
            l2_regularization=1.0, random_state=42
        )
        classifier.fit(X_encoded, (y_train > 0).astype(int))
        positive = y_train > 0
        if int(positive.sum()) < 2:
            raise DataContractError("Two-stage regressor requires at least two positive training targets.")
        regressor = HistGradientBoostingRegressor(
            max_iter=160, learning_rate=0.06, max_leaf_nodes=15,
            l2_regularization=1.0, random_state=42
        )
        regressor.fit(X_encoded[positive], y_train[positive])
        probability = classifier.predict_proba(X_pred_encoded)[:, 1]
        conditional_mean = np.maximum(0.0, regressor.predict(X_pred_encoded))
        # Expected demand = P(positive horizon demand) × E[demand | positive].
        pred = probability * conditional_mean
    elif model_name == "catboost":
        model = _estimator(model_name)
        cat_cols = ["shop_id", "category_id"]
        model.fit(X_train, y_train, cat_features=cat_cols)
        pred = model.predict(X_pred)
    elif model_name == "lightgbm":
        from lightgbm import LGBMRegressor
        cat_cols = ["shop_id", "category_id"]
        for column in cat_cols:
            categories = pd.Index(X_train[column].astype(str).unique())
            X_train[column] = pd.Categorical(X_train[column].astype(str), categories=categories)
            X_pred[column] = pd.Categorical(X_pred[column].astype(str), categories=categories)
        model = LGBMRegressor(
            objective="tweedie", tweedie_variance_power=1.3,
            n_estimators=500, learning_rate=0.025, num_leaves=15,
            max_depth=-1, min_child_samples=30, reg_lambda=2.0,
            subsample=0.85, subsample_freq=1, colsample_bytree=0.85,
            random_state=42, verbosity=-1
        )
        model.fit(X_train, y_train, categorical_feature=cat_cols)
        pred = model.predict(X_pred)
    else:
        model = _estimator(model_name)
        model.fit(X_train, y_train)
        pred = model.predict(X_pred)
    return np.maximum(0.0, np.asarray(pred, dtype=float))


def _metric_row(actual: np.ndarray, predicted: np.ndarray, scale: float | np.ndarray) -> dict:
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    abs_error = np.abs(actual - predicted)
    scales = np.asarray(scale, dtype=float)
    if scales.ndim == 0:
        scales = np.full(len(abs_error), float(scales))
    if len(scales) != len(abs_error):
        raise ValueError("MASE scale must be scalar or one value per forecast series.")
    mase = float(np.mean(abs_error / np.where(scales > 0, scales, np.nan))) if len(abs_error) else None
    denom = float(np.abs(actual).sum())
    return {
        "n": int(len(actual)),
        "wape": float(abs_error.sum() / denom) if denom > 0 else None,
        "mae": float(mean_absolute_error(actual, predicted)) if len(actual) else None,
        "rmse": float(np.sqrt(mean_squared_error(actual, predicted))) if len(actual) else None,
        "mase": mase,
        "bias": float((predicted - actual).sum() / denom) if denom > 0 else None,
        "actual_total": float(actual.sum()),
        "forecast_total": float(predicted.sum())
    }


def rolling_origins(panel: pd.DataFrame, horizon: int, folds: int = 3,
                    min_history: int = 56,
                    development_end: str | pd.Timestamp | None = None) -> list[pd.Timestamp]:
    """Select monthly spaced rolling origins strictly before the exclusive dev cutoff.

    The default CLI cutoff is 2025-10-01, protecting the previously inspected
    2025-Q4 legacy test period from all model selection.
    """
    if min_history < max(LAGS):
        raise DataContractError(f"min_history must be at least {max(LAGS)} days for the configured lag features.")
    if horizon < 1 or folds < 1:
        raise DataContractError("horizon and folds must be positive integers.")
    if panel.empty:
        return []
    cutoff = (pd.Timestamp(development_end).normalize()
              if development_end is not None
              else panel["date"].max().normalize() + pd.Timedelta(days=1))
    first_date = panel["date"].min().normalize()
    earliest = first_date + pd.Timedelta(days=min_history)
    latest_origin = cutoff - pd.Timedelta(days=horizon)
    spacing = max(30, horizon)
    origins = [latest_origin - pd.Timedelta(days=spacing * k)
               for k in reversed(range(folds))]
    return [origin for origin in origins if origin >= earliest and origin + pd.Timedelta(days=horizon) <= cutoff]

def _seasonal_naive_forecast(history: np.ndarray, horizon: int, season: int = 7,
                                lookback_cycles: int = 4) -> float:
    """Sum forecasts from matching weekdays in up to four completed weekly cycles."""
    values = np.asarray(history, dtype=float)
    if len(values) == 0:
        return 0.0
    daily = []
    for step in range(horizon):
        target_index = len(values) + step
        matches = [
            values[target_index - season * cycle]
            for cycle in range(1, lookback_cycles + 1)
            if 0 <= target_index - season * cycle < len(values)
        ]
        daily.append(float(np.mean(matches)) if matches else float(np.mean(values[-min(season, len(values)):])) )
    return max(0.0, float(np.sum(daily)))


def run_experiment(panel: pd.DataFrame, horizons=HORIZONS, folds=3,
                   min_history=56, candidates=None,
                   development_end: str | pd.Timestamp | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Rolling-origin comparison on development data only; Q4-2025 stays excluded."""
    candidates = candidates or ["seasonal_naive_7", "croston", "sba", "tsb", "two_stage_hist",
                                "hist_gradient_boosting", "lightgbm", "catboost"]
    summaries, predictions = [], []
    cutoff = (pd.Timestamp(development_end).normalize()
              if development_end is not None
              else panel["date"].max().normalize() + pd.Timedelta(days=1))
    development_panel = panel.loc[panel["date"] < cutoff].copy()
    development_panel = development_panel.sort_values([*KEYS, "date"]).reset_index(drop=True)
    for horizon in horizons:
        origins = rolling_origins(development_panel, horizon, folds, min_history, cutoff)
        if not origins:
            summaries.append({"horizon": horizon, "model": "ALL", "status": "not_evaluable",
                              "reason": "insufficient_development_history_for_requested_folds"})
            continue
        training_stride = max(7, horizon)
        supervised = make_supervised(development_panel, horizon, min_history, stride=training_stride)
        for origin in origins:
            train = supervised.loc[
                supervised["origin"] + pd.Timedelta(days=horizon) <= origin
            ].copy()
            current_rows, histories, actuals = [], [], []
            for key, group in development_panel.groupby(KEYS, sort=False):
                group = group.sort_values("date")
                hist = group[group["date"] < origin]
                future = group[(group["date"] >= origin) &
                               (group["date"] < origin + pd.Timedelta(days=horizon))]
                if len(hist) < min_history or len(future) != horizon:
                    continue
                feat = _features(hist, origin)
                feat["shop_id"], feat["category_id"] = str(key[0]), str(key[1])
                current_rows.append(feat)
                hist_values = hist["demand"].to_numpy(dtype=float)
                histories.append(hist_values)
                actuals.append(float(future["demand"].sum()))
            if not current_rows:
                continue
            pred_frame = pd.DataFrame(current_rows)
            actual_arr = np.asarray(actuals)
            scales = []
            for hist_values in histories:
                weekly_scale = float(np.mean(np.abs(hist_values[7:] - hist_values[:-7]))) if len(hist_values) > 7 else 0.0
                scales.append(weekly_scale * horizon if np.isfinite(weekly_scale) and weekly_scale > 0 else 1.0)
            scales = np.asarray(scales, dtype=float)
            regimes = [demand_profile(h).regime for h in histories]
            for name in candidates:
                try:
                    if name == "seasonal_naive_7":
                        forecasts = [_seasonal_naive_forecast(h, horizon) for h in histories]
                    elif name in {"croston", "sba", "tsb"}:
                        forecasts = [croston_forecast(h, horizon, name) for h in histories]
                    else:
                        if train.empty:
                            raise DataContractError("No eligible supervised training rows.")
                        forecasts = _fit_predict(name, train, pred_frame)
                    forecasts = np.maximum(0.0, np.asarray(forecasts, dtype=float))
                    for idx, (actual, forecast) in enumerate(zip(actual_arr, forecasts)):
                        predictions.append({
                            "horizon": horizon, "origin": origin.date().isoformat(),
                            "shop_id": pred_frame.iloc[idx]["shop_id"],
                            "category_id": pred_frame.iloc[idx]["category_id"],
                            "model": name, "regime": regimes[idx],
                            "actual": float(actual), "forecast": float(forecast)
                        })
                    metrics = _metric_row(actual_arr, forecasts, scales)
                    summaries.append({"horizon": horizon, "origin": origin.date().isoformat(),
                                      "model": name, "level": "all", "group_value": "all",
                                      "status": "ok", "series_count": int(len(actual_arr)), **metrics})
                    dimensions = {
                        "shop": pred_frame["shop_id"].astype(str).to_numpy(),
                        "category": pred_frame["category_id"].astype(str).to_numpy(),
                        "demand_regime": np.asarray(regimes, dtype=str),
                    }
                    for level, labels in dimensions.items():
                        for label in sorted(set(labels)):
                            mask = labels == label
                            subgroup_metrics = _metric_row(actual_arr[mask], forecasts[mask], scales[mask])
                            summaries.append({"horizon": horizon, "origin": origin.date().isoformat(),
                                              "model": name, "level": level, "group_value": label,
                                              "status": "ok", "series_count": int(mask.sum()), **subgroup_metrics})
                except ImportError as exc:
                    summaries.append({"horizon": horizon, "origin": origin.date().isoformat(),
                                      "model": name, "level": "all", "group_value": "all",
                                      "status": "skipped_dependency", "reason": str(exc)})
                except Exception as exc:
                    summaries.append({"horizon": horizon, "origin": origin.date().isoformat(),
                                      "model": name, "level": "all", "group_value": "all",
                                      "status": "failed", "reason": f"{type(exc).__name__}: {exc}"})
    return pd.DataFrame(summaries), pd.DataFrame(predictions)

def write_figures(summary: pd.DataFrame, predictions: pd.DataFrame, output: Path) -> list[str]:
    """Write reproducible validation plots from the supplied development predictions."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return ["matplotlib unavailable; figures skipped"]
    output.mkdir(parents=True, exist_ok=True)
    written = []
    level = summary["level"] if "level" in summary.columns else pd.Series("", index=summary.index)
    valid = summary[(summary["status"] == "ok") & (level == "all")].copy()
    if not valid.empty:
        means = valid.groupby(["horizon", "model"], as_index=False)["wape"].mean()
        for horizon, group in means.groupby("horizon"):
            group = group.dropna(subset=["wape"]).sort_values("wape")
            if group.empty:
                continue
            fig, ax = plt.subplots(figsize=(10, 5))
            ax.bar(group["model"], group["wape"] * 100)
            ax.set(title=f"Rolling-origin WAPE — {horizon}-day horizon", ylabel="WAPE (%)")
            ax.tick_params(axis="x", rotation=30)
            fig.tight_layout()
            path = output / f"wape_comparison_h{horizon}.png"
            fig.savefig(path, dpi=180)
            plt.close(fig)
            written.append(path.name)
    if not predictions.empty:
        p7 = predictions[predictions["horizon"] == 7].copy()
        if not p7.empty:
            scores = pd.Series({
                name: ((g["actual"] - g["forecast"]).abs().sum() / g["actual"].abs().sum())
                if g["actual"].abs().sum() > 0 else np.nan
                for name, g in p7.groupby("model")
            }).dropna()
            if not scores.empty:
                best = str(scores.idxmin())
                selected = p7[p7["model"] == best]
                series = selected.groupby(["shop_id", "category_id"])["actual"].sum().sort_values(ascending=False)
                if not series.empty:
                    shop, category = series.index[0]
                    line = selected[(selected["shop_id"] == shop) &
                                    (selected["category_id"] == category)].sort_values("origin")
                    fig, ax = plt.subplots(figsize=(10, 5))
                    ax.plot(line["origin"], line["actual"], marker="o", label="Actual")
                    ax.plot(line["origin"], line["forecast"], marker="o", label=f"Forecast ({best})")
                    ax.set(title=f"7-day rolling forecasts — shop {shop}, category {category}",
                           ylabel="Next 7-day demand")
                    ax.tick_params(axis="x", rotation=30)
                    ax.legend()
                    fig.tight_layout()
                    path = output / "actual_vs_forecast_7d.png"
                    fig.savefig(path, dpi=180)
                    plt.close(fig)
                    written.append(path.name)
                per_series = pd.DataFrame([
                    {"shop_id": shop_id, "category_id": category_id,
                     "wape": ((g["actual"] - g["forecast"]).abs().sum() / g["actual"].abs().sum())
                     if g["actual"].abs().sum() > 0 else np.nan}
                    for (shop_id, category_id), g in selected.groupby(["shop_id", "category_id"])
                ])
                heat = per_series.pivot(index="shop_id", columns="category_id", values="wape")
                if not heat.empty:
                    fig, ax = plt.subplots(figsize=(max(9, len(heat.columns) * 0.55),
                                                    max(5, len(heat.index) * 0.25)))
                    image = ax.imshow(heat.to_numpy(dtype=float), aspect="auto", interpolation="nearest")
                    ax.set(title=f"Shop × category WAPE — 7-day, {best}",
                           xlabel="Category", ylabel="Shop")
                    ax.set_xticks(range(len(heat.columns)), heat.columns, rotation=90)
                    ax.set_yticks(range(len(heat.index)), heat.index)
                    fig.colorbar(image, ax=ax, label="WAPE")
                    fig.tight_layout()
                    path = output / "shop_category_wape_heatmap_7d.png"
                    fig.savefig(path, dpi=180)
                    plt.close(fig)
                    written.append(path.name)
    return written


def build_diagnostics(panel: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for key, group in panel.groupby(KEYS, sort=False):
        profile = demand_profile(group.sort_values("date")["demand"].to_numpy(dtype=float))
        rows.append({"shop_id": key[0], "category_id": key[1], **asdict(profile),
                     "date_start": group["date"].min().date().isoformat(),
                     "date_end": group["date"].max().date().isoformat()})
    return pd.DataFrame(rows)


def select_models_by_regime(summary: pd.DataFrame, min_origins: int = 3,
                            min_series_per_origin: int = 20) -> pd.DataFrame:
    """Select candidates using development CV only; insufficient groups stay unselected."""
    required = {"horizon", "origin", "model", "level", "group_value", "status",
                "wape", "actual_total", "n", "series_count"}
    columns = ["horizon", "demand_regime", "selected_model", "development_wape",
               "origins", "min_series_per_origin", "forecasts", "status"]
    if summary.empty or not required.issubset(summary.columns):
        return pd.DataFrame(columns=columns)
    rows = summary[
        (summary["level"] == "demand_regime") &
        (summary["status"] == "ok") &
        summary["wape"].notna() &
        (summary["actual_total"] > 0)
    ].copy()
    if rows.empty:
        return pd.DataFrame(columns=columns)
    rows["absolute_error_total"] = rows["wape"] * rows["actual_total"]
    aggregate = rows.groupby(["horizon", "group_value", "model"], as_index=False).agg(
        absolute_error_total=("absolute_error_total", "sum"),
        actual_total=("actual_total", "sum"),
        origins=("origin", "nunique"),
        forecasts=("n", "sum"),
        min_series_per_origin=("series_count", "min")
    )
    aggregate["development_wape"] = aggregate["absolute_error_total"] / aggregate["actual_total"]
    selected = []
    for (horizon, regime), group in aggregate.groupby(["horizon", "group_value"]):
        eligible = group[(group["origins"] >= min_origins) &
                         (group["min_series_per_origin"] >= min_series_per_origin)]
        if eligible.empty:
            selected.append({"horizon": int(horizon), "demand_regime": regime,
                             "selected_model": None, "development_wape": None,
                             "origins": int(group["origins"].max()),
                             "min_series_per_origin": int(group["min_series_per_origin"].max()),
                             "forecasts": int(group["forecasts"].max()),
                             "status": "insufficient_validation_support"})
        else:
            best = eligible.sort_values(["development_wape", "model"]).iloc[0]
            selected.append({"horizon": int(horizon), "demand_regime": regime,
                             "selected_model": best["model"],
                             "development_wape": float(best["development_wape"]),
                             "origins": int(best["origins"]),
                             "min_series_per_origin": int(best["min_series_per_origin"]),
                             "forecasts": int(best["forecasts"]),
                             "status": "selected_on_development_cv"})
    return pd.DataFrame(selected)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="B-SMART adaptive daily-demand forecasting research pipeline")
    parser.add_argument("--input", required=True, help="CSV daily panel with date,shop_id,category_id,demand")
    parser.add_argument("--output", default="artifacts/adaptive_forecasting")
    parser.add_argument("--folds", type=int, default=3)
    parser.add_argument("--min-history", type=int, default=56)
    parser.add_argument("--development-end", default="2025-10-01", help="Exclusive development cutoff; defaults to protect the inspected 2025-Q4 test period")
    parser.add_argument("--evidence-status", choices=["real_user_provided", "verified_observed", "observed_unverified", "synthetic_fixture"], default="observed_unverified")
    parser.add_argument("--fill-missing-dates-as-zero", action="store_true",
                        help="Explicitly assume unrecorded dates inside each series are zero-demand days")
    parser.add_argument("--candidates", default="seasonal_naive_7,croston,sba,tsb,two_stage_hist,hist_gradient_boosting,lightgbm,catboost")
    args = parser.parse_args(argv)
    source = Path(args.input).resolve()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    panel = load_daily_panel(source, args.fill_missing_dates_as_zero)
    diagnostics = build_diagnostics(panel)
    horizons = list(HORIZONS)
    summary, predictions = run_experiment(
        panel, horizons=horizons, folds=args.folds, min_history=args.min_history,
        candidates=[x.strip() for x in args.candidates.split(",") if x.strip()],
        development_end=args.development_end
    )
    diagnostics.to_csv(output / "demand_diagnostics.csv", index=False)
    summary.to_csv(output / "rolling_origin_metrics.csv", index=False)
    predictions.to_csv(output / "rolling_origin_predictions.csv", index=False)
    regime_selection = select_models_by_regime(summary)
    regime_selection.to_csv(output / "selected_model_by_regime.csv", index=False)
    manifest = {
        "pipeline": "bsmart_adaptive_demand_forecasting",
        "pipeline_version": "0.1.0",
        "input_file_name": source.name,
        "input_sha256": sha256_file(source),
        "evidence_class": args.evidence_status,
        "dataset_source": "Researcher-supplied package; source provenance is unverified.",
        "development_end_exclusive": args.development_end,
        "legacy_test_period": "2025-10-01 through 2025-12-31; excluded from development model selection",
        "input_rows": int(len(panel)),
        "shop_count": int(panel["shop_id"].nunique()),
        "category_count": int(panel["category_id"].nunique()),
        "series_count": int(panel.groupby(KEYS).ngroups),
        "date_start": panel["date"].min().date().isoformat(),
        "date_end": panel["date"].max().date().isoformat(),
        "missing_dates_filled_as_zero": bool(args.fill_missing_dates_as_zero),
        "horizons_days": horizons,
        "rolling_folds": args.folds,
        "training_stride_days_by_horizon": {str(h): max(7, h) for h in horizons},
        "mase_definition": "horizon-scaled seasonal MASE using mean absolute lag-7 difference in each series history",
        "min_history_days": args.min_history,
        "candidate_models": [x.strip() for x in args.candidates.split(",") if x.strip()],
        "python": sys.version,
        "platform": platform.platform(),
        "random_seed": 42,
        "final_holdout_evaluated": False,
        "regime_selection": "selected_model_by_regime.csv; rolling-origin development CV only; requires >=2 origins and >=10 series forecasts",
        "two_stage_probability_calibration": "not_calibrated_in_v0.1.0; expected demand uses raw classifier probability",
        "prediction_intervals": "not_implemented_in_v0.1.0",
        "selection_rule": "development rolling-origin results only; no final test selection",
        "warnings": [
            "A daily panel does not identify stockout-censored demand unless stock availability is supplied.",
            "Development origins and training data are restricted to dates before development_end_exclusive.",
            "The 2025-10 to 2025-12 legacy test period is not evaluated by this development run.",
            "The dataset classification is recorded from the researcher's identification of the supplied Google Drive SME dataset.",
            "WAPE is undefined when the actual total is zero; such rows are retained with null WAPE."
        ]
    }
    manifest["figures"] = write_figures(summary, predictions, output)
    (output / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Rows={len(panel)} series={manifest['series_count']} shops={manifest['shop_count']} categories={manifest['category_count']}")
    print(f"Artifacts written to: {output.resolve()}")
    print("No final holdout was evaluated. Inspect failures and provenance before making thesis claims.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
