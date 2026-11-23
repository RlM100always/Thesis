"""Leakage-aware RQ2 customer inactivity experiment.

Uses the supplied chronological TRAIN/TEST split, reconstructs the 90-day
no-repeat label from order headers, selects models on rolling-origin TRAIN
predictions, calibrates with training-only out-of-time predictions, and writes
aggregate outputs only. Customer identifiers and names are never predictors or
written to result files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import numpy as np
import pandas as pd
from catboost import CatBoostClassifier
from lightgbm import LGBMClassifier
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, fbeta_score,
    precision_score, recall_score, roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

NUMERIC = [
    "recency_days", "orders_last_30d", "orders_last_90d", "orders_last_180d",
    "sales_last_90d_bdt", "mean_basket_last_90d_bdt", "lifetime_orders_so_far",
    "tenure_days", "snapshot_year", "snapshot_month", "snapshot_quarter",
    "month_sin", "month_cos", "orders_90_180d", "orders_30_90d",
    "sales_per_order_90d", "orders_per_tenure_90d", "recent_order_share_90d",
    "recency_frequency_ratio", "tenure_years",
]
CATEGORICAL = ["home_shop_id"]
FEATURES = NUMERIC + CATEGORICAL
VALIDATION_DATES = pd.to_datetime(["2024-06-30", "2024-09-30", "2024-12-31"])


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_data(data_dir: Path, snapshot_name: str):
    snapshot_path = data_dir / snapshot_name
    orders_path = data_dir / "sales_orders.csv"
    snapshots = pd.read_csv(snapshot_path)
    label_col = next((c for c in ["inactive_next_90d_label", "inactive_next_90d_synthetic_label"] if c in snapshots), None)
    if label_col is None:
        raise ValueError("RQ2 target column is missing.")
    snapshots = snapshots.rename(columns={label_col: "target"})
    required = {
        "snapshot_id", "customer_id", "home_shop_id", "snapshot_date", "horizon_end",
        "recency_days", "orders_last_30d", "orders_last_90d", "orders_last_180d",
        "sales_last_90d_bdt", "mean_basket_last_90d_bdt", "lifetime_orders_so_far",
        "tenure_days", "target", "split",
    }
    missing = sorted(required - set(snapshots.columns))
    if missing:
        raise ValueError(f"Missing RQ2 columns: {missing}")
    snapshots["snapshot_date"] = pd.to_datetime(snapshots["snapshot_date"], errors="raise")
    snapshots["horizon_end"] = pd.to_datetime(snapshots["horizon_end"], errors="raise")
    snapshots["customer_id"] = snapshots["customer_id"].astype("string")
    snapshots["target"] = pd.to_numeric(snapshots["target"], errors="raise").astype(int)
    if not snapshots["target"].isin([0, 1]).all():
        raise ValueError("RQ2 target must be binary.")
    if snapshots["snapshot_id"].duplicated().any():
        raise ValueError("Duplicate snapshot_id values found.")
    if snapshots.duplicated(["customer_id", "snapshot_date"]).any():
        raise ValueError("Duplicate customer/date snapshots found.")
    if not set(snapshots["split"].unique()).issubset({"TRAIN", "TEST"}):
        raise ValueError("Unexpected split values.")

    # Reconstruct the label from orders strictly after the snapshot date and
    # through the supplied horizon_end. This validates the target definition.
    orders = pd.read_csv(orders_path, usecols=["customer_id", "order_datetime"], parse_dates=["order_datetime"])
    orders = orders.dropna(subset=["customer_id"]).copy()
    orders["customer_id"] = orders["customer_id"].astype(str)
    orders["order_date"] = orders["order_datetime"].dt.normalize()
    order_dates = {
        key: np.sort(group["order_date"].to_numpy(dtype="datetime64[D]").astype("int64"))
        for key, group in orders.groupby("customer_id", sort=False)
    }
    reconstructed = np.zeros(len(snapshots), dtype=np.int8)
    for i, row in enumerate(snapshots[["customer_id", "snapshot_date", "horizon_end"]].itertuples(index=False, name=None)):
        customer, start, end = row
        dates = order_dates.get(str(customer), np.empty(0, dtype=np.int64))
        lo = np.searchsorted(dates, np.datetime64(start.date()).astype("datetime64[D]").astype("int64"), side="right")
        hi = np.searchsorted(dates, np.datetime64(end.date()).astype("datetime64[D]").astype("int64"), side="right")
        reconstructed[i] = int(hi == lo)
    label_agreement = float(np.mean(reconstructed == snapshots["target"].to_numpy()))
    if label_agreement != 1.0:
        raise ValueError(f"Supplied RQ2 label disagrees with source orders on {1-label_agreement:.2%} of rows.")
    # Only use attributes stored in the historical snapshot. Current customer-master
    # fields have no effective-date history and are excluded to avoid point-in-time leakage.

    snapshots["snapshot_year"] = snapshots["snapshot_date"].dt.year
    snapshots["snapshot_month"] = snapshots["snapshot_date"].dt.month
    snapshots["snapshot_quarter"] = snapshots["snapshot_date"].dt.quarter
    snapshots["month_sin"] = np.sin(2 * np.pi * (snapshots["snapshot_month"] - 1) / 12)
    snapshots["month_cos"] = np.cos(2 * np.pi * (snapshots["snapshot_month"] - 1) / 12)
    snapshots["orders_90_180d"] = np.maximum(0, snapshots["orders_last_180d"] - snapshots["orders_last_90d"])
    snapshots["orders_30_90d"] = np.maximum(0, snapshots["orders_last_90d"] - snapshots["orders_last_30d"])
    snapshots["sales_per_order_90d"] = snapshots["sales_last_90d_bdt"] / snapshots["orders_last_90d"].replace(0, np.nan)
    snapshots["orders_per_tenure_90d"] = snapshots["lifetime_orders_so_far"] / np.maximum(snapshots["tenure_days"], 1) * 90
    snapshots["recent_order_share_90d"] = snapshots["orders_last_30d"] / snapshots["orders_last_90d"].replace(0, np.nan)
    snapshots["recency_frequency_ratio"] = snapshots["recency_days"] / (snapshots["orders_last_90d"] + 1)
    snapshots["tenure_years"] = snapshots["tenure_days"] / 365.25
    for column in CATEGORICAL:
        snapshots[column] = snapshots[column].fillna("UNKNOWN").astype(str)
    for column in NUMERIC:
        snapshots[column] = pd.to_numeric(snapshots[column], errors="coerce")
    if snapshots[FEATURES].isna().all(axis=1).any():
        raise ValueError("At least one row has no usable model features.")
    return snapshots, label_agreement


def make_logistic():
    transformer = ColumnTransformer([
        ("num", Pipeline([("impute", SimpleImputer(strategy="median")), ("scale", StandardScaler())]), NUMERIC),
        ("cat", Pipeline([("impute", SimpleImputer(strategy="most_frequent")),
                          ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=5))]), CATEGORICAL),
    ])
    return Pipeline([("transform", transformer),
                     ("model", LogisticRegression(max_iter=1000, class_weight="balanced", C=0.5))])


def fit_lgbm(x, y):
    model = LGBMClassifier(
        objective="binary", n_estimators=250, learning_rate=0.03, num_leaves=15,
        min_child_samples=100, colsample_bytree=0.9, subsample=0.85,
        subsample_freq=1, reg_lambda=5.0, random_state=42, n_jobs=2, verbosity=-1,
    )
    data = x.copy()
    for column in CATEGORICAL:
        data[column] = data[column].astype("category")
    model.fit(data, y, categorical_feature=CATEGORICAL)
    return model, data


def fit_catboost(x, y):
    model = CatBoostClassifier(
        iterations=250, depth=6, learning_rate=0.04, l2_leaf_reg=5,
        loss_function="Logloss", eval_metric="PRAUC", random_seed=42,
        verbose=False, allow_writing_files=False, thread_count=2,
    )
    data = x.copy()
    for column in CATEGORICAL:
        data[column] = data[column].fillna("UNKNOWN").astype(str)
    model.fit(data, y, cat_features=CATEGORICAL)
    return model, data


def ranking_metrics(y, score, fraction=0.10):
    y = np.asarray(y, dtype=int)
    score = np.asarray(score, dtype=float)
    count = max(1, int(np.ceil(len(y) * fraction)))
    selected = np.argsort(-score)[:count]
    precision = float(y[selected].mean())
    recall = float(y[selected].sum() / max(1, y.sum()))
    return {"precision_at_10pct": precision, "recall_at_10pct": recall,
            "lift_at_10pct": precision / float(y.mean()) if y.mean() else np.nan}


def fit_platt(raw, y):
    raw = np.clip(np.asarray(raw, dtype=float), 1e-6, 1 - 1e-6)
    logit = np.log(raw / (1 - raw)).reshape(-1, 1)
    model = LogisticRegression(C=1e6, solver="lbfgs", max_iter=1000)
    model.fit(logit, y)
    return model


def apply_platt(model, raw):
    raw = np.clip(np.asarray(raw, dtype=float), 1e-6, 1 - 1e-6)
    logit = np.log(raw / (1 - raw)).reshape(-1, 1)
    return model.predict_proba(logit)[:, 1]


def choose_f2_threshold(y, probability):
    thresholds = np.unique(np.quantile(probability, np.linspace(0, 1, 501)))
    scores = [fbeta_score(y, probability >= threshold, beta=2, zero_division=0) for threshold in thresholds]
    index = int(np.argmax(scores))
    return float(thresholds[index]), float(scores[index])


def evaluate(y, probability, threshold=None):
    result = {
        "n": int(len(y)), "positive_rate": float(np.mean(y)),
        "pr_auc": float(average_precision_score(y, probability)),
        "roc_auc": float(roc_auc_score(y, probability)),
        "brier": float(brier_score_loss(y, probability)),
        **ranking_metrics(y, probability),
    }
    if threshold is not None:
        predicted = probability >= threshold
        result.update({
            "threshold": float(threshold),
            "precision": float(precision_score(y, predicted, zero_division=0)),
            "recall": float(recall_score(y, predicted, zero_division=0)),
            "f2": float(fbeta_score(y, predicted, beta=2, zero_division=0)),
        })
    return result


def cluster_bootstrap(y, probability, customer_ids, replicates=1000, seed=20261123):
    unique, inverse = np.unique(np.asarray(customer_ids, dtype=str), return_inverse=True)
    rng = np.random.default_rng(seed)
    rows = []
    for _ in range(replicates):
        sampled = rng.integers(0, len(unique), size=len(unique))
        weights = np.bincount(sampled, minlength=len(unique))[inverse]
        rows.append([
            average_precision_score(y, probability, sample_weight=weights),
            roc_auc_score(y, probability, sample_weight=weights),
            brier_score_loss(y, probability, sample_weight=weights),
        ])
    array = np.asarray(rows)
    return {
        metric: np.quantile(array[:, i], [0.025, 0.5, 0.975]).tolist()
        for i, metric in enumerate(["PR_AUC", "ROC_AUC", "Brier"])
    }


def run(data_dir: Path, output_dir: Path, snapshot_name: str, bootstrap_replicates: int):
    started = time.time()
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = data_dir / snapshot_name
    orders_path = data_dir / "sales_orders.csv"
    snapshots, label_agreement = load_data(data_dir, snapshot_name)
    train = snapshots[snapshots["split"] == "TRAIN"].copy()
    test = snapshots[snapshots["split"] == "TEST"].copy()
    y_test = test["target"].to_numpy(dtype=int)
    oof = {name: [] for name in ["Recency_rule", "Logistic", "LightGBM", "CatBoost"]}

    for validation_date in VALIDATION_DATES:
        print(f"[RQ2] validation origin {validation_date.date()}", flush=True)
        training = train[(train["snapshot_date"] < validation_date) & (train["horizon_end"] < validation_date)].copy()
        validation = train[train["snapshot_date"] == validation_date].copy()
        if training.empty or validation.empty:
            raise ValueError(f"Missing rolling-origin fold for {validation_date.date()}.")
        x_train, x_validation = training[FEATURES].copy(), validation[FEATURES].copy()
        y_train = training["target"].to_numpy(dtype=int)
        y_validation = validation["target"].to_numpy(dtype=int)
        common = {"customer_id": validation["customer_id"].astype(str).to_numpy(),
                  "snapshot_date": str(validation_date.date()), "y": y_validation}
        oof["Recency_rule"].append(pd.DataFrame({**common, "score": validation["recency_days"].to_numpy(float)}))

        print("[RQ2] fit logistic", flush=True)
        logistic = make_logistic()
        logistic.fit(x_train, y_train)
        oof["Logistic"].append(pd.DataFrame({**common, "score": logistic.predict_proba(x_validation)[:, 1]}))

        print("[RQ2] fit LightGBM", flush=True)
        lgbm, x_lgb_train = fit_lgbm(x_train, y_train)
        x_lgb_validation = x_validation.copy()
        for column in CATEGORICAL:
            x_lgb_validation[column] = pd.Categorical(x_lgb_validation[column], categories=x_lgb_train[column].cat.categories)
        oof["LightGBM"].append(pd.DataFrame({**common, "score": lgbm.predict_proba(x_lgb_validation)[:, 1]}))

        print("[RQ2] fit CatBoost", flush=True)
        catboost, x_cat_train = fit_catboost(x_train, y_train)
        x_cat_validation = x_validation.copy()
        for column in CATEGORICAL:
            x_cat_validation[column] = x_cat_validation[column].fillna("UNKNOWN").astype(str)
        oof["CatBoost"].append(pd.DataFrame({**common, "score": catboost.predict_proba(x_cat_validation)[:, 1]}))

    validation_rows, validation_by_date = [], []
    calibrators, thresholds, oof_calibrated = {}, {}, {}
    for name, parts in oof.items():
        frame = pd.concat(parts, ignore_index=True)
        y, score = frame["y"].to_numpy(dtype=int), frame["score"].to_numpy(float)
        if name == "Recency_rule":
            row = {"model": name, "n": int(len(y)), "positive_rate": float(np.mean(y)),
                   "pr_auc": float(average_precision_score(y, score)), "roc_auc": float(roc_auc_score(y, score)),
                   **ranking_metrics(y, score)}
        else:
            row = {"model": name, **evaluate(y, score)}
        if name != "Recency_rule":
            calibrator = fit_platt(score, y)
            calibrated = apply_platt(calibrator, score)
            threshold, f2 = choose_f2_threshold(y, calibrated)
            calibrators[name], thresholds[name], oof_calibrated[name] = calibrator, threshold, calibrated
            row["brier_calibrated"] = float(brier_score_loss(y, calibrated))
            row["f2_threshold_from_oof"] = threshold
            row["f2_oof"] = f2
        validation_rows.append(row)
        for date, group in frame.groupby("snapshot_date"):
            gy, gs = group["y"].to_numpy(dtype=int), group["score"].to_numpy(float)
            if name == "Recency_rule":
                validation_by_date.append({"model": name, "snapshot_date": date, "n": int(len(gy)),
                                           "positive_rate": float(np.mean(gy)),
                                           "pr_auc": float(average_precision_score(gy, gs)),
                                           "roc_auc": float(roc_auc_score(gy, gs)), **ranking_metrics(gy, gs)})
            else:
                validation_by_date.append({"model": name, "snapshot_date": date, **evaluate(gy, gs)})

    validation_metrics = pd.DataFrame(validation_rows)
    eligible = validation_metrics[validation_metrics["model"] != "Recency_rule"].sort_values(
        ["pr_auc", "brier_calibrated"], ascending=[False, True]
    )
    selected_name = str(eligible.iloc[0]["model"])

    # Final models fit on the full supplied TRAIN split. TEST is opened only now.
    print(f"[RQ2] selected {selected_name}; fitting final models", flush=True)
    x_train, x_test = train[FEATURES].copy(), test[FEATURES].copy()
    y_train = train["target"].to_numpy(dtype=int)
    final_models, test_probabilities = {}, {}
    print("[RQ2] final logistic", flush=True)
    logistic = make_logistic(); logistic.fit(x_train, y_train)
    final_models["Logistic"] = logistic
    test_probabilities["Logistic"] = apply_platt(calibrators["Logistic"], logistic.predict_proba(x_test)[:, 1])

    print("[RQ2] final LightGBM", flush=True)
    lgbm, x_lgb_train = fit_lgbm(x_train, y_train)
    x_lgb_test = x_test.copy()
    for column in CATEGORICAL:
        x_lgb_test[column] = pd.Categorical(x_lgb_test[column], categories=x_lgb_train[column].cat.categories)
    final_models["LightGBM"] = lgbm
    test_probabilities["LightGBM"] = apply_platt(calibrators["LightGBM"], lgbm.predict_proba(x_lgb_test)[:, 1])

    print("[RQ2] final CatBoost", flush=True)
    catboost, _ = fit_catboost(x_train, y_train)
    x_cat_test = x_test.copy()
    for column in CATEGORICAL:
        x_cat_test[column] = x_cat_test[column].fillna("UNKNOWN").astype(str)
    final_models["CatBoost"] = catboost
    test_probabilities["CatBoost"] = apply_platt(calibrators["CatBoost"], catboost.predict_proba(x_cat_test)[:, 1])

    test_rows = []
    for name, probability in test_probabilities.items():
        test_rows.append({"model": name, "selection_rule": "training-only rolling-origin OOF",
                          **evaluate(y_test, probability, thresholds[name])})
    rule_score = test["recency_days"].to_numpy(float)
    test_rows.append({"model": "Recency_rule", "selection_rule": "rank by recency_days",
                      "n": int(len(y_test)), "positive_rate": float(np.mean(y_test)),
                      "pr_auc": float(average_precision_score(y_test, rule_score)),
                      "roc_auc": float(roc_auc_score(y_test, rule_score)), "brier": None,
                      **ranking_metrics(y_test, rule_score)})
    test_metrics = pd.DataFrame(test_rows)

    selected_probability = test_probabilities[selected_name]
    print("[RQ2] customer-cluster bootstrap", flush=True)
    bootstrap = cluster_bootstrap(y_test, selected_probability, test["customer_id"].astype(str), bootstrap_replicates)
    customer_ids = set(train["customer_id"].astype(str))
    test_customer_ids = set(test["customer_id"].astype(str))
    label_rate = float(np.mean(y_test))
    selected_threshold = thresholds[selected_name]

    # Aggregate only; never save row-level customer predictions.
    test_by_date = []
    for date, group in test.assign(_p=selected_probability).groupby("snapshot_date"):
        test_by_date.append({"snapshot_date": str(date.date()),
                             **evaluate(group["target"].to_numpy(int), group["_p"].to_numpy(float))})
    calibration_bins = []
    edges = np.linspace(0, 1, 11)
    for index in range(10):
        mask = (selected_probability >= edges[index]) & (selected_probability < (edges[index + 1] if index < 9 else edges[index + 1] + 1e-9))
        if mask.any():
            calibration_bins.append({"bin": index + 1, "n": int(mask.sum()),
                                     "mean_predicted": float(selected_probability[mask].mean()),
                                     "observed_rate": float(y_test[mask].mean())})
    if selected_name == "CatBoost":
        feature_importance = pd.DataFrame({"feature": FEATURES, "importance": final_models[selected_name].get_feature_importance()})
    elif selected_name == "LightGBM":
        feature_importance = pd.DataFrame({"feature": FEATURES, "importance": final_models[selected_name].feature_importances_})
    else:
        feature_importance = pd.DataFrame()
    if not feature_importance.empty:
        feature_importance = feature_importance.sort_values("importance", ascending=False)

    validation_metrics.to_csv(output_dir / "validation_metrics.csv", index=False)
    pd.DataFrame(validation_by_date).to_csv(output_dir / "validation_by_date.csv", index=False)
    test_metrics.to_csv(output_dir / "test_metrics.csv", index=False)
    pd.DataFrame(test_by_date).to_csv(output_dir / "test_by_date.csv", index=False)
    pd.DataFrame(calibration_bins).to_csv(output_dir / "calibration_bins.csv", index=False)
    pd.DataFrame([{"metric": key, "lower_2_5": value[0], "median": value[1], "upper_97_5": value[2],
                   "resampling_unit": "customer_id", "replicates": bootstrap_replicates} for key, value in bootstrap.items()]).to_csv(
        output_dir / "customer_cluster_bootstrap_ci.csv", index=False)
    feature_importance.to_csv(output_dir / "feature_importance.csv", index=False)

    audit = {
        "snapshot_rows": int(len(snapshots)), "unique_customers": int(snapshots["customer_id"].nunique()),
        "train_rows": int(len(train)), "test_rows": int(len(test)),
        "train_customers": int(len(customer_ids)), "test_customers": int(len(test_customer_ids)),
        "customer_overlap": int(len(customer_ids & test_customer_ids)),
        "train_date_range": [str(train["snapshot_date"].min().date()), str(train["snapshot_date"].max().date())],
        "test_date_range": [str(test["snapshot_date"].min().date()), str(test["snapshot_date"].max().date())],
        "train_positive_rate": float(train["target"].mean()), "test_positive_rate": label_rate,
        "target_reconstruction_agreement": label_agreement,
        "target_definition": "No order in (snapshot_date, horizon_end], reconstructed from sales_orders.csv",
        "customer_id_excluded_from_features": True, "customer_name_excluded": True,
        "current_customer_master_attributes_excluded": ["customer_type", "loyalty_member", "home_division", "home_district"],
        "feature_availability_policy": "snapshot columns and deterministic transforms only",
    }
    (output_dir / "data_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    manifest = {
        "experiment": "rq2_temporal_customer_inactivity_prediction_v1",
        "snapshot_file": snapshot_name, "snapshot_sha256": sha256(snapshot_path),
        "sales_orders_sha256": sha256(orders_path),
        "rows": int(len(snapshots)), "unique_customers": int(snapshots["customer_id"].nunique()),
        "split": "Supplied chronological TRAIN/TEST split preserved",
        "validation_dates": [str(date.date()) for date in VALIDATION_DATES],
        "target_reconstruction_agreement": label_agreement,
        "features": FEATURES,
        "excluded": ["snapshot_id", "customer_id", "customer_name", "horizon_end", "split", "target",
                     "customer_type", "loyalty_member", "home_division", "home_district"],
        "feature_availability_policy": "snapshot columns and deterministic transformations only; undated current customer-master attributes excluded",
        "models": ["Recency_rule", "LogisticRegression", "LightGBMClassifier", "CatBoostClassifier"],
        "selected_model": selected_name,
        "selection_rule": "Highest training-only OOF PR-AUC, tie-broken by calibrated Brier",
        "calibration": "Platt sigmoid fit on rolling-origin OOF TRAIN predictions",
        "threshold_rule": "F2-maximising threshold selected on OOF calibrated probabilities",
        "test_metrics_selected_model": test_metrics[test_metrics["model"] == selected_name].iloc[0].to_dict(),
        "customer_cluster_bootstrap": {"replicates": bootstrap_replicates, "seed": 20261123, "ci": bootstrap},
        "limitations": [
            "Temporal evaluation within the supplied customer population; repeated customers occur across the time split.",
            "Customer identifiers and names are excluded from predictors.",
            "The target is no repeat purchase within 90 days, not permanent churn or causal campaign response.",
        ],
        "runtime_seconds": round(time.time() - started, 2),
        "python": platform.python_version(), "pandas": pd.__version__, "numpy": np.__version__,
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"selected_model": selected_name, "test": manifest["test_metrics_selected_model"],
                      "bootstrap": bootstrap, "output_dir": str(output_dir)}, indent=2, default=str))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--snapshot-file", default="rq2_customer_snapshots_90d_A.csv")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--bootstrap-replicates", type=int, default=500)
    args = parser.parse_args()
    run(args.data_dir, args.output_dir, args.snapshot_file, args.bootstrap_replicates)


if __name__ == "__main__":
    main()