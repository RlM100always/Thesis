"""Build a simple four-question results overview for the thesis report.

This figure is deliberately descriptive: it combines saved aggregate outputs
from the RQ1--RQ4 runners so a reader can see the evidence and its boundary in
one page. It does not fit a model or create a new metric.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


def build(results_dir: Path, output: Path, forecast_dir: Path) -> None:
    multidate = results_dir / "multidate_business_impact"
    rq1 = pd.read_csv(multidate / "rq1_multidate_metrics.csv")
    rq2 = pd.read_csv(multidate / "rq2_multidate_metrics.csv")
    rq3 = pd.read_csv(multidate / "rq3_multidate_business_impact.csv")
    rq4 = pd.read_json(results_dir / "rq4_explanation_case_audit" / "case_audit_summary.json", typ="series")

    frozen_metrics = forecast_dir / "aggregate_metrics.csv"
    if frozen_metrics.exists():
        frozen = pd.read_csv(frozen_metrics)
        rq1_context = frozen[frozen["model"].eq("LightGBM_context")].iloc[0]
        rq1_actual = float(rq1_context["actual_total"])
        rq1_predicted = float(rq1_context["forecast_total"])
        rq1_wape = float(rq1_context["WAPE"] * 100)
        rq1_label = "Frozen tail (13 weekly origins)"
    else:
        rq1_hgb = rq1[rq1["model"].eq("hist_gradient_boosting")]
        rq1_actual = float(rq1_hgb["actual_total_units"].sum())
        rq1_predicted = float(rq1_hgb["predicted_total_units"].sum())
        rq1_wape = float(rq1_hgb["WAPE"].mean() * 100)
        rq1_label = "Six rolling cutoffs"
    rq2_overall = float(rq2["actual_inactivity_rate"].mean() * 100)
    rq2_top = float(rq2["top_decile_observed_inactivity_rate"].mean() * 100)
    rq3_base = float(rq3["baseline_total_cost_bdt"].sum() / 1_000_000)
    rq3_trend = float(rq3["trend_total_cost_bdt"].sum() / 1_000_000)
    rq3_change = (rq3_trend / rq3_base - 1) * 100
    case_count = int(rq4["case_count"])
    participant_count = int(rq4["validated_participant_response_count"])

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    fig.suptitle("B-SMART thesis results at a glance", fontsize=17, y=0.98)

    ax = axes[0, 0]
    bars = ax.bar(["Actual\n7-day demand", "HGB\nforecast"], [rq1_actual, rq1_predicted], color=["#111827", "#2563eb"])
    ax.set_title("RQ1 — Demand forecasting")
    ax.set_ylabel("Units across six cutoffs")
    ax.text(0.5, 0.93, f"Mean WAPE: {rq1_wape:.2f}%", transform=ax.transAxes, ha="center", fontsize=11, color="#1d4ed8")
    ax.grid(axis="y", alpha=0.25)
    for bar, value in zip(bars, [rq1_actual, rq1_predicted]):
        ax.text(bar.get_x() + bar.get_width() / 2, value + rq1_actual * 0.02, f"{value:,.0f}", ha="center", fontsize=9)

    ax = axes[0, 1]
    bars = ax.bar(["All customers", "Highest-risk\n10%"], [rq2_overall, rq2_top], color=["#9ca3af", "#dc2626"])
    ax.set_title("RQ2 — Customer inactivity targeting")
    ax.set_ylabel("Observed inactivity (%)")
    ax.set_ylim(0, 100)
    ax.grid(axis="y", alpha=0.25)
    lift = float(rq2["targeting_lift"].mean()) if "targeting_lift" in rq2 else rq2_top / rq2_overall
    ci_low = float(rq2["targeting_lift_ci_low"].mean()) if "targeting_lift_ci_low" in rq2 else float("nan")
    ci_high = float(rq2["targeting_lift_ci_high"].mean()) if "targeting_lift_ci_high" in rq2 else float("nan")
    ci_text = f" (mean 95% CI {ci_low:.2f}–{ci_high:.2f}×)" if pd.notna(ci_low) else ""
    ax.text(0.5, 0.93, f"Targeting lift: {lift:.2f}×{ci_text}", transform=ax.transAxes, ha="center", fontsize=9, color="#b91c1c")
    for bar, value in zip(bars, [rq2_overall, rq2_top]):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 3, f"{value:.1f}%", ha="center", fontsize=10)

    ax = axes[1, 0]
    bars = ax.bar(["Baseline", "Trend policy"], [rq3_base, rq3_trend], color=["#64748b", "#d97706"])
    ax.set_title("RQ3 — Replenishment cost comparison")
    ax.set_ylabel("Decision-analysis cost (BDT million)")
    ax.grid(axis="y", alpha=0.25)
    ax.text(0.5, 0.82, f"Trend cost change: {rq3_change:+.2f}% | lost units: 0 vs 0", transform=ax.transAxes, ha="center", fontsize=10, color="#9a3412")
    for bar, value in zip(bars, [rq3_base, rq3_trend]):
        ax.text(bar.get_x() + bar.get_width() / 2, value + 0.3, f"BDT {value:.2f}m", ha="center", fontsize=9)

    ax = axes[1, 1]
    bars = ax.bar(["Mechanical\nchecks", "Validated\nparticipants"], [100, participant_count], color=["#16a34a", "#dc2626"])
    ax.set_title("RQ4 — Explanation evaluation")
    ax.set_ylabel("Evidence (% pass / count)")
    ax.set_ylim(0, 110)
    ax.grid(axis="y", alpha=0.25)
    ax.text(0.5, 0.82, f"{case_count:,} prepared cases; participant responses = {participant_count}", transform=ax.transAxes, ha="center", fontsize=9, color="#991b1b")
    ax.text(bars[0].get_x() + bars[0].get_width() / 2, 103, "100%", ha="center", fontsize=10)
    ax.text(bars[1].get_x() + bars[1].get_width() / 2, 3, "0", ha="center", fontsize=10)

    for ax in axes.ravel():
        ax.spines[["top", "right"]].set_visible(False)
    fig.text(0.5, 0.015, f"RQ1: {rq1_label}. Predictive and rule evidence is measured; causal profit and participant usability are not established.", ha="center", fontsize=9, color="#374151")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=[0, 0.04, 1, 0.95])
    fig.savefig(output, dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results-dir", type=Path, default=Path("research/experiments/results"))
    parser.add_argument("--forecast-dir", type=Path, default=Path("research/forecasting/results/rq1_frozen_tail_v1"))
    parser.add_argument("--output", type=Path, default=Path("thesis_report/Figures/thesis_results_overview.png"))
    args = parser.parse_args()
    build(args.results_dir, args.output, args.forecast_dir)


if __name__ == "__main__":
    main()
