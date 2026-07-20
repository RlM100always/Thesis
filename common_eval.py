"""
=============================================================
SHARED EVALUATION HELPERS
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
Used by 07_return_prediction.py and 08_churn_prediction.py so both binary
classifiers are judged the same way, and so the evaluation logic lives in
one place rather than being copy-pasted per script.

Why these particular helpers:
  - bootstrap_ci   : a point estimate cannot support "A beats B"
  - pr_curve_plot  : for rare events, precision-recall is the honest curve.
                     ROC looks flattering when negatives dominate.
  - lift_at_k      : the metric a business actually acts on — "if we only
                     have budget to contact the top 10%, how much better
                     than random are we?"
"""

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.metrics import (
    average_precision_score, confusion_matrix, precision_recall_curve,
    roc_auc_score, roc_curve,
)

RNG = np.random.default_rng(42)
N_BOOTSTRAP = 2000


def bootstrap_ci(y_true, y_score, metric_fn, n=N_BOOTSTRAP, alpha=0.05):
    """Percentile bootstrap CI. Resamples the test set with replacement."""
    stats = []
    n_obs = len(y_true)
    for _ in range(n):
        idx = RNG.integers(0, n_obs, n_obs)
        # A resample with only one class present makes AUC undefined
        if len(np.unique(y_true[idx])) < 2:
            continue
        stats.append(metric_fn(y_true[idx], y_score[idx]))
    if not stats:
        return (float("nan"), float("nan"))
    lo, hi = np.percentile(stats, [alpha / 2 * 100, (1 - alpha / 2) * 100])
    return float(lo), float(hi)


def lift_at_k(y_true, y_score, k=0.10):
    """
    Lift in the top-k fraction ranked by predicted probability.

    lift = (positive rate in top k) / (positive rate overall)

    A lift of 3.0 means: contacting the top 10% by model score finds three
    times as many true positives as contacting a random 10% would.
    """
    n_top = max(1, int(len(y_true) * k))
    top_idx = np.argsort(y_score)[::-1][:n_top]
    base_rate = y_true.mean()
    if base_rate == 0:
        return float("nan")
    return float(y_true[top_idx].mean() / base_rate)


def evaluate_binary(name, y_true, y_pred, y_score, positive_label="Positive"):
    """Print and return the metric set appropriate for an imbalanced binary task."""
    base_rate = y_true.mean()
    roc = roc_auc_score(y_true, y_score)
    pr = average_precision_score(y_true, y_score)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()

    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0.0

    roc_lo, roc_hi = bootstrap_ci(y_true, y_score, roc_auc_score)
    pr_lo, pr_hi = bootstrap_ci(y_true, y_score, average_precision_score)

    print(f"\n  [{name}]")
    print(f"    Base rate ({positive_label}) : {base_rate*100:.2f}%"
          f"   ← predicting all-negative scores {(1-base_rate)*100:.2f}% 'accuracy'")
    print(f"    ROC-AUC   : {roc:.4f}   95% CI [{roc_lo:.4f}, {roc_hi:.4f}]")
    print(f"    PR-AUC    : {pr:.4f}   95% CI [{pr_lo:.4f}, {pr_hi:.4f}]"
          f"   (baseline = {base_rate:.4f})")
    print(f"    Precision : {precision:.4f}")
    print(f"    Recall    : {recall:.4f}")
    print(f"    F1        : {f1:.4f}")
    print(f"    Lift @10% : {lift_at_k(y_true, y_score, 0.10):.2f}x")
    print(f"    Lift @20% : {lift_at_k(y_true, y_score, 0.20):.2f}x")
    print(f"    Confusion : TN={tn}  FP={fp}  FN={fn}  TP={tp}")

    # PR-AUC below the base rate means the ranking is worse than random
    if pr <= base_rate:
        print(f"    ⚠ PR-AUC is at or below the base rate — the model adds nothing")

    return {
        "base_rate": float(base_rate),
        "roc_auc": float(roc), "roc_auc_ci": (roc_lo, roc_hi),
        "pr_auc": float(pr), "pr_auc_ci": (pr_lo, pr_hi),
        "precision": float(precision), "recall": float(recall), "f1": float(f1),
        "lift_10": lift_at_k(y_true, y_score, 0.10),
        "lift_20": lift_at_k(y_true, y_score, 0.20),
        "confusion": [int(tn), int(fp), int(fn), int(tp)],
    }


def plot_pr_and_roc(y_true, scores_by_model, title, filename):
    """PR curve (left) and ROC (right). PR first — it is the honest one here."""
    fig, axes = plt.subplots(1, 2, figsize=(13, 5))
    base_rate = y_true.mean()

    for name, y_score in scores_by_model.items():
        prec, rec, _ = precision_recall_curve(y_true, y_score)
        ap = average_precision_score(y_true, y_score)
        axes[0].plot(rec, prec, linewidth=2, label=f"{name} (AP={ap:.3f})")

        fpr, tpr, _ = roc_curve(y_true, y_score)
        axes[1].plot(fpr, tpr, linewidth=2, label=f"{name} (AUC={roc_auc_score(y_true, y_score):.3f})")

    axes[0].axhline(base_rate, color="gray", linestyle="--", linewidth=1,
                    label=f"Random ({base_rate:.3f})")
    axes[0].set_title(f"Precision-Recall — {title}", fontsize=12, fontweight="bold")
    axes[0].set_xlabel("Recall"); axes[0].set_ylabel("Precision")

    axes[1].plot([0, 1], [0, 1], "k--", linewidth=1, alpha=0.5, label="Random")
    axes[1].set_title(f"ROC — {title}", fontsize=12, fontweight="bold")
    axes[1].set_xlabel("False Positive Rate"); axes[1].set_ylabel("True Positive Rate")

    for ax in axes:
        ax.legend(fontsize=9); ax.grid(alpha=0.3)
        ax.spines[["top", "right"]].set_visible(False)

    plt.tight_layout()
    plt.savefig(f"output/figures/{filename}", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    → Saved: output/figures/{filename}")


def plot_binary_confusion(y_true, y_pred, labels, title, filename):
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(5.5, 4.5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Greens",
                xticklabels=labels, yticklabels=labels,
                linewidths=0.5, linecolor="gray")
    plt.title(title, fontsize=12, fontweight="bold")
    plt.ylabel("Actual"); plt.xlabel("Predicted")
    plt.tight_layout()
    plt.savefig(f"output/figures/{filename}", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    → Saved: output/figures/{filename}")


def plot_feature_importance(model, feature_names, title, filename, top_n=15):
    """Works for tree models (feature_importances_) and linear ones (coef_)."""
    imp = getattr(model, "feature_importances_", None)
    xlabel = "Importance"
    signed = None

    if imp is None:
        coef = getattr(model, "coef_", None)
        if coef is None:
            print(f"    (skipped {filename}: model exposes neither "
                  f"feature_importances_ nor coef_)")
            return
        # Binary logistic regression gives shape (1, n_features)
        signed = coef[0] if coef.ndim > 1 else coef
        imp = np.abs(signed)
        xlabel = "|Coefficient|  (green = raises risk, red = lowers)"

    order = np.argsort(imp)[::-1][:top_n]
    names = [feature_names[i].replace("_", " ") for i in order][::-1]
    vals = imp[order][::-1]

    if signed is not None:
        # Direction matters for a linear model — show which way each pushes
        colors = ["#0A8754" if signed[i] > 0 else "#E63946" for i in order][::-1]
    else:
        colors = "#0A8754"

    plt.figure(figsize=(8, 6))
    plt.barh(range(len(names)), vals, color=colors, edgecolor="white")
    plt.yticks(range(len(names)), names, fontsize=9)
    plt.xlabel(xlabel)
    plt.title(title, fontsize=12, fontweight="bold")
    plt.grid(axis="x", alpha=0.3)
    plt.gca().spines[["top", "right"]].set_visible(False)
    plt.tight_layout()
    plt.savefig(f"output/figures/{filename}", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    → Saved: output/figures/{filename}")
