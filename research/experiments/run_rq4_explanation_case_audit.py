"""Mechanical consistency audit for prepared explanation cases.

This is a computational audit of generated cases. It does not analyse
participant ratings or usability; those require a real, consented user study.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def run(data_dir: Path, out: Path) -> None:
    cases_path = data_dir / "rq4_explanation_cases.csv"
    products_path = data_dir / "products.csv"
    if not cases_path.exists() or not products_path.exists():
        raise FileNotFoundError("RQ4 cases and products.csv are both required.")
    out.mkdir(parents=True, exist_ok=True)
    data = pd.read_csv(cases_path, parse_dates=["as_of_date"])
    products = pd.read_csv(products_path)
    required = {
        "case_id", "sku_id", "observed_stock_units", "reorder_point_units",
        "pending_purchase_units", "purchase_cost_bdt", "available_budget_bdt_scenario",
        "suggested_order_qty_scenario", "action", "explanation",
        "evidence_complete", "constraint_reason", "human_rating",
    }
    missing = required - set(data.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    data = data.merge(
        products[["sku_id", "case_pack_units"]],
        on="sku_id", how="left", validate="many_to_one",
    )
    if data["case_pack_units"].isna().any():
        raise ValueError("Some cases do not match a product case pack.")
    inventory_position = data["observed_stock_units"] + data["pending_purchase_units"]
    deficit = (data["reorder_point_units"] - inventory_position).clip(lower=0)
    pack = data["case_pack_units"].astype(int)
    min_pack_cost = pack * data["purchase_cost_bdt"]
    can_afford_min_pack = min_pack_cost <= data["available_budget_bdt_scenario"] + 0.01
    expected_reason = np.where(
        deficit.eq(0), "SUFFICIENT_STOCK",
        np.where(can_afford_min_pack, "UNDER_REORDER_POINT_AND_BUDGET_OK", "BUDGET_INSUFFICIENT"),
    )
    # The supplied schema has no separate blocked-action value. When the
    # budget cannot buy one case pack, the safe action is no order.
    expected_action = np.where(
        deficit.eq(0) | ~can_afford_min_pack, "NO_ACTION", "REORDER"
    )
    action_match = data["action"].to_numpy() == expected_action
    reason_match = data["constraint_reason"].to_numpy() == expected_reason
    suggested = data["suggested_order_qty_scenario"].to_numpy(dtype=float)
    pack_multiple = np.isclose(np.mod(suggested, pack), 0)
    quantity_affordable = suggested * data["purchase_cost_bdt"].to_numpy() <= (
        data["available_budget_bdt_scenario"].to_numpy() + 0.01
    )
    text = data["explanation"].fillna("").astype(str)
    mentions_scenario_stock = text.str.contains("synthetic", case=False)
    mentions_stock = text.str.contains(r"stock\s+\d+", case=False, regex=True)
    mentions_reorder_point = text.str.contains(r"reorder\s+point\s+\d+", case=False, regex=True)
    mentions_pack = text.str.contains(r"pack\s+multiple\s+\d+", case=False, regex=True)
    mentions_budget = text.str.contains(r"scenario\s+budget\s+BDT\s+\d", case=False, regex=True)
    if data["case_id"].duplicated().any():
        raise ValueError("Duplicate case_id values.")
    rating = data["human_rating"].fillna("").astype(str).str.strip().str.upper()
    # Rating text in a generated case sheet is not participant provenance.
    summary = {
        "case_count": int(len(data)),
        "date_range": [str(data["as_of_date"].min().date()), str(data["as_of_date"].max().date())],
        "actions_as_supplied": {str(k): int(v) for k, v in data["action"].value_counts(dropna=False).items()},
        "evidence_complete_as_supplied": {str(k): int(v) for k, v in data["evidence_complete"].value_counts(dropna=False).items()},
        "cases_below_reorder_point_after_pending_orders": int(deficit.gt(0).sum()),
        "rule_action_matches_including_budget_block": int(action_match.sum()),
        "rule_action_match_rate": float(action_match.mean()),
        "constraint_reason_matches": int(reason_match.sum()),
        "constraint_reason_match_rate": float(reason_match.mean()),
        "suggested_quantities_that_are_case_pack_multiples": int(pack_multiple.sum()),
        "suggested_quantity_case_pack_rate": float(pack_multiple.mean()),
        "suggested_quantities_within_scenario_budget": int(quantity_affordable.sum()),
        "suggested_quantity_budget_compliance_rate": float(quantity_affordable.mean()),
        "reorders_without_reorder_point_need": int((data["action"].eq("REORDER") & deficit.eq(0)).sum()),
        "no_action_below_reorder_point_due_to_budget": int((data["action"].eq("NO_ACTION") & deficit.gt(0) & ~can_afford_min_pack).sum()),
        "explanations_mark_stock_as_scenario_data": int(mentions_scenario_stock.sum()),
        "explanations_mention_stock": int(mentions_stock.sum()),
        "explanations_mention_reorder_point": int(mentions_reorder_point.sum()),
        "explanations_mention_pack_multiple": int(mentions_pack.sum()),
        "explanations_mention_scenario_budget": int(mentions_budget.sum()),
        "supplied_human_rating_values": {str(k): int(v) for k, v in rating.value_counts(dropna=False).items()},
        "validated_participant_response_count": 0,
        "human_usability_metrics": None,
        "interpretation": "All rows are prepared generated explanation rule-test cases. Action and constraint checks use the supplied reorder point, pending quantity, pack size and scenario budget. The target order-up-to quantity is absent from the file, so this audit does not assess whether the quantity is economically optimal. The human_rating field has no linked participant, consent, task, timestamp, or response provenance and is excluded from human-study results.",
    }
    (out / "case_audit_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    manifest = {
        "experiment": "RQ4 computational explanation-case audit",
        "scope": "rule and text consistency only; no participant study",
        "input_hashes": {
            cases_path.name: sha256(cases_path),
            products_path.name: sha256(products_path),
        },
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("research/experiments/results/rq4_explanation_case_audit"))
    args = parser.parse_args()
    run(args.data_dir, args.output_dir)


if __name__ == "__main__":
    main()
