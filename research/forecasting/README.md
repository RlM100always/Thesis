# Adaptive daily-demand forecasting research module

This is a separate, reproducible research pipeline. It does not alter the
operational B-SMART application, its database, tenant records, serving API or
existing thesis evidence.

## Evidence warning

The user-provided Google Drive package has now been located and structurally
audited. The current Drive manifest claims "100% real SME sales or real people",
but the linked `rq1_daily_sku_sales_observed` sheet marks all 699,220 rows
`synthetic_flag=YES`. The earlier repository onboarding record quotes a
previous manifest that explicitly classified the package as synthetic. These
sources conflict. Until the source owner resolves the flag/manifest discrepancy
and supplies auditable provenance, the package is classified as
`provenance_conflict`; experiment outputs are exploratory and must not be
presented as verified real-world SME evidence.

The RQ1 shop-category panel has 561,152 rows: 32 shops × 16 categories × 1,096
days (2023-01-01 to 2025-12-31). It contains 1,580,361 units and a 37.5962%
zero-sales share overall. The previously inspected 2025-Q4 window contains
47,104 observations and a 39.8204% zero-sales share, matching the previously
reported test-set size and zero rate. The reported WAPE values (83.98%, 84.04%,
84.56%) still require exact reproduction from their original scripts and
definition.

## Input contract

Accepted CSV/XLSX columns include the native RQ1 Drive schema:

- `date`: daily date (ISO date or Excel serial)
- `shop_id`: shop identifier
- `category_id` or `category`: product category identifier
- `demand` or `units_sold_observed`: non-negative quantity sold, not revenue
- optional `is_zero_observed_sales`: must exactly match whether demand is zero

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
python -m pytest --confcutdir=research/forecasting research/forecasting/tests -q
python -m research.forecasting.adaptive_engine --input path\to\rq1_daily_shop_category.csv --output artifacts\adaptive_forecasting --development-end 2025-10-01 --evidence-status provenance_conflict
```

Optional candidate packages are LightGBM and CatBoost. Missing optional
packages are recorded as skipped, not replaced with fabricated results.

## Implemented in v0.1.0

- Strict daily-panel validation and explicit missing-date policy
- Shop/category demand diagnostics: ADI, CV², zero ratio and four demand regimes
- Lag, rolling, recency and calendar feature construction using past data only
- Direct 1/7/14/28-day cumulative-demand targets
- Seasonal-naive, Croston, SBA, TSB, two-stage hurdle, HistGradientBoosting,
  optional LightGBM and optional CatBoost candidates
- Rolling-origin development comparisons with WAPE, MAE, RMSE, series-scaled MASE and bias
- Per-origin forecasts plus pooled, per-shop, per-category and demand-regime metrics
- Development-only model selection per demand regime, requiring at least two origins and ten series forecasts
- `selected_model_by_regime.csv` records those validation-only selections
- Validation figures: WAPE comparison, actual-versus-forecast example and shop-category error heatmap
- Diagnostics, SHA-256 run manifest and automated contract tests
- Tests for data contracts, zero demand, missingness, duplicates and metrics

## Important limitations

- The October–December 2025 legacy test period has already been inspected and
  is excluded from development model selection by the default exclusive cutoff
  of 2025-10-01. The development run uses three monthly spaced origins before
  that cutoff. Q4-2025 is not an untouched final holdout.
- The regime labels are descriptive (ADI/CV²), not proof that one model family
  will win. Candidate choice must be made on development validation and reported
  with per-series/per-shop dispersion.
- The two-stage classifier probability is not calibrated in v0.1.0; the model uses raw probability to form expected demand. Do not interpret it as a calibrated sale probability. v0.1.0 does not yet implement calibrated prediction intervals, stockout
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
