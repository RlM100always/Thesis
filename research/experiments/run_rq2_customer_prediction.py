"""Leakage-conscious customer inactivity model comparison.

Raw snapshots remain outside Git. Outputs contain aggregate metrics only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    balanced_accuracy_score,
    brier_score_loss,
    f1_score,
    precision_recall_curve,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

SEED = 20261109
TARGET = "inactive_next_90d_label"
NUMERIC = [
    "recency_days",
    "orders_last_30d",
    "orders_last_90d",
    "orders_last_180d",
    "sales_last_90d_bdt",
    "mean_basket_last_90d_bdt",
    "lifetime_orders_so_far",
    "tenure_days",
    "snapshot_month_sin",
    "snapshot_month_cos",
]
CATEGORICAL = ["home_shop_id"]


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def prepare(path: Path, orders_path: Path) -> tuple[pd.DataFrame, dict]:
    frame = pd.read_csv(path, parse_dates=["snapshot_date", "horizon_end"])
    required = {
        "snapshot_id", "customer_id", "home_shop_id", "snapshot_date",
        "horizon_end", TARGET, "split", *NUMERIC[:8],
    }
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    if frame["snapshot_id"].duplicated().any():
        raise ValueError("Duplicate snapshot_id values found.")
    if not set(frame["split"].dropna().unique()) <= {"TRAIN", "TEST"}:
        raise ValueError("Unexpected split values.")
    if not set(frame[TARGET].dropna().unique()) <= {0, 1}:
        raise ValueError("Target must be binary.")
    if frame[list(NUMERIC[:8])].isna().any().any() or frame[CATEGORICAL].isna().any().any():
        raise ValueError("Missing feature values require documented handling.")
    horizon_days = (frame["horizon_end"] - frame["snapshot_date"]).dt.days
    if not horizon_days.eq(90).all():
        raise ValueError("Snapshot outcome windows are not uniformly 90 days.")
    orders = pd.read_csv(
        orders_path, usecols=["customer_id", "order_datetime"], parse_dates=["order_datetime"]
    )
    orders["order_date"] = orders["order_datetime"].dt.normalize()
    by_customer = {
        str(customer): np.sort(group["order_date"].to_numpy(dtype="datetime64[D]"))
        for customer, group in orders.dropna(subset=["customer_id"]).groupby("customer_id", sort=False)
    }
    observed_future_order_counts = np.zeros(len(frame), dtype=np.int32)
    missing_customer_order_history = 0
    for i, row in enumerate(frame[["customer_id", "snapshot_date", "horizon_end"]].itertuples(index=False, name=None)):
        customer, cutoff, horizon_end = row
        dates_for_customer = by_customer.get(str(customer))
        if dates_for_customer is None:
            missing_customer_order_history += 1
            continue
        start_day = np.datetime64(cutoff.date())
        end_day = np.datetime64(horizon_end.date())
        observed_future_order_counts[i] = (
            np.searchsorted(dates_for_customer, end_day, side="right")
            - np.searchsorted(dates_for_customer, start_day, side="right")
        )
    reconstructed_label = (observed_future_order_counts == 0).astype(np.int8)
    label_mismatches = int(
        np.count_nonzero(reconstructed_label != frame[TARGET].to_numpy(dtype=np.int8))
    )
    if missing_customer_order_history:
        raise ValueError(f"{missing_customer_order_history} snapshots have no source-order history.")
    if label_mismatches:
        raise ValueError(f"Provided inactivity target disagrees with future source orders in {label_mismatches} rows.")
    # Calendar features are known at the snapshot cutoff.
    month_angle = 2 * np.pi * (frame["snapshot_date"].dt.month - 1) / 12
    frame["snapshot_month_sin"] = np.sin(month_angle)
    frame["snapshot_month_cos"] = np.cos(month_angle)
    train = frame[frame["split"].eq("TRAIN")]
    test = frame[frame["split"].eq("TEST")]
    if train.empty or test.empty:
        raise ValueError("Both supplied TRAIN and TEST splits must be non-empty.")
    customer_overlap = len(set(train["customer_id"]) & set(test["customer_id"]))
    summary = {
        "rows": int(len(frame)),
        "train_rows": int(len(train)),
        "test_rows": int(len(test)),
        "customers": int(frame["customer_id"].nunique()),
        "train_customers": int(train["customer_id"].nunique()),
        "test_customers": int(test["customer_id"].nunique()),
        "customers_in_both_splits": int(customer_overlap),
        "train_target_rate": float(train[TARGET].mean()),
        "test_target_rate": float(test[TARGET].mean()),
        "train_snapshot_min": str(train["snapshot_date"].min().date()),
        "train_snapshot_max": str(train["snapshot_date"].max().date()),
        "test_snapshot_min": str(test["snapshot_date"].min().date()),
        "test_snapshot_max": str(test["snapshot_date"].max().date()),
        "train_horizon_end_max": str(train["horizon_end"].max().date()),
        "label_validation": {
            "source": orders_path.name,
            "rule": "inactive=1 iff no customer order occurs after snapshot_date and on/before horizon_end",
            "horizon_days": 90,
            "missing_customer_order_history": int(missing_customer_order_history),
            "label_mismatches": label_mismatches,
            "recomputed_positive_label_rows": int(reconstructed_label.sum()),
        },
    }
    return frame, summary


def make_models() -> dict:
    numeric_lr = Pipeline([
        ("imputer", SimpleImputer(strategy="median")),
        ("scale", StandardScaler()),
    ])
    pre_lr = ColumnTransformer([
        ("numeric", numeric_lr, NUMERIC),
        ("categorical", OneHotEncoder(handle_unknown="ignore"), CATEGORICAL),
    ])
    pre_tree = ColumnTransformer([
        ("numeric", SimpleImputer(strategy="median"), NUMERIC),
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CATEGORICAL),
    ])
    return {
        "logistic_regression": Pipeline([
            ("prep", pre_lr),
            ("model", LogisticRegression(C=0.5, max_iter=1200, random_state=SEED)),
        ]),
        "hist_gradient_boosting": Pipeline([
            ("prep", pre_tree),
            ("model", HistGradientBoostingClassifier(
                learning_rate=0.06,
                max_iter=140,
                max_leaf_nodes=15,
                min_samples_leaf=40,
                l2_regularization=5.0,
                random_state=SEED,
            )),
        ]),
        "random_forest": Pipeline([
            ("prep", pre_tree),
            ("model", RandomForestClassifier(
                n_estimators=160,
                max_depth=14,
                min_samples_leaf=20,
                max_features=0.8,
                n_jobs=-1,
                random_state=SEED,
            )),
        ]),
    }


def best_f1_threshold(y: np.ndarray, p: np.ndarray) -> float:
    precision, recall, thresholds = precision_recall_curve(y, p)
    if not len(thresholds):
        return 0.5
    f1 = 2 * precision[:-1] * recall[:-1] / np.maximum(precision[:-1] + recall[:-1], 1e-12)
    return float(thresholds[int(np.nanargmax(f1))])


def ece_10(y: np.ndarray, p: np.ndarray) -> float:
    edges = np.linspace(0, 1, 11)
    bins = np.digitize(p, edges[1:-1], right=True)
    total = len(y)
    value = 0.0
    for bucket in range(10):
        mask = bins == bucket
        if mask.any():
            value += mask.sum() / total * abs(float(y[mask].mean()) - float(p[mask].mean()))
    return float(value)


def metrics(y: np.ndarray, p: np.ndarray, threshold: float, prevalence: float) -> dict:
    pred = p >= threshold
    top_n = max(1, int(np.ceil(len(p) * 0.10)))
    top = np.argpartition(p, -top_n)[-top_n:]
    top_precision = float(y[top].mean())
    return {
        "n": int(len(y)),
        "prevalence": float(y.mean()),
        "average_precision": float(average_precision_score(y, p)),
        "roc_auc": float(roc_auc_score(y, p)),
        "brier_score": float(brier_score_loss(y, p)),
        "ece_10_equal_width": ece_10(y, p),
        "threshold": float(threshold),
        "precision": float(precision_score(y, pred, zero_division=0)),
        "recall": float(recall_score(y, pred, zero_division=0)),
        "f1": float(f1_score(y, pred, zero_division=0)),
        "balanced_accuracy": float(balanced_accuracy_score(y, pred)),
        "precision_at_top_10pct": top_precision,
        "lift_at_top_10pct": float(top_precision / prevalence) if prevalence else None,
    }


def cluster_bootstrap_ap(y: np.ndarray, p: np.ndarray, groups: np.ndarray, baseline_p: float) -> dict:
    """Customer-cluster bootstrap; repeated snapshots stay in their sampled cluster."""
    rng = np.random.default_rng(SEED)
    unique, inverse = np.unique(groups, return_inverse=True)
    reps = 300
    model_ap, baseline_ap, delta = [], [], []
    for _ in range(reps):
        sampled = rng.integers(0, len(unique), size=len(unique))
        counts = np.bincount(sampled, minlength=len(unique))
        weights = counts[inverse]
        if weights.sum() == 0 or np.dot(weights, y) == 0:
            continue
        a = float(average_precision_score(y, p, sample_weight=weights))
        b = float(average_precision_score(y, np.full(len(y), baseline_p), sample_weight=weights))
        model_ap.append(a)
        baseline_ap.append(b)
        delta.append(a - b)
    return {
        "unit": "customer_id cluster",
        "replicates_requested": reps,
        "replicates_used": len(delta),
        "selected_model_average_precision_95pct_ci": [
            float(np.quantile(model_ap, 0.025)), float(np.quantile(model_ap, 0.975))
        ],
        "constant_train_prevalence_average_precision_95pct_ci": [
            float(np.quantile(baseline_ap, 0.025)), float(np.quantile(baseline_ap, 0.975))
        ],
        "paired_ap_difference_95pct_ci": [
            float(np.quantile(delta, 0.025)), float(np.quantile(delta, 0.975))
        ],
        "paired_ap_difference_mean": float(np.mean(delta)),
    }


def run(data_dir: Path, out: Path) -> None:
    source = data_dir / "rq2_customer_snapshots_90d.csv"
    orders_source = data_dir / "sales_orders.csv"
    if not source.exists() or not orders_source.exists():
        raise FileNotFoundError("RQ2 snapshots and source sales_orders.csv are both required.")
    out.mkdir(parents=True, exist_ok=True)
    frame, data_summary = prepare(source, orders_source)
    train = frame[frame["split"].eq("TRAIN")].copy()
    test = frame[frame["split"].eq("TEST")].copy()
    last_train_date = train["snapshot_date"].max()
    fit = train[train["snapshot_date"] < last_train_date]
    validation = train[train["snapshot_date"].eq(last_train_date)]
    if fit.empty or validation.empty:
        raise ValueError("Could not form an earlier-train / latest-cohort validation split.")

    X_fit, y_fit = fit[NUMERIC + CATEGORICAL], fit[TARGET].to_numpy(dtype=int)
    X_val, y_val = validation[NUMERIC + CATEGORICAL], validation[TARGET].to_numpy(dtype=int)
    X_train, y_train = train[NUMERIC + CATEGORICAL], train[TARGET].to_numpy(dtype=int)
    X_test, y_test = test[NUMERIC + CATEGORICAL], test[TARGET].to_numpy(dtype=int)
    prevalence = float(y_train.mean())
    validation_rows = []
    test_rows = []
    predictions = {}
    thresholds = {}

    constant_validation = np.full(len(y_val), prevalence)
    validation_rows.append({
        "model": "constant_train_prevalence",
        "validation_cohort_date": str(last_train_date.date()),
        **metrics(y_val, constant_validation, 0.5, float(y_val.mean())),
    })

    for name, model in make_models().items():
        model.fit(X_fit, y_fit)
        val_probability = model.predict_proba(X_val)[:, 1]
        threshold = best_f1_threshold(y_val, val_probability)
        thresholds[name] = threshold
        validation_rows.append({
            "model": name,
            "validation_cohort_date": str(last_train_date.date()),
            **metrics(y_val, val_probability, threshold, float(y_val.mean())),
        })
        model.fit(X_train, y_train)
        probability = model.predict_proba(X_test)[:, 1]
        predictions[name] = probability
        test_rows.append({
            "model": name,
            "threshold_selected_on_validation": threshold,
            **metrics(y_test, probability, threshold, float(y_test.mean())),
            "precision_recall_at_fixed_0_5_f1": float(f1_score(y_test, probability >= 0.5, zero_division=0)),
        })

    validation_frame = pd.DataFrame(validation_rows)
    candidates = validation_frame[validation_frame["model"].ne("constant_train_prevalence")]
    selected = str(candidates.sort_values(
        ["average_precision", "brier_score"], ascending=[False, True]
    ).iloc[0]["model"])
    test_rows.insert(0, {
        "model": "constant_train_prevalence",
        "threshold_selected_on_validation": 0.5,
        **metrics(y_test, np.full(len(y_test), prevalence), 0.5, float(y_test.mean())),
        "precision_recall_at_fixed_0_5_f1": float(f1_score(y_test, np.full(len(y_test), prevalence) >= 0.5, zero_division=0)),
    })
    test_frame = pd.DataFrame(test_rows)
    selected_probs = predictions[selected]
    ci = cluster_bootstrap_ap(
        y_test, selected_probs, test["customer_id"].astype(str).to_numpy(), prevalence
    )
    ci["selected_model"] = selected
    selected_row = test_frame.loc[test_frame["model"].eq(selected)].iloc[0].to_dict()
    ci["observed_test_average_precision"] = float(selected_row["average_precision"])
    ci["observed_constant_baseline_average_precision"] = float(
        test_frame.loc[test_frame["model"].eq("constant_train_prevalence"), "average_precision"].iloc[0]
    )

    # Calibration table is descriptive only; no test-set recalibration is performed.
    bins = pd.qcut(pd.Series(selected_probs), q=10, labels=False, duplicates="drop")
    reliability = pd.DataFrame({
        "probability": selected_probs,
        "label": y_test,
        "bin": bins,
    }).groupby("bin", as_index=False).agg(
        n=("label", "size"),
        mean_predicted_probability=("probability", "mean"),
        observed_inactivity_rate=("label", "mean"),
    )
    reliability.to_csv(out / "reliability_bins.csv", index=False)
    validation_frame.to_csv(out / "validation_metrics.csv", index=False)
    test_frame.to_csv(out / "test_metrics.csv", index=False)
    (out / "cluster_bootstrap.json").write_text(json.dumps(ci, indent=2), encoding="utf-8")
    manifest = {
        "experiment": "RQ2 customer inactivity prediction",
        "protocol": "supplied temporal TRAIN/TEST split; latest TRAIN snapshot cohort used for model selection and threshold selection; final fits use all TRAIN rows; TEST evaluated once",
        "label": "no repeat purchase during the following 90-day window, as supplied",
        "features": NUMERIC + CATEGORICAL,
        "excluded_features": ["customer_id", "snapshot_id", "horizon_end", "split"],
        "validation_date": str(last_train_date.date()),
        "selected_model_by_validation_average_precision": selected,
        "selected_threshold": thresholds[selected],
        "data_audit": data_summary,
        "input": {"file": source.name, "sha256": sha256(source)},
        "label_source": {"file": orders_source.name, "sha256": sha256(orders_source)},
        "output_files": ["validation_metrics.csv", "test_metrics.csv", "reliability_bins.csv", "cluster_bootstrap.json"],
        "seed": SEED,
        "python": platform.python_version(),
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "scikit_learn": sklearn.__version__,
        "raw_customer_ids_written": False,
        "caveat": "This evaluates the supplied snapshots and target; it does not establish real-world retention impact or independently verify source provenance.",
    }
    (out / "run_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(json.dumps({
        "data_audit": data_summary,
        "selected_model": selected,
        "validation": validation_frame.to_dict(orient="records"),
        "test": test_frame.to_dict(orient="records"),
        "cluster_bootstrap": ci,
    }, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("research/experiments/results/rq2_customer_prediction"))
    args = parser.parse_args()
    run(args.data_dir, args.output_dir)


if __name__ == "__main__":
    main()
