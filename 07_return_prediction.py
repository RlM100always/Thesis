"""
=============================================================
STEP 7: PRODUCT RETURN PREDICTION
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
Run AFTER 01_preprocessing.py.

WHY THIS EXISTS
---------------
Return_Binary was created in 01_preprocessing.py and saved into
data_splits.pkl, but no model ever used it — the target was built and
abandoned. Predicting returns before dispatch is worth real money: a
flagged order can be re-checked, re-packed, or have its address verified
before it ships.

TWO LEAKAGE TRAPS, BOTH AVOIDED HERE
------------------------------------
1. Group leakage. A return is a TRANSACTION event, so the unit is the
   transaction — but the same customer owns ~6.4 of them. A plain split
   would put a customer's transactions on both sides, exactly the flaw
   found in the segment task. This script uses GroupShuffleSplit on
   Customer_ID, so a customer belongs to one split only.

2. Post-outcome features. Delivery_Status and Return_Reason are only known
   AFTER the return happens. Including them would let the model read the
   answer. They are dropped explicitly below.

WHY NOT ACCURACY
----------------
Only ~7% of transactions are returned, so a model that predicts "no
return" every single time scores ~93% accuracy while being useless. This
script reports PR-AUC and lift instead, which cannot be gamed that way.

HOW TO RUN:
    PYTHONIOENCODING=utf-8 ./.venv312/Scripts/python.exe 07_return_prediction.py
"""

import os
import pickle
import warnings

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupShuffleSplit
from sklearn.preprocessing import MinMaxScaler
from xgboost import XGBClassifier

from common_eval import (
    evaluate_binary, plot_binary_confusion, plot_feature_importance,
    plot_pr_and_roc,
)

warnings.filterwarnings("ignore")
os.makedirs("output/figures", exist_ok=True)
os.makedirs("output/models", exist_ok=True)

print("=" * 65)
print("  STEP 7: PRODUCT RETURN PREDICTION")
print("=" * 65)

# ─────────────────────────────────────────────
# 1. LOAD
# ─────────────────────────────────────────────
print("\n[1] Loading transaction data...")
df = pd.read_csv("output/processed_dataset.csv")
print(f"    Transactions: {len(df):,}")
print(f"    Return rate : {df['Return_Binary'].mean()*100:.2f}%")

# ─────────────────────────────────────────────
# 2. FEATURES — everything knowable BEFORE dispatch
# ─────────────────────────────────────────────
print("\n[2] Selecting pre-dispatch features...")

# Known only after the outcome — including any of these is leakage
POST_OUTCOME = [
    "Delivery_Status_Enc",   # "Returned" is one of its categories
    "Return_Reason",         # only exists when a return happened
    "Is_Returned",           # the target in string form
    "Return_Binary",         # the target
    # Customer_Satisfaction_Score is rated AFTER the purchase experience,
    # so a return causes a low score rather than the score predicting the
    # return. The data makes this unambiguous: every transaction scoring
    # >= 4.1 has a 0.00% return rate, while 2.4 has 37.45%, and no returned
    # item scores above 4.0. Including it gave ROC-AUC 0.97 — the same
    # too-good-to-be-true signature as the CLV leak in the segment task.
    "Customer_Satisfaction_Score",
]

FEATURES = [
    # Order economics
    "Quantity", "Unit_Price_BDT", "Gross_Amount_BDT",
    "Discount_Percent", "Discount_Amount_BDT", "Net_Amount_BDT",
    "Profit_Margin_Percent", "Net_Profit_Ratio", "High_Discount_Flag",
    # Fulfilment (delivery DAYS is planned up front; STATUS is not)
    "Delivery_Days",
    # Customer context at time of order
    "Customer_Age", "Purchase_Frequency_Monthly",
    "Days_Since_Last_Purchase",
    "RFM_Score", "Recency_Score", "Frequency_Score", "Monetary_Score",
    # Seasonality
    "Is_Eid_Season", "Is_Ramadan", "Is_Pohela_Boishakh",
    "Is_YearEnd_Sale", "Is_Weekend",
    # Business context
    "Employee_Count", "Revenue_Per_Employee",
    # Categorical (already label-encoded upstream)
    "Business_Category_Enc", "Business_Type_Enc", "Payment_Method_Enc",
    "Order_Channel_Enc", "Marketing_Channel_Enc", "Campaign_Type_Enc",
    "Division_Enc", "Season_Enc", "Customer_Gender_Enc",
    "Customer_Type_Enc", "Stock_Level_Enc", "Day_of_Week_Enc",
]

leaked = [f for f in FEATURES if f in POST_OUTCOME]
assert not leaked, f"Post-outcome features leaked into the feature set: {leaked}"
print(f"    Features: {len(FEATURES)}")
print(f"    Excluded as post-outcome: {', '.join(POST_OUTCOME)}")

X = df[FEATURES].values
y = df["Return_Binary"].values
groups = df["Customer_ID"].values

# ─────────────────────────────────────────────
# 3. GROUP-AWARE SPLIT
# ─────────────────────────────────────────────
print("\n[3] Group-aware split (a customer lives in one split only)...")

gss = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=42)
idx_train, idx_test = next(gss.split(X, y, groups=groups))

overlap = set(groups[idx_train]) & set(groups[idx_test])
print(f"    Train: {len(idx_train):,} txns / {len(set(groups[idx_train])):,} customers")
print(f"    Test : {len(idx_test):,} txns / {len(set(groups[idx_test])):,} customers")
print(f"    Customer overlap: {len(overlap)}")
assert not overlap, "Group leakage: a customer appears in both splits"
print("    ✓ No group leakage")

X_train_raw, X_test_raw = X[idx_train], X[idx_test]
y_train, y_test = y[idx_train], y[idx_test]

print(f"    Return rate — train {y_train.mean()*100:.2f}% | test {y_test.mean()*100:.2f}%")

# Scale: fit on train only
scaler = MinMaxScaler()
X_train = scaler.fit_transform(X_train_raw)
X_test = scaler.transform(X_test_raw)
print("    ✓ Scaler fit on train only")

# ─────────────────────────────────────────────
# 4. TRAIN — weighted for the ~7% positive class
# ─────────────────────────────────────────────
print("\n[4] Training (class-weighted for imbalance)...")

n_neg, n_pos = (y_train == 0).sum(), (y_train == 1).sum()
spw = n_neg / n_pos
print(f"    scale_pos_weight = {spw:.2f}  ({n_neg:,} negative / {n_pos:,} positive)")

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
    results[name] = evaluate_binary(name, y_test, y_pred, y_score, "returned")
    scores[name] = y_score

# ─────────────────────────────────────────────
# 5. FIGURES
# ─────────────────────────────────────────────
print("\n[5] Generating figures...")
plot_pr_and_roc(y_test, scores, "Return Prediction", "return_pr_roc.png")

best_name = max(results, key=lambda n: results[n]["pr_auc"])
best_pred = (scores[best_name] >= 0.5).astype(int)
plot_binary_confusion(y_test, best_pred, ["Not Returned", "Returned"],
                      f"Return Prediction — {best_name}", "return_confusion.png")
plot_feature_importance(models[best_name], FEATURES,
                        f"Return Drivers — {best_name}", "return_feature_importance.png")

# ─────────────────────────────────────────────
# 6. SAVE
# ─────────────────────────────────────────────
print("\n[6] Saving...")
with open("output/models/return_model.pkl", "wb") as f:
    pickle.dump({"model": models[best_name], "scaler": scaler,
                 "features": FEATURES, "model_name": best_name}, f)
print("    → Saved: output/models/return_model.pkl")

with open("output/return_results.pkl", "wb") as f:
    pickle.dump({"results": results, "best_model": best_name,
                 "n_train": len(y_train), "n_test": len(y_test),
                 "features": FEATURES}, f)
print("    → Saved: output/return_results.pkl")

# ─────────────────────────────────────────────
# SUMMARY
# ─────────────────────────────────────────────
base = y_test.mean()
print("\n" + "=" * 65)
print("  RETURN PREDICTION SUMMARY")
print("=" * 65)
print(f"  {'Model':<22}{'PR-AUC':>10}{'ROC-AUC':>10}{'Recall':>10}{'Lift@10%':>11}")
print("  " + "-" * 63)
for n, r in results.items():
    print(f"  {n:<22}{r['pr_auc']:>10.4f}{r['roc_auc']:>10.4f}"
          f"{r['recall']:>10.4f}{r['lift_10']:>10.2f}x")
print(f"\n  Random baseline PR-AUC = {base:.4f} (the {base*100:.2f}% return rate)")
print(f"  Best: {best_name}")

best = results[best_name]
print(f"\n  HONEST READING:")
if best["roc_auc"] < 0.60:
    print(f"    ROC-AUC {best['roc_auc']:.3f} is WEAK (0.5 = random, 0.7 = usable).")
    print(f"    PR-AUC {best['pr_auc']:.4f} vs {base:.4f} random and {best['lift_10']:.2f}x")
    print(f"    lift mean there is a real but small signal — the top-scoring 10% of")
    print(f"    orders contain {best['lift_10']:.2f}x more returns than a random 10%.")
    print(f"    Marginally useful for prioritising manual checks; NOT reliable enough")
    print(f"    to auto-block orders.")
    print(f"\n    Report this as a NEGATIVE RESULT. Returns are close to random with")
    print(f"    respect to the features knowable before dispatch. That is a finding")
    print(f"    about the data, not a failure of the model — and it is the correct")
    print(f"    outcome for synthetic data whose returns were generated randomly.")
elif best["roc_auc"] < 0.70:
    print(f"    ROC-AUC {best['roc_auc']:.3f} — modest signal, {best['lift_10']:.2f}x lift.")
    print(f"    Usable for ranking, not for automated decisions.")
else:
    print(f"    ROC-AUC {best['roc_auc']:.3f}, PR-AUC {best['pr_auc']:.4f} vs {base:.4f}")
    print(f"    random, {best['lift_10']:.2f}x lift — a genuinely useful ranking model.")
    print(f"    ⚠ Above 0.90, re-check for post-outcome features before believing it.")
print("=" * 65)
