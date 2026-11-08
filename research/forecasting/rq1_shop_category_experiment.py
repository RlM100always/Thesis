"""Reproducible RQ1 direct-horizon experiment on the supplied daily shop-category panel."""
from __future__ import annotations
import argparse, hashlib, json, platform, sys, time
from pathlib import Path
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import mean_absolute_error, mean_squared_error
from catboost import CatBoostRegressor, CatBoostClassifier

HORIZONS = [1, 7, 14, 28]
ORIGINS = pd.to_datetime(["2025-07-01", "2025-08-01", "2025-09-01"])
LAGS, WINDOWS = [1, 7, 14, 28, 56], [7, 14, 28, 56]
KEYS = ["shop_id", "category"]

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()

def load_panel(path: Path):
    data = pd.read_csv(path, parse_dates=["date"])
    required = set(KEYS + ["date", "units_sold_observed", "is_zero_observed_sales"])
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if data[list(required)].isna().any().any():
        raise ValueError("Missing values in required panel fields")
    if data.duplicated(KEYS + ["date"]).any():
        raise ValueError("Duplicate shop-category-date keys")
    data["demand"] = pd.to_numeric(data["units_sold_observed"], errors="raise")
    if (data.demand < 0).any() or not np.isfinite(data.demand).all():
        raise ValueError("Demand must be finite and non-negative")
    zero_flag = data["is_zero_observed_sales"].astype(int).to_numpy()
    if not np.array_equal(zero_flag, (data.demand == 0).astype(int).to_numpy()):
        raise ValueError("Zero-sales indicator does not match observed quantity")
    start, end = data.date.min(), data.date.max()
    expected = pd.date_range(start, end, freq="D")
    series = {}
    for key, group in data.sort_values(KEYS + ["date"]).groupby(KEYS, sort=True):
        dates = pd.DatetimeIndex(group.date)
        if not dates.equals(expected):
            raise ValueError(f"Incomplete daily panel for {key}; do not impute dates blindly")
        series[key] = group.demand.to_numpy(dtype=float)
    return data.sort_values(KEYS + ["date"]).reset_index(drop=True), series, start, end

def make_features(y, date, shop, category):
    f = {f"lag_{k}": float(y[-k]) for k in LAGS}
    for window in WINDOWS:
        recent = y[-window:]
        f[f"mean_{window}"] = float(recent.mean())
        f[f"std_{window}"] = float(recent.std())
        f[f"sum_{window}"] = float(recent.sum())
        f[f"zero_{window}"] = float((recent == 0).mean())
    positive = y[y > 0]
    nonzero_idx = np.flatnonzero(y > 0)
    f["days_since_sale"] = float(len(y) - 1 - nonzero_idx[-1]) if len(positive) else float(len(y))
    f["adi"] = float(len(y) / len(positive)) if len(positive) else float(len(y) + 1)
    f["positive_mean"] = float(positive.mean()) if len(positive) else 0.0
    f["positive_cv2"] = float((positive.std() / positive.mean()) ** 2) if len(positive) and positive.mean() else 0.0
    f.update(
        shop_id=shop, category=category, dow=date.dayofweek, day=date.day,
        month=date.month, week=int(date.isocalendar().week),
        dow_sin=np.sin(2*np.pi*date.dayofweek/7), dow_cos=np.cos(2*np.pi*date.dayofweek/7),
        month_sin=np.sin(2*np.pi*(date.month-1)/12), month_cos=np.cos(2*np.pi*(date.month-1)/12)
    )
    return f

def croston_sba(y, alpha=0.1):
    nonzero = np.flatnonzero(y > 0)
    if not len(nonzero):
        return 0.0
    size, interval, gap = float(y[nonzero[0]]), float(nonzero[0] + 1), 1
    for i in range(nonzero[0] + 1, len(y)):
        if y[i] > 0:
            size = alpha*y[i] + (1-alpha)*size
            interval = alpha*gap + (1-alpha)*interval
            gap = 1
        else:
            gap += 1
    return max(0.0, (size / max(interval, 1e-9)) * (1-alpha/2))

def tsb(y, alpha=0.1, beta=0.1):
    nonzero = np.flatnonzero(y > 0)
    if not len(nonzero):
        return 0.0
    probability, size = 1.0/(nonzero[0]+1), float(y[nonzero[0]])
    for i in range(nonzero[0] + 1, len(y)):
        occurrence = 1.0 if y[i] > 0 else 0.0
        probability += beta * (occurrence - probability)
        if occurrence:
            size += alpha * (y[i] - size)
    return max(0.0, probability * size)

def seasonal_naive(y, origin, horizon):
    # Sum forecasts based on up to four most recent observations of each target weekday.
    forecasts = []
    for offset in range(horizon):
        values = []
        for back in range(7, 29, 7):
            index = len(y) - (back - offset)
            if 0 <= index < len(y):
                values.append(y[index])
        forecasts.append(float(np.mean(values)) if values else float(np.mean(y[-7:])))
    return float(sum(forecasts))

def metric_row(actual, forecast, mase_scale=None):
    actual = np.asarray(actual, dtype=float)
    forecast = np.maximum(0, np.asarray(forecast, dtype=float))
    denominator = np.abs(actual).sum()
    return {
        "n": int(len(actual)),
        "actual_total": float(actual.sum()),
        "forecast_total": float(forecast.sum()),
        "WAPE": float(np.abs(actual-forecast).sum()/denominator) if denominator else np.nan,
        "MAE": float(mean_absolute_error(actual, forecast)),
        "RMSE": float(np.sqrt(mean_squared_error(actual, forecast))),
        "Bias_units": float((forecast-actual).sum()),
        "Bias_pct": float((forecast-actual).sum()/denominator) if denominator else np.nan,
        "MASE_weekly_h": float(np.nanmean(np.abs(actual-forecast)/np.asarray(mase_scale, dtype=float))) if mase_scale is not None and np.isfinite(np.asarray(mase_scale, dtype=float)).any() else np.nan,
    }

def demand_regime(y):
    positive = y[y > 0]
    if not len(positive):
        return "No observed demand"
    adi = len(y) / len(positive)
    cv2 = (positive.std()/positive.mean())**2 if positive.mean() else np.inf
    if adi >= 1.32 and cv2 >= 0.49:
        return "Lumpy"
    if adi >= 1.32:
        return "Intermittent"
    if cv2 >= 0.49:
        return "Erratic"
    return "Smooth"

def cluster_bootstrap_h7(predictions, n_bootstrap=2000, seed=20261108):
    """Cluster-resample shop-category series; compare pooled 7-day WAPE differences."""
    frame = predictions[predictions.horizon == 7].copy()
    base = frame[frame.model == "LightGBM_Tweedie"]
    keys = sorted(set(zip(base.shop_id, base.category)))
    actual = np.stack([
        base[(base.shop_id == shop) & (base.category == category)]
        .sort_values("origin").actual.to_numpy(float)
        for shop, category in keys
    ])
    forecasts = {}
    for model_name in frame.model.unique():
        part = frame[frame.model == model_name]
        forecasts[model_name] = np.stack([
            part[(part.shop_id == shop) & (part.category == category)]
            .sort_values("origin").forecast.to_numpy(float)
            for shop, category in keys
        ])
    rng = np.random.default_rng(seed)
    rows = []
    challenger_order = ["CatBoost_Tweedie", "CatBoost_Hurdle_raw", "Seasonal_Naive_7", "Croston_SBA", "TSB"]
    for challenger in [name for name in challenger_order if name in forecasts]:
        differences = []
        for _ in range(n_bootstrap):
            sample = rng.integers(0, len(keys), size=len(keys))
            y = actual[sample]
            reference = forecasts["LightGBM_Tweedie"][sample]
            comparison = forecasts[challenger][sample]
            denominator = np.abs(y).sum()
            differences.append(
                np.abs(y-reference).sum()/denominator -
                np.abs(y-comparison).sum()/denominator
            )
        lower, median, upper = np.quantile(differences, [0.025, 0.5, 0.975])
        rows.append({
            "horizon": 7, "reference_model": "LightGBM_Tweedie",
            "challenger_model": challenger, "series_clusters": len(keys),
            "bootstrap_replicates": n_bootstrap, "median_wape_difference": median,
            "ci_2_5": lower, "ci_97_5": upper,
            "difference_definition": "WAPE(LightGBM) - WAPE(challenger)"
        })
    return pd.DataFrame(rows)


def validate_provenance_evidence(input_path: Path, evidence_status: str, evidence_path: Path | None = None):
    """Require auditable source documentation before labelling a run verified-observed."""
    allowed = {"verified_observed", "observed_unverified", "synthetic", "provenance_conflict"}
    if evidence_status not in allowed:
        raise ValueError(f"Unsupported evidence status: {evidence_status}")
    if evidence_status != "verified_observed":
        return None
    if evidence_path is None or not evidence_path.is_file():
        raise ValueError("verified_observed requires --provenance-evidence JSON from the source owner.")
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
    required = {
        "source_system", "source_owner", "collection_start", "collection_end",
        "collection_method", "consent_or_licence", "anonymisation_method",
        "data_dictionary", "synthetic_flag_explanation", "input_sha256"
    }
    missing = sorted(required - set(evidence))
    if missing:
        raise ValueError(f"Provenance evidence is incomplete; missing fields: {missing}")
    if evidence["input_sha256"].lower() != sha256(input_path).lower():
        raise ValueError("Provenance evidence input_sha256 does not match the supplied dataset.")
    empty = [key for key in required if not str(evidence[key]).strip()]
    if empty:
        raise ValueError(f"Provenance evidence contains empty fields: {sorted(empty)}")
    return {"evidence_sha256": sha256(evidence_path), "source_system": evidence["source_system"],
            "source_owner": evidence["source_owner"]}


def run(input_path: Path, output_path: Path, evidence_status="provenance_conflict", provenance_evidence: Path | None = None):
    provenance_record = validate_provenance_evidence(input_path, evidence_status, provenance_evidence)
    output_path.mkdir(parents=True, exist_ok=True)
    started = time.time()
    data, series, start, end = load_panel(input_path)
    predictions, origin_metrics = [], []

    for horizon in HORIZONS:
        for origin in ORIGINS:
            train_x, train_y, test_x, actual, meta, histories = [], [], [], [], [], []
            origin_index = (origin - start).days
            for (shop, category), values in series.items():
                # Every training target window ends before the forecast origin.
                for index in range(56, origin_index-horizon+1, 28):
                    feature_date = start + pd.Timedelta(days=index)
                    train_x.append(make_features(values[:index], feature_date, shop, category))
                    train_y.append(float(values[index:index+horizon].sum()))
                history = values[:origin_index]
                test_x.append(make_features(history, origin, shop, category))
                actual.append(float(values[origin_index:origin_index+horizon].sum()))
                meta.append((shop, category))
                histories.append(history)

            x_train, y_train = pd.DataFrame(train_x), np.asarray(train_y, dtype=float)
            x_test, y_test = pd.DataFrame(test_x), np.asarray(actual, dtype=float)
            categorical = ["shop_id", "category"]
            for column in categorical:
                x_train[column] = x_train[column].astype("category")
                x_test[column] = pd.Categorical(x_test[column], categories=x_train[column].cat.categories)

            model = lgb.LGBMRegressor(
                objective="tweedie", tweedie_variance_power=1.3,
                n_estimators=100, learning_rate=0.035, num_leaves=31,
                min_child_samples=80, subsample=0.85, subsample_freq=1, colsample_bytree=0.85,
                reg_lambda=2.0, random_state=42, n_jobs=4, verbosity=-1
            )
            fit_start = time.time()
            model.fit(x_train, y_train, categorical_feature=categorical)
            lgb_forecast = model.predict(x_test)

            cat_model = CatBoostRegressor(
                loss_function="Tweedie:variance_power=1.3", iterations=120,
                learning_rate=0.04, depth=6, l2_leaf_reg=5,
                random_seed=42, verbose=False, allow_writing_files=False, thread_count=4
            )
            cat_model.fit(x_train, y_train, cat_features=categorical)
            cat_forecast = cat_model.predict(x_test)

            occurrence = (y_train > 0).astype(int)
            if np.unique(occurrence).size == 2 and int(occurrence.sum()) >= 30:
                classifier = CatBoostClassifier(
                    iterations=100, depth=5, learning_rate=0.04,
                    loss_function="Logloss", random_seed=42, verbose=False,
                    allow_writing_files=False, thread_count=4,
                    auto_class_weights="Balanced"
                )
                classifier.fit(x_train, occurrence, cat_features=categorical)
                probability = classifier.predict_proba(x_test)[:, 1]
                positive = y_train > 0
                if int(positive.sum()) >= 30:
                    positive_regressor = CatBoostRegressor(
                        loss_function="RMSE", iterations=100, depth=5,
                        learning_rate=0.04, l2_leaf_reg=5, random_seed=42,
                        verbose=False, allow_writing_files=False, thread_count=4
                    )
                    positive_regressor.fit(x_train.loc[positive], y_train[positive],
                                           cat_features=categorical)
                    conditional_quantity = np.maximum(0.0, positive_regressor.predict(x_test))
                else:
                    conditional_quantity = np.full(len(x_test), float(y_train[positive].mean()))
                hurdle_forecast = probability * conditional_quantity
            else:
                hurdle_forecast = np.full(len(x_test), float(y_train.mean()))

            mase_scale = []
            for history in histories:
                weekly_scale = float(np.mean(np.abs(history[7:] - history[:-7]))) if len(history) > 7 else 0.0
                mase_scale.append(weekly_scale * horizon if np.isfinite(weekly_scale) and weekly_scale > 0 else np.nan)
            mase_scale = np.asarray(mase_scale, dtype=float)

            candidates = {
                "LightGBM_Tweedie": lgb_forecast,
                "CatBoost_Tweedie": cat_forecast,
                "CatBoost_Hurdle_raw": hurdle_forecast,
                "Seasonal_Naive_7": [seasonal_naive(y, origin, horizon) for y in histories],
                "Croston_SBA": [croston_sba(y)*horizon for y in histories],
                "TSB": [tsb(y)*horizon for y in histories],
            }
            elapsed = round(time.time()-fit_start, 2)
            for name, forecast in candidates.items():
                forecast = np.asarray(forecast, dtype=float)
                origin_metrics.append({
                    "horizon": horizon, "origin": str(origin.date()), "model": name,
                    "train_rows": len(x_train), "candidate_fit_block_seconds": elapsed,
                    **metric_row(y_test, forecast, mase_scale)
                })
                for i, (shop, category) in enumerate(meta):
                    predictions.append({
                        "horizon": horizon, "origin": str(origin.date()),
                        "shop_id": shop, "category": category, "model": name,
                        "actual": y_test[i], "forecast": max(0.0, float(forecast[i])),
                        "mase_scale_weekly_h": mase_scale[i]
                    })

    pred = pd.DataFrame(predictions)
    origin_frame = pd.DataFrame(origin_metrics)
    aggregate = []
    for (horizon, model), group in pred.groupby(["horizon", "model"]):
        aggregate.append({
            "horizon": horizon, "model": model,
            **metric_row(group.actual, group.forecast, group.mase_scale_weekly_h),
            "origins": int(group.origin.nunique())
        })
    aggregate_frame = pd.DataFrame(aggregate).sort_values(["horizon", "WAPE"])

    # Regimes are defined only from the history available before the first origin.
    cutoff = (pd.Timestamp("2025-07-01") - start).days
    regime_rows = []
    regime_map = {}
    for key, values in series.items():
        history = values[:cutoff]
        positive = history[history > 0]
        adi = len(history)/len(positive) if len(positive) else np.inf
        cv2 = (positive.std()/positive.mean())**2 if len(positive) and positive.mean() else np.inf
        label = demand_regime(history)
        regime_map[key] = label
        regime_rows.append({
            "shop_id": key[0], "category": key[1], "ADI": adi, "CV2": cv2,
            "zero_ratio": float((history == 0).mean()), "regime": label,
            "positive_days": int(len(positive))
        })
    pred["regime"] = [regime_map[(row.shop_id, row.category)] for row in pred.itertuples()]
    regime_metrics = []
    seven_day = pred[pred.horizon == 7]
    for (model_name, regime), group in seven_day.groupby(["model", "regime"]):
        regime_metrics.append({"model": model_name, "regime": regime, **metric_row(group.actual, group.forecast, group.mase_scale_weekly_h)})

    regime_frame = pd.DataFrame(regime_rows)
    bootstrap = cluster_bootstrap_h7(pred)
    bootstrap.to_csv(output_path/"cluster_bootstrap_h7.csv", index=False)
    regime_summary = regime_frame.groupby("regime").agg(
        series=("shop_id", "size"), mean_zero_ratio=("zero_ratio", "mean"),
        median_ADI=("ADI", "median"), median_CV2=("CV2", "median")
    ).reset_index()
    pred.to_csv(output_path/"predictions.csv", index=False)
    origin_frame.to_csv(output_path/"origin_metrics.csv", index=False)
    aggregate_frame.to_csv(output_path/"aggregate_metrics.csv", index=False)
    pd.DataFrame(regime_metrics).to_csv(output_path/"regime_metrics_h7.csv", index=False)
    regime_summary.to_csv(output_path/"regime_distribution.csv", index=False)

    manifest = {
        "pipeline": "rq1_shop_category_direct_horizon_v1",
        "input_file": input_path.name, "input_sha256": sha256(input_path),
        "rows": int(len(data)), "shops": int(data.shop_id.nunique()),
        "categories": int(data.category.nunique()), "series": int(len(series)),
        "date_start": str(start.date()), "date_end": str(end.date()),
        "observed_units": int(data.units_sold_observed.sum()),
        "zero_sales_ratio": float((data.units_sold_observed == 0).mean()),
        "origins": [str(x.date()) for x in ORIGINS], "horizons": HORIZONS,
        "training_origin_stride_days": 28, "feature_history_days": 56,
        "models": ["LightGBM Tweedie", "CatBoost Tweedie", "CatBoost hurdle (raw uncalibrated probability)", "weekly seasonal naive", "Croston SBA", "TSB"],
        "evidence_status": evidence_status,
        "provenance_evidence": provenance_record,
        "source_provenance_note": "Drive manifest claims real, while 2 November GitHub onboarding record classifies same-seed/same-count package as synthetic; current accessible SKU sheet does not expose the previously reported synthetic_flag.",
        "mase_definition": "Mean absolute error divided by per-series mean absolute lag-7 difference, multiplied by forecast horizon; labelled horizon-scaled weekly MASE.",
        "cluster_bootstrap": {"horizon": 7, "replicates": 2000, "cluster": "shop-category series", "seed": 20261108},
        "lightgbm_parameters": {
            "objective": "tweedie", "tweedie_variance_power": 1.3,
            "n_estimators": 100, "learning_rate": 0.035, "num_leaves": 31,
            "min_child_samples": 80, "subsample": 0.85, "colsample_bytree": 0.85,
            "reg_lambda": 2.0, "random_state": 42, "n_jobs": 4
        },
        "python": sys.version, "platform": platform.platform(),
        "pandas": pd.__version__, "numpy": np.__version__, "lightgbm": lgb.__version__,
        "catboost": __import__("catboost").__version__,
        "sklearn": __import__("sklearn").__version__,
        "final_holdout_evaluated": False, "fourth_quarter_2025_used_for_selection": False,
        "catboost_parameters": {"loss_function": "Tweedie:variance_power=1.3", "iterations": 120, "learning_rate": 0.04, "depth": 6, "l2_leaf_reg": 5, "random_seed": 42},
        "hurdle_parameters": {"classifier_iterations": 100, "regressor_iterations": 100, "depth": 5, "learning_rate": 0.04, "classifier_auto_class_weights": "Balanced", "probability_calibrated": False},
        "elapsed_seconds": round(time.time()-started, 2)
    }
    (output_path/"run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(aggregate_frame.to_string(index=False))
    return manifest

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--evidence-status", default="provenance_conflict", choices=["verified_observed", "observed_unverified", "synthetic", "provenance_conflict"])
    parser.add_argument("--provenance-evidence", type=Path, help="Source-owner JSON required when evidence-status=verified_observed; must contain the source, consent, anonymisation and matching input SHA-256 fields.")
    args = parser.parse_args()
    run(args.input, args.output, evidence_status=args.evidence_status, provenance_evidence=args.provenance_evidence)
