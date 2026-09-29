"""Auditable advanced preprocessing and forecasting benchmark.

The script never invents unavailable fields.  UCI transactions support gross,
returns, net and revenue targets plus lagged business covariates.  The real
Bangladesh series supports quantity only.  Generated B-SMART data is retained
as a labelled synthetic control.  Every feature at forecast date t is computed
from observations strictly before t.
"""

from __future__ import annotations

import gc
import json
from pathlib import Path
from typing import Callable

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import TransformedTargetRegressor
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor
from sklearn.linear_model import HuberRegressor, PoissonRegressor, TweedieRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import RobustScaler
from xgboost import XGBRegressor

from ml.external_datasets import load_bd_retailer_demand

SEED = 20260906
RAW_UCI = Path("data/real_public/online_retail_II.csv")
OUT = Path("artifacts/advanced")
FIG = Path("output/figures")
MODELS = Path("output/models/advanced")
for directory in (OUT, FIG, MODELS):
    directory.mkdir(parents=True, exist_ok=True)


def _daily_uci() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Clean UCI in chunks and return daily aggregates, SKU-day data and audit."""
    cols = ["Invoice", "StockCode", "Quantity", "InvoiceDate", "Price", "Customer ID"]
    probe = pd.read_csv(RAW_UCI, usecols=["InvoiceDate"], parse_dates=["InvoiceDate"])
    first, last = probe.InvoiceDate.min(), probe.InvoiceDate.max()
    dev_cut = first + (last - first) * .85
    del probe
    gc.collect()

    # Product thresholds are learned only from the development interval.
    qframe = pd.read_csv(
        RAW_UCI, usecols=["StockCode", "Quantity", "InvoiceDate"],
        dtype={"StockCode": "string", "Quantity": "int32"}, parse_dates=["InvoiceDate"],
    )
    qdev = qframe[(qframe.InvoiceDate < dev_cut) & (qframe.Quantity > 0) & qframe.StockCode.notna()]
    bulk_threshold = qdev.groupby("StockCode", observed=True).Quantity.quantile(.995).clip(lower=10)
    global_impossible = float(qdev.Quantity.quantile(.9999))
    del qframe, qdev
    gc.collect()

    audit = {
        "source_rows": 0, "exact_duplicates_removed": 0, "cancelled_lines": 0,
        "negative_quantity_lines": 0, "zero_quantity_lines": 0,
        "invalid_price_lines": 0, "missing_date": 0, "missing_sku": 0,
        "missing_customer_id": 0, "potential_impossible_quantity_lines": 0,
        "bulk_threshold": "per-SKU 99.5th percentile, learned before 85% time cutoff",
        "impossible_flag_threshold_global_dev_q9999": global_impossible,
        "development_threshold_cutoff": str(dev_cut),
        "currency": "GBP as supplied by UCI; no conversion performed",
        "timezone": "UTC-normalized naive source timestamps",
    }
    seen: set[int] = set()
    daily_parts, sku_day_parts = [], []
    for chunk in pd.read_csv(
        RAW_UCI, usecols=cols, chunksize=100_000,
        dtype={"Invoice": "string", "StockCode": "string", "Quantity": "int32",
               "Price": "float32", "Customer ID": "float32"},
        parse_dates=["InvoiceDate"],
    ):
        audit["source_rows"] += len(chunk)
        hashes = pd.util.hash_pandas_object(chunk, index=False)
        duplicate = hashes.duplicated(keep="first") | hashes.isin(seen)
        audit["exact_duplicates_removed"] += int(duplicate.sum())
        seen.update(int(x) for x in hashes[~duplicate].to_numpy())
        chunk = chunk.loc[~duplicate].copy()
        invoice = chunk.Invoice.fillna("")
        cancelled = invoice.str.startswith("C")
        negative = chunk.Quantity < 0
        zero = chunk.Quantity == 0
        invalid_price = chunk.Price.isna() | (chunk.Price < 0)
        audit["cancelled_lines"] += int(cancelled.sum())
        audit["negative_quantity_lines"] += int(negative.sum())
        audit["zero_quantity_lines"] += int(zero.sum())
        audit["invalid_price_lines"] += int(invalid_price.sum())
        audit["missing_date"] += int(chunk.InvoiceDate.isna().sum())
        audit["missing_sku"] += int(chunk.StockCode.isna().sum())
        audit["missing_customer_id"] += int(chunk["Customer ID"].isna().sum())
        threshold = chunk.StockCode.map(bulk_threshold).fillna(global_impossible)
        impossible = chunk.Quantity.abs() > global_impossible
        audit["potential_impossible_quantity_lines"] += int(impossible.sum())
        valid = chunk.InvoiceDate.notna() & chunk.StockCode.notna() & ~zero & ~invalid_price
        x = chunk.loc[valid].copy()
        x["date"] = x.InvoiceDate.dt.floor("D")
        x["is_return"] = cancelled[valid].to_numpy() | (x.Quantity < 0)
        x["gross_quantity"] = np.where(~x.is_return, x.Quantity.clip(lower=0), 0)
        x["return_quantity"] = np.where(x.is_return, x.Quantity.abs(), 0)
        x["gross_revenue"] = x.gross_quantity * x.Price
        x["return_value"] = x.return_quantity * x.Price
        x["is_bulk"] = (~x.is_return) & (x.Quantity > x.StockCode.map(bulk_threshold).fillna(global_impossible))
        x["bulk_quantity"] = np.where(x.is_bulk, x.gross_quantity, 0)
        x["customer_known"] = x["Customer ID"].notna()

        daily_parts.append(x.groupby("date", as_index=False).agg(
            gross_quantity=("gross_quantity", "sum"), return_quantity=("return_quantity", "sum"),
            gross_revenue=("gross_revenue", "sum"), return_value=("return_value", "sum"),
            transaction_lines=("Invoice", "size"), invoice_count=("Invoice", "nunique"),
            active_customers=("Customer ID", "nunique"), active_skus=("StockCode", "nunique"),
            average_price=("Price", "mean"), bulk_quantity=("bulk_quantity", "sum"),
        ))
        sku_day_parts.append(x.loc[~x.is_return].groupby(["StockCode", "date"], as_index=False).agg(
            quantity=("gross_quantity", "sum"), revenue=("gross_revenue", "sum"),
            invoice_count=("Invoice", "nunique")))
    daily = pd.concat(daily_parts).groupby("date", as_index=False).sum(numeric_only=True)
    # Mean price must be reconstructed approximately from value/quantity, not summed chunk means.
    daily["average_price"] = daily.gross_revenue / daily.gross_quantity.replace(0, np.nan)
    daily["net_quantity"] = daily.gross_quantity - daily.return_quantity
    daily["net_revenue"] = daily.gross_revenue - daily.return_value
    daily["return_rate"] = daily.return_quantity / daily.gross_quantity.replace(0, np.nan)
    daily["bulk_share"] = daily.bulk_quantity / daily.gross_quantity.replace(0, np.nan)
    daily["average_basket_quantity"] = daily.gross_quantity / daily.invoice_count.replace(0, np.nan)
    daily = daily.sort_values("date").reset_index(drop=True)
    sku_day = pd.concat(sku_day_parts).groupby(["StockCode", "date"], as_index=False).sum(numeric_only=True)
    audit["clean_rows_retained"] = int(audit["source_rows"] - audit["exact_duplicates_removed"]
                                       - audit["zero_quantity_lines"] - audit["invalid_price_lines"]
                                       - audit["missing_date"] - audit["missing_sku"])
    audit["date_from"], audit["date_to"] = str(daily.date.min().date()), str(daily.date.max().date())
    return daily, sku_day, audit


def _simple_daily(sales: pd.DataFrame) -> pd.DataFrame:
    daily = sales.assign(date=sales.sold_at.dt.tz_localize(None).dt.floor("D")).groupby("date", as_index=False).agg(
        gross_quantity=("quantity", "sum"))
    return daily.sort_values("date").reset_index(drop=True)


def _product_segments(sku_day: pd.DataFrame) -> pd.DataFrame:
    span = max((sku_day.date.max() - sku_day.date.min()).days + 1, 1)
    product = sku_day.groupby("StockCode").agg(
        total_quantity=("quantity", "sum"), revenue=("revenue", "sum"),
        active_days=("date", "nunique"), mean_nonzero=("quantity", "mean"),
        std_nonzero=("quantity", "std"), first_sale=("date", "min"), last_sale=("date", "max"),
    ).fillna({"std_nonzero": 0}).reset_index()
    product["adi"] = span / product.active_days.clip(lower=1)
    product["cv2"] = (product.std_nonzero / product.mean_nonzero.replace(0, np.nan)) ** 2
    product = product.sort_values("revenue", ascending=False)
    share = product.revenue.cumsum() / max(product.revenue.sum(), 1e-9)
    product["abc"] = np.select([share <= .80, share <= .95], ["A", "B"], default="C")
    product["xyz"] = pd.cut(product.cv2, [-np.inf, .25, 1, np.inf], labels=["X", "Y", "Z"]).astype(str)
    product["demand_pattern"] = np.select(
        [(product.adi < 1.32) & (product.cv2 < .49),
         (product.adi < 1.32) & (product.cv2 >= .49),
         (product.adi >= 1.32) & (product.cv2 < .49)],
        ["smooth", "erratic", "intermittent"], default="lumpy")
    product["velocity"] = pd.qcut(product.active_days.rank(method="first"), 3,
                                   labels=["slow", "medium", "fast"]).astype(str)
    product["cold_start"] = product.first_sale >= sku_day.date.max() - pd.Timedelta(days=90)
    monthly = sku_day.assign(month=sku_day.date.dt.month).groupby(["StockCode", "month"]).quantity.sum()
    concentration = monthly.groupby(level=0).max() / monthly.groupby(level=0).sum()
    product["seasonal_candidate"] = product.StockCode.map(concentration).fillna(0) >= .25
    return product.sort_values("StockCode").reset_index(drop=True)


def _features(daily: pd.DataFrame, target: str, horizon: int, country: str) -> pd.DataFrame:
    date_index = pd.date_range(daily.date.min(), daily.date.max(), freq="D")
    base = daily.set_index("date").reindex(date_index)
    base.index.name = "date"
    base["observed_record_day"] = base[target].notna().astype(int)
    # dict.fromkeys de-duplicates while preserving order: `target` is often one
    # of the named columns too, and a repeated label makes the assignment below
    # raise "Columns must be same length as key".
    quantity_cols = list(dict.fromkeys(
        c for c in ["gross_quantity", "return_quantity", "net_quantity",
                    "gross_revenue", "net_revenue", target] if c in base))
    base[quantity_cols] = base[quantity_cols].fillna(0)
    for col in base.columns:
        if col not in quantity_cols and col != "observed_record_day":
            base[col] = base[col].fillna(0)
    s = base[target].astype(float)
    frame = pd.DataFrame({"date": date_index})
    frame["target"] = s.rolling(horizon).sum().shift(-(horizon - 1)).to_numpy()
    lags = [1, 2, 3, 7, 14, 21, 28, 56] + ([365] if len(s) >= 730 else [])
    for lag in lags:
        frame[f"lag_{lag}"] = s.shift(lag).to_numpy()
    for window in (7, 14, 28, 56):
        past = s.shift(1).rolling(window)
        frame[f"roll_mean_{window}"] = past.mean().to_numpy()
        frame[f"roll_median_{window}"] = past.median().to_numpy()
        frame[f"roll_std_{window}"] = past.std().to_numpy()
        frame[f"roll_min_{window}"] = past.min().to_numpy()
        frame[f"roll_max_{window}"] = past.max().to_numpy()
    frame["ewm_7"] = s.shift(1).ewm(span=7, adjust=False).mean().to_numpy()
    frame["ewm_28"] = s.shift(1).ewm(span=28, adjust=False).mean().to_numpy()
    frame["growth_7"] = (s.shift(1) / s.shift(8).replace(0, np.nan) - 1).replace([np.inf, -np.inf], np.nan).to_numpy()
    frame["previous_week_total"] = s.shift(1).rolling(7).sum().to_numpy()
    frame["previous_month_total"] = s.shift(1).rolling(30).sum().to_numpy()
    past_positive = (s.shift(1) > 0).to_numpy()
    days_since, zero_streak, last_seen, streak = [], [], None, 0
    for i, positive in enumerate(past_positive):
        if positive:
            last_seen, streak = i, 0
        else:
            streak += 1
        days_since.append(i - last_seen if last_seen is not None else np.nan)
        zero_streak.append(streak)
    frame["days_since_last_positive"] = days_since
    frame["recent_zero_streak"] = zero_streak
    d = frame.date.dt
    frame["dow_sin"], frame["dow_cos"] = np.sin(2*np.pi*d.dayofweek/7), np.cos(2*np.pi*d.dayofweek/7)
    frame["month_sin"], frame["month_cos"] = np.sin(2*np.pi*d.month/12), np.cos(2*np.pi*d.month/12)
    frame["quarter"], frame["week_of_year"] = d.quarter, d.isocalendar().week.astype(int)
    frame["month_start"], frame["month_end"] = d.is_month_start.astype(int), d.is_month_end.astype(int)
    frame["payday_window"] = ((d.day <= 3) | (d.day >= 25)).astype(int)
    weekend = [4, 5] if country == "BD" else [5, 6]
    frame["is_weekend"] = d.dayofweek.isin(weekend).astype(int)
    frame["trend"] = np.arange(len(frame))
    # Business variables are lagged; same-day transaction counts would leak demand.
    for col in ["invoice_count", "active_customers", "active_skus", "average_basket_quantity",
                "average_price", "return_rate", "bulk_share", "observed_record_day"]:
        if col in base:
            frame[f"prev_{col}"] = base[col].shift(1).to_numpy()
            frame[f"mean7_{col}"] = base[col].shift(1).rolling(7).mean().to_numpy()
    frame["baseline"] = (s.shift(7) if horizon == 1 else s.shift(1).rolling(horizon).sum()).to_numpy()
    return frame.replace([np.inf, -np.inf], np.nan).dropna().reset_index(drop=True)


def _metrics(y: np.ndarray, pred: np.ndarray, scale: np.ndarray | None = None) -> dict:
    y, pred = np.asarray(y, float), np.maximum(0, np.asarray(pred, float))
    error, ae = y - pred, np.abs(y - pred)
    denominator = max(np.abs(y).sum(), 1e-9)
    naive_scale = np.mean(np.abs(np.diff(scale))) if scale is not None and len(scale) > 1 else np.nan
    rms_scale = np.sqrt(np.mean(np.diff(scale) ** 2)) if scale is not None and len(scale) > 1 else np.nan
    nonzero = np.abs(y) > 1e-9
    return {
        "wape": float(ae.sum()/denominator), "mae": float(mean_absolute_error(y, pred)),
        "rmse": float(mean_squared_error(y, pred)**.5),
        "mase": float(ae.mean()/naive_scale) if naive_scale and np.isfinite(naive_scale) else None,
        "rmsse": float(np.sqrt(np.mean(error**2))/rms_scale) if rms_scale and np.isfinite(rms_scale) else None,
        "mape_nonzero": float(np.mean(ae[nonzero]/np.abs(y[nonzero]))) if nonzero.any() else None,
        "bias": float(error.mean()), "overforecast_mae": float(np.maximum(-error, 0).mean()),
        "underforecast_mae": float(np.maximum(error, 0).mean()),
        "r2": float(r2_score(y, pred)) if len(y) > 1 else None,
    }


def _model_factories() -> dict[str, Callable[[], object]]:
    return {
        "hist_l1": lambda: HistGradientBoostingRegressor(loss="absolute_error", max_iter=300,
                    learning_rate=.04, max_leaf_nodes=15, l2_regularization=3, random_state=SEED),
        "hist_huber_proxy": lambda: make_pipeline(RobustScaler(), HuberRegressor(max_iter=1000, epsilon=1.5)),
        "hist_quantile50": lambda: HistGradientBoostingRegressor(loss="quantile", quantile=.5,
                    max_iter=300, learning_rate=.04, max_leaf_nodes=15, random_state=SEED),
        "extra_l1": lambda: ExtraTreesRegressor(n_estimators=300, criterion="absolute_error",
                    min_samples_leaf=3, max_features=.8, n_jobs=1, random_state=SEED),
        "xgb_l1": lambda: XGBRegressor(n_estimators=400, learning_rate=.025, max_depth=3,
                    min_child_weight=5, subsample=.85, colsample_bytree=.85, reg_lambda=4,
                    objective="reg:absoluteerror", n_jobs=1, random_state=SEED),
        "hist_log1p": lambda: TransformedTargetRegressor(
                    regressor=HistGradientBoostingRegressor(max_iter=300, learning_rate=.04,
                    max_leaf_nodes=15, l2_regularization=3, random_state=SEED),
                    func=np.log1p, inverse_func=np.expm1),
        "poisson": lambda: make_pipeline(RobustScaler(), PoissonRegressor(alpha=1, max_iter=1000)),
        "tweedie": lambda: make_pipeline(RobustScaler(), TweedieRegressor(power=1.5, alpha=1, max_iter=1000)),
    }


def _run_task(dataset: str, daily: pd.DataFrame, target: str, horizon: int, country: str) -> dict:
    data = _features(daily, target, horizon, country)
    cut = int(len(data)*.85)
    dev, test = data.iloc[:cut], data.iloc[cut:]
    features = [c for c in data if c not in {"date", "target", "baseline"}]
    splitter = TimeSeriesSplit(n_splits=4)
    factories = _model_factories()
    cv, oof_errors = {"seasonal_or_recent_baseline": []}, {}
    for _, val_idx in splitter.split(dev):
        val = dev.iloc[val_idx]
        cv["seasonal_or_recent_baseline"].append(_metrics(val.target, val.baseline)["wape"])
    for name, factory in factories.items():
        scores, errors = [], []
        for train_idx, val_idx in splitter.split(dev):
            train, val = dev.iloc[train_idx], dev.iloc[val_idx]
            if name in {"poisson", "tweedie", "hist_log1p"} and (train.target < 0).any():
                scores = []
                break
            model = factory()
            try:
                model.fit(train[features], train.target)
                pred = np.maximum(0, model.predict(val[features]))
            except (ValueError, FloatingPointError):
                scores = []
                break
            scores.append(_metrics(val.target, pred)["wape"])
            errors.extend(np.abs(val.target.to_numpy()-pred).tolist())
        if scores:
            cv[name], oof_errors[name] = scores, errors
    summary = {name: {"mean_wape": float(np.mean(scores)), "std_wape": float(np.std(scores)),
                      "fold_wape": scores} for name, scores in cv.items()}
    ranked_models = [n for n in sorted(oof_errors, key=lambda n: summary[n]["mean_wape"])]
    selected = min(summary, key=lambda n: summary[n]["mean_wape"])
    predictions = {"seasonal_or_recent_baseline": test.baseline.to_numpy()}
    fitted = {}
    for name in ranked_models:
        model = factories[name]()
        model.fit(dev[features], dev.target)
        fitted[name] = model
        predictions[name] = np.maximum(0, model.predict(test[features]))
    top = ranked_models[:3]
    if top:
        inv = np.array([1/max(summary[n]["mean_wape"], 1e-6) for n in top])
        weights = inv/inv.sum()
        predictions["cv_weighted_ensemble"] = sum(w*predictions[n] for w, n in zip(weights, top))
        # Ensemble is eligible only through development-CV members; its test result is diagnostic.
    holdout = {name: _metrics(test.target.to_numpy(), pred, dev.target.to_numpy())
               for name, pred in predictions.items()}
    chosen_pred = predictions[selected]
    q90 = float(np.quantile(oof_errors[selected], .90)) if selected in oof_errors else float(
        np.quantile(np.abs(dev.target-dev.baseline), .90))
    lower, upper = np.maximum(0, chosen_pred-q90), chosen_pred+q90
    holdout[selected]["prediction_interval_90_coverage"] = float(
        np.mean((test.target.to_numpy() >= lower) & (test.target.to_numpy() <= upper)))
    holdout[selected]["wape_bootstrap_95_ci"] = _bootstrap_wape(test.target.to_numpy(), chosen_pred)
    base_wape = holdout["seasonal_or_recent_baseline"]["wape"]
    holdout[selected]["relative_wape_improvement_vs_baseline"] = float(
        (base_wape-holdout[selected]["wape"])/base_wape) if base_wape else None
    if selected in fitted:
        joblib.dump({"model": fitted[selected], "features": features, "target": target,
                     "horizon_days": horizon, "trained_until": str(dev.date.max())},
                    MODELS/f"{dataset}_{target}_h{horizon}_{selected}.joblib")
    return {
        "target": target, "horizon_days": horizon, "forecast_mode": "direct rolling-origin",
        "development_rows": len(dev), "holdout_rows": len(test),
        "holdout_from": str(test.date.min().date()), "holdout_to": str(test.date.max().date()),
        "selected_by_cv": selected, "cv": summary, "holdout": holdout,
        "ensemble_members": top, "fixed_holdout_is_development_evidence_after_prior_inspection": True,
    }


def _bootstrap_wape(y: np.ndarray, pred: np.ndarray) -> list[float]:
    rng, values = np.random.default_rng(SEED), []
    for _ in range(500):
        idx = rng.integers(0, len(y), len(y))
        values.append(np.abs(y[idx]-pred[idx]).sum()/max(np.abs(y[idx]).sum(), 1e-9))
    return [float(np.quantile(values, .025)), float(np.quantile(values, .975))]


def main() -> None:
    uci, sku_day, audit = _daily_uci()
    bd = _simple_daily(load_bd_retailer_demand())
    raw_syn = pd.read_csv("BD_Pharmacy_Dataset.csv", usecols=["Transaction_Date", "Quantity"])
    syn = raw_syn.assign(sold_at=pd.to_datetime(raw_syn.Transaction_Date, utc=True))
    syn = _simple_daily(syn[["sold_at", "Quantity"]].rename(columns={"Quantity": "quantity"}))
    product = _product_segments(sku_day)
    product.to_csv(OUT/"uci_product_segments.csv", index=False)
    (OUT/"uci_cleaning_audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    tasks = {}
    specifications = [
        ("uci", uci, "gross_quantity", 1, "UK"), ("uci", uci, "gross_quantity", 7, "UK"),
        ("uci", uci, "gross_quantity", 30, "UK"), ("uci", uci, "return_quantity", 1, "UK"),
        ("uci", uci, "net_quantity", 1, "UK"), ("uci", uci, "gross_revenue", 1, "UK"),
        ("bangladesh", bd, "gross_quantity", 1, "BD"), ("bangladesh", bd, "gross_quantity", 7, "BD"),
        ("bangladesh", bd, "gross_quantity", 30, "BD"),
        ("synthetic", syn, "gross_quantity", 1, "BD"),
    ]
    for dataset, daily, target, horizon, country in specifications:
        key = f"{dataset}_{target}_h{horizon}"
        print(f"Running {key}", flush=True)
        tasks[key] = _run_task(dataset, daily, target, horizon, country)
        result = tasks[key]
        metric = result["holdout"][result["selected_by_cv"]]["wape"]
        print(f"  selected {result['selected_by_cv']}: {metric*100:.2f}% WAPE", flush=True)
    status = {
        "implemented": [
            "deduplication and explicit cancellation/return/invalid/missing audits",
            "gross, return, net, revenue and 1/7/30-day direct targets where observed",
            "per-SKU development-only bulk thresholds without deleting extreme orders",
            "ABC/XYZ, velocity, ADI-CV2 demand pattern, cold-start and seasonal-candidate segmentation",
            "rich strictly lagged rolling, EWMA, trend, zero-streak, calendar and observed business features",
            "robust L1, Huber, quantile, log1p, Poisson, Tweedie, Extra Trees and XGBoost candidates",
            "four-fold time-series CV, fixed holdout, baseline, uncertainty and expanded error metrics",
        ],
        "not_observed_do_not_fabricate": {
            "bangladesh_retailer": ["customer", "price/revenue", "SKU/category", "branch", "returns",
                                       "inventory/stock-out", "promotion", "supplier", "payment", "weather"],
            "uci": ["true product category", "stock/inventory", "promotion", "supplier lead time",
                    "payment method", "perishable flag", "known store-closure flag"],
        },
        "deferred_reasons": {
            "Prophet/LightGBM/CatBoost/Optuna/deep architectures/survival":
                "packages absent and sample size does not justify adding them before lighter baselines win",
            "Bangladesh holidays/weather":
                "no versioned aligned source is bundled; adding guessed historical values would fabricate evidence",
            "new SME data and future confirmation": "requires external collection and elapsed future time",
        },
    }
    report = {"protocol": {"seed": SEED, "selection": "development rolling CV only",
                           "evidence_boundary": "real and synthetic results remain separate"},
              "cleaning_audit": audit, "product_segment_counts": {
                  "abc": product.abc.value_counts().to_dict(),
                  "xyz": product.xyz.value_counts().to_dict(),
                  "demand_pattern": product.demand_pattern.value_counts().to_dict(),
                  "velocity": product.velocity.value_counts().to_dict()},
              "tasks": tasks, "checklist_status": status}
    (OUT/"advanced_benchmark.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    keys = [k for k in tasks if k.endswith("gross_quantity_h1")]
    values = [tasks[k]["holdout"][tasks[k]["selected_by_cv"]]["wape"]*100 for k in keys]
    fig, ax = plt.subplots(figsize=(9, 4.8))
    bars = ax.bar([k.split("_")[0].title() for k in keys], values, color=["#22577A", "#0A8754", "#9C6644"])
    ax.set_ylabel("Fixed-holdout WAPE (%) — lower is better")
    ax.set_title("Advanced Leakage-Safe Daily Gross-Demand Benchmark")
    for bar, value in zip(bars, values):
        ax.text(bar.get_x()+bar.get_width()/2, value+.4, f"{value:.2f}%", ha="center")
    ax.set_ylim(0, max(values)*1.25); ax.grid(axis="y", alpha=.25); fig.tight_layout()
    fig.savefig(FIG/"advanced_daily_gross_wape.png", dpi=180); plt.close(fig)
    print("Saved artifacts/advanced/advanced_benchmark.json")


if __name__ == "__main__":
    main()
