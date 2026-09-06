"""Comparable daily demand benchmark for two real sources plus a synthetic control.

Both sources are reduced to the same observed target: total quantity per day.
Models are selected only by expanding-window cross-validation in the training
period, then evaluated once on the final 15% chronological holdout. Test lags
use quantities already observed before each forecast date, so this is a
rolling one-day-ahead operational forecast, not a multi-step oracle forecast.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from xgboost import XGBRegressor

from ml.external_datasets import load_bd_retailer_demand

SEED = 20260906
OUT = Path("artifacts/real_public")
FIG = Path("output/figures")
MODELS = Path("output/models")
for path in (OUT, FIG, MODELS):
    path.mkdir(parents=True, exist_ok=True)


def daily_features(sales: pd.DataFrame) -> pd.DataFrame:
    series = sales.assign(date=sales.sold_at.dt.tz_localize(None).dt.floor("D")).groupby("date").quantity.sum()
    series = series.reindex(pd.date_range(series.index.min(), series.index.max(), freq="D"), fill_value=0.0)
    frame = pd.DataFrame({"date": series.index, "quantity": series.to_numpy(dtype=float)})
    for lag in (1, 2, 3, 7, 14, 28):
        frame[f"lag_{lag}"] = frame.quantity.shift(lag)
    for window in (7, 14, 28):
        frame[f"mean_{window}"] = frame.quantity.shift(1).rolling(window).mean()
        frame[f"std_{window}"] = frame.quantity.shift(1).rolling(window).std()
    frame["dow_sin"] = np.sin(2 * np.pi * frame.date.dt.dayofweek / 7)
    frame["dow_cos"] = np.cos(2 * np.pi * frame.date.dt.dayofweek / 7)
    frame["month_sin"] = np.sin(2 * np.pi * frame.date.dt.month / 12)
    frame["month_cos"] = np.cos(2 * np.pi * frame.date.dt.month / 12)
    frame["trend"] = np.arange(len(frame))
    return frame.dropna().reset_index(drop=True)


def load_uci_quantity_only() -> pd.DataFrame:
    """Memory-safe UCI adapter for the aggregate-demand task.

    The full canonical adapter intentionally retains customer/SKU fields for
    future-repeat and SKU experiments. This benchmark needs only date and
    quantity, so materialising IDs and descriptions wastes hundreds of MB.
    """
    raw = pd.read_csv(
        "data/real_public/online_retail_II.csv",
        usecols=["Invoice", "InvoiceDate", "Quantity", "Price"],
        dtype={"Invoice": "string", "Quantity": "int32", "Price": "float32"},
        parse_dates=["InvoiceDate"],
    )
    valid = (~raw.Invoice.str.startswith("C", na=False)) & (raw.Quantity > 0) & (raw.Price >= 0)
    raw = raw.loc[valid, ["InvoiceDate", "Quantity"]]
    return pd.DataFrame({
        "sold_at": pd.to_datetime(raw.InvoiceDate, utc=True),
        "quantity": raw.Quantity.astype(float),
    })


def metrics(y: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    pred = np.maximum(0.0, np.asarray(pred, dtype=float))
    y = np.asarray(y, dtype=float)
    ae = np.abs(y - pred)
    nonzero = np.abs(y) > 1e-9
    return {
        "wape": float(ae.sum() / max(np.abs(y).sum(), 1e-9)),
        "mae": float(mean_absolute_error(y, pred)),
        "rmse": float(mean_squared_error(y, pred) ** 0.5),
        "mape_nonzero": float(np.mean(ae[nonzero] / np.abs(y[nonzero]))) if nonzero.any() else float("nan"),
        "r2": float(r2_score(y, pred)),
    }


def candidates() -> dict:
    return {
        "hist_gbr": HistGradientBoostingRegressor(max_iter=350, learning_rate=.045, max_leaf_nodes=15,
                                                    l2_regularization=2.0, random_state=SEED),
        "hist_gbr_l1": HistGradientBoostingRegressor(loss="absolute_error", max_iter=350,
                                                       learning_rate=.045, max_leaf_nodes=15,
                                                       l2_regularization=2.0, random_state=SEED),
        "extra_trees": ExtraTreesRegressor(n_estimators=500, min_samples_leaf=3, max_features=.8,
                                             n_jobs=1, random_state=SEED),
        "extra_trees_l1": ExtraTreesRegressor(n_estimators=400, criterion="absolute_error",
                                                min_samples_leaf=3, max_features=.8, n_jobs=1,
                                                random_state=SEED),
        "random_forest": RandomForestRegressor(n_estimators=400, min_samples_leaf=3, max_features=.8,
                                                 n_jobs=1, random_state=SEED),
        "random_forest_l1": RandomForestRegressor(n_estimators=350, criterion="absolute_error",
                                                    min_samples_leaf=3, max_features=.8, n_jobs=1,
                                                    random_state=SEED),
        "xgboost": XGBRegressor(n_estimators=500, learning_rate=.025, max_depth=3, min_child_weight=5,
                                 subsample=.85, colsample_bytree=.85, reg_lambda=4.0,
                                 objective="reg:squarederror", n_jobs=1, random_state=SEED),
        "xgboost_l1": XGBRegressor(n_estimators=500, learning_rate=.025, max_depth=3, min_child_weight=5,
                                    subsample=.85, colsample_bytree=.85, reg_lambda=4.0,
                                    objective="reg:absoluteerror", n_jobs=1, random_state=SEED),
    }


def run_dataset(name: str, sales: pd.DataFrame) -> dict:
    data = daily_features(sales)
    feature_cols = [c for c in data.columns if c not in {"date", "quantity"}]
    holdout_start = int(len(data) * .85)
    development, holdout = data.iloc[:holdout_start], data.iloc[holdout_start:]
    splitter = TimeSeriesSplit(n_splits=4)
    cv_results: dict[str, dict] = {}

    # Operational baselines are also ranked by the same development folds.
    baseline_cols = {"naive_1": "lag_1", "seasonal_naive_7": "lag_7", "rolling_mean_7": "mean_7"}
    for model_name, col in baseline_cols.items():
        scores = []
        for _, val_idx in splitter.split(development):
            val = development.iloc[val_idx]
            scores.append(metrics(val.quantity.to_numpy(), val[col].to_numpy())["wape"])
        cv_results[model_name] = {"mean_cv_wape": float(np.mean(scores)), "fold_wape": scores}

    model_defs = candidates()
    for model_name, model in model_defs.items():
        scores = []
        for train_idx, val_idx in splitter.split(development):
            train, val = development.iloc[train_idx], development.iloc[val_idx]
            model.fit(train[feature_cols], train.quantity)
            scores.append(metrics(val.quantity.to_numpy(), model.predict(val[feature_cols]))["wape"])
        cv_results[model_name] = {"mean_cv_wape": float(np.mean(scores)), "fold_wape": scores}
        print(f"{name:22s} {model_name:18s} CV WAPE {np.mean(scores)*100:6.2f}%")

    selected = min(cv_results, key=lambda key: cv_results[key]["mean_cv_wape"])
    holdout_results: dict[str, dict] = {}
    predictions: dict[str, list[float]] = {}
    for model_name, col in baseline_cols.items():
        pred = holdout[col].to_numpy()
        predictions[model_name] = pred.tolist()
        holdout_results[model_name] = metrics(holdout.quantity.to_numpy(), pred)
    for model_name, model in model_defs.items():
        model.fit(development[feature_cols], development.quantity)
        pred = np.maximum(0.0, model.predict(holdout[feature_cols]))
        predictions[model_name] = pred.tolist()
        holdout_results[model_name] = metrics(holdout.quantity.to_numpy(), pred)
        joblib.dump({"pipeline": model, "features": feature_cols, "trained_until": str(development.date.max())},
                    MODELS / f"real_daily_{name}_{model_name}.joblib")

    selected_metrics = holdout_results[selected]
    best_observed = min(holdout_results, key=lambda key: holdout_results[key]["wape"])
    result = {
        "target": "aggregate observed daily quantity",
        "forecast_mode": "rolling one-day-ahead; all lags precede forecast date",
        "rows_source": int(len(sales)),
        "daily_observations_after_lags": int(len(data)),
        "development_days": int(len(development)),
        "holdout_days": int(len(holdout)),
        "development_from": str(development.date.min().date()),
        "development_to": str(development.date.max().date()),
        "holdout_from": str(holdout.date.min().date()),
        "holdout_to": str(holdout.date.max().date()),
        "selection": "lowest mean WAPE in four-fold expanding-window CV",
        "selected_model": selected,
        "selected_holdout_metrics": selected_metrics,
        "best_holdout_model_diagnostic_only": best_observed,
        "cv": cv_results,
        "holdout_metrics_all": holdout_results,
    }

    fig, ax = plt.subplots(figsize=(10.5, 5.3))
    view = holdout.tail(min(120, len(holdout)))
    offset = len(holdout) - len(view)
    ax.plot(view.date, view.quantity, label="Actual", color="#152536", linewidth=1.8)
    ax.plot(view.date, np.asarray(predictions[selected])[offset:], label=f"Selected: {selected}",
            color="#0A8754", linewidth=1.6)
    ax.set_title(f"Real-data daily demand holdout - {name.replace('_', ' ').title()}")
    ax.set_ylabel("Quantity per day")
    ax.grid(alpha=.25)
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(FIG / f"real_daily_{name}_holdout.png", dpi=180)
    plt.close(fig)
    return result


def main() -> None:
    started = time.perf_counter()
    synthetic_raw = pd.read_csv(
        "BD_Business_Analytics_Dataset.csv", usecols=["Transaction_Date", "Quantity"],
    )
    synthetic = pd.DataFrame({
        "sold_at": pd.to_datetime(synthetic_raw.Transaction_Date, utc=True),
        "quantity": pd.to_numeric(synthetic_raw.Quantity, errors="coerce"),
    }).dropna()
    sources = {
        "uci_online_retail_ii": load_uci_quantity_only(),
        "bangladesh_retailer_demand": load_bd_retailer_demand(),
        "synthetic_bsmart_control": synthetic,
    }
    report = {
        "protocol": {
            "seed": SEED,
            "real_data_only": False,
            "evidence_labels": {
                "uci_online_retail_ii": "real UK transactions",
                "bangladesh_retailer_demand": "real Bangladesh one-product demand",
                "synthetic_bsmart_control": "generated comparison only",
            },
            "canonical_target_same_across_datasets": True,
            "untouched_final_holdout_fraction": .15,
            "holdout_used_for_selection": False,
        },
        "datasets": {name: run_dataset(name, sales) for name, sales in sources.items()},
        "elapsed_seconds": float(time.perf_counter() - started),
    }
    labels = ["UCI Online\nRetail II", "Bangladesh\nretailer", "Generated\nB-SMART"]
    values = [
        report["datasets"][name]["selected_holdout_metrics"]["wape"] * 100
        for name in sources
    ]
    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    bars = ax.bar(labels, values, color=["#22577A", "#0A8754", "#9C6644"])
    ax.set_ylabel("Holdout WAPE (%) — lower is better")
    ax.set_title("Comparable Daily-Quantity Benchmark")
    ax.set_ylim(0, max(values) * 1.25)
    ax.grid(axis="y", alpha=.25)
    for bar, value in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, value + .5, f"{value:.2f}%",
                ha="center", va="bottom", fontweight="bold")
    fig.tight_layout()
    fig.savefig(FIG / "comparable_daily_wape.png", dpi=180)
    plt.close(fig)
    (OUT / "comparable_demand_benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    for name, result in report["datasets"].items():
        m = result["selected_holdout_metrics"]
        print(f"{name}: selected={result['selected_model']}, holdout WAPE={m['wape']*100:.2f}%, R2={m['r2']:.3f}")
    print("Saved artifacts/real_public/comparable_demand_benchmark.json")


if __name__ == "__main__":
    main()
