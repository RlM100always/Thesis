"""Frozen-tail RQ1 evaluation with point-in-time features.

The model is fitted once using observations through 30 September 2025 and
then evaluated on weekly seven-day origins in October--December 2025. The
tail was previously inspected during the project, so the manifest calls it a
pre-inspected tail evaluation rather than an untouched final holdout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
from pathlib import Path

import lightgbm as lgb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from context_aware_experiment import MODEL_PARAMS, FeatureStore, read_panel


def demand_regime(values: np.ndarray) -> str:
    """Classify a series using only the history available at training cutoff."""
    positive = values[values > 0]
    if not len(positive):
        return "no_observed_demand"
    adi = len(values) / len(positive)
    cv2 = (positive.std() / positive.mean()) ** 2 if positive.mean() else np.inf
    if adi >= 1.32 and cv2 >= 0.49:
        return "lumpy"
    if adi >= 1.32:
        return "intermittent"
    if cv2 >= 0.49:
        return "erratic"
    return "smooth"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def metric(actual: np.ndarray, forecast: np.ndarray) -> dict[str, float | int]:
    actual = np.asarray(actual, dtype=float)
    forecast = np.maximum(np.asarray(forecast, dtype=float), 0.0)
    denominator = float(np.abs(actual).sum())
    error = forecast - actual
    return {
        "n": int(len(actual)),
        "actual_total": float(actual.sum()),
        "forecast_total": float(forecast.sum()),
        "WAPE": float(np.abs(error).sum() / denominator) if denominator else float("nan"),
        "MAE": float(np.abs(error).mean()),
        "RMSE": float(np.sqrt(np.square(error).mean())),
        "bias_units": float(error.sum()),
        "bias_pct": float(error.sum() / denominator) if denominator else float("nan"),
    }


def fit_model(store: FeatureStore, train_origin_index: int, horizon: int, context: bool):
    x_train, y_train, _, _ = store.build_fold(train_origin_index, horizon, context)
    categorical = ["shop_id", "category"]
    for column in categorical:
        x_train[column] = x_train[column].astype("category")
    model = lgb.LGBMRegressor(**MODEL_PARAMS)
    model.fit(x_train, y_train, categorical_feature=categorical)
    return model, x_train, y_train


def run(input_path: Path, output_path: Path, figures_path: Path) -> None:
    output_path.mkdir(parents=True, exist_ok=True)
    figures_path.mkdir(parents=True, exist_ok=True)
    frame, pivot, dates, shops, categories = read_panel(input_path)
    store = FeatureStore(pivot, shops, categories)
    store.dates = dates

    horizon = 7
    train_cutoff = pd.Timestamp("2025-09-30")
    train_origin = train_cutoff + pd.Timedelta(days=1)
    train_origin_index = int((train_origin - dates[0]).days)
    holdout_origins = pd.date_range("2025-10-01", "2025-12-24", freq="7D")

    regime_map = {
        key: demand_regime(values[:train_origin_index])
        for key, values in zip(store.keys, store.y)
    }
    predictions: list[dict] = []
    origin_rows: list[dict] = []
    regime_rows: list[dict] = []
    aggregate_rows: list[dict] = []

    for model_name, context in (("LightGBM_base", False), ("LightGBM_context", True)):
        model, x_train, _ = fit_model(store, train_origin_index, horizon, context)
        for origin in holdout_origins:
            origin_index = int((origin - dates[0]).days)
            x_test = store.snapshot(origin_index, context)
            for column in ["shop_id", "category"]:
                x_test[column] = pd.Categorical(
                    x_test[column], categories=x_train[column].cat.categories
                )
            actual = store.y[:, origin_index : origin_index + horizon].sum(axis=1)
            forecast = np.maximum(model.predict(x_test), 0.0)
            for index, key in enumerate(store.keys):
                predictions.append({
                    "model": model_name,
                    "origin": origin.date().isoformat(),
                    "shop_id": key[0],
                    "category": key[1],
                    "regime": regime_map[key],
                    "actual": float(actual[index]),
                    "forecast": float(forecast[index]),
                })
            origin_rows.append({
                "model": model_name,
                "origin": origin.date().isoformat(),
                **metric(actual, forecast),
            })

    prediction_frame = pd.DataFrame(predictions)
    origin_frame = pd.DataFrame(origin_rows)
    for (model_name, regime), group in prediction_frame.groupby(["model", "regime"]):
        regime_rows.append({
            "model": model_name,
            "regime": regime,
            **metric(group["actual"].to_numpy(), group["forecast"].to_numpy()),
        })
    for model_name, group in prediction_frame.groupby("model"):
        aggregate_rows.append({
            "model": model_name,
            **metric(group["actual"].to_numpy(), group["forecast"].to_numpy()),
            "origins": int(group["origin"].nunique()),
            "series": int(group[["shop_id", "category"]].drop_duplicates().shape[0]),
        })

    aggregate_frame = pd.DataFrame(aggregate_rows)
    origin_frame.to_csv(output_path / "origin_metrics.csv", index=False)
    aggregate_frame.to_csv(output_path / "aggregate_metrics.csv", index=False)
    pd.DataFrame(regime_rows).to_csv(output_path / "regime_metrics.csv", index=False)
    # Keep detailed predictions local for auditability; the committed result
    # files remain aggregate-only and contain no customer or transaction data.
    prediction_frame.to_csv(output_path / "predictions.csv", index=False)

    context = prediction_frame[prediction_frame["model"].eq("LightGBM_context")]
    by_origin = context.groupby("origin", as_index=False).agg(
        actual=("actual", "sum"), forecast=("forecast", "sum")
    )
    x = np.arange(len(by_origin))
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.plot(x, by_origin["actual"], marker="o", linewidth=3, color="#111827", label="Actual next-7-day demand")
    ax.plot(x, by_origin["forecast"], marker="o", linewidth=2.5, color="#2563eb", label="Frozen context forecast")
    context_metric = aggregate_frame[aggregate_frame["model"].eq("LightGBM_context")].iloc[0]
    ax.set_title("RQ1 frozen-tail check: actual demand versus context forecast")
    ax.set_ylabel("Units across 512 series")
    ax.set_xlabel("Holdout forecast origin")
    ax.set_xticks(x, by_origin["origin"], rotation=30, ha="right")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    ax.text(0.99, 0.97, f"WAPE: {context_metric['WAPE'] * 100:.2f}% | bias: {context_metric['bias_pct'] * 100:+.2f}%",
            transform=ax.transAxes, ha="right", va="top", color="#1d4ed8", fontsize=10)
    fig.tight_layout()
    fig.savefig(figures_path / "rq1_final_holdout_actual_vs_predicted.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    regime_plot = pd.DataFrame(regime_rows)
    regimes = [x for x in ["erratic", "lumpy", "smooth", "intermittent"] if x in set(regime_plot.regime)]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    xpos = np.arange(len(regimes))
    width = 0.36
    for offset, model_name, color in [(-width / 2, "LightGBM_base", "#64748b"), (width / 2, "LightGBM_context", "#2563eb")]:
        part = regime_plot[regime_plot.model.eq(model_name)].set_index("regime").reindex(regimes)
        bars = ax.bar(xpos + offset, part["WAPE"] * 100, width=width, label=model_name.replace("LightGBM_", ""), color=color)
        for bar, value in zip(bars, part["WAPE"] * 100):
            ax.text(bar.get_x() + bar.get_width() / 2, value + 1, f"{value:.1f}%", ha="center", fontsize=8)
    ax.set_title("RQ1 frozen-tail error by demand regime")
    ax.set_ylabel("WAPE (%)")
    ax.set_xticks(xpos, [name.title() for name in regimes])
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(figures_path / "rq1_final_holdout_regime_wape.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    manifest = {
        "pipeline": "rq1_frozen_tail_context_holdout_v1",
        "input_file": input_path.name,
        "input_sha256": sha256(input_path),
        "model_frozen_training_cutoff": train_cutoff.date().isoformat(),
        "holdout_start": holdout_origins.min().date().isoformat(),
        "holdout_end": (holdout_origins.max() + pd.Timedelta(days=horizon - 1)).date().isoformat(),
        "holdout_origins": [x.date().isoformat() for x in holdout_origins],
        "horizon_days": horizon,
        "feature_policy": "all own-series and cross-series features use observations strictly before each forecast origin",
        "holdout_status": "pre_inspected_tail_not_untouched",
        "why_not_untouched": "The project previously inspected Q4 2025; this evaluation is retained as a frozen-tail stress check, not an untouched final claim.",
        "models": ["LightGBM_base", "LightGBM_context"],
        "regime_definition_cutoff": train_cutoff.date().isoformat(),
        "raw_business_data_committed": False,
        "python": sys.version,
        "platform": platform.platform(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "lightgbm": lgb.__version__,
    }
    (output_path / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(aggregate_frame.to_string(index=False))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--figures-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.input, args.output, args.figures_dir)


if __name__ == "__main__":
    main()
