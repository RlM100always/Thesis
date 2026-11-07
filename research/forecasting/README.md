# Adaptive daily-demand forecasting research module

This is a separate, reproducible research pipeline. It does not alter the
operational B-SMART application, its database, tenant records, serving API or
existing thesis evidence.

## Evidence warning

The previous 32-shop simulation is documented in
`docs/REAL_DATA_ONBOARDING.md` as 100% synthetic. It is suitable for software
and controlled simulation tests, not for a real-SME accuracy claim. The current
repository checkout contains no primary research dataset. The reported
LightGBM WAPE values (83.98%, 84.04%, 84.56%) are therefore not reproducible
from this checkout and are not independently verified by this module.

## Input contract

CSV columns (exact names):

- `date`: daily date, YYYY-MM-DD
- `shop_id`: stable pseudonymous business/shop identifier
- `category_id`: stable product/category identifier
- `demand`: non-negative quantity sold, not sales revenue

One row per date × shop × category is required. Missing dates are rejected by
default. Only use `--fill-missing-dates-as-zero` after source-system evidence
confirms that a missing row means a genuine zero-sales day rather than a closed
shop, stockout, incomplete export or missing record. Negative quantities must
be reconciled upstream with returns/cancellations; they are not silently
clipped.

The input must be frozen and accompanied by provenance/consent, timezone,
currency/unit, coverage and synthetic/observed status. The run manifest records
a SHA-256 checksum but cannot independently verify provenance.

## Install and run (PowerShell)

```powershell
python -m pip install -r requirements-research.txt
python -m pytest tests/test_adaptive_forecasting.py -q
python -m research.forecasting.adaptive_engine --input path\to\daily_panel.csv --output artifacts\adaptive_forecasting
```

Optional candidate packages are LightGBM and CatBoost. Missing optional
packages are recorded as skipped, not replaced with fabricated results.

## Implemented in v0.1.0

- Strict daily-panel validation and explicit missing-date policy
- Shop/category demand diagnostics: ADI, CV², zero ratio and four demand regimes
- Lag, rolling, recency and calendar feature construction using past data only
- Direct 1/7/14/28-day cumulative-demand targets
- Seasonal-naive, Croston, SBA, TSB, HistGradientBoosting, optional LightGBM
  and optional CatBoost candidates
- Rolling-origin development comparisons with WAPE, MAE, RMSE, series-scaled MASE and bias
- Per-origin forecasts plus pooled, per-shop, per-category and demand-regime metrics
- Validation figures: WAPE comparison, actual-versus-forecast example and shop-category error heatmap
- Diagnostics, SHA-256 run manifest and automated contract tests
- Tests for data contracts, zero demand, missingness, duplicates and metrics

## Important limitations

- The old October–December 2025 test period has already been inspected by the
  researcher and must not be used for new model selection. This module performs
  development rolling-origin evaluation only; it does not label any period as
  an untouched final holdout.
- The regime labels are descriptive (ADI/CV²), not proof that one model family
  will win. Candidate choice must be made on development validation and reported
  with per-series/per-shop dispersion.
- v0.1.0 does not yet implement calibrated prediction intervals, stockout
  censoring correction, promotion/price features, hierarchical reconciliation,
  or inventory-policy simulation. Those require verified source fields and
  separately tested implementations.
- The current implementation's seasonal-naive candidate is a transparent
  weekly seasonal reference, not a universal best baseline.
- A forecast of sales is not unconstrained demand when inventory availability
  is unknown. Do not use sales-only predictions as demand truth during stockouts.
- WAPE is undefined when the actual total is zero. The code records null rather
  than hiding or changing the denominator.

## Next research gates

1. Attach the frozen dataset and its signed/traceable manifest.
2. Verify whether each daily zero means zero demand, closed day, missing data or
   stockout-censored sales.
3. Reproduce the 83.98% benchmark from its original script, exact rows, split,
   horizon, aggregation and WAPE definition.
4. Run this development comparison; inspect failed/skipped models and results
   by shop, category and demand regime.
5. Freeze features, candidate selection and thresholds before obtaining a new
   untouched future period or held-out business.
6. Add calibrated intervals and price/promotion/stock features only if the
   fields are present and known at forecast origin.
7. Evaluate reorder policies separately on identical demand paths and validated
   cost/lead-time/stock data.

Do not update thesis empirical-results claims until a frozen run is produced
from eligible evidence.
