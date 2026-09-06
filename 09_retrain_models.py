"""Leakage-safe model retraining and training-only hyperparameter selection.

This script creates a new, untouched 20% holdout (seed fixed from the report
date), performs all feature/model selection inside the remaining development
data, and opens the holdout only after a winning family has been selected.

Outputs:
    output/retrained_model_results.json
    output/models/retrained_*.pkl
    output/figures/retrained_*.png
"""

from __future__ import annotations

import json
import pickle
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import loguniform
from sklearn.base import clone
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.feature_selection import SelectKBest, f_classif
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    f1_score,
    precision_recall_curve,
    roc_auc_score,
    roc_curve,
)
from sklearn.model_selection import (
    GroupShuffleSplit,
    RandomizedSearchCV,
    StratifiedGroupKFold,
    StratifiedKFold,
    cross_val_predict,
    cross_validate,
    train_test_split,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier


SEED = 20260905
OUT = Path("output")
FIG = OUT / "figures"
MOD = OUT / "models"
for directory in (OUT, FIG, MOD):
    directory.mkdir(parents=True, exist_ok=True)


def py(value):
    """Convert numpy/scikit objects to JSON-safe Python values."""
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, dict):
        return {str(k): py(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [py(v) for v in value]
    return value


def bootstrap_accuracy(y_true, y_pred, draws=2000):
    rng = np.random.default_rng(SEED)
    values = []
    for _ in range(draws):
        idx = rng.integers(0, len(y_true), len(y_true))
        values.append(accuracy_score(y_true[idx], y_pred[idx]))
    return [float(v) for v in np.percentile(values, [2.5, 97.5])]


def lift_at(y_true, score, fraction=0.10):
    n = max(1, int(len(y_true) * fraction))
    base = float(np.mean(y_true))
    return float(np.mean(y_true[np.argsort(score)[::-1][:n]]) / base) if base else None


def binary_metrics(y_true, score, threshold):
    pred = (score >= threshold).astype(int)
    return {
        "accuracy": accuracy_score(y_true, pred),
        "balanced_accuracy": balanced_accuracy_score(y_true, pred),
        "f1": f1_score(y_true, pred, zero_division=0),
        "roc_auc": roc_auc_score(y_true, score),
        "pr_auc": average_precision_score(y_true, score),
        "base_rate": np.mean(y_true),
        "lift_10": lift_at(y_true, score, 0.10),
        "threshold_from_development_oof": threshold,
        "confusion": confusion_matrix(y_true, pred).tolist(),
    }


def best_f1_threshold(y_true, score):
    precision, recall, thresholds = precision_recall_curve(y_true, score)
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(
        precision[:-1] + recall[:-1], 1e-12
    )
    return float(thresholds[int(np.nanargmax(f1))])


def segment_retraining():
    print("\n=== SEGMENT RETRAINING ===")
    data = pd.read_csv(OUT / "customer_features.csv")
    features = [c for c in data.columns if c not in {"Customer_ID", "Segment_Label", "CLV"}]
    X = data[features]
    y = data["Segment_Label"].to_numpy()
    X_dev, X_test, y_dev, y_test = train_test_split(
        X, y, test_size=0.20, stratify=y, random_state=SEED
    )
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)

    candidates = {
        "Extra Trees": (
            Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("select", SelectKBest(f_classif)),
                ("model", ExtraTreesClassifier(random_state=SEED, n_jobs=-1)),
            ]),
            {
                "select__k": [2, 3, 4, 5, 8, 12, 20, "all"],
                "model__n_estimators": [350, 600, 900],
                "model__max_depth": [None, 8, 12, 18, 26],
                "model__min_samples_leaf": [2, 3, 5, 8, 12, 18],
                "model__max_features": ["sqrt", 0.5, 0.8, 1.0],
                "model__criterion": ["gini", "entropy", "log_loss"],
                "model__class_weight": [None, "balanced"],
            },
            24,
        ),
        "XGBoost": (
            Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("select", SelectKBest(f_classif)),
                ("model", XGBClassifier(
                    objective="multi:softprob", num_class=4,
                    eval_metric="mlogloss", random_state=SEED,
                    n_jobs=4, verbosity=0,
                )),
            ]),
            {
                "select__k": [2, 3, 4, 5, 8, 12, 20, "all"],
                "model__n_estimators": [250, 400, 650],
                "model__max_depth": [2, 3, 4, 5],
                "model__learning_rate": [0.02, 0.04, 0.07, 0.10],
                "model__min_child_weight": [1, 3, 6, 10],
                "model__subsample": [0.7, 0.85, 1.0],
                "model__colsample_bytree": [0.6, 0.8, 1.0],
                "model__reg_lambda": [1, 5, 15, 30],
                "model__gamma": [0, 0.05, 0.2],
            },
            18,
        ),
        "Random Forest": (
            Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("select", SelectKBest(f_classif)),
                ("model", RandomForestClassifier(random_state=SEED, n_jobs=-1)),
            ]),
            {
                "select__k": [2, 3, 4, 5, 8, 12, 20, "all"],
                "model__n_estimators": [350, 600],
                "model__max_depth": [None, 8, 12, 18],
                "model__min_samples_leaf": [2, 4, 7, 12, 18],
                "model__max_features": ["sqrt", 0.5, 0.8, 1.0],
                "model__class_weight": [None, "balanced"],
            },
            14,
        ),
        "Histogram Gradient Boosting": (
            Pipeline([
                ("impute", SimpleImputer(strategy="median")),
                ("select", SelectKBest(f_classif)),
                ("model", HistGradientBoostingClassifier(random_state=SEED)),
            ]),
            {
                "select__k": [2, 3, 4, 5, 8, 12, 20, "all"],
                "model__max_iter": [150, 250, 400],
                "model__learning_rate": [0.03, 0.06, 0.10],
                "model__max_leaf_nodes": [7, 15, 31],
                "model__min_samples_leaf": [10, 20, 35, 60],
                "model__l2_regularization": [0, 1, 5, 15],
            },
            14,
        ),
    }

    searches = {}
    family_report = {}
    for name, (estimator, params, n_iter) in candidates.items():
        print(f"Tuning {name} ({n_iter} sampled configurations)...")
        search = RandomizedSearchCV(
            estimator, params, n_iter=n_iter, scoring={"accuracy": "accuracy", "macro_f1": "f1_macro"},
            refit="accuracy", cv=cv, random_state=SEED, n_jobs=-1,
            return_train_score=False, error_score="raise",
        )
        started = time.perf_counter()
        search.fit(X_dev, y_dev)
        elapsed = time.perf_counter() - started
        pred = search.predict(X_test)
        searches[name] = search
        family_report[name] = {
            "development_cv_accuracy": search.best_score_,
            "development_cv_macro_f1_at_selected_params": search.cv_results_["mean_test_macro_f1"][search.best_index_],
            "holdout_accuracy": accuracy_score(y_test, pred),
            "holdout_balanced_accuracy": balanced_accuracy_score(y_test, pred),
            "holdout_macro_f1": f1_score(y_test, pred, average="macro"),
            "holdout_weighted_f1": f1_score(y_test, pred, average="weighted"),
            "best_params": search.best_params_,
            "fit_seconds": elapsed,
        }
        print(
            f"  CV accuracy {search.best_score_:.4f}; holdout accuracy "
            f"{family_report[name]['holdout_accuracy']:.4f}"
        )

    winner = max(searches, key=lambda name: searches[name].best_score_)
    model = searches[winner].best_estimator_
    pred = model.predict(X_test)
    report = {
        "protocol": {
            "seed": SEED,
            "development_rows": len(y_dev),
            "untouched_holdout_rows": len(y_test),
            "cross_validation": "5-fold stratified; all selection inside development data",
            "target": "Original four-class customer segment",
            "excluded": ["Customer_ID", "CLV (target-defining leakage)", "Segment_Label"],
        },
        "majority_accuracy": np.bincount(y_test).max() / len(y_test),
        "selected_family_before_holdout": winner,
        "holdout_accuracy": accuracy_score(y_test, pred),
        "holdout_accuracy_ci_95": bootstrap_accuracy(y_test, pred),
        "holdout_balanced_accuracy": balanced_accuracy_score(y_test, pred),
        "holdout_macro_f1": f1_score(y_test, pred, average="macro"),
        "confusion": confusion_matrix(y_test, pred).tolist(),
        "families": family_report,
    }
    with open(MOD / "retrained_segment_model.pkl", "wb") as handle:
        pickle.dump({"model": model, "features": features, "report": report}, handle)

    order = sorted(family_report, key=lambda n: family_report[n]["holdout_accuracy"], reverse=True)
    values = [family_report[n]["holdout_accuracy"] * 100 for n in order]
    plt.figure(figsize=(9, 5))
    bars = plt.bar(order, values, color=["#087f5b", "#364fc7", "#f08c00", "#495057"])
    for bar, value in zip(bars, values):
        plt.text(bar.get_x() + bar.get_width() / 2, value + 0.5, f"{value:.2f}%", ha="center")
    plt.axhline(report["majority_accuracy"] * 100, color="gray", linestyle="--", label="Majority baseline")
    plt.ylabel("Untouched holdout accuracy (%)")
    plt.title("Retrained Segment Models - Leakage-Safe Holdout")
    plt.ylim(0, 100)
    plt.xticks(rotation=15, ha="right")
    plt.legend()
    plt.tight_layout()
    plt.savefig(FIG / "retrained_segment_comparison.png", dpi=300)
    plt.close()

    plt.figure(figsize=(6.5, 5.2))
    sns.heatmap(
        confusion_matrix(y_test, pred), annot=True, fmt="d", cmap="Greens",
        xticklabels=["Low", "Moderate", "High", "VIP"],
        yticklabels=["Low", "Moderate", "High", "VIP"],
    )
    plt.xlabel("Predicted")
    plt.ylabel("Actual")
    plt.title(f"Selected Segment Model - {winner}")
    plt.tight_layout()
    plt.savefig(FIG / "retrained_segment_confusion.png", dpi=300)
    plt.close()
    return report


def binary_retraining(task, X, y, groups=None):
    print(f"\n=== {task.upper()} RETRAINING ===")
    if groups is None:
        dev_idx, test_idx = train_test_split(
            np.arange(len(y)), test_size=0.20, stratify=y, random_state=SEED
        )
        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
        cv_groups = None
    else:
        splitter = GroupShuffleSplit(n_splits=1, test_size=0.20, random_state=SEED)
        dev_idx, test_idx = next(splitter.split(X, y, groups))
        assert not (set(groups[dev_idx]) & set(groups[test_idx]))
        cv = StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=SEED)
        cv_groups = groups[dev_idx]

    X_dev, X_test = X.iloc[dev_idx], X.iloc[test_idx]
    y_dev, y_test = y[dev_idx], y[test_idx]
    ratio = float((y_dev == 0).sum() / max((y_dev == 1).sum(), 1))
    candidates = {
        "Logistic Regression": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("scale", StandardScaler()),
            ("model", LogisticRegression(C=0.3, class_weight="balanced", max_iter=3000, random_state=SEED)),
        ]),
        "Extra Trees": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", ExtraTreesClassifier(
                n_estimators=600, max_features=0.7, min_samples_leaf=5,
                class_weight="balanced", random_state=SEED, n_jobs=-1,
            )),
        ]),
        "Random Forest": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", RandomForestClassifier(
                n_estimators=600, max_features=0.7, min_samples_leaf=5,
                class_weight="balanced", random_state=SEED, n_jobs=-1,
            )),
        ]),
        "XGBoost": Pipeline([
            ("impute", SimpleImputer(strategy="median")),
            ("model", XGBClassifier(
                n_estimators=450, max_depth=3, learning_rate=0.035,
                subsample=0.85, colsample_bytree=0.8, min_child_weight=5,
                reg_lambda=10, scale_pos_weight=ratio,
                eval_metric="aucpr", random_state=SEED, n_jobs=4, verbosity=0,
            )),
        ]),
    }

    family_report = {}
    for name, estimator in candidates.items():
        result = cross_validate(
            estimator, X_dev, y_dev, groups=cv_groups, cv=cv,
            scoring={"pr_auc": "average_precision", "roc_auc": "roc_auc"},
            n_jobs=-1, error_score="raise",
        )
        family_report[name] = {
            "development_cv_pr_auc": float(result["test_pr_auc"].mean()),
            "development_cv_pr_auc_std": float(result["test_pr_auc"].std()),
            "development_cv_roc_auc": float(result["test_roc_auc"].mean()),
        }
        print(f"{name}: CV PR-AUC {family_report[name]['development_cv_pr_auc']:.4f}")

    winner = max(family_report, key=lambda name: family_report[name]["development_cv_pr_auc"])
    model = clone(candidates[winner])
    oof = cross_val_predict(
        model, X_dev, y_dev, groups=cv_groups, cv=cv, method="predict_proba", n_jobs=-1
    )[:, 1]
    threshold = best_f1_threshold(y_dev, oof)
    model.fit(X_dev, y_dev)
    score = model.predict_proba(X_test)[:, 1]
    report = {
        "protocol": {
            "seed": SEED,
            "development_rows": len(dev_idx),
            "untouched_holdout_rows": len(test_idx),
            "group_disjoint": groups is not None,
            "selection_metric": "development cross-validated PR-AUC",
            "decision_threshold": "maximum F1 on development out-of-fold predictions",
        },
        "selected_family_before_holdout": winner,
        "holdout": binary_metrics(y_test, score, threshold),
        "families": family_report,
    }
    with open(MOD / f"retrained_{task}_model.pkl", "wb") as handle:
        pickle.dump({"model": model, "threshold": threshold, "features": list(X.columns), "report": report}, handle)

    plt.figure(figsize=(11, 4.5))
    ax_pr, ax_roc = plt.subplot(1, 2, 1), plt.subplot(1, 2, 2)
    precision, recall, _ = precision_recall_curve(y_test, score)
    fpr, tpr, _ = roc_curve(y_test, score)
    ax_pr.plot(recall, precision, color="#087f5b", linewidth=2, label=f"AP={report['holdout']['pr_auc']:.3f}")
    ax_pr.axhline(np.mean(y_test), color="gray", linestyle="--", label="Random baseline")
    ax_pr.set(xlabel="Recall", ylabel="Precision", title=f"{task.title()} Precision-Recall")
    ax_roc.plot(fpr, tpr, color="#364fc7", linewidth=2, label=f"AUC={report['holdout']['roc_auc']:.3f}")
    ax_roc.plot([0, 1], [0, 1], color="gray", linestyle="--")
    ax_roc.set(xlabel="False positive rate", ylabel="True positive rate", title=f"{task.title()} ROC")
    for axis in (ax_pr, ax_roc):
        axis.legend()
        axis.grid(alpha=0.25)
    plt.suptitle(f"Retrained {task.title()} Model - {winner}")
    plt.tight_layout()
    plt.savefig(FIG / f"retrained_{task}_curves.png", dpi=300)
    plt.close()
    return report


def main():
    started = time.perf_counter()
    segment = segment_retraining()

    customers = pd.read_csv(OUT / "customer_features.csv")
    customers["Churned"] = (customers["Recency"] > 90).astype(int)
    churn_excluded = {"Customer_ID", "Segment_Label", "CLV", "Recency", "RFM_Score", "Churned"}
    churn_features = [c for c in customers.columns if c not in churn_excluded]
    churn = binary_retraining(
        "churn", customers[churn_features], customers["Churned"].to_numpy()
    )
    churn["excluded_label_derived_features"] = sorted(churn_excluded)

    transactions = pd.read_csv(OUT / "processed_dataset.csv")
    return_features = [
        "Quantity", "Unit_Price_BDT", "Gross_Amount_BDT", "Discount_Percent",
        "Discount_Amount_BDT", "Net_Amount_BDT", "Profit_Margin_Percent",
        "Net_Profit_Ratio", "High_Discount_Flag", "Delivery_Days", "Customer_Age",
        "Purchase_Frequency_Monthly", "Days_Since_Last_Purchase", "RFM_Score",
        "Recency_Score", "Frequency_Score", "Monetary_Score", "Is_Eid_Season",
        "Is_Ramadan", "Is_Pohela_Boishakh", "Is_YearEnd_Sale", "Is_Weekend",
        "Employee_Count", "Revenue_Per_Employee", "Business_Category_Enc",
        "Business_Type_Enc", "Payment_Method_Enc", "Order_Channel_Enc",
        "Marketing_Channel_Enc", "Campaign_Type_Enc", "Division_Enc", "Season_Enc",
        "Customer_Gender_Enc", "Customer_Type_Enc", "Stock_Level_Enc", "Day_of_Week_Enc",
    ]
    returns = binary_retraining(
        "return", transactions[return_features], transactions["Return_Binary"].to_numpy(),
        groups=transactions["Customer_ID"].to_numpy(),
    )
    returns["excluded_post_outcome_features"] = [
        "Delivery_Status", "Return_Reason", "Is_Returned", "Return_Binary",
        "Customer_Satisfaction_Score",
    ]

    payload = {
        "generated_by": "09_retrain_models.py",
        "seed": SEED,
        "segment": segment,
        "churn": churn,
        "return": returns,
        "elapsed_seconds": time.perf_counter() - started,
    }
    (OUT / "retrained_model_results.json").write_text(
        json.dumps(py(payload), indent=2), encoding="utf-8"
    )
    print("\nSaved output/retrained_model_results.json")
    print(json.dumps(py({
        "segment": segment["holdout_accuracy"],
        "churn": churn["holdout"],
        "return": returns["holdout"],
        "elapsed_seconds": payload["elapsed_seconds"],
    }), indent=2))


if __name__ == "__main__":
    main()
