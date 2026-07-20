"""
=============================================================
STEP 2b: CLASSIFICATION v2 — LEAK-FREE + STATISTICALLY VALIDATED
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
Run AFTER 01b_customer_features.py.

WHAT THIS ADDS OVER 02_classification.py
----------------------------------------
02_classification.py reports a single number from a single split on
leaked data. This script fixes the validation itself:

  1. Customer-level, leak-free splits (from 01b) — no customer appears
     in both train and test.
  2. 5-fold stratified cross-validation, scaler re-fit INSIDE each fold
     via a Pipeline, so no fold sees another fold's statistics.
  3. Bootstrap 95% confidence intervals — a point estimate alone cannot
     support "model A beats model B".
  4. McNemar's test — the correct paired test for comparing two
     classifiers on the same test set.
  5. Macro-averaged metrics alongside weighted, because weighted hides
     poor performance on the small VIP-Platinum class (6.9% of data).
  6. Class weighting to counter that imbalance.
  7. ROC/AUC curves and learning curves — promised by the docstring of
     02_classification.py but never actually generated there.

HOW TO RUN:
    PYTHONIOENCODING=utf-8 ./.venv312/Scripts/python.exe 02b_classification_v2.py
"""

import os
import pickle
import warnings

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, auc, classification_report, confusion_matrix,
    f1_score, precision_score, recall_score, roc_curve,
)
from sklearn.model_selection import StratifiedKFold, cross_val_score, learning_curve
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler, label_binarize
from sklearn.utils.class_weight import compute_sample_weight
from statsmodels.stats.contingency_tables import mcnemar
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")
os.makedirs("output/figures", exist_ok=True)
os.makedirs("output/models", exist_ok=True)

CLASS_NAMES = ["Low-Engagement", "Moderate-Spender", "High-Value", "VIP-Platinum"]
N_BOOTSTRAP = 2000
RNG = np.random.default_rng(42)

print("=" * 65)
print("  STEP 2b: CLASSIFICATION v2 (LEAK-FREE + VALIDATED)")
print("=" * 65)

# ─────────────────────────────────────────────
# 1. LOAD LEAK-FREE SPLITS
# ─────────────────────────────────────────────
print("\n[1] Loading customer-level splits...")
with open("output/customer_splits.pkl", "rb") as f:
    S = pickle.load(f)

X_train, X_val, X_test = S["X_train"], S["X_val"], S["X_test"]
y_train, y_val, y_test = S["y_train"], S["y_val"], S["y_test"]
feature_names = S["feature_names"]

# Train the final models on train+val (val was used for early stopping only)
X_fit = np.vstack([X_train, X_val])
y_fit = np.concatenate([y_train, y_val])

print(f"    Train {len(y_train):,} | Val {len(y_val):,} | Test {len(y_test):,} customers")
print(f"    Features: {len(feature_names)}  |  CLV included: {S['include_clv']}")
assert not (set(S["ids_train"]) & set(S["ids_test"])), "Group leakage detected"
print("    ✓ Verified: no customer in both train and test")

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────
def bootstrap_ci(y_true, y_pred, metric_fn, n=N_BOOTSTRAP, alpha=0.05):
    """Percentile bootstrap CI — resample the test set, recompute the metric."""
    stats = []
    n_obs = len(y_true)
    for _ in range(n):
        idx = RNG.integers(0, n_obs, n_obs)
        # Skip degenerate resamples that lost a class entirely
        if len(np.unique(y_true[idx])) < 2:
            continue
        stats.append(metric_fn(y_true[idx], y_pred[idx]))
    lo, hi = np.percentile(stats, [alpha / 2 * 100, (1 - alpha / 2) * 100])
    return lo, hi


def evaluate(name, model, X_te, y_te):
    y_pred = model.predict(X_te)
    acc = accuracy_score(y_te, y_pred)
    res = {
        "accuracy": acc,
        "precision_weighted": precision_score(y_te, y_pred, average="weighted", zero_division=0),
        "recall_weighted": recall_score(y_te, y_pred, average="weighted", zero_division=0),
        "f1_weighted": f1_score(y_te, y_pred, average="weighted", zero_division=0),
        # Macro treats every class equally — this is where VIP-Platinum shows up
        "precision_macro": precision_score(y_te, y_pred, average="macro", zero_division=0),
        "recall_macro": recall_score(y_te, y_pred, average="macro", zero_division=0),
        "f1_macro": f1_score(y_te, y_pred, average="macro", zero_division=0),
        "y_pred": y_pred,
    }
    lo, hi = bootstrap_ci(y_te, y_pred, accuracy_score)
    res["acc_ci"] = (lo, hi)

    print(f"\n  [{name}]")
    print(f"    Accuracy       : {acc*100:.2f}%   95% CI [{lo*100:.2f}, {hi*100:.2f}]")
    print(f"    F1 (weighted)  : {res['f1_weighted']*100:.2f}%")
    print(f"    F1 (macro)     : {res['f1_macro']*100:.2f}%   ← treats VIP equally")
    print(f"\n{classification_report(y_te, y_pred, target_names=CLASS_NAMES, zero_division=0)}")
    return res


def plot_confusion(name, y_true, y_pred, filename):
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(7, 5))
    sns.heatmap(cm, annot=True, fmt="d", cmap="Greens",
                xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES,
                linewidths=0.5, linecolor="gray")
    plt.title(f"Confusion Matrix — {name} (leak-free)", fontsize=13, fontweight="bold")
    plt.ylabel("Actual"); plt.xlabel("Predicted")
    plt.xticks(rotation=30, ha="right"); plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(f"output/figures/{filename}", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    → Saved: output/figures/{filename}")


# ─────────────────────────────────────────────
# 2. MODELS — with class weighting for the 6.9% VIP class
# ─────────────────────────────────────────────
print("\n[2] Training models (class-weighted)...")

sample_w = compute_sample_weight("balanced", y_fit)

models = {}

xgb = XGBClassifier(
    n_estimators=300, max_depth=6, learning_rate=0.1,
    subsample=0.8, colsample_bytree=0.8,
    eval_metric="mlogloss", random_state=42, verbosity=0,
)
xgb.fit(X_fit, y_fit, sample_weight=sample_w)
models["XGBoost"] = xgb

rf = RandomForestClassifier(
    n_estimators=200, max_depth=10, min_samples_split=5,
    class_weight="balanced", random_state=42, n_jobs=-1,
)
rf.fit(X_fit, y_fit)
models["Random Forest"] = rf

lr = LogisticRegression(max_iter=2000, class_weight="balanced", random_state=42)
lr.fit(X_fit, y_fit)
models["Logistic Regression"] = lr

print(f"    ✓ Trained {len(models)} models on {len(y_fit):,} customers")

# ─────────────────────────────────────────────
# 3. TEST-SET EVALUATION
# ─────────────────────────────────────────────
print("\n[3] Test-set results")
print("-" * 65)
results = {name: evaluate(name, m, X_test, y_test) for name, m in models.items()}

plot_confusion("XGBoost", y_test, results["XGBoost"]["y_pred"], "v2_confusion_xgboost.png")
plot_confusion("Random Forest", y_test, results["Random Forest"]["y_pred"], "v2_confusion_rf.png")

# ─────────────────────────────────────────────
# 4. CROSS-VALIDATION — scaler re-fit inside every fold
# ─────────────────────────────────────────────
print("\n[4] 5-fold stratified cross-validation...")
print("    (scaler re-fit inside each fold — no cross-fold leakage)")

X_all_raw, y_all = S["X_all_raw"], S["y_all"]
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

cv_results = {}
for name, model in models.items():
    pipe = Pipeline([("scaler", MinMaxScaler()), ("clf", model)])
    scores = cross_val_score(pipe, X_all_raw, y_all, cv=cv, scoring="accuracy", n_jobs=-1)
    cv_results[name] = {"scores": scores.tolist(), "mean": scores.mean(), "std": scores.std()}
    print(f"    {name:22s} {scores.mean()*100:6.2f}% ± {scores.std()*100:.2f}%"
          f"   folds: {', '.join(f'{s*100:.1f}' for s in scores)}")

# ─────────────────────────────────────────────
# 5. McNEMAR'S TEST — is XGBoost really better than RF?
# ─────────────────────────────────────────────
print("\n[5] McNemar's test — XGBoost vs Random Forest")
print("-" * 65)

xgb_correct = results["XGBoost"]["y_pred"] == y_test
rf_correct = results["Random Forest"]["y_pred"] == y_test

# 2x2 contingency of paired agreement/disagreement
n00 = int(np.sum(~xgb_correct & ~rf_correct))   # both wrong
n01 = int(np.sum(~xgb_correct & rf_correct))    # only RF right
n10 = int(np.sum(xgb_correct & ~rf_correct))    # only XGBoost right
n11 = int(np.sum(xgb_correct & rf_correct))     # both right

table = [[n11, n10], [n01, n00]]
print(f"    Both correct        : {n11}")
print(f"    Only XGBoost correct: {n10}")
print(f"    Only RF correct     : {n01}")
print(f"    Both wrong          : {n00}")

# exact=True when the discordant count is small, where chi-square is unreliable
use_exact = (n01 + n10) < 25
mc = mcnemar(table, exact=use_exact, correction=not use_exact)
print(f"\n    Test: {'exact binomial' if use_exact else 'chi-square w/ continuity correction'}")
print(f"    statistic = {mc.statistic:.4f}   p-value = {mc.pvalue:.4f}")

if mc.pvalue < 0.05:
    better = "XGBoost" if n10 > n01 else "Random Forest"
    verdict = f"SIGNIFICANT (p < 0.05) — {better} is genuinely better"
else:
    verdict = "NOT significant (p >= 0.05) — the difference could be chance"
print(f"    → {verdict}")

mcnemar_result = {
    "table": table, "statistic": float(mc.statistic),
    "pvalue": float(mc.pvalue), "exact": use_exact, "verdict": verdict,
}

# ─────────────────────────────────────────────
# 6. ROC CURVES (one-vs-rest) — promised by 02 but never generated
# ─────────────────────────────────────────────
print("\n[6] ROC curves (one-vs-rest)...")

y_test_bin = label_binarize(y_test, classes=[0, 1, 2, 3])
fig, axes = plt.subplots(1, 2, figsize=(13, 5))

for ax, (name, model) in zip(axes, [("XGBoost", xgb), ("Random Forest", rf)]):
    y_score = model.predict_proba(X_test)
    for i, cname in enumerate(CLASS_NAMES):
        fpr, tpr, _ = roc_curve(y_test_bin[:, i], y_score[:, i])
        ax.plot(fpr, tpr, linewidth=2, label=f"{cname} (AUC={auc(fpr, tpr):.3f})")
    ax.plot([0, 1], [0, 1], "k--", linewidth=1, alpha=0.5, label="Random")
    ax.set_title(f"ROC — {name}", fontsize=13, fontweight="bold")
    ax.set_xlabel("False Positive Rate"); ax.set_ylabel("True Positive Rate")
    ax.legend(fontsize=8, loc="lower right"); ax.grid(alpha=0.3)
    ax.spines[["top", "right"]].set_visible(False)

plt.tight_layout()
plt.savefig("output/figures/v2_roc_curves.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/v2_roc_curves.png")

# ─────────────────────────────────────────────
# 7. LEARNING CURVE — is more data the bottleneck?
# ─────────────────────────────────────────────
print("\n[7] Learning curve (XGBoost)...")

pipe = Pipeline([("scaler", MinMaxScaler()), ("clf", xgb)])
sizes, train_sc, val_sc = learning_curve(
    pipe, X_all_raw, y_all, cv=cv, n_jobs=-1,
    train_sizes=np.linspace(0.1, 1.0, 8), scoring="accuracy",
)

fig, ax = plt.subplots(figsize=(8, 5))
ax.plot(sizes, train_sc.mean(axis=1), "o-", color="#0D1B2A", linewidth=2, label="Training")
ax.fill_between(sizes, train_sc.mean(axis=1) - train_sc.std(axis=1),
                train_sc.mean(axis=1) + train_sc.std(axis=1), alpha=0.15, color="#0D1B2A")
ax.plot(sizes, val_sc.mean(axis=1), "s--", color="#0A8754", linewidth=2, label="Cross-validation")
ax.fill_between(sizes, val_sc.mean(axis=1) - val_sc.std(axis=1),
                val_sc.mean(axis=1) + val_sc.std(axis=1), alpha=0.15, color="#0A8754")
ax.set_title("Learning Curve — XGBoost (leak-free)", fontsize=13, fontweight="bold")
ax.set_xlabel("Training customers"); ax.set_ylabel("Accuracy")
ax.legend(); ax.grid(alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("output/figures/v2_learning_curve.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/v2_learning_curve.png")

gap = train_sc.mean(axis=1)[-1] - val_sc.mean(axis=1)[-1]
print(f"    Final train-CV gap: {gap*100:.2f} points "
      f"({'overfitting' if gap > 0.05 else 'well generalised'})")

# ─────────────────────────────────────────────
# 8. MODEL COMPARISON CHART (with CIs)
# ─────────────────────────────────────────────
print("\n[8] Comparison chart...")

names = list(results.keys())
accs = [results[n]["accuracy"] * 100 for n in names]
errs = [[(results[n]["accuracy"] - results[n]["acc_ci"][0]) * 100 for n in names],
        [(results[n]["acc_ci"][1] - results[n]["accuracy"]) * 100 for n in names]]

fig, ax = plt.subplots(figsize=(9, 5))
bars = ax.bar(names, accs, yerr=errs, capsize=6,
              color=["#0A8754", "#0D1B2A", "#64748B"], edgecolor="white")
for b, a in zip(bars, accs):
    ax.text(b.get_x() + b.get_width() / 2, a + 1.5, f"{a:.2f}%",
            ha="center", fontsize=10, fontweight="bold")
ax.set_ylabel("Test Accuracy (%)")
ax.set_title("Model Comparison — leak-free, with 95% bootstrap CI",
             fontsize=13, fontweight="bold")
ax.set_ylim(0, 105); ax.grid(axis="y", alpha=0.3)
ax.spines[["top", "right"]].set_visible(False)
plt.tight_layout()
plt.savefig("output/figures/v2_model_comparison.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/v2_model_comparison.png")

# ─────────────────────────────────────────────
# 9. SAVE
# ─────────────────────────────────────────────
print("\n[9] Saving models and results...")
for fname, model in [("v2_xgboost.pkl", xgb), ("v2_rf.pkl", rf), ("v2_lr.pkl", lr)]:
    with open(f"output/models/{fname}", "wb") as f:
        pickle.dump(model, f)

payload = {
    name: {k: v for k, v in r.items() if k != "y_pred"} for name, r in results.items()
}
with open("output/classification_v2_results.pkl", "wb") as f:
    pickle.dump({
        "test": payload, "cv": cv_results, "mcnemar": mcnemar_result,
        "include_clv": S["include_clv"], "n_features": len(feature_names),
        "n_train": len(y_fit), "n_test": len(y_test),
    }, f)
print("    → Saved: output/classification_v2_results.pkl")

# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
print("\n" + "=" * 65)
print("  RESULTS SUMMARY — LEAK-FREE")
print("=" * 65)
print(f"  {'Model':<22}{'Test Acc':>10}{'95% CI':>18}{'F1-macro':>10}{'CV mean':>12}")
print("  " + "-" * 70)
for n in names:
    r, c = results[n], cv_results[n]
    print(f"  {n:<22}{r['accuracy']*100:9.2f}%"
          f"  [{r['acc_ci'][0]*100:5.2f},{r['acc_ci'][1]*100:6.2f}]"
          f"{r['f1_macro']*100:9.2f}%{c['mean']*100:9.2f}% ±{c['std']*100:.1f}")
print(f"\n  McNemar XGBoost vs RF: p = {mc.pvalue:.4f} — {verdict}")
print("\n  ⚠ Accuracy is LOWER than 02_classification.py's 94.81% — that number")
print("    came from leaked splits. These numbers are the honest ones.")
print("=" * 65)
