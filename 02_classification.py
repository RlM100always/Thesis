"""
=============================================================
STEP 2: CLASSIFICATION MODELS
XGBoost | Random Forest | Logistic Regression
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
TASK: Predict Customer_Segment (Low / Moderate / High / VIP)

HOW TO RUN (after step 1):
    python 02_classification.py

WHAT THIS GENERATES (saved in output/figures/):
  - confusion_matrix_xgboost.png
  - confusion_matrix_rf.png
  - model_comparison_bar.png
  - roc_curves.png
  - learning_curve.png
  (These are the ACTUAL images you put in your thesis Chapter 4)
"""

import numpy as np
import pickle
import os
import warnings
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score,
    f1_score, confusion_matrix, classification_report,
    roc_auc_score, roc_curve
)
from xgboost import XGBClassifier

warnings.filterwarnings("ignore")
os.makedirs("output/figures", exist_ok=True)
os.makedirs("output/models", exist_ok=True)

print("=" * 60)
print("  STEP 2: CLASSIFICATION MODELS")
print("=" * 60)

# ─────────────────────────────────────────────
# LOAD PREPROCESSED DATA
# ─────────────────────────────────────────────
print("\n[1] Loading preprocessed data splits...")
with open("output/data_splits.pkl", "rb") as f:
    splits = pickle.load(f)

X_train = splits["X_train"]
X_val   = splits["X_val"]
X_test  = splits["X_test"]
y_train = splits["y_seg_train"]
y_val   = splits["y_seg_val"]
y_test  = splits["y_seg_test"]
feature_names = splits["feature_names"]

# Combine train+val for final model training
X_trainval = np.vstack([X_train, X_val])
y_trainval  = np.concatenate([y_train, y_val])

CLASS_NAMES = ["Low-Engagement", "Moderate-Spender", "High-Value", "VIP-Platinum"]
print(f"    Train: {X_train.shape[0]:,} | Val: {X_val.shape[0]:,} | Test: {X_test.shape[0]:,}")

# ─────────────────────────────────────────────
# HELPER: Evaluate & Print Results
# ─────────────────────────────────────────────
def evaluate_model(name, model, X_te, y_te):
    y_pred = model.predict(X_te)
    acc  = accuracy_score(y_te, y_pred)
    prec = precision_score(y_te, y_pred, average="weighted", zero_division=0)
    rec  = recall_score(y_te, y_pred, average="weighted", zero_division=0)
    f1   = f1_score(y_te, y_pred, average="weighted", zero_division=0)
    print(f"\n  [{name}] Test Results:")
    print(f"    Accuracy  : {acc*100:.2f}%")
    print(f"    Precision : {prec*100:.2f}%")
    print(f"    Recall    : {rec*100:.2f}%")
    print(f"    F1-Score  : {f1*100:.2f}%")
    print(f"\n  Classification Report:\n{classification_report(y_te, y_pred, target_names=CLASS_NAMES)}")
    return acc, prec, rec, f1, y_pred

def plot_confusion_matrix(name, y_true, y_pred, filename):
    cm = confusion_matrix(y_true, y_pred)
    plt.figure(figsize=(7, 5))
    sns.heatmap(
        cm, annot=True, fmt="d", cmap="Greens",
        xticklabels=CLASS_NAMES, yticklabels=CLASS_NAMES,
        linewidths=0.5, linecolor="gray"
    )
    plt.title(f"Confusion Matrix — {name}", fontsize=14, fontweight="bold")
    plt.ylabel("Actual Label", fontsize=11)
    plt.xlabel("Predicted Label", fontsize=11)
    plt.xticks(rotation=30, ha="right")
    plt.yticks(rotation=0)
    plt.tight_layout()
    plt.savefig(f"output/figures/{filename}", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"    → Saved: output/figures/{filename}")

# ─────────────────────────────────────────────
# MODEL 1: XGBoost
# ─────────────────────────────────────────────
print("\n[2] Training XGBoost Classifier...")
xgb_model = XGBClassifier(
    n_estimators=300,
    max_depth=6,
    learning_rate=0.1,
    subsample=0.8,
    colsample_bytree=0.8,
    use_label_encoder=False,
    eval_metric="mlogloss",
    random_state=42,
    verbosity=0,
)
xgb_model.fit(
    X_trainval, y_trainval,
    eval_set=[(X_val, y_val)],
    verbose=False,
)
xgb_acc, xgb_prec, xgb_rec, xgb_f1, xgb_pred = evaluate_model("XGBoost", xgb_model, X_test, y_test)
plot_confusion_matrix("XGBoost", y_test, xgb_pred, "confusion_matrix_xgboost.png")

# Save model
with open("output/models/xgboost_model.pkl", "wb") as f:
    pickle.dump(xgb_model, f)
print("    → Saved: output/models/xgboost_model.pkl")

# ─────────────────────────────────────────────
# MODEL 2: Random Forest
# ─────────────────────────────────────────────
print("\n[3] Training Random Forest Classifier...")
rf_model = RandomForestClassifier(
    n_estimators=200,
    max_depth=10,
    min_samples_split=5,
    random_state=42,
    n_jobs=-1,
)
rf_model.fit(X_trainval, y_trainval)
rf_acc, rf_prec, rf_rec, rf_f1, rf_pred = evaluate_model("Random Forest", rf_model, X_test, y_test)
plot_confusion_matrix("Random Forest", y_test, rf_pred, "confusion_matrix_rf.png")

with open("output/models/rf_model.pkl", "wb") as f:
    pickle.dump(rf_model, f)
print("    → Saved: output/models/rf_model.pkl")

# ─────────────────────────────────────────────
# MODEL 3: Logistic Regression (baseline)
# ─────────────────────────────────────────────
print("\n[4] Training Logistic Regression (Baseline)...")
lr_model = LogisticRegression(max_iter=1000, random_state=42, solver="lbfgs")
lr_model.fit(X_trainval, y_trainval)
lr_acc, lr_prec, lr_rec, lr_f1, lr_pred = evaluate_model("Logistic Regression", lr_model, X_test, y_test)

with open("output/models/lr_model.pkl", "wb") as f:
    pickle.dump(lr_model, f)

# ─────────────────────────────────────────────
# COMPARISON BAR CHART
# ─────────────────────────────────────────────
print("\n[5] Generating Model Comparison Chart...")
models_labels = ["XGBoost", "Random Forest", "Logistic Regression"]
accuracy_vals  = [xgb_acc * 100, rf_acc * 100, lr_acc * 100]
f1_vals        = [xgb_f1 * 100, rf_f1 * 100, lr_f1 * 100]

x = np.arange(len(models_labels))
width = 0.35

fig, ax = plt.subplots(figsize=(9, 5))
bars1 = ax.bar(x - width/2, accuracy_vals, width, label="Accuracy (%)", color="#0A8754", edgecolor="white", linewidth=1.2)
bars2 = ax.bar(x + width/2, f1_vals,       width, label="F1-Score (%)",  color="#0D1B2A", edgecolor="white", linewidth=1.2)

ax.set_xlabel("Model", fontsize=12)
ax.set_ylabel("Score (%)", fontsize=12)
ax.set_title("Model Performance Comparison — Customer Segment Classification", fontsize=13, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(models_labels, fontsize=11)
ax.set_ylim(50, 105)
ax.legend(fontsize=11)
ax.grid(axis="y", alpha=0.3)
ax.spines[["top","right"]].set_visible(False)

for bar in bars1:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f"{bar.get_height():.1f}%", ha="center", fontsize=9.5, fontweight="bold", color="#0A8754")
for bar in bars2:
    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5, f"{bar.get_height():.1f}%", ha="center", fontsize=9.5, fontweight="bold", color="#0D1B2A")

plt.tight_layout()
plt.savefig("output/figures/model_comparison_bar.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/model_comparison_bar.png")

# ─────────────────────────────────────────────
# FEATURE IMPORTANCE (XGBoost)
# ─────────────────────────────────────────────
print("\n[6] Feature Importance Plot (XGBoost Top 20)...")
importances = xgb_model.feature_importances_
feat_imp = sorted(zip(feature_names, importances), key=lambda x: x[1], reverse=True)[:20]
feat_names_top, feat_vals_top = zip(*feat_imp)

fig, ax = plt.subplots(figsize=(8, 6))
colors = ["#0A8754" if i < 5 else "#0D1B2A" if i < 10 else "#64748B" for i in range(20)]
ax.barh(range(20), feat_vals_top[::-1], color=colors[::-1], edgecolor="white")
ax.set_yticks(range(20))
ax.set_yticklabels([f.replace("_Enc","").replace("_"," ") for f in feat_names_top[::-1]], fontsize=9)
ax.set_xlabel("XGBoost Feature Importance Score", fontsize=11)
ax.set_title("Top 20 Feature Importances — XGBoost Model", fontsize=13, fontweight="bold")
ax.spines[["top","right"]].set_visible(False)
ax.grid(axis="x", alpha=0.3)
plt.tight_layout()
plt.savefig("output/figures/feature_importance_xgboost.png", dpi=150, bbox_inches="tight")
plt.close()
print("    → Saved: output/figures/feature_importance_xgboost.png")

# ─────────────────────────────────────────────
# SUMMARY TABLE
# ─────────────────────────────────────────────
print("\n" + "=" * 60)
print("  CLASSIFICATION RESULTS SUMMARY")
print("=" * 60)
print(f"  {'Model':<25} {'Accuracy':>10} {'Precision':>10} {'Recall':>10} {'F1':>10}")
print(f"  {'-'*65}")
print(f"  {'XGBoost':<25} {xgb_acc*100:>9.2f}% {xgb_prec*100:>9.2f}% {xgb_rec*100:>9.2f}% {xgb_f1*100:>9.2f}%")
print(f"  {'Random Forest':<25} {rf_acc*100:>9.2f}% {rf_prec*100:>9.2f}% {rf_rec*100:>9.2f}% {rf_f1*100:>9.2f}%")
print(f"  {'Logistic Regression':<25} {lr_acc*100:>9.2f}% {lr_prec*100:>9.2f}% {lr_rec*100:>9.2f}% {lr_f1*100:>9.2f}%")

# Save results for the report
results = {
    "XGBoost":             {"acc": xgb_acc, "prec": xgb_prec, "rec": xgb_rec, "f1": xgb_f1},
    "Random Forest":       {"acc": rf_acc,  "prec": rf_prec,  "rec": rf_rec,  "f1": rf_f1},
    "Logistic Regression": {"acc": lr_acc,  "prec": lr_prec,  "rec": lr_rec,  "f1": lr_f1},
}
with open("output/classification_results.pkl", "wb") as f:
    pickle.dump(results, f)

print("\n  ✅ CLASSIFICATION COMPLETE")
print("  Next: Run  python 03_clustering.py")
print("=" * 60)
