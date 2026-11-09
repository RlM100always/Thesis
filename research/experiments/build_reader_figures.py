"""Build compact, reader-facing graphs from the committed aggregate results.

The figures are deliberately simple: one business question per panel, direct
labels, and no raw customer or transaction records.  Run from the repository
root after the experiment result CSVs have been generated.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
FIGURES = ROOT / "thesis_report" / "Figures"
R1 = ROOT / "research" / "forecasting" / "results"
R2 = ROOT / "research" / "experiments" / "results"

GREEN = "#087f5b"
BLUE = "#2563eb"
ORANGE = "#d97706"
RED = "#dc2626"
GRAY = "#64748b"
LIGHT = "#e2e8f0"


def save(fig: plt.Figure, name: str) -> None:
    fig.tight_layout()
    fig.savefig(FIGURES / name, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def style(ax: plt.Axes) -> None:
    ax.grid(axis="y", color=LIGHT, linewidth=0.8)
    ax.set_axisbelow(True)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def rq1_origin_wape() -> None:
    path = R1 / "rq1_fixed_origin_v2" / "origin_metrics_h7.csv"
    df = pd.read_csv(path)
    names = {
        "LightGBM_Tweedie": ("LightGBM", GREEN),
        "CatBoost_Tweedie": ("CatBoost", ORANGE),
        "CatBoost_Hurdle_raw": ("Hurdle", RED),
        "Croston_SBA": ("Croston-SBA", BLUE),
        "TSB": ("TSB", GRAY),
        "Seasonal_Naive_7": ("Weekly naive", "#94a3b8"),
    }
    df["origin"] = pd.to_datetime(df["origin"])
    origins = sorted(df["origin"].unique())
    x = list(range(len(origins)))
    fig, ax = plt.subplots(figsize=(8.6, 4.5))
    for model, (label, colour) in names.items():
        part = df[df["model"] == model].sort_values("origin")
        ax.plot(x, part["WAPE"].to_numpy() * 100, marker="o", linewidth=2,
                label=label, color=colour)
    ax.set_title("RQ1: seven-day WAPE at each development origin", loc="left", weight="bold")
    ax.set_ylabel("WAPE (%)")
    ax.set_xlabel("Forecast origin")
    ax.set_xticks(x, [d.strftime("%b %Y") for d in origins])
    ax.legend(ncol=3, frameon=False, fontsize=8)
    style(ax)
    save(fig, "rq1_origin_wape.png")


def rq1_context_origin() -> None:
    path = R1 / "context_aware_v1" / "fold_metrics.csv"
    df = pd.read_csv(path)
    df = df[(df["horizon"] == 7) & df["model"].isin(["LightGBM_base", "LightGBM_context"])].copy()
    df["origin"] = pd.to_datetime(df["origin"])
    origins = sorted(df["origin"].unique())
    x = list(range(len(origins)))
    labels = {"LightGBM_base": ("Historical features", GRAY),
              "LightGBM_context": ("Context features", BLUE)}
    fig, ax = plt.subplots(figsize=(8.6, 4.5))
    for model, (label, colour) in labels.items():
        part = df[df["model"] == model].sort_values("origin")
        ax.plot(x, part["WAPE"].to_numpy() * 100, marker="o", linewidth=2,
                label=label, color=colour)
    ax.set_title("RQ1: context features do not win at every date", loc="left", weight="bold")
    ax.set_ylabel("Seven-day WAPE (%)")
    ax.set_xlabel("Forecast origin")
    ax.set_xticks(x, [d.strftime("%b %Y") for d in origins])
    ax.legend(frameon=False)
    style(ax)
    save(fig, "rq1_context_origin_wape.png")


def rq2_model_comparison() -> None:
    path = R2 / "rq2_customer_prediction" / "test_metrics.csv"
    df = pd.read_csv(path)
    labels = {
        "constant_train_prevalence": "Constant",
        "logistic_regression": "Logistic",
        "hist_gradient_boosting": "HGB",
        "random_forest": "Random forest",
    }
    df["label"] = df["model"].map(labels)
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 4.2))
    x = range(len(df))
    axes[0].bar([i - 0.18 for i in x], df["average_precision"], 0.36,
                label="PR-AUC", color=BLUE)
    axes[0].bar([i + 0.18 for i in x], df["roc_auc"], 0.36,
                label="ROC-AUC", color=GREEN)
    axes[0].set_xticks(list(x), df["label"], rotation=25, ha="right")
    axes[0].set_ylim(0, 1)
    axes[0].set_ylabel("Score")
    axes[0].set_title("Ranking quality", weight="bold")
    axes[0].legend(frameon=False, fontsize=8)
    axes[1].bar(df["label"], df["precision_at_top_10pct"], color=RED)
    axes[1].axhline(df["prevalence"].iloc[0], color=GRAY, linestyle="--",
                    label="Full-test prevalence")
    axes[1].set_ylim(0, 1)
    axes[1].set_ylabel("Precision in selected 10%")
    axes[1].set_title("Who is found by targeting?", weight="bold")
    axes[1].tick_params(axis="x", rotation=25)
    axes[1].legend(frameon=False, fontsize=8)
    for ax in axes:
        style(ax)
    fig.suptitle("RQ2: model comparison on the temporal test split", weight="bold", x=0.03, ha="left")
    save(fig, "rq2_model_comparison.png")


def rq2_multidate() -> None:
    path = R2 / "multidate_business_impact" / "rq2_multidate_metrics.csv"
    df = pd.read_csv(path)
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"])
    df = df.sort_values("snapshot_date")
    x = list(range(len(df)))
    fig, ax = plt.subplots(figsize=(8.6, 4.5))
    ax.plot(x, df["actual_inactivity_rate"] * 100, marker="o",
            linewidth=2.2, label="All customers", color=GRAY)
    ax.plot(x, df["top_decile_observed_inactivity_rate"] * 100,
            marker="o", linewidth=2.2, label="Highest-risk 10%", color=RED)
    ax.plot(x, df["mean_predicted_inactivity_probability"] * 100,
            marker="o", linewidth=1.8, linestyle="--", label="Mean predicted probability", color=BLUE)
    ax.set_title("RQ2: the targeting lift remains visible across snapshot dates", loc="left", weight="bold")
    ax.set_ylabel("Inactivity (%)")
    ax.set_xlabel("Snapshot date")
    ax.set_xticks(x, [d.strftime("%b %Y") for d in df["snapshot_date"]])
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, ncol=3, fontsize=8)
    style(ax)
    save(fig, "rq2_multidate_lift.png")


def rq3_multidate_demand() -> None:
    path = R2 / "multidate_business_impact" / "rq3_multidate_business_impact.csv"
    df = pd.read_csv(path)
    df["cutoff"] = pd.to_datetime(df["cutoff"])
    df = df.sort_values("cutoff")
    x = list(range(len(df)))
    fig, ax = plt.subplots(figsize=(8.6, 4.5))
    ax.plot(x, df["actual_future_demand_30d"], marker="o", linewidth=2.2,
            label="Actual next-30-day demand", color="#111827")
    ax.plot(x, df["baseline_predicted_demand_30d"], marker="o", linewidth=2,
            label="Baseline forecast", color=GRAY)
    ax.plot(x, df["trend_predicted_demand_30d"], marker="o", linewidth=2,
            label="Trend forecast", color=ORANGE)
    ax.set_title("RQ3: actual demand versus the two reorder forecasts", loc="left", weight="bold")
    ax.set_ylabel("Units in following 30 days")
    ax.set_xlabel("Historical cutoff")
    ax.set_xticks(x, [d.strftime("%b %Y") for d in df["cutoff"]])
    ax.legend(frameon=False, fontsize=8)
    style(ax)
    save(fig, "rq3_multidate_demand.png")


def rq3_scenario_tradeoff() -> None:
    path = R2 / "rq3_scenario_comparison" / "policy_metrics.csv"
    df = pd.read_csv(path).set_index("metric")
    labels = ["Baseline", "Trend policy"]
    costs = [df.loc["baseline_cost_bdt_scenario", "sum"] / 1e6,
             df.loc["trend_cost_bdt_scenario", "sum"] / 1e6]
    lost = [df.loc["baseline_lost_units_scenario", "sum"],
            df.loc["trend_lost_units_scenario", "sum"]]
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 4.2))
    axes[0].bar(labels, costs, color=[GRAY, ORANGE])
    axes[0].set_title("Total scenario cost", weight="bold")
    axes[0].set_ylabel("BDT million")
    axes[1].bar(labels, lost, color=[GRAY, RED])
    axes[1].set_title("Lost units", weight="bold")
    axes[1].set_ylabel("Units")
    for ax in axes:
        style(ax)
    fig.suptitle("RQ3: lower assumed cost comes with more lost units", weight="bold", x=0.03, ha="left")
    save(fig, "rq3_scenario_tradeoff.png")


def main() -> None:
    FIGURES.mkdir(parents=True, exist_ok=True)
    rq1_origin_wape()
    rq1_context_origin()
    rq2_model_comparison()
    rq2_multidate()
    rq3_multidate_demand()
    rq3_scenario_tradeoff()
    print("Reader-facing figures written to", FIGURES)


if __name__ == "__main__":
    main()
