"""RQ2 v2: train-only threshold refinement for 90-day customer inactivity.

Run the three stages in order: select, threshold, score. The supplied chronological
split is preserved. Stage 1 compares CatBoost's original snapshot features with
a past-only trajectory extension on the first two TRAIN origins. Stage 2 fits
calibration on those origins and selects the operating threshold on the final
TRAIN origin. Stage 3 fits on all TRAIN and evaluates TEST once. Only aggregate
outputs are written; no customer-level predictions or identifiers are exported.
"""
from __future__ import annotations

import argparse
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from sklearn.metrics import (
    average_precision_score, balanced_accuracy_score, brier_score_loss,
    confusion_matrix, f1_score, fbeta_score, precision_recall_curve,
    precision_score, recall_score, roc_auc_score, roc_curve,
)
from research.experiments.rq2_customer_prediction import (
    CATEGORICAL, FEATURES, VALIDATION_DATES, apply_platt, cluster_bootstrap,
    fit_catboost, fit_platt, load_data, sha256,
)

LAG_SOURCE = [
    "recency_days", "orders_last_30d", "orders_last_90d", "orders_last_180d",
    "sales_last_90d_bdt", "lifetime_orders_so_far", "tenure_days",
]


def prepare_features(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.sort_values(["customer_id", "snapshot_date"], kind="stable").copy()
    frame["avg_gap_days"] = frame["tenure_days"] / np.maximum(frame["lifetime_orders_so_far"] - 1, 1)
    frame["recency_vs_avg_gap"] = frame["recency_days"] / (frame["avg_gap_days"] + 1)
    for column in LAG_SOURCE:
        previous = frame.groupby("customer_id", sort=False)[column].shift(1)
        frame[f"prev_{column}"] = previous
        frame[f"delta_{column}"] = frame[column] - previous
        frame[f"ratio_{column}"] = (frame[column] + 1) / (previous + 1)
    return frame


def feature_list(variant: str) -> list[str]:
    if variant == "baseline":
        return FEATURES
    return FEATURES + ["avg_gap_days", "recency_vs_avg_gap"] + [
        f"{prefix}_{column}" for column in LAG_SOURCE
        for prefix in ("prev", "delta", "ratio")
    ]


def fit_variant(variant: str, train: pd.DataFrame, valid: pd.DataFrame, features: list[str]):
    x_train, x_valid = train[features].copy(), valid[features].copy()
    y_train = train["target"].to_numpy(dtype=int)
    if variant == "baseline":
        model, _ = fit_catboost(x_train, y_train)
    else:
        model = CatBoostClassifier(
            iterations=250, depth=4, learning_rate=0.04, l2_leaf_reg=8,
            loss_function="Logloss", eval_metric="PRAUC", random_seed=42,
            verbose=False, allow_writing_files=False, thread_count=2,
        )
        for column in CATEGORICAL:
            x_train[column] = x_train[column].fillna("UNKNOWN").astype(str)
            x_valid[column] = x_valid[column].fillna("UNKNOWN").astype(str)
        model.fit(x_train, y_train, cat_features=CATEGORICAL)
        return model, model.predict_proba(x_valid)[:, 1]
    for column in CATEGORICAL:
        x_valid[column] = x_valid[column].fillna("UNKNOWN").astype(str)
    return model, model.predict_proba(x_valid)[:, 1]


def fit_final_variant(variant: str, train: pd.DataFrame, features: list[str]):
    x_train = train[features].copy()
    y_train = train["target"].to_numpy(dtype=int)
    if variant == "baseline":
        model, _ = fit_catboost(x_train, y_train)
    else:
        model = CatBoostClassifier(
            iterations=250, depth=4, learning_rate=0.04, l2_leaf_reg=8,
            loss_function="Logloss", eval_metric="PRAUC", random_seed=42,
            verbose=False, allow_writing_files=False, thread_count=2,
        )
        for column in CATEGORICAL:
            x_train[column] = x_train[column].fillna("UNKNOWN").astype(str)
        model.fit(x_train, y_train, cat_features=CATEGORICAL)
    return model


def apply_platt_parameters(raw, coefficient: float, intercept: float):
    raw = np.clip(np.asarray(raw, dtype=float), 1e-6, 1 - 1e-6)
    logits = np.log(raw / (1 - raw)) * coefficient + intercept
    return 1 / (1 + np.exp(-np.clip(logits, -35, 35)))


def classification_metrics(y, probability, threshold):
    y = np.asarray(y, dtype=int)
    probability = np.asarray(probability, dtype=float)
    predicted = probability >= float(threshold)
    tn, fp, fn, tp = confusion_matrix(y, predicted, labels=[0, 1]).ravel()
    result = {
        "n": int(len(y)), "positive_rate": float(y.mean()),
        "pr_auc": float(average_precision_score(y, probability)),
        "roc_auc": float(roc_auc_score(y, probability)),
        "brier": float(brier_score_loss(y, probability)),
        "threshold": float(threshold),
        "precision": float(precision_score(y, predicted, zero_division=0)),
        "recall": float(recall_score(y, predicted, zero_division=0)),
        "f1": float(f1_score(y, predicted, zero_division=0)),
        "f2": float(fbeta_score(y, predicted, beta=2, zero_division=0)),
        "specificity": float(tn / max(1, tn + fp)),
        "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
        "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp),
        "predicted_positive": int(predicted.sum()),
    }
    for fraction in (0.10, 0.20):
        count = max(1, int(np.ceil(len(y) * fraction)))
        selected = np.argsort(-probability)[:count]
        precision_at_k = float(y[selected].mean())
        result[f"precision_at_{int(fraction * 100)}pct"] = precision_at_k
        result[f"recall_at_{int(fraction * 100)}pct"] = float(y[selected].sum() / max(1, y.sum()))
        result[f"lift_at_{int(fraction * 100)}pct"] = precision_at_k / float(y.mean())
    return result


def choose_threshold(y, probability, objective: str, recall_floor: float | None = None):
    precision, recall, thresholds = precision_recall_curve(y, probability)
    precision, recall = precision[:-1], recall[:-1]
    f1 = 2 * precision * recall / np.maximum(precision + recall, 1e-12)
    f2 = 5 * precision * recall / np.maximum(4 * precision + recall, 1e-12)
    if objective == "f1":
        scores = f1
        candidates = np.flatnonzero(np.isclose(scores, scores.max()))
        index = candidates[np.argmax(thresholds[candidates])]
    elif objective == "f2":
        scores = f2
        candidates = np.flatnonzero(np.isclose(scores, scores.max()))
        index = candidates[np.argmax(thresholds[candidates])]
    elif objective == "precision_at_recall_floor":
        candidates = np.flatnonzero(recall >= float(recall_floor))
        if not len(candidates):
            raise ValueError(f"No threshold meets recall floor {recall_floor}")
        best_precision = precision[candidates].max()
        candidates = candidates[np.isclose(precision[candidates], best_precision)]
        index = candidates[np.argmax(thresholds[candidates])]
    else:
        raise ValueError(objective)
    threshold = float(thresholds[index])
    row = classification_metrics(y, probability, threshold)
    row["threshold_objective"] = objective
    row["recall_floor"] = recall_floor
    return threshold, row


def model_selection_metrics(y, probability):
    result = {
        "n": int(len(y)),
        "positive_rate": float(np.mean(y)),
        "pr_auc": float(average_precision_score(y, probability)),
        "roc_auc": float(roc_auc_score(y, probability)),
        "brier": float(brier_score_loss(y, probability)),
    }
    for fraction in (0.10, 0.20):
        count = max(1, int(np.ceil(len(y) * fraction)))
        selected = np.argsort(-probability)[:count]
        precision_at_k = float(np.mean(np.asarray(y, dtype=int)[selected]))
        result[f"precision_at_{int(fraction * 100)}pct"] = precision_at_k
        result[f"recall_at_{int(fraction * 100)}pct"] = float(
            np.sum(np.asarray(y, dtype=int)[selected]) / max(1, np.sum(y))
        )
        result[f"lift_at_{int(fraction * 100)}pct"] = precision_at_k / float(np.mean(y))
    return result


def stage_select(data_dir: Path, output_dir: Path, snapshot_name: str):
    output_dir.mkdir(parents=True, exist_ok=True)
    frame, agreement = load_data(data_dir, snapshot_name)
    frame = prepare_features(frame)
    train = frame[frame["split"] == "TRAIN"].copy()
    oof = {"baseline": [], "trajectory": []}
    fold_rows = []
    for date in VALIDATION_DATES[:2]:
        fold_train = train[(train.snapshot_date < date) & (train.horizon_end < date)].copy()
        valid = train[train.snapshot_date == date].copy()
        for variant in ("baseline", "trajectory"):
            features = feature_list(variant)
            model, raw = fit_variant(variant, fold_train, valid, features)
            y = valid.target.to_numpy(dtype=int)
            oof[variant].append(pd.DataFrame({"y": y, "raw": raw}))
            fold_rows.append({"variant": variant, "validation_date": str(date.date()),
                              **model_selection_metrics(y, raw)})
            print(f"[RQ2v2] {variant} {date.date()} PR-AUC={average_precision_score(y, raw):.4f}", flush=True)
            del model
    selection_rows = []
    for variant, parts in oof.items():
        pooled = pd.concat(parts, ignore_index=True)
        selection_rows.append({"variant": variant, **model_selection_metrics(pooled.y, pooled.raw)})
    selection = pd.DataFrame(selection_rows).sort_values(
        ["pr_auc", "brier"], ascending=[False, True]
    )
    selected = str(selection.iloc[0].variant)
    pooled = pd.concat(oof[selected], ignore_index=True)
    calibrator = fit_platt(pooled.raw.to_numpy(), pooled.y.to_numpy(dtype=int))
    state = {
        "selected_model": "CatBoost", "selected_feature_variant": selected,
        "features": feature_list(selected),
        "calibrator_coef": float(calibrator.coef_[0][0]),
        "calibrator_intercept": float(calibrator.intercept_[0]),
        "model_selection_rows": selection.to_dict("records"),
        "fold_rows": fold_rows, "target_reconstruction_agreement": agreement,
        "snapshot_sha256": sha256(data_dir / snapshot_name),
        "sales_orders_sha256": sha256(data_dir / "sales_orders.csv"),
    }
    (output_dir / "pretest_state.json").write_text(json.dumps(state, indent=2), encoding="utf-8")
    selection.to_csv(output_dir / "model_selection_train_only.csv", index=False)
    pd.DataFrame(fold_rows).to_csv(output_dir / "fold_metrics_train_only.csv", index=False)
    print(json.dumps({"stage": "select_complete", "selected_feature_variant": selected,
                      "model_selection": selection.to_dict("records")}, indent=2))


def stage_threshold(data_dir: Path, output_dir: Path, snapshot_name: str):
    state_path = output_dir / "pretest_state.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    frame, agreement = load_data(data_dir, snapshot_name)
    frame = prepare_features(frame)
    train = frame[frame["split"] == "TRAIN"].copy()
    date = VALIDATION_DATES[-1]
    fold_train = train[(train.snapshot_date < date) & (train.horizon_end < date)].copy()
    valid = train[train.snapshot_date == date].copy()
    model, raw = fit_variant(state["selected_feature_variant"], fold_train, valid, state["features"])
    probability = apply_platt_parameters(raw, state["calibrator_coef"], state["calibrator_intercept"])
    y = valid.target.to_numpy(dtype=int)
    policies = [
        ("F1_max", "f1", None),
        ("F2_max", "f2", None),
        ("Precision_at_recall_85pct", "precision_at_recall_floor", 0.85),
    ]
    rows = []
    for name, objective, floor in policies:
        threshold, row = choose_threshold(y, probability, objective, floor)
        rows.append({"policy": name, "validation_date": str(date.date()), **row})
    thresholds = pd.DataFrame(rows)
    primary = float(thresholds.loc[
        thresholds.policy == "Precision_at_recall_85pct", "threshold"
    ].iloc[0])
    state["threshold"] = primary
    state["threshold_selection"] = (
        "Maximise precision subject to recall >= 0.85 on the 2024-12-31 TRAIN origin"
    )
    state["threshold_validation_metrics"] = {
        "n": int(len(y)), "precision": float(precision_score(y, probability >= primary)),
        "recall": float(recall_score(y, probability >= primary)),
    }
    state["threshold_rows"] = thresholds.to_dict("records")
    state["target_reconstruction_agreement"] = agreement
    state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")
    thresholds.to_csv(output_dir / "threshold_selection_train_only.csv", index=False)
    print(json.dumps({"stage": "threshold_complete", "threshold": primary,
                      "thresholds": thresholds[["policy", "threshold", "precision", "recall", "f1"]].to_dict("records")}, indent=2))
    del model


def stage_score(data_dir: Path, output_dir: Path, snapshot_name: str, bootstrap_replicates: int):
    started = time.time()
    state = json.loads((output_dir / "pretest_state.json").read_text(encoding="utf-8"))
    frame, agreement = load_data(data_dir, snapshot_name)
    frame = prepare_features(frame)
    train = frame[frame["split"] == "TRAIN"].copy()
    test = frame[frame["split"] == "TEST"].copy()
    model = fit_final_variant(state["selected_feature_variant"], train, state["features"])
    raw = model.predict_proba(test[state["features"]].copy())[:, 1]
    probability = apply_platt_parameters(raw, state["calibrator_coef"], state["calibrator_intercept"])
    y = test.target.to_numpy(dtype=int)
    primary = float(state["threshold"])
    primary_metrics = classification_metrics(y, probability, primary)
    test_metrics = {"model": "CatBoost", "feature_variant": state["selected_feature_variant"],
                    "threshold_policy": state["threshold_selection"], **primary_metrics}

    operating_rows = []
    for row in state["threshold_rows"]:
        operating_rows.append({
            "policy": row["policy"], "threshold": row["threshold"],
            "train_threshold_precision": row["precision"],
            "train_threshold_recall": row["recall"],
            "train_threshold_f1": row["f1"],
            "train_threshold_f2": row["f2"],
            **classification_metrics(y, probability, float(row["threshold"])),
        })
    operating = pd.DataFrame(operating_rows)

    scored = test[["customer_id", "snapshot_date", "target"]].copy()
    scored["probability"] = probability
    latest = scored.sort_values("snapshot_date").groupby("customer_id", sort=False).tail(1)
    latest_metrics = {"evaluation": "latest_TEST_snapshot_per_customer", "model": "CatBoost",
                      **classification_metrics(latest.target, latest.probability, primary)}
    by_date = []
    for date in sorted(test.snapshot_date.unique()):
        mask = test.snapshot_date.to_numpy() == date
        by_date.append({"snapshot_date": str(pd.Timestamp(date).date()),
                        **classification_metrics(y[mask], probability[mask], primary)})
    tn, fp, fn, tp = confusion_matrix(y, probability >= primary, labels=[0, 1]).ravel()
    confusion = pd.DataFrame([{
        "model": "CatBoost", "threshold": primary, "positive_class": "inactive_next_90d",
        "tn_active_correct": int(tn), "fp_active_flagged_inactive": int(fp),
        "fn_inactive_missed": int(fn), "tp_inactive_detected": int(tp),
    }])

    fpr, tpr, _ = roc_curve(y, probability, pos_label=1)
    grid = np.linspace(0, 1, 101)
    roc_points = pd.DataFrame({
        "false_positive_rate": grid,
        "true_positive_rate": np.interp(grid, fpr, tpr),
    })
    bins, edges = [], np.linspace(0, 1, 11)
    for index in range(10):
        mask = (probability >= edges[index]) & (
            probability < (edges[index + 1] if index < 9 else edges[index + 1] + 1e-12)
        )
        if mask.any():
            bins.append({"bin": index + 1, "n": int(mask.sum()),
                         "mean_predicted": float(probability[mask].mean()),
                         "observed_rate": float(y[mask].mean())})
    bootstrap_raw = cluster_bootstrap(y, probability, test.customer_id.astype(str), bootstrap_replicates)
    bootstrap = {key.lower(): value for key, value in bootstrap_raw.items()}
    importance = pd.DataFrame({
        "feature": state["features"], "importance": model.get_feature_importance()
    }).sort_values("importance", ascending=False)

    output_dir.mkdir(parents=True, exist_ok=True)
    operating.to_csv(output_dir / "test_operating_points.csv", index=False)
    pd.DataFrame([test_metrics]).to_csv(output_dir / "test_metrics.csv", index=False)
    pd.DataFrame([latest_metrics]).to_csv(output_dir / "latest_customer_metrics.csv", index=False)
    pd.DataFrame(by_date).to_csv(output_dir / "test_by_date.csv", index=False)
    confusion.to_csv(output_dir / "confusion_matrix.csv", index=False)
    roc_points.to_csv(output_dir / "roc_curve_points.csv", index=False)
    pd.DataFrame(bins).to_csv(output_dir / "calibration_bins.csv", index=False)
    importance.to_csv(output_dir / "feature_importance.csv", index=False)
    pd.DataFrame([
        {"metric": key, "lower_2_5": value[0], "median": value[1], "upper_97_5": value[2],
         "resampling_unit": "customer_id", "replicates": bootstrap_replicates}
        for key, value in bootstrap.items()
    ]).to_csv(output_dir / "customer_cluster_bootstrap_ci.csv", index=False)

    audit = {
        "snapshot_rows": int(len(frame)), "unique_customers": int(frame.customer_id.nunique()),
        "train_rows": int(len(train)), "test_rows": int(len(test)),
        "train_dates": [str(train.snapshot_date.min().date()), str(train.snapshot_date.max().date())],
        "test_dates": [str(test.snapshot_date.min().date()), str(test.snapshot_date.max().date())],
        "selected_feature_variant": state["selected_feature_variant"],
        "train_customer_count": int(train.customer_id.nunique()),
        "test_customer_count": int(test.customer_id.nunique()),
        "train_test_customer_overlap": int(len(set(train.customer_id.astype(str)) & set(test.customer_id.astype(str)))),
        "target_reconstruction_agreement": agreement,
        "snapshot_sha256": sha256(data_dir / snapshot_name),
        "sales_orders_sha256": sha256(data_dir / "sales_orders.csv"),
        "selected_feature_variant": state["selected_feature_variant"],
        "customer_id_used_as_predictor": False,
        "previous_snapshot_target_used_as_predictor": False,
    }
    (output_dir / "data_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    manifest = {
        "experiment": "rq2_temporal_customer_inactivity_prediction_v2",
        "selected_model": "CatBoost",
        "selected_feature_variant": state["selected_feature_variant"],
        "model_selection": "First two rolling-origin TRAIN folds only; PR-AUC primary, Brier tie-breaker",
        "calibration": "Platt sigmoid fitted on the first two rolling-origin TRAIN prediction sets",
        "threshold_selection": state["threshold_selection"],
        "threshold": primary,
        "threshold_validation_metrics": state["threshold_validation_metrics"],
        "test_metrics": test_metrics,
        "latest_customer_metrics": latest_metrics,
        "customer_cluster_bootstrap": bootstrap,
        "limitations": [
            "The same customers occur in TRAIN and TEST; this is temporal, not cold-start evaluation.",
            "The target is no repeat purchase in the next 90 days, not permanent churn or causal campaign response.",
            "The TEST set was already evaluated in v1; v2 TEST results are a repeated-holdout diagnostic, not a pristine independent confirmation.",
        ],
        "runtime_seconds": round(time.time() - started, 2),
        "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"stage": "score_complete", "test_metrics": test_metrics,
                      "latest_customer_metrics": latest_metrics, "bootstrap": bootstrap}, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--snapshot-file", default="rq2_customer_snapshots_90d_A.csv")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int, default=500)
    parser.add_argument("--stage", choices=["select", "threshold", "score"], required=True)
    args = parser.parse_args()
    if args.stage == "select":
        stage_select(args.data_dir, args.output_dir, args.snapshot_file)
    elif args.stage == "threshold":
        stage_threshold(args.data_dir, args.output_dir, args.snapshot_file)
    else:
        stage_score(args.data_dir, args.output_dir, args.snapshot_file, args.bootstrap_replicates)


if __name__ == "__main__":
    main()
