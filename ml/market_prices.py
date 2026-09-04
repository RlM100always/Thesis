"""Real Bangladeshi market prices — WFP Price Database via HDX.

THE ONLY REAL BANGLADESHI DATA IN THIS REPOSITORY.
--------------------------------------------------
Everything under output/ comes from the synthetic Faker dataset. This module
is different: `data/real_public/wfp_food_prices_bgd.csv` holds actual observed
retail/wholesale prices in BDT, collected by the World Food Programme from
Bangladesh's Department of Agricultural Marketing (DAM) and FAO GIEWS.

    Source   : https://data.humdata.org/dataset/wfp-food-prices-for-bangladesh
    License  : CC BY-IGO (attribution required — cite WFP and DAM)
    Coverage : 110 markets, all 8 divisions, 73 commodities, monthly

WHAT IT CAN AND CANNOT SUPPORT
------------------------------
It CAN support: real market-price context features (the X_market term in the
problem formulation), and a genuine real-data price-forecasting benchmark.

It CANNOT support: SKU demand forecasting, churn, RFM, or inventory strategy.
There are no invoices, no quantities sold, and no customers here — only prices.
Those still require the consenting-SME collection in docs/REAL_DATA_PROTOCOL.md.
Do not describe results from this file as "SME sales data".

Usage:
    python -m ml.market_prices --commodity "Rice (coarse)"
    python -m ml.market_prices --all --output artifacts/real_public
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

RAW_PATH = Path("data/real_public/wfp_food_prices_bgd.csv")

# WFP widened its Bangladesh basket in Feb 2024, so the series split into two
# groups. Only these four run back to 2004-2005 and are long enough to train and
# test a seasonal model on — use them for benchmarking.
LONG_HISTORY_COMMODITIES = [
    "Rice (coarse)",            # 216 months from 2004-01
    "Wheat flour",              # 212 months from 2005-10
    "Lentils (masur)",          # 199 months from 2005-10
    "Oil (palm)",               # 197 months from 2005-10
]

# The wider basket, mostly starting 2024-02. Too short to benchmark a seasonal
# model on, but valid as market-context features for recent sales.
RECENT_BASKET_COMMODITIES = LONG_HISTORY_COMMODITIES + [
    "Sugar", "Oil (soybean, fortified)", "Potatoes (Holland, white)",
    "Chili (green)", "Garlic (imported, China)", "Meat (chicken, broiler)",
    "Onions (imported, China)", "Eggs (brown)",
]

STAPLE_COMMODITIES = LONG_HISTORY_COMMODITIES  # default for the CLI benchmark


class InsufficientPriceData(RuntimeError):
    """Raised instead of returning a fabricated series."""


def load_prices(path: Path = RAW_PATH) -> pd.DataFrame:
    """Load and clean the WFP file into tidy monthly observations."""
    if not path.is_file():
        raise InsufficientPriceData(
            f"Missing {path}. Download it first:\n"
            "  curl -sL -o data/real_public/wfp_food_prices_bgd.csv \\\n"
            "    https://data.humdata.org/dataset/c76eabb7-fdb5-43b7-a5c4-09091bb8acde"
            "/resource/966ab7ac-56d6-4dac-8eba-dfe815d59a52/download/wfp_food_prices_bgd.csv"
        )
    frame = pd.read_csv(path, low_memory=False)
    # HDX ships a HXL tag row ("#date", "#adm1+name", ...) directly under the header.
    if str(frame.iloc[0].get("date", "")).startswith("#"):
        frame = frame.iloc[1:].reset_index(drop=True)

    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["price"] = pd.to_numeric(frame["price"], errors="coerce")
    frame = frame.dropna(subset=["date", "price", "commodity", "unit"])

    # Only directly observed prices; "aggregate" rows are WFP's own derived values.
    if "priceflag" in frame.columns:
        frame = frame[frame["priceflag"].astype(str).str.strip() == "actual"]
    # A single stray 1900 record exists in the source file.
    frame = frame[frame["date"] >= "1998-01-01"]
    return frame.reset_index(drop=True)


def monthly_series(
    frame: pd.DataFrame, commodity: str, pricetype: str = "Retail", min_months: int = 48,
) -> pd.Series:
    """National monthly price for one commodity, in BDT per its own unit.

    Prices are aggregated across markets with the median, which is robust to a
    single market reporting an outlier. Units are never mixed: the most-reported
    unit for the commodity wins, and rows in other units are dropped.
    """
    subset = frame[(frame.commodity == commodity) & (frame.pricetype == pricetype)]
    if subset.empty:
        raise InsufficientPriceData(f"No {pricetype} rows for {commodity!r}")

    unit = subset["unit"].value_counts().idxmax()
    subset = subset[subset.unit == unit]

    series = (
        subset.set_index("date")["price"].resample("MS").median().dropna()
    )
    if len(series) < min_months:
        raise InsufficientPriceData(
            f"{commodity!r} has {len(series)} monthly points; need {min_months}+"
        )
    series.attrs["unit"] = unit
    series.attrs["commodity"] = commodity
    return series


def _metrics(actual: np.ndarray, predicted: np.ndarray, train: np.ndarray) -> dict:
    """MAE/RMSE/WAPE plus MASE against a seasonal-naive scale, as Chapter 5 requires."""
    error = np.abs(actual - predicted)
    denominator = np.abs(actual).sum()
    # MASE scale: in-sample seasonal-naive (12-month) mean absolute error.
    scale = np.mean(np.abs(train[12:] - train[:-12])) if len(train) > 12 else np.nan
    return {
        "mae": float(error.mean()),
        "rmse": float(np.sqrt(((actual - predicted) ** 2).mean())),
        "wape": float(error.sum() / denominator) if denominator else float("nan"),
        "mase": float(error.mean() / scale) if scale and not np.isnan(scale) else None,
    }


def benchmark(series: pd.Series, test_months: int = 12) -> dict:
    """Chronological hold-out benchmark: seasonal-naive vs SARIMA vs gradient boosting.

    The split is strictly by time — the test window is the final `test_months`
    and no model sees any of it during fitting.
    """
    if len(series) < test_months + 36:
        raise InsufficientPriceData(
            f"Need {test_months + 36}+ months, have {len(series)}"
        )
    train, test = series.iloc[:-test_months], series.iloc[-test_months:]
    actual = test.to_numpy()
    train_values = train.to_numpy()
    results: dict[str, dict] = {}

    # 1. Seasonal-naive: same month last year. The baseline that must be beaten.
    seasonal = series.shift(12).iloc[-test_months:].to_numpy()
    if not np.isnan(seasonal).any():
        results["seasonal_naive_12"] = _metrics(actual, seasonal, train_values)

    # 2. Naive: last observed value carried forward.
    results["naive_last_value"] = _metrics(
        actual, np.repeat(train_values[-1], test_months), train_values
    )

    # 3. SARIMA. Skipped (not faked) when statsmodels is absent or fitting fails.
    try:
        from statsmodels.tsa.statespace.sarimax import SARIMAX

        model = SARIMAX(
            train_values, order=(1, 1, 1), seasonal_order=(1, 1, 0, 12),
            enforce_stationarity=False, enforce_invertibility=False,
        ).fit(disp=False)
        results["sarima_111_110_12"] = _metrics(
            actual, np.asarray(model.forecast(steps=test_months)), train_values
        )
    except Exception as exc:  # noqa: BLE001 — report, never substitute a fake number
        results["sarima_111_110_12"] = {"unavailable": str(exc)[:200]}

    # 4. Gradient boosting on lag features, forecast recursively.
    try:
        from sklearn.ensemble import HistGradientBoostingRegressor

        lags = [1, 2, 3, 6, 12]
        frame = pd.DataFrame({"y": series})
        for lag in lags:
            frame[f"lag_{lag}"] = frame["y"].shift(lag)
        frame["month"] = frame.index.month
        frame = frame.dropna()
        features = [f"lag_{lag}" for lag in lags] + ["month"]

        fit_frame = frame.iloc[:-test_months]
        model = HistGradientBoostingRegressor(max_iter=300, random_state=42)
        model.fit(fit_frame[features], fit_frame["y"])

        history = list(train_values)
        predictions = []
        for step in range(test_months):
            row = {f"lag_{lag}": history[-lag] for lag in lags}
            row["month"] = test.index[step].month
            predictions.append(float(model.predict(pd.DataFrame([row])[features])[0]))
            history.append(predictions[-1])
        results["gradient_boosting"] = _metrics(
            actual, np.asarray(predictions), train_values
        )
    except Exception as exc:  # noqa: BLE001
        results["gradient_boosting"] = {"unavailable": str(exc)[:200]}

    scored = {k: v for k, v in results.items() if "wape" in v}
    return {
        "commodity": series.attrs.get("commodity"),
        "unit": series.attrs.get("unit"),
        "months_total": len(series),
        "train_from": str(train.index[0].date()), "train_to": str(train.index[-1].date()),
        "test_from": str(test.index[0].date()), "test_to": str(test.index[-1].date()),
        "models": results,
        "best_by_wape": min(scored, key=lambda k: scored[k]["wape"]) if scored else None,
    }


def price_feature_table(frame: pd.DataFrame, commodities: list[str] | None = None) -> pd.DataFrame:
    """Wide month x commodity table for joining real prices onto sales data.

    This is the X_market term in the problem formulation: join on the sale's
    month to give a demand model the real market context it sat in.
    """
    commodities = commodities or RECENT_BASKET_COMMODITIES
    columns = {}
    for commodity in commodities:
        try:
            # 12 months is enough to be a useful feature, even if far too short
            # to benchmark a seasonal model on.
            columns[commodity] = monthly_series(frame, commodity, min_months=12)
        except InsufficientPriceData:
            continue
    if not columns:
        raise InsufficientPriceData("No commodity had enough monthly history")
    return pd.DataFrame(columns).sort_index()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--commodity", default=None)
    parser.add_argument("--all", action="store_true", help="benchmark every staple")
    parser.add_argument("--test-months", type=int, default=12)
    parser.add_argument("--output", type=Path, default=Path("artifacts/real_public"))
    args = parser.parse_args()

    frame = load_prices()
    targets = (
        STAPLE_COMMODITIES if args.all
        else [args.commodity] if args.commodity
        else STAPLE_COMMODITIES[:1]
    )

    report = {
        "source": "WFP Price Database via HDX (CC BY-IGO)",
        "source_url": "https://data.humdata.org/dataset/wfp-food-prices-for-bangladesh",
        "real_data": True,
        "note": "Real observed Bangladeshi market prices. Not SME sales data.",
        "rows_loaded": len(frame),
        "results": [],
    }
    for commodity in targets:
        try:
            report["results"].append(benchmark(monthly_series(frame, commodity), args.test_months))
        except InsufficientPriceData as exc:
            report["results"].append({"commodity": commodity, "skipped": str(exc)})

    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / "price_forecast_benchmark.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
