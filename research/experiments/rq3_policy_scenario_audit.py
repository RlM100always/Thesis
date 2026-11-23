"""Paired audit of the supplied RQ3 replenishment-policy scenarios.

The input contains synthetic future oracle demand. Results are scenario
trade-offs only, not realised savings or an owner's observed policy replay.
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

REQUIRED = [
    "case_id", "shop_id", "sku_id", "cutoff", "stock_at_cutoff",
    "last_30_day_sales_units", "last_90_day_sales_units",
    "synthetic_future_30_day_oracle_demand_units", "assumed_lead_days",
    "assumed_reorder_budget_bdt", "baseline_order_qty", "trend_policy_order_qty",
    "baseline_lost_units_scenario", "trend_lost_units_scenario",
    "baseline_avg_stock_units", "trend_avg_stock_units",
    "baseline_cost_bdt_scenario", "trend_cost_bdt_scenario",
    "cost_gap_trend_minus_baseline_bdt",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def cluster_bootstrap(frame: pd.DataFrame, columns: list[str], replicates: int, seed: int = 20261123):
    shop_means = frame.groupby("shop_id")[columns].mean()
    values = shop_means.to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    draws = rng.integers(0, len(values), size=(replicates, len(values)))
    samples = values[draws].mean(axis=1)
    rows = []
    for j, column in enumerate(columns):
        lo, med, hi = np.quantile(samples[:, j], [0.025, 0.5, 0.975])
        rows.append({
            "metric": column, "lower_2_5": float(lo), "median": float(med),
            "upper_97_5": float(hi), "resampling_unit": "shop_id",
            "clusters": int(len(values)), "replicates": replicates,
        })
    return pd.DataFrame(rows)


def run(data_dir: Path, output_dir: Path, input_name: str, products_name: str, replicates: int):
    started = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path, products_path = data_dir / input_name, data_dir / products_name
    data = pd.read_csv(input_path)
    products = pd.read_csv(products_path, usecols=["sku_id", "case_pack_units"])
    missing = sorted(set(REQUIRED) - set(data.columns))
    if missing:
        raise ValueError(f"Missing RQ3 fields: {missing}")
    if data["case_id"].duplicated().any():
        raise ValueError("Duplicate RQ3 case_id values.")
    data = data.merge(products, on="sku_id", how="left", validate="many_to_one")
    if data["case_pack_units"].isna().any():
        raise ValueError("Some RQ3 SKU IDs are missing from the product master.")
    pack = data["case_pack_units"].astype(int)
    if (pack <= 0).any():
        raise ValueError("case_pack_units must be positive.")

    data["cost_delta"] = data["trend_cost_bdt_scenario"] - data["baseline_cost_bdt_scenario"]
    data["lost_delta"] = data["trend_lost_units_scenario"] - data["baseline_lost_units_scenario"]
    data["stock_delta"] = data["trend_avg_stock_units"] - data["baseline_avg_stock_units"]
    data["order_delta"] = data["trend_policy_order_qty"] - data["baseline_order_qty"]
    identity_error = float(np.max(np.abs(data["cost_delta"] - data["cost_gap_trend_minus_baseline_bdt"])))
    if identity_error > 1e-6:
        raise ValueError("Cost-gap field does not equal trend cost minus baseline cost.")
    baseline_pack_rate = float(((data["baseline_order_qty"] % pack) == 0).mean())
    trend_pack_rate = float(((data["trend_policy_order_qty"] % pack) == 0).mean())

    measures = [
        ("lost_units", "baseline_lost_units_scenario", "trend_lost_units_scenario", "units"),
        ("average_stock", "baseline_avg_stock_units", "trend_avg_stock_units", "units"),
        ("scenario_cost", "baseline_cost_bdt_scenario", "trend_cost_bdt_scenario", "BDT"),
        ("order_quantity", "baseline_order_qty", "trend_policy_order_qty", "units"),
    ]
    rows = []
    for name, baseline, trend, unit in measures:
        b_total, t_total = float(data[baseline].sum()), float(data[trend].sum())
        rows.append({
            "measure": name, "unit": unit, "cases": int(len(data)),
            "baseline_total": b_total, "trend_total": t_total,
            "baseline_mean_per_case": float(data[baseline].mean()),
            "trend_mean_per_case": float(data[trend].mean()),
            "mean_delta_trend_minus_baseline": float(data[trend].mean() - data[baseline].mean()),
            "relative_change_pct": ((t_total / b_total) - 1) * 100 if b_total else None,
        })
    pd.DataFrame(rows).to_csv(output_dir / "scenario_metrics.csv", index=False)

    bootstrap = cluster_bootstrap(data, ["cost_delta", "lost_delta", "stock_delta", "order_delta"], replicates)
    bootstrap.to_csv(output_dir / "shop_cluster_bootstrap_ci.csv", index=False)
    oracle = float(data["synthetic_future_30_day_oracle_demand_units"].sum())
    case_counts = {
        "cost_lower": int((data["cost_delta"] < 0).sum()),
        "cost_equal": int((data["cost_delta"] == 0).sum()),
        "cost_higher": int((data["cost_delta"] > 0).sum()),
        "lost_units_lower": int((data["lost_delta"] < 0).sum()),
        "lost_units_equal": int((data["lost_delta"] == 0).sum()),
        "lost_units_higher": int((data["lost_delta"] > 0).sum()),
    }
    summary = {
        "cases": int(len(data)), "shops": int(data["shop_id"].nunique()),
        "skus": int(data["sku_id"].nunique()),
        "cutoff_dates": sorted(data["cutoff"].astype(str).unique().tolist()),
        "synthetic_oracle_demand_units": oracle,
        "baseline_lost_units": float(data["baseline_lost_units_scenario"].sum()),
        "trend_lost_units": float(data["trend_lost_units_scenario"].sum()),
        "baseline_lost_share_of_oracle_pct": 100 * float(data["baseline_lost_units_scenario"].sum()) / oracle if oracle else None,
        "trend_lost_share_of_oracle_pct": 100 * float(data["trend_lost_units_scenario"].sum()) / oracle if oracle else None,
        "case_counts": case_counts,
        "baseline_order_pack_multiple_rate": baseline_pack_rate,
        "trend_order_pack_multiple_rate": trend_pack_rate,
        "cost_gap_identity_max_abs_error": identity_error,
        "scenario_cost_formula_documented_in_source": False,
        "owner_current_policy_available": False,
        "interpretation": "Scenario trade-off only; synthetic oracle demand and supplied scenario costs are not observed business outcomes.",
    }
    (output_dir / "scenario_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest = {
        "experiment": "rq3_paired_policy_scenario_audit_v1",
        "input_file": input_name, "input_sha256": sha256(input_path),
        "product_master_file": products_name, "product_master_sha256": sha256(products_path),
        "rows": int(len(data)), "shops": int(data["shop_id"].nunique()), "skus": int(data["sku_id"].nunique()),
        "bootstrap": {"unit": "shop_id", "clusters": int(data["shop_id"].nunique()), "replicates": replicates, "seed": 20261123},
        "validation": {"cost_gap_identity_max_abs_error": identity_error, "baseline_pack_multiple_rate": baseline_pack_rate, "trend_pack_multiple_rate": trend_pack_rate},
        "limitations": [
            "Future demand is explicitly labelled synthetic oracle demand.",
            "No participating owner's actual current replenishment policy is supplied.",
            "The scenario-cost formula is not documented in the input file; cost is reported as supplied.",
            "Scenario results cannot establish realised savings or causal policy effects.",
        ],
        "runtime_seconds": round(time.time() - started, 2),
        "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"summary": summary, "bootstrap": bootstrap.to_dict("records"), "output_dir": str(output_dir)}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--input-file", default="rq3_offline_policy_comparison.csv")
    parser.add_argument("--products-file", default="products.csv")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int, default=5000)
    args = parser.parse_args()
    run(args.data_dir, args.output_dir, args.input_file, args.products_file, args.bootstrap_replicates)


if __name__ == "__main__":
    main()
