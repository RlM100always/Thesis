"""
=============================================================
STEP 8: CUSTOMER CHURN PREDICTION
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
Run AFTER 01b_customer_features.py.

WHY THIS EXISTS
---------------
The SHAP analysis already identified inactivity past ~90 days as the
strongest churn signal in the data, but no model ever acted on it. Churn
is the most directly actionable prediction in the whole project: a
customer flagged before they lapse can still be won back, whereas a
customer already gone is expensive to recover.

THE LEAKAGE TRAP, AND HOW IT IS AVOIDED
---------------------------------------
The label is defined as Recency > CHURN_DAYS. So Recency — and anything
derived from it — IS the answer. Leaving it in the feature set would give
~100% accuracy while teaching the model nothing.

This is the third leak of this family in the project (CLV determined the
segment; satisfaction score followed the return). The pattern is always
the same: a feature that is a restatement or a consequence of the label.
The assertion below makes the exclusion explicit and self-checking.

Unit of prediction: the CUSTOMER, reusing 01b_customer_features.py, so
group leakage is impossible by construction.

HOW TO RUN:
    python 08_churn_prediction.py
"""


import utf8_console  # noqa: F401  — UTF-8 stdout before any printing
import os
import pickle
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import MinMaxScaler
from xgboost import XGBClassifier

from common_eval import (
    evaluate_binary, plot_binary_confusion, plot_feature_importance,
    plot_pr_and_roc,
)

warnings.filterwarnings("ignore")
os.makedirs("output/figures", exist_ok=True)
os.makedirs("output/models", exist_ok=True)

CHURN_DAYS = 90  # matches the 90-day threshold surfaced by the SHAP analysis

print("=" * 65)
print("  STEP 8: CUSTOMER CHURN PREDICTION")
print("=" * 65)

# ─────────────────────────────────────────────
# 1. LOAD CUSTOMER-LEVEL TABLE
# ─────────────────────────────────────────────
print("\n[1] Loading customer features...")
cust = pd.read_csv("output/customer_features.csv")
print(f"    Customers: {len(cust):,}")

# ─────────────────────────────────────────────
# 2. TARGET
# ─────────────────────────────────────────────
print(f"\n[2] Defining churn as Recency > {CHURN_DAYS} days...")
cust["Churned"] = (cust["Recency"] > CHURN_DAYS).astype(int)
churn_rate = cust["Churned"].mean()
print(f"    Churned  : {cust['Churned'].sum():,} ({churn_rate*100:.2f}%)")
print(f"    Retained : {(~cust['Churned'].astype(bool)).sum():,}")

# ─────────────────────────────────────────────
# 3. FEATURES — Recency and its derivatives must go
# ─────────────────────────────────────────────
print("\n[3] Selecting features...")

# The label IS a function of these — keeping any would be circular
LABEL_DERIVED = ["Recency", "Churned", "Customer_ID", "Segment_Label", "CLV"]

FEATURES = [c for c in cust.columns if c not in LABEL_DERIVED]

# RFM_Score embeds a recency component, so it goes too — subtler than
# Recency itself, and exactly the kind of thing that slips through.
FEATURES = [f for f in FEATURES if f != "RFM_Score"]

for banned in ("Recency", "RFM_Score"):
    assert banned not in FEATURES, f"{banned} leaks the churn label"
print(f"    ✓ Excluded (label-derived): {', '.join(LABEL_DERIVED)}, RFM_Score")
print(f"    Features: {len(FEATURES)}")

X = cust[FEATURES].values
y = cust["Churned"].values

# ─────────────────────────────────────────────
# 4. SPLIT (one row per customer — no group leakage possible)
# ─────────────────────────────────────────────
print("\n[4] Stratified 80/20 split...")
X_train_raw, X_test_raw, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42, stratify=y
)
print(f"    Train {len(y_train):,} | Test {len(y_test):,}")
print(f"    Churn rate — train {y_train.mean()*100:.2f}% | test {y_test.mean()*100:.2f}%")

scaler = MinMaxScaler()
X_train = scaler.fit_transform(X_train_raw)
X_test = scaler.transform(X_test_raw)
print("    ✓ Scaler fit on train only")

# ─────────────────────────────────────────────
# 5. TRAIN
# ─────────────────────────────────────────────
print("\n[5] Training...")

n_neg, n_pos = (y_train == 0).sum(), (y_train == 1).sum()
spw = n_neg / n_pos if n_pos else 1.0
print(f"    scale_pos_weight = {spw:.2f}")

models = {
    "XGBoost": XGBClassifier(
        n_estimators=300, max_depth=5, learning_rate=0.05,
        subsample=0.8, colsample_bytree=0.8, scale_pos_weight=spw,
        eval_metric="aucpr", random_state=42, verbosity=0,
    ),
    "Random Forest": RandomForestClassifier(
        n_estimators=200, max_depth=10, min_samples_split=5,
        class_weight="balanced", random_state=42, n_jobs=-1,
    ),
    "Logistic Regression": LogisticRegression(
        max_iter=2000, class_weight="balanced", random_state=42,
    ),
}

results, scores = {}, {}
for name, model in models.items():
    model.fit(X_train, y_train)
    y_score = model.predict_proba(X_test)[:, 1]
    y_pred = (y_score >= 0.5).astype(int)
    results[name] = evaluate_binary(name, y_test, y_pred, y_score, "churned")
    scores[name] = y_score

# ─────────────────────────────────────────────
# 6. CROSS-VALIDATION
# ─────────────────────────────────────────────
print("\n[6] 5-fold CV (scaler re-fit per fold, scored on PR-AUC)...")
cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)
cv_results = {}
for name, model in models.items():
    pipe = Pipeline([("scaler", MinMaxScaler()), ("clf", model)])
    sc = cross_val_score(pipe, X, y, cv=cv, scoring="average_precision", n_jobs=-1)
    cv_results[name] = {"mean": float(sc.mean()), "std": float(sc.std())}
    print(f"    {name:22s} PR-AUC {sc.mean():.4f} ± {sc.std():.4f}")

# ─────────────────────────────────────────────
# 7. FIGURES
# ─────────────────────────────────────────────
print("\n[7] Generating figures...")
plot_pr_and_roc(y_test, scores, "Churn Prediction", "churn_pr_roc.png")

best_name = max(results, key=lambda n: results[n]["pr_auc"])
best_pred = (scores[best_name] >= 0.5).astype(int)
plot_binary_confusion(y_test, best_pred, ["Retained", "Churned"],
                      f"Churn Prediction — {best_name}", "churn_confusion.png")
plot_feature_importance(models[best_name], FEATURES,
                        f"Churn Drivers — {best_name}", "churn_feature_importance.png")

# ─────────────────────────────────────────────
# 8. SAVE
# ─────────────────────────────────────────────
print("\n[8] Saving...")
with open("output/models/churn_model.pkl", "wb") as f:
    pickle.dump({"model": models[best_name], "scaler": scaler,
                 "features": FEATURES, "model_name": best_name,
                 "churn_days": CHURN_DAYS}, f)
print("    → Saved: output/models/churn_model.pkl")

with open("output/churn_results.pkl", "wb") as f:
    pickle.dump({"results": results, "cv": cv_results, "best_model": best_name,
                 "churn_days": CHURN_DAYS, "churn_rate": float(churn_rate),
                 "features": FEATURES}, f)
print("    → Saved: output/churn_results.pkl")

# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
base = y_test.mean()
print("\n" + "=" * 65)
print("  CHURN PREDICTION SUMMARY")
print("=" * 65)
print(f"  {'Model':<22}{'PR-AUC':>10}{'ROC-AUC':>10}{'Recall':>10}{'Lift@10%':>11}")
print("  " + "-" * 63)
for n, r in results.items():
    print(f"  {n:<22}{r['pr_auc']:>10.4f}{r['roc_auc']:>10.4f}"
          f"{r['recall']:>10.4f}{r['lift_10']:>10.2f}x")
print(f"\n  Random baseline PR-AUC = {base:.4f}")
print(f"  Best: {best_name}")

best = results[best_name]
print(f"\n  HONEST READING:")
if best["roc_auc"] < 0.60:
    print(f"    ROC-AUC {best['roc_auc']:.3f} — essentially random. Once Recency is")
    print(f"    removed, the remaining behavioural features carry little churn signal.")
    print(f"    Report as a negative result.")
elif best["roc_auc"] < 0.70:
    print(f"    ROC-AUC {best['roc_auc']:.3f} — modest but real signal ({best['lift_10']:.2f}x")
    print(f"    lift). Usable to prioritise a retention campaign, not to automate one.")
else:
    print(f"    ROC-AUC {best['roc_auc']:.3f}, {best['lift_10']:.2f}x lift in the top 10%.")
    print(f"    A retention team contacting the top-scoring 10% of customers would")
    print(f"    reach {best['lift_10']:.2f}x more future churners than contacting at random.")
print("=" * 65)
