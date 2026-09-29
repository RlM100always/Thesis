"""
=============================================================
RUN_ALL.py — MASTER RUNNER
AI-Powered Business Analytics System — CSE 4th Year Thesis
=============================================================
Runs the whole pipeline in dependency order: dataset generation, preprocessing,
all models, the untouched-holdout retrain, and B-SMART Algorithm 1.

HOW TO RUN:
    python run_all.py

REQUIREMENTS (install first):
    pip install -r requirements.txt
=============================================================
"""


import utf8_console  # noqa: F401  — UTF-8 stdout before any printing
import subprocess
import sys
import time

STEPS = [
    ("Step 0a: Generate Bangladesh-Pharmacy Dataset", "00a_generate_pharmacy_dataset.py"),
    ("Step 0: Normalize Dataset (Relational Schema)", "00_normalize_dataset.py"),
    ("Step 1: Data Preprocessing",           "01_preprocessing.py"),
    ("Step 1b: Customer Features (leak-free)", "01b_customer_features.py"),
    ("Step 2: Classification v1 (leaky, for ablation)", "02_classification.py"),
    ("Step 2b: Classification v2 (leak-free)", "02b_classification_v2.py"),
    ("Step 3: K-Means Clustering",           "03_clustering.py"),
    ("Step 4: LSTM vs ARIMA vs Seasonal-Naive", "04_forecasting.py"),
    ("Step 5: SHAP Explainability",          "05_shap_analysis.py"),
    ("Step 7: Return Prediction",            "07_return_prediction.py"),
    ("Step 8: Churn Prediction",             "08_churn_prediction.py"),
    ("Step 6: Final Report",                 "06_final_report.py"),
    # 09 must run before 13: it trains the churn model the engine loads.
    ("Step 9: Retrain on Untouched Holdout", "09_retrain_models.py"),
    ("Step 10: Rolling-Origin Forecast Retrain", "10_retrain_forecasting.py"),
    ("Step 13: B-SMART Algorithm 1 (R_t)",  "13_bsmart_recommendation_engine.py"),
]

print("=" * 65)
print("  AI BUSINESS ANALYTICS — FULL PIPELINE")
print("  CSE 4th Year Thesis — Bangladesh Business Dataset")
print("=" * 65)

for i, (desc, script) in enumerate(STEPS, 1):
    print(f"\n{'─'*65}")
    print(f"  [{i}/{len(STEPS)}] Running: {desc}")
    print(f"{'─'*65}")
    start = time.time()
    result = subprocess.run([sys.executable, script], capture_output=False)
    elapsed = time.time() - start
    if result.returncode == 0:
        print(f"  ✓ Done in {elapsed:.1f}s")
    else:
        print(f"  ✗ FAILED (exit code {result.returncode}) — check error above")
        break

print("\n" + "=" * 65)
print("  ALL STEPS COMPLETE — Check output/ folder for results")
print("=" * 65)
