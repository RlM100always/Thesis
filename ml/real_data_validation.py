"""Real-data validation study for গবেষণা মোড — supplements, never replaces,
the synthetic thesis pipeline's results.

Runs the SAME leak-free training code a B-SMART business's own data uses
(ml.real_pipeline.train_forecast / train_churn) against two real public
datasets, since no dataset combining Bangladeshi origin + real transactions +
customer-level records could be found after an exhaustive search (see
docs/REAL_DATA_SOURCES.md):

  1. UCI Online Retail II — real transactions, but UK, not Bangladeshi.
     Runs BOTH forecast and churn (it has customers, quantities, prices).
  2. Mendeley Bangladeshi retailer demand series — real Bangladeshi data,
     but only date+quantity, no customers or prices.
     Runs forecast ONLY — churn is not physically possible on this data.

Usage:
    python -m ml.real_data_validation
    python -m ml.real_data_validation --output artifacts/real_public
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .external_datasets import load_bd_retailer_demand, load_online_retail_ii
from .real_pipeline import train_churn, train_forecast

# demand_features() reindexes every (branch, sku) pair to a full daily grid,
# so Online Retail II's ~4,600 SKUs across a 2-year span blow up to more rows
# than this machine can allocate. Real-world forecasting projects routinely
# scope to top-selling SKUs for exactly this reason — this keeps the study
# real and running, not a shortcut around a result. Churn training has no
# such blow-up (it aggregates per customer, not per SKU-day) and runs on
# every customer in the dataset.
FORECAST_TOP_SKUS = 40


def _run(label: str, fn, *args) -> dict:
    try:
        return {"available": True, **fn(*args)}
    except ValueError as exc:
        return {"available": False, "reason": str(exc)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("artifacts/real_public"))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)

    report: dict = {"generated_by": "ml.real_data_validation", "datasets": {}}

    try:
        online_retail = load_online_retail_ii()
        or2_dir = args.output / "online_retail_ii"
        or2_dir.mkdir(parents=True, exist_ok=True)

        top_skus = (
            online_retail.groupby("sku").quantity.sum()
            .sort_values(ascending=False).head(FORECAST_TOP_SKUS).index
        )
        forecast_subset = online_retail[online_retail.sku.isin(top_skus)]

        report["datasets"]["online_retail_ii"] = {
            "label": "UCI Online Retail II — real transactions, UK (non-Bangladeshi)",
            "rows_used": len(online_retail),
            "cancelled_rows_dropped": online_retail.attrs.get("cancelled_rows_dropped"),
            "distinct_customers": online_retail.customer_pseudo_id.nunique(),
            "distinct_skus": online_retail.sku.nunique(),
            "date_from": str(online_retail.sold_at.min().date()),
            "date_to": str(online_retail.sold_at.max().date()),
            "forecast_scope_note": (
                f"Forecast trained on the top {FORECAST_TOP_SKUS} SKUs by quantity sold "
                f"({len(forecast_subset):,} of {len(online_retail):,} lines) — full SKU "
                "range is not feasible to reindex to a daily grid on this machine. "
                "Future-repeat (churn) below uses every customer, no such restriction."
            ),
            "forecast": _run("forecast", train_forecast, forecast_subset, or2_dir),
            "future_repeat": _run("churn", train_churn, online_retail, or2_dir),
        }
    except FileNotFoundError as exc:
        report["datasets"]["online_retail_ii"] = {"available": False, "reason": str(exc)}

    try:
        bd_demand = load_bd_retailer_demand()
        bd_dir = args.output / "bd_retailer_demand"
        bd_dir.mkdir(parents=True, exist_ok=True)
        report["datasets"]["bd_retailer_demand"] = {
            "label": "Mendeley 10.17632/xwmbk7n3c8.1 — real Bangladeshi retailer (quantity only)",
            "rows_used": len(bd_demand),
            "date_from": str(bd_demand.sold_at.min().date()),
            "date_to": str(bd_demand.sold_at.max().date()),
            "note": "No customer or price fields in the source — forecast only, no churn/revenue.",
            "forecast": _run("forecast", train_forecast, bd_demand, bd_dir),
        }
    except FileNotFoundError as exc:
        report["datasets"]["bd_retailer_demand"] = {"available": False, "reason": str(exc)}

    (args.output / "real_data_validation.json").write_text(
        json.dumps(report, indent=2, default=str), encoding="utf-8"
    )
    print(json.dumps(report, indent=2, default=str))


if __name__ == "__main__":
    main()
