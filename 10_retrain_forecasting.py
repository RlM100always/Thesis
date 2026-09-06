"""Leakage-safe rolling-origin selection for monthly sales forecasting.

The final six months are never used for model selection. Candidate models are
ranked by mean WAPE across expanding-window validation folds inside the first
42 months, after which the selected specification is refit once and evaluated
on the untouched holdout.
"""

from __future__ import annotations

import json
import math
import os
import time
import warnings
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA
from statsmodels.tsa.holtwinters import ExponentialSmoothing, Holt

warnings.filterwarnings("ignore")

SEED = 20260906
TEST_MONTHS = 6
OUT = Path("output")
FIG = OUT / "figures"
FIG.mkdir(parents=True, exist_ok=True)


def metrics(actual: np.ndarray, pred: np.ndarray) -> dict[str, float]:
    actual = np.asarray(actual, dtype=float)
    pred = np.asarray(pred, dtype=float)
    err = actual - pred
    return {
        "rmse": float(np.sqrt(np.mean(err**2))),
        "mae": float(np.mean(np.abs(err))),
        "mape": float(np.mean(np.abs(err) / np.maximum(np.abs(actual), 1e-9)) * 100),
        "wape": float(np.sum(np.abs(err)) / np.maximum(np.sum(np.abs(actual)), 1e-9) * 100),
    }


def forecast(name: str, train: np.ndarray, horizon: int) -> np.ndarray:
    train = np.asarray(train, dtype=float)
    if name == "seasonal_naive":
        return np.resize(train[-12:], horizon)
    if name == "seasonal_naive_bias":
        base = np.resize(train[-12:], horizon)
        if len(train) >= 24:
            bias = float(np.mean(train[-12:] - train[-24:-12]))
            return base + bias
        return base
    if name == "seasonal_naive_ratio":
        base = np.resize(train[-12:], horizon)
        if len(train) >= 24 and np.mean(train[-24:-12]) != 0:
            return base * float(np.mean(train[-12:]) / np.mean(train[-24:-12]))
        return base
    if name == "drift":
        slope = (train[-1] - train[0]) / max(len(train) - 1, 1)
        return train[-1] + slope * np.arange(1, horizon + 1)
    if name == "mean_12":
        return np.repeat(np.mean(train[-12:]), horizon)
    if name == "holt":
        return np.asarray(Holt(train, damped_trend=False).fit(optimized=True).forecast(horizon))
    if name == "holt_damped":
        return np.asarray(Holt(train, damped_trend=True).fit(optimized=True).forecast(horizon))
    if name == "ets_add":
        return np.asarray(ExponentialSmoothing(train, trend="add", seasonal="add", seasonal_periods=12,
                                                initialization_method="estimated").fit(optimized=True).forecast(horizon))
    if name == "ets_add_damped":
        return np.asarray(ExponentialSmoothing(train, trend="add", damped_trend=True, seasonal="add",
                                                seasonal_periods=12, initialization_method="estimated")
                          .fit(optimized=True).forecast(horizon))
    if name.startswith("arima_"):
        order = tuple(int(x) for x in name.split("_")[1])
        return np.asarray(ARIMA(train, order=order).fit().forecast(horizon))
    raise ValueError(name)


def main() -> None:
    started = time.perf_counter()
    df = pd.read_csv(OUT / "processed_dataset.csv")
    df["Transaction_Date"] = pd.to_datetime(df["Transaction_Date"])
    monthly = (df.assign(Year_Month=df["Transaction_Date"].dt.to_period("M"))
                 .groupby("Year_Month", as_index=False)["Net_Amount_BDT"].sum()
                 .sort_values("Year_Month"))
    labels = monthly["Year_Month"].astype(str).to_numpy()
    series = monthly["Net_Amount_BDT"].to_numpy(dtype=float)
    development, holdout = series[:-TEST_MONTHS], series[-TEST_MONTHS:]

    candidates = [
        "seasonal_naive", "seasonal_naive_bias", "seasonal_naive_ratio",
        "drift", "mean_12", "holt", "holt_damped", "ets_add",
        "ets_add_damped", "arima_110", "arima_111", "arima_210",
        "arima_211", "arima_212",
    ]
    # Each cutoff forecasts the next six months; all folds are inside development.
    cutoffs = [24, 30, 36]
    cv: dict[str, dict] = {}
    for name in candidates:
        folds = []
        for cutoff in cutoffs:
            actual = development[cutoff:cutoff + TEST_MONTHS]
            try:
                pred = forecast(name, development[:cutoff], len(actual))
                if len(pred) != len(actual) or not np.all(np.isfinite(pred)):
                    raise ValueError("non-finite or wrong-length prediction")
                folds.append(metrics(actual, pred))
            except Exception as exc:
                folds.append({"error": str(exc), "wape": math.inf})
        valid = [f for f in folds if math.isfinite(float(f.get("wape", math.inf)))]
        cv[name] = {
            "folds": folds,
            "mean_wape": float(np.mean([f["wape"] for f in valid])) if len(valid) == len(folds) else math.inf,
            "mean_mape": float(np.mean([f["mape"] for f in valid])) if len(valid) == len(folds) else math.inf,
        }
        print(f"{name:24s} rolling CV WAPE: {cv[name]['mean_wape']:.3f}%")

    selected = min(candidates, key=lambda n: cv[n]["mean_wape"])
    holdout_predictions: dict[str, list[float]] = {}
    holdout_metrics: dict[str, dict[str, float]] = {}
    for name in candidates:
        try:
            pred = forecast(name, development, TEST_MONTHS)
            holdout_predictions[name] = [float(x) for x in pred]
            holdout_metrics[name] = metrics(holdout, pred)
        except Exception as exc:
            holdout_metrics[name] = {"error": str(exc)}

    selected_metrics = holdout_metrics[selected]
    baseline_metrics = holdout_metrics["seasonal_naive"]
    result = {
        "protocol": {
            "random_seed": SEED,
            "n_months": len(series),
            "development_months": len(development),
            "untouched_holdout_months": TEST_MONTHS,
            "rolling_origin_cutoffs": cutoffs,
            "selection_metric": "mean rolling-origin WAPE",
            "holdout_used_for_selection": False,
        },
        "selected_model": selected,
        "rolling_cv": cv,
        "holdout": {
            "months": labels[-TEST_MONTHS:].tolist(),
            "actual": [float(x) for x in holdout],
            "predictions": holdout_predictions,
            "metrics": holdout_metrics,
            "selected_metrics": selected_metrics,
            "seasonal_naive_metrics": baseline_metrics,
        },
        "elapsed_seconds": float(time.perf_counter() - started),
    }
    (OUT / "retrained_forecast_results.json").write_text(json.dumps(result, indent=2), encoding="utf-8")

    ranked = sorted(candidates, key=lambda n: cv[n]["mean_wape"])
    fig, ax = plt.subplots(figsize=(10, 5.5))
    names = ranked
    values = [cv[n]["mean_wape"] for n in names]
    colors = ["#0A8754" if n == selected else "#8093A1" for n in names]
    ax.barh(names[::-1], values[::-1], color=colors[::-1])
    ax.set_xlabel("Mean rolling-origin WAPE (%) - lower is better")
    ax.set_title("Forecast Model Selection on Development Period Only")
    ax.grid(axis="x", alpha=.25)
    fig.tight_layout()
    fig.savefig(FIG / "retrained_forecast_comparison.png", dpi=180)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 5.5))
    x = np.arange(TEST_MONTHS)
    ax.plot(x, holdout / 1e6, marker="o", linewidth=2.4, label="Actual")
    ax.plot(x, np.array(holdout_predictions[selected]) / 1e6, marker="s", linewidth=2,
            label=f"Selected: {selected.replace('_', ' ')}")
    if selected != "seasonal_naive":
        ax.plot(x, np.array(holdout_predictions["seasonal_naive"]) / 1e6, marker="^",
                linestyle="--", label="Seasonal naive")
    ax.set_xticks(x, labels[-TEST_MONTHS:], rotation=30)
    ax.set_ylabel("Monthly net sales (BDT million)")
    ax.set_title("Untouched Six-Month Forecast Holdout")
    ax.grid(alpha=.25)
    ax.legend()
    fig.tight_layout()
    fig.savefig(FIG / "retrained_forecast_holdout.png", dpi=180)
    plt.close(fig)

    print(f"\nSelected from development CV: {selected}")
    print(json.dumps(selected_metrics, indent=2))
    print("Saved output/retrained_forecast_results.json")


if __name__ == "__main__":
    os.environ.setdefault("PYTHONHASHSEED", str(SEED))
    main()
