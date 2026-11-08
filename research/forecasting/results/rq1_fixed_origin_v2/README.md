# RQ1 fixed-origin multi-candidate benchmark — v2

## Evidence classification

`provenance_conflict`. The input SHA-256 is recorded in `run_manifest.json`. The current Drive manifest claims real observations, but the repository's 2 November onboarding record classifies a same-seed/same-count package as synthetic. Do not present these scores as verified real-world SME accuracy.

## Protocol

- Input: complete daily shop-category panel, 561,152 rows, 512 series.
- Origins: 2025-07-01, 2025-08-01, 2025-09-01.
- Horizons: direct cumulative 1, 7, 14, 28 days.
- Forecasts: 1,536 series-origin forecasts per horizon.
- Minimum history: 56 days; training origin stride: 28 days.
- Features: lags 1/7/14/28/56; rolling mean/std/sum/zero ratio over 7/14/28/56; recency; ADI; positive-demand mean/CV²; shop/category; calendar and cyclical encodings.
- Q4 2025 excluded because it was previously inspected; no final holdout evaluated.

## Candidates

1. LightGBM Tweedie (100 estimators, variance power 1.3, 31 leaves, learning rate 0.035, minimum child samples 80, subsample 0.85, subsample frequency 1, column sample 0.85, L2 2.0, seed 42).
2. CatBoost Tweedie (120 iterations, depth 6, learning rate 0.04, L2 5, seed 42).
3. CatBoost hurdle (100-iteration occurrence classifier × 100-iteration positive-quantity regressor, depth 5, learning rate 0.04, balanced class weights). Occurrence probabilities are not calibrated.
4. Weekly seasonal-naive: average of up to four previous observations for each matching weekday, summed over the horizon.
5. Croston-SBA and 6. TSB (alpha/beta 0.1).

## Results

See `aggregate_metrics.csv`, `origin_metrics_h7.csv`, `regime_metrics_h7.csv`, `regime_distribution.csv`, and `cluster_bootstrap_h7.csv`.

- LightGBM has the lowest pooled WAPE at 7/14/28 days.
- Raw hurdle has the lowest 1-day WAPE but under-forecasts by 28.18%; this is not sufficient for selection.
- At seven days LightGBM has lower WAPE than CatBoost in 22/32 shops and 14/16 categories; per-shop heterogeneity remains.
- Only four of 512 series are classified intermittent, so regime-specific automatic switching is not justified.
- Bootstrap intervals resample shop-category series (2,000 replicates); they quantify variation within development series, not final-test uncertainty.

## Reproduction

```powershell
python -m pip install -r requirements-research.txt
python research/forecasting/rq1_shop_category_experiment.py --input path\to\rq1_daily_shop_category.csv --output path\to\rq1_fixed_origin_v2 --evidence-status provenance_conflict
```

The raw Drive package is not committed. Reproduction requires the exact input checksum in `run_manifest.json`. The script writes full predictions and all metric outputs to the requested output directory.

## Decision

Retain LightGBM Tweedie as the current category-level fallback candidate, CatBoost as challenger, and hurdle as an uncalibrated research candidate. Do not call this an adaptive SKU-level solution. SKU-level work requires a source-aware active-assortment and stock-exposure panel, plus quarantine of negative-ledger events and positive-sale days with non-positive reconstructed stock.
