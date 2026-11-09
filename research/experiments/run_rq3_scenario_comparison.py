"""Paired evaluation of the supplied RQ3 replenishment scenarios."""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 20261109


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def bootstrap_mean_difference(a: np.ndarray, b: np.ndarray, rng: np.random.Generator, reps: int = 5000) -> dict:
    delta = np.asarray(a, dtype=float) - np.asarray(b, dtype=float)
    n = len(delta)
    samples = np.empty(reps, dtype=float)
    for start in range(0, reps, 100):
        end = min(reps, start + 100)
        indices = rng.integers(0, n, size=(end - start, n))
        samples[start:end] = delta[indices].mean(axis=1)
    return {
        "mean_paired_difference": float(delta.mean()),
        "percentile_95pct_ci": [float(np.quantile(samples, 0.025)), float(np.quantile(samples, 0.975))],
        "positive_cases": int((delta > 0).sum()),
        "zero_cases": int((delta == 0).sum()),
        "negative_cases": int((delta < 0).sum()),
    }


def run(data_dir: Path, out: Path) -> None:
    scenarios_path = data_dir / "rq3_offline_policy_comparison.csv"
    products_path = data_dir / "products.csv"
    if not scenarios_path.exists() or not products_path.exists():
        raise FileNotFoundError("RQ3 scenarios and products.csv are both required.")
    out.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(scenarios_path, parse_dates=["cutoff"])
    products = pd.read_csv(products_path)
    required = {
        "case_id", "shop_id", "sku_id", "stock_at_cutoff",
        "synthetic_future_30_day_oracle_demand_units", "assumed_reorder_budget_bdt",
        "baseline_order_qty", "trend_policy_order_qty",
        "baseline_lost_units_scenario", "trend_lost_units_scenario",
        "baseline_avg_stock_units", "trend_avg_stock_units",
        "baseline_cost_bdt_scenario", "trend_cost_bdt_scenario",
        "cost_gap_trend_minus_baseline_bdt",
    }
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Missing scenario columns: {sorted(missing)}")
    merged = data.merge(
        products[["sku_id", "standard_purchase_cost_bdt"]],
        on="sku_id", how="left", validate="many_to_one",
    )
    if merged["standard_purchase_cost_bdt"].isna().any():
        raise ValueError("Some scenario SKUs could not be matched to product cost.")
    if data["case_id"].duplicated().any():
        raise ValueError("Duplicate scenario case identifiers.")
    if not np.allclose(
        data["cost_gap_trend_minus_baseline_bdt"],
        data["trend_cost_bdt_scenario"] - data["baseline_cost_bdt_scenario"],
        atol=0.011,
    ):
        raise ValueError("Provided cost-gap field does not reconcile to policy costs.")

    baseline_order_cost = merged["baseline_order_qty"] * merged["standard_purchase_cost_bdt"]
    trend_order_cost = merged["trend_policy_order_qty"] * merged["standard_purchase_cost_bdt"]
    budget = merged["assumed_reorder_budget_bdt"]
    cost = {
        "baseline": bootstrap_mean_difference(
            merged["baseline_cost_bdt_scenario"].to_numpy(),
            merged["trend_cost_bdt_scenario"].to_numpy(),
            np.random.default_rng(SEED),
        ),
        "trend_minus_baseline": bootstrap_mean_difference(
            merged["trend_cost_bdt_scenario"].to_numpy(),
            merged["baseline_cost_bdt_scenario"].to_numpy(),
            np.random.default_rng(SEED),
        ),
    }
    lost = bootstrap_mean_difference(
        merged["trend_lost_units_scenario"].to_numpy(),
        merged["baseline_lost_units_scenario"].to_numpy(),
        np.random.default_rng(SEED + 1),
    )
    summary = {
        "n_scenarios": int(len(data)),
        "cutoff_dates": sorted(str(x.date()) for x in data["cutoff"].dropna().unique()),
        "shops": int(data["shop_id"].nunique()),
        "skus": int(data["sku_id"].nunique()),
        "scenario_oracle_nonzero_share": float((data["synthetic_future_30_day_oracle_demand_units"] > 0).mean()),
        "baseline": {
            "total_cost_bdt_scenario": float(data["baseline_cost_bdt_scenario"].sum()),
            "mean_cost_bdt_scenario": float(data["baseline_cost_bdt_scenario"].mean()),
            "lost_units_scenario": float(data["baseline_lost_units_scenario"].sum()),
            "mean_average_stock_units_scenario": float(data["baseline_avg_stock_units"].mean()),
            "total_order_units": float(data["baseline_order_qty"].sum()),
            "budget_violation_count_using_product_cost": int((baseline_order_cost > budget + 0.01).sum()),
        },
        "trend": {
            "total_cost_bdt_scenario": float(data["trend_cost_bdt_scenario"].sum()),
            "mean_cost_bdt_scenario": float(data["trend_cost_bdt_scenario"].mean()),
            "lost_units_scenario": float(data["trend_lost_units_scenario"].sum()),
            "mean_average_stock_units_scenario": float(data["trend_avg_stock_units"].mean()),
            "total_order_units": float(data["trend_policy_order_qty"].sum()),
            "budget_violation_count_using_product_cost": int((trend_order_cost > budget + 0.01).sum()),
        },
        "trend_minus_baseline_cost_bdt": float(
            data["trend_cost_bdt_scenario"].sum() - data["baseline_cost_bdt_scenario"].sum()
        ),
        "trend_cost_relative_change_percent": float(
            100 * (data["trend_cost_bdt_scenario"].sum() / data["baseline_cost_bdt_scenario"].sum() - 1)
        ),
        "trend_minus_baseline_lost_units": float(
            data["trend_lost_units_scenario"].sum() - data["baseline_lost_units_scenario"].sum()
        ),
        "paired_cost_bootstrap_trend_minus_baseline": cost["trend_minus_baseline"],
        "paired_lost_units_bootstrap_trend_minus_baseline": lost,
        "provided_cost_gap_reconciliation_mismatches": 0,
        "input_semantics": "The future oracle-demand field contains generated scenario values; budgets and costs are assumptions, not realised business outcomes.",
    }
    (out / "scenario_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    paired = data[[
        "baseline_cost_bdt_scenario", "trend_cost_bdt_scenario",
        "baseline_lost_units_scenario", "trend_lost_units_scenario",
        "baseline_avg_stock_units", "trend_avg_stock_units",
    ]].agg(["sum", "mean"]).T.reset_index(names="metric")
    paired.to_csv(out / "policy_metrics.csv", index=False)
    manifest = {
        "experiment": "RQ3 paired scenario comparison",
        "comparison": "provided baseline policy versus provided trend policy on identical scenario rows",
        "uncertainty": "paired percentile bootstrap over the 2,500 scenario rows; not a real-business sampling interval",
        "seed": SEED,
        "input_hashes": {
            scenarios_path.name: sha256(scenarios_path),
            products_path.name: sha256(products_path),
        },
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "raw_customer_ids_written": False,
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("research/experiments/results/rq3_scenario_comparison"))
    args = parser.parse_args()
    run(args.data_dir, args.output_dir)


if __name__ == "__main__":
    main()
