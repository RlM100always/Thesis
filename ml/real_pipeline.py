"""Train real-data forecasting and future-repeat models.

Usage:
    python -m ml.real_pipeline --input path/to/bsmart_sales_anonymized.csv

The command refuses insufficient data and never falls back to simulated results.
All splits are chronological. Preprocessing lives inside fitted sklearn pipelines.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, brier_score_loss, mean_absolute_error,
    mean_squared_error, roc_auc_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

REQUIRED = {
    "branch_id", "invoice_id", "line_id", "sold_at", "customer_pseudo_id",
    "sku", "quantity", "unit_price", "discount_amount", "line_total",
}


def load_sales(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    missing = sorted(REQUIRED - set(frame.columns))
    if missing:
        raise ValueError(f"Missing canonical columns: {', '.join(missing)}")
    frame["sold_at"] = pd.to_datetime(frame["sold_at"], utc=True, errors="coerce")
    for column in ["quantity", "unit_price", "discount_amount", "line_total"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    invalid = frame[["sold_at", "sku", "quantity", "line_total"]].isna().any(axis=1)
    if invalid.any():
        raise ValueError(f"{int(invalid.sum())} rows contain invalid required values")
    if (frame["quantity"] <= 0).any() or (frame["line_total"] < 0).any():
        raise ValueError("Quantities must be positive and line totals non-negative")
    return frame.sort_values("sold_at").reset_index(drop=True)


def wape(actual: np.ndarray, predicted: np.ndarray) -> float:
    denominator = np.abs(actual).sum()
    return float(np.abs(actual - predicted).sum() / denominator) if denominator else float("nan")


def demand_features(sales: pd.DataFrame) -> pd.DataFrame:
    daily = sales.assign(date=sales.sold_at.dt.floor("D")).groupby(
        ["branch_id", "sku", "date"], as_index=False
    ).agg(quantity=("quantity", "sum"), revenue=("line_total", "sum"),
          avg_price=("unit_price", "mean"), discount=("discount_amount", "sum"))
    pieces = []
    for (branch, sku), group in daily.groupby(["branch_id", "sku"]):
        group = group.set_index("date").sort_index()
        full = group.reindex(pd.date_range(group.index.min(), group.index.max(), freq="D"))
        full.index.name = "date"
        full[["quantity", "revenue", "discount"]] = full[["quantity", "revenue", "discount"]].fillna(0)
        full["avg_price"] = full["avg_price"].ffill().bfill()
        full["branch_id"], full["sku"] = branch, sku
        pieces.append(full.reset_index())
    if not pieces:
        return pd.DataFrame()
    data = pd.concat(pieces, ignore_index=True).sort_values(["branch_id", "sku", "date"])
    grouped = data.groupby(["branch_id", "sku"])["quantity"]
    for lag in (1, 7, 14, 28):
        data[f"lag_{lag}"] = grouped.shift(lag)
    data["rolling_7"] = grouped.transform(lambda x: x.shift(1).rolling(7).mean())
    data["rolling_28"] = grouped.transform(lambda x: x.shift(1).rolling(28).mean())
    data["day_of_week"] = data.date.dt.dayofweek
    data["day_of_month"] = data.date.dt.day
    data["month"] = data.date.dt.month
    data["is_weekend"] = data.day_of_week.isin([4, 5]).astype(int)  # Bangladesh Fri/Sat
    return data.dropna(subset=["lag_28", "rolling_28"]).reset_index(drop=True)


def train_forecast(sales: pd.DataFrame, output: Path) -> dict:
    data = demand_features(sales)
    if data.empty or data.date.nunique() < 90 or len(data) < 500:
        raise ValueError("Forecasting needs at least 90 days and 500 prepared branch-SKU-day rows")
    dates = np.sort(data.date.unique())
    split_date = dates[int(len(dates) * 0.8)]
    train, test = data[data.date < split_date], data[data.date >= split_date]
    features = ["branch_id", "sku", "avg_price", "discount", "lag_1", "lag_7", "lag_14", "lag_28", "rolling_7", "rolling_28", "day_of_week", "day_of_month", "month", "is_weekend"]
    categorical = ["branch_id", "sku"]
    numeric = [f for f in features if f not in categorical]
    preprocessor = ColumnTransformer([
        ("categorical", OneHotEncoder(handle_unknown="ignore", sparse_output=False), categorical),
        ("numeric", SimpleImputer(strategy="median"), numeric),
    ])
    model = Pipeline([
        ("features", preprocessor),
        ("model", HistGradientBoostingRegressor(max_iter=200, learning_rate=.06, random_state=42)),
    ])
    model.fit(train[features], train.quantity)
    prediction = np.maximum(0, model.predict(test[features]))
    baseline = test.lag_7.to_numpy()
    actual = test.quantity.to_numpy()
    result = {
        "split_date": pd.Timestamp(split_date).isoformat(), "train_rows": len(train), "test_rows": len(test),
        "hist_gradient_boosting": {"wape": wape(actual, prediction), "mae": float(mean_absolute_error(actual, prediction)), "rmse": float(mean_squared_error(actual, prediction) ** .5)},
        "seasonal_naive_7": {"wape": wape(actual, baseline), "mae": float(mean_absolute_error(actual, baseline)), "rmse": float(mean_squared_error(actual, baseline) ** .5)},
    }
    joblib.dump({"pipeline": model, "features": features, "trained_until": str(train.date.max())}, output / "demand_model.joblib")
    return result


def churn_snapshots(sales: pd.DataFrame, horizon_days: int = 90, history_days: int = 180) -> pd.DataFrame:
    eligible = sales[sales.customer_pseudo_id.ne("ANONYMOUS")].copy()
    if eligible.empty:
        return pd.DataFrame()
    start = eligible.sold_at.min().floor("D") + pd.Timedelta(days=history_days)
    end = eligible.sold_at.max().floor("D") - pd.Timedelta(days=horizon_days)
    if start > end:
        return pd.DataFrame()
    rows = []
    for cutoff in pd.date_range(start, end, freq="30D"):
        history = eligible[(eligible.sold_at < cutoff) & (eligible.sold_at >= cutoff - pd.Timedelta(days=history_days))]
        future = set(eligible[(eligible.sold_at >= cutoff) & (eligible.sold_at < cutoff + pd.Timedelta(days=horizon_days))].customer_pseudo_id)
        for customer, group in history.groupby("customer_pseudo_id"):
            last = group.sold_at.max()
            rows.append({
                "customer": customer, "cutoff": cutoff,
                "recency": (cutoff - last).days,
                "transactions": group.invoice_id.nunique(),
                "monetary": group.line_total.sum(),
                "avg_order": group.groupby("invoice_id").line_total.sum().mean(),
                "unique_skus": group.sku.nunique(),
                "discount_share": float((group.discount_amount > 0).mean()),
                "will_return": int(customer in future),
            })
    return pd.DataFrame(rows)


def lift_at_10(actual: np.ndarray, probability: np.ndarray) -> float:
    n = max(1, int(np.ceil(len(actual) * .1)))
    base = actual.mean()
    return float(actual[np.argsort(probability)[::-1][:n]].mean() / base) if base else float("nan")


def train_churn(sales: pd.DataFrame, output: Path, horizon_days: int = 90) -> dict:
    data = churn_snapshots(sales, horizon_days=horizon_days)
    if data.empty or len(data) < 300 or data.will_return.nunique() < 2:
        raise ValueError("Future-repeat modelling needs 300+ snapshots and both outcome classes")
    cutoffs = np.sort(data.cutoff.unique())
    test_start = pd.Timestamp(cutoffs[int(len(cutoffs) * .8)])
    # Purge one outcome horizon so training labels cannot overlap test features.
    train = data[data.cutoff < test_start - pd.Timedelta(days=horizon_days)]
    test = data[data.cutoff >= test_start]
    if len(train) < 100 or test.will_return.nunique() < 2:
        raise ValueError("Not enough temporally separated snapshots after horizon purging")
    features = ["recency", "transactions", "monetary", "avg_order", "unique_skus", "discount_share"]
    models = {
        "logistic": Pipeline([("scale", StandardScaler()), ("model", LogisticRegression(class_weight="balanced", max_iter=2000, random_state=42))]),
        "random_forest": RandomForestClassifier(n_estimators=300, max_depth=10, class_weight="balanced", random_state=42, n_jobs=-1),
    }
    results, fitted = {}, {}
    for name, model in models.items():
        model.fit(train[features], train.will_return)
        probability = model.predict_proba(test[features])[:, 1]
        results[name] = {
            "pr_auc": float(average_precision_score(test.will_return, probability)),
            "roc_auc": float(roc_auc_score(test.will_return, probability)),
            "brier": float(brier_score_loss(test.will_return, probability)),
            "lift_at_10": lift_at_10(test.will_return.to_numpy(), probability),
        }
        fitted[name] = model
    winner = min(results, key=lambda n: results[n]["brier"])
    joblib.dump({"pipeline": fitted[winner], "features": features, "horizon_days": horizon_days, "trained_until": str(train.cutoff.max())}, output / "future_repeat_model.joblib")
    return {"test_start": test_start.isoformat(), "purge_days": horizon_days, "train_rows": len(train), "test_rows": len(test), "positive_rate": float(test.will_return.mean()), "models": results, "winner_by_brier": winner}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--organization-id", type=str, default=None,
                         help="Sets the default --output to artifacts/real/<id>/ so the "
                              "live API (ml/serving.py) can find this organization's model.")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    if args.output is None:
        args.output = Path("artifacts/real") / args.organization_id if args.organization_id else Path("artifacts/real")
    args.output.mkdir(parents=True, exist_ok=True)
    sales = load_sales(args.input)
    report = {"source": str(args.input), "rows": len(sales), "real_data_only": True}
    for name, trainer in [("forecast", train_forecast), ("future_repeat", train_churn)]:
        try:
            report[name] = trainer(sales, args.output)
        except ValueError as exc:
            report[name] = {"available": False, "reason": str(exc)}
    (args.output / "evaluation.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
