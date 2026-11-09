"""Mechanical consistency audit for prepared explanation cases.

This is a computational audit of prepared rule-test cases. It does not analyse
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
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def save_rq4_figure(summary: dict, figures_dir: Path) -> None:
    figures_dir.mkdir(parents=True, exist_ok=True)
    checks = [
        ("Action", summary["rule_action_match_rate"] * 100),
        ("Reason", summary["constraint_reason_match_rate"] * 100),
        ("Pack multiple", summary["suggested_quantity_case_pack_rate"] * 100),
        ("Budget", summary["suggested_quantity_budget_compliance_rate"] * 100),
        ("Text evidence", 100.0 if summary["explanations_mention_stock"] == summary["case_count"] and summary["explanations_mention_reorder_point"] == summary["case_count"] and summary["explanations_mention_pack_multiple"] == summary["case_count"] and summary["explanations_mention_scenario_budget"] == summary["case_count"] else 0.0),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), gridspec_kw={"width_ratios": [1.35, 1]})
    labels = [x[0] for x in checks]
    values = [x[1] for x in checks]
    bars = axes[0].barh(labels, values, color="#16a34a")
    axes[0].set_xlim(0, 105)
    axes[0].set_xlabel("Pass rate (%)")
    axes[0].set_title("Mechanical explanation checks")
    axes[0].grid(axis="x", alpha=0.25)
    for bar, value in zip(bars, values):
        axes[0].text(min(value + 1, 101), bar.get_y() + bar.get_height() / 2, f"{value:.0f}%", va="center", fontsize=9)

    human_labels = ["Prepared cases audited", "Validated participant\nresponses"]
    human_values = [summary["case_count"], summary["validated_participant_response_count"]]
    human_bars = axes[1].bar(human_labels, human_values, color=["#64748b", "#dc2626"])
    axes[1].set_ylabel("Count")
    axes[1].set_title("Human-study evidence")
    axes[1].grid(axis="y", alpha=0.25)
    axes[1].set_ylim(0, max(human_values[0] * 1.15, 10))
    for bar, value in zip(human_bars, human_values):
        axes[1].text(bar.get_x() + bar.get_width() / 2, max(value, 1) + human_values[0] * 0.03, f"{value:,}", ha="center", fontsize=10)
    fig.suptitle("RQ4: What is verified, and what is still missing?", fontsize=14, y=1.02)
    fig.tight_layout()
    fig.savefig(figures_dir / "rq4_explanation_evidence.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def run(data_dir: Path, out: Path, figures_dir: Path) -> None:
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
    mentions_scenario_stock = text.str.contains(r"scenario|generated|prepared", case=False, regex=True)
    mentions_stock = text.str.contains(r"stock\s+\d+", case=False, regex=True)
    mentions_reorder_point = text.str.contains(r"reorder\s+point\s+\d+", case=False, regex=True)
    mentions_pack = text.str.contains(r"pack\s+multiple\s+\d+", case=False, regex=True)
    mentions_budget = text.str.contains(r"scenario\s+budget\s+BDT\s+\d", case=False, regex=True)
    if data["case_id"].duplicated().any():
        raise ValueError("Duplicate case_id values.")
    rating = data["human_rating"].fillna("").astype(str).str.strip().str.upper()
    # Rating text in a prepared case sheet is not participant provenance.
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
        "interpretation": "All rows are prepared explanation rule-test cases. Action and constraint checks use the supplied reorder point, pending quantity, pack size and scenario budget. The target order-up-to quantity is absent from the file, so this audit does not assess whether the quantity is economically optimal. The human_rating field has no linked participant, consent, task, timestamp, or response provenance and is excluded from human-study results.",
    }
    (out / "case_audit_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    save_rq4_figure(summary, figures_dir)
    manifest = {
        "experiment": "RQ4 computational explanation-case audit",
        "scope": "rule and text consistency only; no participant study",
        "figure_outputs": ["rq4_explanation_evidence.png"],
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
    parser.add_argument("--figures-dir", type=Path, default=Path("thesis_report/Figures"))
    args = parser.parse_args()
    run(args.data_dir, args.output_dir, args.figures_dir)


if __name__ == "__main__":
    main()
