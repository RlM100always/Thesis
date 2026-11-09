"""Multi-date validation for forecasting, customer inactivity, and policy impact.

This runner creates date-level, aggregate-only evidence for the report:

* RQ1: six rolling seven-day demand cutoffs with actual versus predicted
  network demand for a HistGradientBoosting model and two simple baselines.
* RQ2: six chronological customer snapshot dates, fitting only earlier
  snapshots and comparing predicted inactivity rate with the observed rate.
* RQ3: eight historical 30-day replenishment backtests using observed sales,
  reconstructed stock, explicit policy formulas, and an assumption-based
  cost function.

Raw files remain outside the repository. The RQ3 cost function is a declared
decision-analysis assumption, not an observed accounting profit measure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier, HistGradientBoostingRegressor
from sklearn.metrics import average_precision_score, brier_score_loss, f1_score, mean_absolute_error, mean_squared_error, roc_auc_score

SEED = 20261109
RAW_DATE_START = pd.Timestamp("2023-01-01")
FORECAST_HORIZON = 7
IMPACT_HORIZON = 30


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def savefig(fig: plt.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=220, bbox_inches="tight")
    plt.close(fig)


def rq1_features(values: np.ndarray, series_idx: np.ndarray, origin_idx: np.ndarray, dates: pd.DatetimeIndex) -> np.ndarray:
    cols = []
    for lag in (1, 7, 14, 28):
        cols.append(values[series_idx, origin_idx - lag])
    last7 = np.stack([values[series_idx, origin_idx - lag] for lag in range(1, 8)], axis=1)
    last28 = np.stack([values[series_idx, origin_idx - lag] for lag in range(1, 29)], axis=1)
    cols.append(last7.mean(axis=1))
    cols.append(last28.mean(axis=1))
    cols.append(last28.std(axis=1))
    series_mean = values[series_idx].mean(axis=1)
    cols.append(series_mean)
    day = dates.take(origin_idx).dayofweek.to_numpy()
    month = dates.take(origin_idx).month.to_numpy()
    cols.extend([
        np.sin(2 * np.pi * day / 7),
        np.cos(2 * np.pi * day / 7),
        np.sin(2 * np.pi * (month - 1) / 12),
        np.cos(2 * np.pi * (month - 1) / 12),
    ])
    return np.column_stack(cols).astype(np.float32)


def run_rq1(panel_path: Path, out: Path, figures: Path) -> pd.DataFrame:
    panel = pd.read_csv(panel_path, parse_dates=["date"])
    dates = pd.date_range(panel["date"].min(), panel["date"].max(), freq="D")
    keys = panel[["shop_id", "category"]].drop_duplicates().sort_values(["shop_id", "category"]).reset_index(drop=True)
    pivot = panel.pivot(index=["shop_id", "category"], columns="date", values="units_sold_observed").reindex(index=pd.MultiIndex.from_frame(keys), columns=dates).fillna(0.0)
    values = pivot.to_numpy(dtype=np.float32)
    cutoffs = pd.to_datetime(["2025-04-30", "2025-05-31", "2025-06-30", "2025-07-31", "2025-08-31", "2025-09-30"])
    rows: list[dict] = []
    actual_series_rows = []
    for cutoff in cutoffs:
        cutoff_idx = int(dates.get_loc(cutoff))
        origin = cutoff_idx + 1
        target_end = origin + FORECAST_HORIZON
        if target_end > len(dates):
            continue
        train_origins = np.arange(max(56, origin - 365), origin - FORECAST_HORIZON + 1, 7, dtype=np.int32)
        series_grid = np.arange(values.shape[0], dtype=np.int32)
        train_series = np.tile(series_grid, len(train_origins))
        train_origin = np.repeat(train_origins, values.shape[0])
        X_train = rq1_features(values, train_series, train_origin, dates)
        y_train = np.stack(
            [values[train_series, train_origin + step] for step in range(FORECAST_HORIZON)],
            axis=1,
        ).sum(axis=1)
        model = HistGradientBoostingRegressor(
            loss="poisson", learning_rate=0.05, max_iter=100, max_leaf_nodes=15,
            min_samples_leaf=30, l2_regularization=2.0, random_state=SEED,
        )
        model.fit(X_train, y_train)
        test_series = series_grid
        test_origin = np.full(len(test_series), origin, dtype=np.int32)
        actual = values[:, origin : origin + FORECAST_HORIZON].sum(axis=1)
        hgb = np.maximum(model.predict(rq1_features(values, test_series, test_origin, dates)), 0.0)
        naive7 = values[:, origin - 7 : origin].sum(axis=1)
        mean28 = values[:, origin - 28 : origin].mean(axis=1) * FORECAST_HORIZON
        for name, prediction in [("weekly_naive", naive7), ("mean_28_days", mean28), ("hist_gradient_boosting", hgb)]:
            error = prediction - actual
            rows.append({
                "cutoff": cutoff.date().isoformat(),
                "horizon_days": FORECAST_HORIZON,
                "model": name,
                "actual_total_units": float(actual.sum()),
                "predicted_total_units": float(prediction.sum()),
                "WAPE": float(np.abs(error).sum() / max(np.abs(actual).sum(), 1.0)),
                "MAE_units_per_series": float(np.abs(error).mean()),
                "RMSE_units_per_series": float(np.sqrt(np.square(error).mean())),
                "bias_units": float(error.sum()),
                "bias_pct": float(error.sum() / max(np.abs(actual).sum(), 1.0)),
            })
        actual_series_rows.append({"cutoff": cutoff.date().isoformat(), "actual": float(actual.sum()), "weekly_naive": float(naive7.sum()), "mean_28_days": float(mean28.sum()), "hist_gradient_boosting": float(hgb.sum())})
    metrics = pd.DataFrame(rows)
    metrics.to_csv(out / "rq1_multidate_metrics.csv", index=False)
    series = pd.DataFrame(actual_series_rows)
    fig, axes = plt.subplots(2, 1, figsize=(11, 8), sharex=True)
    x = np.arange(len(series))
    axes[0].plot(x, series["actual"], marker="o", linewidth=2.5, label="Actual 7-day demand", color="#111827")
    for col, color in [("weekly_naive", "#64748b"), ("mean_28_days", "#d97706"), ("hist_gradient_boosting", "#2563eb")]:
        axes[0].plot(x, series[col], marker="o", label=col.replace("_", " ").title(), color=color)
    axes[0].set_ylabel("Units")
    axes[0].set_title("RQ1: Actual versus predicted demand across six dates")
    axes[0].legend(ncol=2, frameon=False)
    for name, color in [("weekly_naive", "#64748b"), ("mean_28_days", "#d97706"), ("hist_gradient_boosting", "#2563eb")]:
        subset = metrics[metrics["model"].eq(name)].sort_values("cutoff")
        axes[1].plot(x, subset["WAPE"] * 100, marker="o", label=name.replace("_", " ").title(), color=color)
    axes[1].set_ylabel("WAPE (%)")
    axes[1].set_xlabel("Forecast cutoff")
    axes[1].set_xticks(x, series["cutoff"], rotation=25, ha="right")
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].legend(frameon=False)
    savefig(fig, figures / "rq1_multidate_actual_vs_predicted.png")
    return metrics


def run_rq2(snapshot_path: Path, out: Path, figures: Path) -> pd.DataFrame:
    frame = pd.read_csv(snapshot_path, parse_dates=["snapshot_date"])
    numeric = ["recency_days", "orders_last_30d", "orders_last_90d", "orders_last_180d", "sales_last_90d_bdt", "mean_basket_last_90d_bdt", "lifetime_orders_so_far", "tenure_days"]
    angle = 2 * np.pi * (frame["snapshot_date"].dt.month - 1) / 12
    frame["snapshot_month_sin"] = np.sin(angle)
    frame["snapshot_month_cos"] = np.cos(angle)
    numeric += ["snapshot_month_sin", "snapshot_month_cos"]
    dates = sorted(frame["snapshot_date"].dropna().unique())
    eval_dates = dates[1:]
    rows: list[dict] = []
    for date in eval_dates:
        train = frame[frame["snapshot_date"] < date]
        test = frame[frame["snapshot_date"].eq(date)]
        model = HistGradientBoostingClassifier(
            learning_rate=0.06, max_iter=120, max_leaf_nodes=15,
            min_samples_leaf=40, l2_regularization=5.0, random_state=SEED,
        )
        model.fit(train[numeric], train["inactive_next_90d_label"].astype(int))
        probability = model.predict_proba(test[numeric])[:, 1]
        y = test["inactive_next_90d_label"].to_numpy(dtype=int)
        top_n = max(1, int(np.ceil(len(y) * 0.10)))
        top_idx = np.argpartition(probability, -top_n)[-top_n:]
        rows.append({
            "snapshot_date": pd.Timestamp(date).date().isoformat(),
            "train_rows": int(len(train)),
            "test_rows": int(len(test)),
            "actual_inactivity_rate": float(y.mean()),
            "mean_predicted_inactivity_probability": float(probability.mean()),
            "top_decile_observed_inactivity_rate": float(y[top_idx].mean()),
            "average_precision": float(average_precision_score(y, probability)),
            "roc_auc": float(roc_auc_score(y, probability)) if len(np.unique(y)) == 2 else None,
            "brier_score": float(brier_score_loss(y, probability)),
            "f1_at_0_5": float(f1_score(y, probability >= 0.5, zero_division=0)),
        })
    metrics = pd.DataFrame(rows)
    metrics.to_csv(out / "rq2_multidate_metrics.csv", index=False)
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    x = np.arange(len(metrics))
    axes[0].plot(x, metrics["actual_inactivity_rate"] * 100, marker="o", linewidth=2.5, color="#111827", label="Actual rate")
    axes[0].plot(x, metrics["mean_predicted_inactivity_probability"] * 100, marker="o", color="#2563eb", label="Mean predicted probability")
    axes[0].set_title("RQ2: Predicted versus actual inactivity")
    axes[0].set_ylabel("Inactivity (%)")
    axes[0].set_xticks(x, metrics["snapshot_date"], rotation=30, ha="right")
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].plot(x, metrics["actual_inactivity_rate"] * 100, marker="o", color="#9ca3af", label="All customers")
    axes[1].plot(x, metrics["top_decile_observed_inactivity_rate"] * 100, marker="o", linewidth=2.5, color="#dc2626", label="Highest-risk 10%")
    axes[1].set_title("RQ2: Operational targeting lift")
    axes[1].set_ylabel("Observed inactivity (%)")
    axes[1].set_xticks(x, metrics["snapshot_date"], rotation=30, ha="right")
    axes[1].legend(frameon=False, fontsize=8)
    for ax in axes:
        ax.grid(axis="y", alpha=0.25)
    savefig(fig, figures / "rq2_multidate_inactivity.png")
    return metrics


def _stock_at_cutoff(movements: pd.DataFrame, cutoff: pd.Timestamp) -> pd.Series:
    eligible = movements[movements["movement_datetime"].dt.normalize() <= cutoff]
    return eligible.groupby(["shop_id", "sku_id"], sort=False)["quantity_delta"].sum()


def run_rq3(data_dir: Path, out: Path, figures: Path) -> pd.DataFrame:
    sales = pd.read_csv(data_dir / "rq1_daily_sku_sales_observed.csv", parse_dates=["date"], usecols=["shop_id", "sku_id", "date", "units_sold_observed"])
    products = pd.read_csv(data_dir / "products.csv", usecols=["sku_id", "standard_purchase_cost_bdt", "base_retail_price_bdt", "reorder_point_units", "case_pack_units"])
    movements = pd.read_csv(data_dir / "inventory_movements.csv", parse_dates=["movement_datetime"], usecols=["shop_id", "sku_id", "movement_datetime", "quantity_delta"])
    sales["units_sold_observed"] = sales["units_sold_observed"].astype(float)
    products["case_pack_units"] = products["case_pack_units"].clip(lower=1)
    products["margin_bdt"] = (products["base_retail_price_bdt"] - products["standard_purchase_cost_bdt"]).clip(lower=0)
    cutoffs = pd.to_datetime(["2025-02-28", "2025-03-31", "2025-04-30", "2025-05-31", "2025-06-30", "2025-07-31", "2025-08-31", "2025-09-30"])
    rows: list[dict] = []
    for cutoff in cutoffs:
        start30 = cutoff - pd.Timedelta(days=29)
        start90 = cutoff - pd.Timedelta(days=89)
        future_end = cutoff + pd.Timedelta(days=30)
        history = sales[(sales["date"] >= start90) & (sales["date"] <= cutoff)]
        future = sales[(sales["date"] > cutoff) & (sales["date"] <= future_end)]
        if future.empty:
            continue
        pairs = pd.concat([history[["shop_id", "sku_id"]], future[["shop_id", "sku_id"]]]).drop_duplicates()
        stock = _stock_at_cutoff(movements, cutoff).rename("stock_at_cutoff").reset_index()
        d90 = history.groupby(["shop_id", "sku_id"], sort=False)["units_sold_observed"].sum().rename("demand_90d")
        d30 = history[history["date"] >= start30].groupby(["shop_id", "sku_id"], sort=False)["units_sold_observed"].sum().rename("demand_30d")
        d_future = future.groupby(["shop_id", "sku_id"], sort=False)["units_sold_observed"].sum().rename("actual_future_demand_30d")
        detail = pairs.merge(stock, on=["shop_id", "sku_id"], how="left")
        detail = detail.merge(d90.reset_index(), on=["shop_id", "sku_id"], how="left")
        detail = detail.merge(d30.reset_index(), on=["shop_id", "sku_id"], how="left")
        detail = detail.merge(d_future.reset_index(), on=["shop_id", "sku_id"], how="left")
        detail = detail.merge(products, on="sku_id", how="inner", validate="many_to_one")
        detail = detail.fillna({"stock_at_cutoff": 0, "demand_90d": 0, "demand_30d": 0, "actual_future_demand_30d": 0})
        detail = detail[detail["standard_purchase_cost_bdt"].gt(0)].copy()
        detail["mean90_per_day"] = detail["demand_90d"] / 90.0
        detail["mean30_per_day"] = detail["demand_30d"] / 30.0
        detail["baseline_predicted_demand_30d"] = detail["mean90_per_day"] * 30.0
        detail["trend_predicted_demand_30d"] = (0.6 * detail["mean30_per_day"] + 0.4 * detail["mean90_per_day"]) * 30.0
        for prefix, forecast_col in [("baseline", "baseline_predicted_demand_30d"), ("trend", "trend_predicted_demand_30d")]:
            raw_order = (detail[forecast_col] + detail["reorder_point_units"] - detail["stock_at_cutoff"]).clip(lower=0)
            detail[f"{prefix}_order_qty"] = np.ceil(raw_order / detail["case_pack_units"]) * detail["case_pack_units"]
            detail[f"{prefix}_available_after_order"] = detail["stock_at_cutoff"] + detail[f"{prefix}_order_qty"]
            detail[f"{prefix}_lost_units"] = (detail["actual_future_demand_30d"] - detail[f"{prefix}_available_after_order"]).clip(lower=0)
            detail[f"{prefix}_ending_stock"] = (detail[f"{prefix}_available_after_order"] - detail["actual_future_demand_30d"]).clip(lower=0)
            detail[f"{prefix}_avg_stock"] = (detail[f"{prefix}_available_after_order"] + detail[f"{prefix}_ending_stock"]) / 2
            detail[f"{prefix}_cost_bdt"] = (
                detail[f"{prefix}_order_qty"] * detail["standard_purchase_cost_bdt"]
                + 0.02 * detail[f"{prefix}_avg_stock"] * detail["standard_purchase_cost_bdt"]
                + detail[f"{prefix}_lost_units"] * detail["margin_bdt"]
            )
        rows.append({
            "cutoff": cutoff.date().isoformat(),
            "pairs": int(len(detail)),
            "actual_future_demand_30d": float(detail["actual_future_demand_30d"].sum()),
            "baseline_predicted_demand_30d": float(detail["baseline_predicted_demand_30d"].sum()),
            "trend_predicted_demand_30d": float(detail["trend_predicted_demand_30d"].sum()),
            "baseline_total_cost_bdt": float(detail["baseline_cost_bdt"].sum()),
            "trend_total_cost_bdt": float(detail["trend_cost_bdt"].sum()),
            "baseline_lost_units": float(detail["baseline_lost_units"].sum()),
            "trend_lost_units": float(detail["trend_lost_units"].sum()),
            "baseline_avg_stock_units": float(detail["baseline_avg_stock"].mean()),
            "trend_avg_stock_units": float(detail["trend_avg_stock"].mean()),
            "trend_cost_change_pct": float(100 * (detail["trend_cost_bdt"].sum() / max(detail["baseline_cost_bdt"].sum(), 1.0) - 1)),
            "trend_lost_unit_change": float(detail["trend_lost_units"].sum() - detail["baseline_lost_units"].sum()),
        })
    metrics = pd.DataFrame(rows)
    metrics.to_csv(out / "rq3_multidate_business_impact.csv", index=False)
    fig, axes = plt.subplots(3, 1, figsize=(11, 10), sharex=True)
    x = np.arange(len(metrics))
    axes[0].plot(x, metrics["actual_future_demand_30d"], marker="o", linewidth=2.5, color="#111827", label="Actual next-30-day demand")
    axes[0].plot(x, metrics["baseline_predicted_demand_30d"], marker="o", color="#64748b", label="Baseline forecast")
    axes[0].plot(x, metrics["trend_predicted_demand_30d"], marker="o", color="#2563eb", label="Trend forecast")
    axes[0].set_ylabel("Units")
    axes[0].set_title("RQ3: Actual demand versus policy forecast across historical dates")
    axes[0].legend(frameon=False, ncol=3, fontsize=8)
    axes[1].plot(x, metrics["baseline_total_cost_bdt"], marker="o", color="#64748b", label="Baseline")
    axes[1].plot(x, metrics["trend_total_cost_bdt"], marker="o", color="#16a34a", label="Trend policy")
    axes[1].set_ylabel("Assumption-based cost (BDT)")
    axes[1].set_title("Owner impact: procurement + holding + lost-margin cost")
    axes[1].legend(frameon=False)
    axes[2].plot(x, metrics["baseline_lost_units"], marker="o", color="#64748b", label="Baseline")
    axes[2].plot(x, metrics["trend_lost_units"], marker="o", color="#dc2626", label="Trend policy")
    axes[2].set_ylabel("Lost units")
    axes[2].set_xlabel("Historical cutoff")
    axes[2].set_title("Owner impact: service loss after each policy")
    axes[2].set_xticks(x, metrics["cutoff"], rotation=25, ha="right")
    axes[2].legend(frameon=False)
    for ax in axes:
        ax.grid(axis="y", alpha=0.25)
    savefig(fig, figures / "rq3_multidate_strategy_impact.png")
    return metrics


def run(data_dir: Path, out: Path, figures: Path) -> None:
    out.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    rq1 = run_rq1(data_dir / "rq1_daily_shop_category.csv", out, figures)
    rq2 = run_rq2(data_dir / "rq2_customer_snapshots_90d.csv", out, figures)
    rq3 = run_rq3(data_dir, out, figures)
    summary = {
        "experiment": "multi-date business impact validation",
        "rq1_cutoffs": rq1["cutoff"].unique().tolist(),
        "rq2_snapshot_dates": rq2["snapshot_date"].tolist(),
        "rq3_cutoffs": rq3["cutoff"].tolist(),
        "rq3_cost_function": "purchase_cost + 0.02 * purchase_cost * average_stock + lost_units * max(retail_price - purchase_cost, 0)",
        "rq3_assumption_note": "Historical backtest uses observed sales after each cutoff; it is a decision-analysis estimate, not audited accounting profit or causal business impact.",
        "outputs": ["rq1_multidate_metrics.csv", "rq2_multidate_metrics.csv", "rq3_multidate_business_impact.csv", "rq1_multidate_actual_vs_predicted.png", "rq2_multidate_inactivity.png", "rq3_multidate_strategy_impact.png"],
        "input_files": {
            "rq1_daily_shop_category.csv": sha256(data_dir / "rq1_daily_shop_category.csv"),
            "rq2_customer_snapshots_90d.csv": sha256(data_dir / "rq2_customer_snapshots_90d.csv"),
            "rq1_daily_sku_sales_observed.csv": sha256(data_dir / "rq1_daily_sku_sales_observed.csv"),
            "inventory_movements.csv": sha256(data_dir / "inventory_movements.csv"),
            "products.csv": sha256(data_dir / "products.csv"),
        },
        "seed": SEED,
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }
    (out / "run_manifest.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps({"rq1": rq1.to_dict(orient="records"), "rq2": rq2.to_dict(orient="records"), "rq3": rq3.to_dict(orient="records")}, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("research/experiments/results/multidate_business_impact"))
    parser.add_argument("--figures-dir", type=Path, default=Path("thesis_report/Figures"))
    args = parser.parse_args()
    run(args.data_dir, args.output_dir, args.figures_dir)


if __name__ == "__main__":
    main()
