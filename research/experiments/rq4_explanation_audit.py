"""RQ4 deterministic decision-rule and explanation audit.

Prepared cases are scenario fixtures, not a completed participant study.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

REQUIRED = [
    "case_id", "shop_id", "sku_id", "as_of_date", "observed_stock_units",
    "reorder_point_units", "pending_purchase_units", "supplier_lead_days_scenario",
    "purchase_cost_bdt", "available_budget_bdt_scenario", "suggested_order_qty_scenario",
    "action", "explanation", "evidence_complete", "constraint_reason", "human_rating",
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def numeric_token_present(text: str, value) -> bool:
    if pd.isna(value):
        return False
    if isinstance(value, (float, np.floating)):
        token = f"{float(value):.2f}"
    else:
        token = str(int(value)) if isinstance(value, (int, np.integer)) else str(value)
    return re.search(r"(?<![\d.])" + re.escape(token) + r"(?!\d)", str(text)) is not None


def build_explanation(row: pd.Series, pack_multiple: int) -> tuple[str, str]:
    stock = int(row["observed_stock_units"])
    pending = int(row["pending_purchase_units"])
    position = stock + pending
    reorder_point = int(row["reorder_point_units"])
    lead = int(row["supplier_lead_days_scenario"])
    unit_cost = float(row["purchase_cost_bdt"])
    budget = float(row["available_budget_bdt_scenario"])
    quantity = int(row["suggested_order_qty_scenario"])
    target = 2 * reorder_point
    required = int(np.ceil(max(0, target - position) / pack_multiple) * pack_multiple) if position < reorder_point else 0
    estimated_cost = quantity * unit_cost
    packs = quantity // pack_multiple
    if row["constraint_reason"] == "SUFFICIENT_STOCK":
        en = (
            f"No reorder is recommended now. Inventory position is {position} units "
            f"({stock} on hand + {pending} pending), at or above the reorder point of {reorder_point}. "
            f"Supplier lead time is {lead} days. Recheck stock and pending receipts before the next review."
        )
        bn = (
            f"এখন নতুন অর্ডার প্রয়োজন নেই। হাতে {stock} ইউনিট এবং পথে {pending} ইউনিট, "
            f"মোট inventory position {position} ইউনিট; এটি reorder point {reorder_point} ইউনিটের সমান বা বেশি। "
            f"Supplier lead time {lead} দিন। পরবর্তী review-তে stock ও pending receipt আবার যাচাই করুন।"
        )
    elif row["constraint_reason"] == "BUDGET_INSUFFICIENT":
        minimum_pack_cost = pack_multiple * unit_cost
        en = (
            f"The reorder trigger is reached: {stock} units are on hand and {pending} are pending, "
            f"so inventory position is {position}, below the reorder point {reorder_point}. "
            f"The target is {target} units and the pack-rounded requirement is {required} units "
            f"({pack_multiple} units per pack). One pack costs BDT {minimum_pack_cost:.2f}, "
            f"above the available budget of BDT {budget:.2f}. No order is recommended until "
            f"the budget or supplier terms are reviewed. Lead time is {lead} days."
        )
        bn = (
            f"পুনঃঅর্ডারের শর্ত পূরণ হয়েছে: হাতে {stock} ইউনিট এবং পথে {pending} ইউনিট, "
            f"মোট inventory position {position} ইউনিট; এটি reorder point {reorder_point}-এর নিচে। "
            f"লক্ষ্য stock {target} ইউনিট এবং pack অনুযায়ী প্রয়োজন {required} ইউনিট "
            f"(প্রতি প্যাকে {pack_multiple} ইউনিট)। এক প্যাকের দাম ৳{minimum_pack_cost:.2f}, "
            f"যা বাজেট ৳{budget:.2f}-এর বেশি। বাজেট বা supplier-এর শর্ত যাচাই না করে অর্ডার দেবেন না। "
            f"Lead time {lead} দিন।"
        )
    else:
        en = (
            f"Reordering is indicated: {stock} units are on hand and {pending} are pending, "
            f"so inventory position is {position}, below the reorder point {reorder_point}. "
            f"The target stock is {target}; the pack-rounded requirement is {required} units. "
            f"The budget-supported suggestion is {quantity} units ({packs} packs of {pack_multiple}), "
            f"with estimated purchase cost BDT {estimated_cost:.2f} against a budget of BDT {budget:.2f}. "
            f"Supplier lead time is {lead} days. Confirm expiry, pack size and pending receipts before placing the order."
        )
        bn = (
            f"পুনঃঅর্ডার করা উচিত: হাতে {stock} ইউনিট এবং পথে {pending} ইউনিট, "
            f"মোট inventory position {position} ইউনিট; এটি reorder point {reorder_point}-এর নিচে। "
            f"লক্ষ্য stock {target} ইউনিট; pack অনুযায়ী প্রয়োজন {required} ইউনিট। "
            f"বাজেট অনুযায়ী প্রস্তাবিত অর্ডার {quantity} ইউনিট ({packs} প্যাক, প্রতি প্যাকে {pack_multiple} ইউনিট); "
            f"আনুমানিক খরচ ৳{estimated_cost:.2f}, উপলব্ধ বাজেট ৳{budget:.2f}। "
            f"Supplier lead time {lead} দিন। অর্ডারের আগে expiry, pack size ও pending receipt যাচাই করুন।"
        )
    return en, bn


def run(data_dir: Path, output_dir: Path, input_name: str, products_name: str):
    started = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    input_path, products_path = data_dir / input_name, data_dir / products_name
    cases = pd.read_csv(input_path)
    products = pd.read_csv(products_path, usecols=["sku_id", "case_pack_units", "reorder_point_units"])
    missing = sorted(set(REQUIRED) - set(cases.columns))
    if missing:
        raise ValueError(f"Missing RQ4 fields: {missing}")
    if cases["case_id"].duplicated().any():
        raise ValueError("Duplicate RQ4 case_id values.")
    cases = cases.merge(products, on="sku_id", how="left", validate="many_to_one", suffixes=("", "_product"))
    if cases["case_pack_units"].isna().any():
        raise ValueError("Some RQ4 SKU IDs are missing from the product master.")
    if (cases["reorder_point_units"] != cases["reorder_point_units_product"]).any():
        raise ValueError("Case reorder points do not match the product master.")
    pack = cases["case_pack_units"].astype(int).to_numpy()
    position = (cases["observed_stock_units"] + cases["pending_purchase_units"]).to_numpy(dtype=int)
    reorder_point = cases["reorder_point_units"].to_numpy(dtype=int)
    budget = cases["available_budget_bdt_scenario"].to_numpy(dtype=float)
    unit_cost = cases["purchase_cost_bdt"].to_numpy(dtype=float)
    if (pack <= 0).any() or (unit_cost <= 0).any() or (budget < 0).any():
        raise ValueError("Pack size and unit cost must be positive; budget cannot be negative.")
    trigger = position < reorder_point
    target = 2 * reorder_point
    requirement = np.maximum(0, target - position)
    pack_rounded = np.where(trigger, np.ceil(requirement / pack) * pack, 0).astype(int)
    affordable = (np.floor(budget / (unit_cost * pack)) * pack).astype(int)
    expected_qty = np.minimum(pack_rounded, affordable)
    expected_action = np.where(expected_qty > 0, "REORDER", "NO_ACTION")
    expected_reason = np.where(position >= reorder_point, "SUFFICIENT_STOCK",
                               np.where(expected_qty == 0, "BUDGET_INSUFFICIENT", "UNDER_REORDER_POINT_AND_BUDGET_OK"))
    qty_match = float(np.mean(expected_qty == cases["suggested_order_qty_scenario"].to_numpy(dtype=int)))
    action_match = float(np.mean(expected_action == cases["action"].to_numpy()))
    reason_match = float(np.mean(expected_reason == cases["constraint_reason"].to_numpy()))

    source_text = cases["explanation"].fillna("").astype(str)
    source_coverage = {
        "stock_units": sum(numeric_token_present(t, v) for t, v in zip(source_text, cases["observed_stock_units"])),
        "reorder_point_units": sum(numeric_token_present(t, v) for t, v in zip(source_text, cases["reorder_point_units"])),
        "pack_multiple_units": sum(numeric_token_present(t, v) for t, v in zip(source_text, cases["case_pack_units"])),
        "available_budget_bdt": sum(numeric_token_present(t, v) for t, v in zip(source_text, cases["available_budget_bdt_scenario"])),
        "numeric_lead_days": sum(numeric_token_present(t, v) for t, v in zip(source_text, cases["supplier_lead_days_scenario"])),
        "pending_purchase_units": sum(numeric_token_present(t, v) for t, v in zip(source_text, cases["pending_purchase_units"])),
        "suggested_order_qty_units": sum(numeric_token_present(t, v) for t, v in zip(source_text, cases["suggested_order_qty_scenario"])),
        "unit_purchase_cost_bdt": sum(numeric_token_present(t, v) for t, v in zip(source_text, cases["purchase_cost_bdt"])),
    }
    pd.DataFrame([{"evidence_field": k, "cases_with_exact_numeric_value": int(v),
                   "total_cases": int(len(cases)), "coverage_pct": 100 * v / len(cases)}
                  for k, v in source_coverage.items()]).to_csv(output_dir / "explanation_numeric_coverage.csv", index=False)

    generated_rows = []
    for _, row in cases.iterrows():
        pack_multiple = int(row["case_pack_units"])
        english, bangla = build_explanation(row, pack_multiple)
        position_value = int(row["observed_stock_units"] + row["pending_purchase_units"])
        reason = row["constraint_reason"]
        required_fields = {
            "on_hand_stock_units": row["observed_stock_units"],
            "pending_purchase_units": row["pending_purchase_units"],
            "inventory_position_units": position_value,
            "reorder_point_units": row["reorder_point_units"],
            "supplier_lead_days": row["supplier_lead_days_scenario"],
        }
        if reason != "SUFFICIENT_STOCK":
            required_fields.update({
                "target_stock_units": 2 * int(row["reorder_point_units"]),
                "pack_rounded_requirement_units": int(np.ceil(max(0, 2 * int(row["reorder_point_units"]) - position_value) / pack_multiple) * pack_multiple),
                "case_pack_units": pack_multiple,
            })
        if reason == "BUDGET_INSUFFICIENT":
            required_fields.update({
                "minimum_pack_cost_bdt": pack_multiple * float(row["purchase_cost_bdt"]),
                "available_budget_bdt": row["available_budget_bdt_scenario"],
            })
        elif reason != "SUFFICIENT_STOCK":
            required_fields.update({
                "suggested_order_qty_units": row["suggested_order_qty_scenario"],
                "estimated_purchase_cost_bdt": float(row["suggested_order_qty_scenario"]) * float(row["purchase_cost_bdt"]),
                "available_budget_bdt": row["available_budget_bdt_scenario"],
            })
        for field, value in required_fields.items():
            generated_rows.append({
                "decision_branch": reason, "evidence_field": field,
                "english_present": numeric_token_present(english, value),
                "bangla_present": numeric_token_present(bangla, value),
            })
    generated = pd.DataFrame(generated_rows)
    generated_summary = generated.groupby(["decision_branch", "evidence_field"], as_index=False).agg(
        required_cases=("english_present", "size"),
        english_cases_with_value=("english_present", "sum"),
        bangla_cases_with_value=("bangla_present", "sum"),
    )
    generated_summary["english_coverage_pct"] = 100 * generated_summary["english_cases_with_value"] / generated_summary["required_cases"]
    generated_summary["bangla_coverage_pct"] = 100 * generated_summary["bangla_cases_with_value"] / generated_summary["required_cases"]
    generated_summary.to_csv(output_dir / "generated_explanation_coverage.csv", index=False)

    human_rating = cases["human_rating"].value_counts(dropna=False).to_dict()
    evidence_complete = cases["evidence_complete"].value_counts(dropna=False).to_dict()
    audit = {
        "cases": int(len(cases)), "shops": int(cases["shop_id"].nunique()),
        "skus": int(cases["sku_id"].nunique()),
        "as_of_dates": sorted(cases["as_of_date"].astype(str).unique().tolist()),
        "decision_quantity_exact_match_rate": qty_match,
        "action_exact_match_rate": action_match,
        "constraint_reason_exact_match_rate": reason_match,
        "product_master_reorder_point_match_rate": 1.0,
        "action_counts": {str(k): int(v) for k, v in cases["action"].value_counts().to_dict().items()},
        "constraint_reason_counts": {str(k): int(v) for k, v in cases["constraint_reason"].value_counts().to_dict().items()},
        "explanation_numeric_coverage": {k: int(v) for k, v in source_coverage.items()},
        "human_rating_values": {str(k): int(v) for k, v in human_rating.items()},
        "evidence_complete_values": {str(k): int(v) for k, v in evidence_complete.items()},
        "human_rating_is_constant": len(human_rating) == 1,
        "generated_explanation_required_evidence_coverage_min_pct": float(min(
            generated_summary["english_coverage_pct"].min(), generated_summary["bangla_coverage_pct"].min()
        )),
        "participant_study_evidence_present": False,
        "interpretation": "Decision-rule consistency and text-field coverage only; no owner usability or human-study effect is estimated.",
    }
    (output_dir / "decision_rule_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    template = """# RQ4 explanation template

Use a deterministic explanation built from the decision evidence.

- **No action:** state on-hand stock, pending receipts, total inventory position, reorder point and lead time.
- **Reorder:** state inventory position, reorder point, target stock, pack-rounded requirement, suggested quantity, pack count, unit cost, total estimated cost, available budget and lead time.
- **Budget block:** state the minimum pack cost and why the available budget cannot fund one pack.
- Always tell the owner to confirm expiry, pack size, pending receipts and supplier lead time before acting.

Bangla explanations should use ordinary business language and show the arithmetic. The explanation is decision support, not an automatic purchase order.
"""
    (output_dir / "explanation_template.md").write_text(template, encoding="utf-8")
    manifest = {
        "experiment": "rq4_rule_and_explanation_audit_v1",
        "input_file": input_name, "input_sha256": sha256(input_path),
        "products_file": products_name, "products_sha256": sha256(products_path),
        "rows": int(len(cases)),
        "decision_rule": {
            "inventory_position": "on_hand + pending_purchase",
            "reorder_trigger": "inventory_position < reorder_point",
            "target_stock": "2 * reorder_point",
            "pack_rounding": "ceil((target_stock - inventory_position) / case_pack_units) * case_pack_units",
            "budget_cap": "floor(available_budget / (unit_cost * case_pack_units)) * case_pack_units",
            "suggested_quantity": "min(pack_rounded_requirement, budget_cap)",
        },
        "exact_match_rates": {"quantity": qty_match, "action": action_match, "constraint_reason": reason_match},
        "generated_explanation_coverage_file": "generated_explanation_coverage.csv",
        "human_rating_warning": "All human_rating values are YES; this constant field is not evidence of a participant study.",
        "limitations": [
            "All cases are prepared scenarios at the same as-of date.",
            "A constant human_rating field cannot measure usability or explanation effectiveness.",
            "The RQ4 research question still requires consenting target users and counterbalanced tasks.",
        ],
        "runtime_seconds": round(time.time() - started, 2),
        "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({"audit": audit, "output_dir": str(output_dir)}, indent=2))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--input-file", default="rq4_explanation_cases_A.csv")
    parser.add_argument("--products-file", default="products.csv")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    run(args.data_dir, args.output_dir, args.input_file, args.products_file)


if __name__ == "__main__":
    main()
