# RQ1 research update — adaptive demand forecasting

**Status:** implementation scaffold committed; empirical rerun pending dataset  
**Date:** 7 November 2026  
**Scope:** RQ1 forecasting only; operational application and tenant data are out of scope

## 1. Verified repository and evidence state

The current repository default branch is `main`. The current checkout contains
no primary research dataset or prior run artifacts. The research onboarding
record classifies the earlier 32-shop, 2023–2025 package as 100% synthetic.
Consequently, the 32-shop counts and the 83.98%, 84.04% and 84.56% WAPE values
provided in the latest conversation are treated as researcher-reported,
unverified results until their source data, code, split and metric calculation
are supplied and reproduced.

The previous 2025-10 to 2025-12 test period has already been inspected. It is
not eligible for new model selection. Any new scores on that same period are
exploratory only and must not be described as an untouched final test.

## 2. Research design

The new implementation introduces a separate adaptive daily-demand pipeline.
Its input unit is shop × category × date, with non-negative quantity demand.
It rejects duplicate daily keys, invalid values and missing dates by default.
Zero-filling missing dates is an explicit user-selected assumption, not a
silent cleaning step.

The pipeline calculates average demand interval (ADI), squared coefficient of
variation (CV²), zero-sales ratio and descriptive smooth/intermittent/erratic/
lumpy regimes. These diagnostics are used to stratify analysis; they do not
automatically establish that a particular algorithm is superior.

## 3. Candidate methods

The v0.1.0 implementation compares a weekly seasonal-naive reference,
Croston, SBA, TSB, a two-stage hurdle model, scikit-learn HistGradientBoosting,
and optional LightGBM and CatBoost. A validation-only selector chooses a
candidate by demand regime when at least two origins and ten series forecasts
are available; unsupported groups remain unselected. Direct cumulative targets
are built for 1, 7, 14 and 28 days.
Features include lagged demand, rolling level/dispersion/zero ratios, time
since last positive sale, ADI/CV² and calendar encodings. Every feature row is
constructed from dates strictly before its forecast origin.

Model fitting uses only training examples whose full target horizon ends before
the validation origin. The development evaluation uses rolling origins. WAPE,
MAE, RMSE, per-series scaled MASE and forecast bias are recorded; zero-total WAPE is null.
Metrics are retained at pooled, per-shop, per-category and demand-regime levels.

## 4. Reproducibility outputs

Each run writes:
- `demand_diagnostics.csv`
- `rolling_origin_metrics.csv`
- `rolling_origin_predictions.csv`
- `selected_model_by_regime.csv`
- `run_manifest.json` including input SHA-256, schema-level counts, date
  coverage, assumptions, horizons, candidate list, environment and limitations.

The isolated research test suite checks panel integrity, duplicate rejection, missing-date
handling, no-demand classification, Croston-family non-negativity, zero-total
WAPE handling, series-specific MASE, direct-horizon target creation, chronological
origins, tree/hurdle model fitting, regime selection and figure generation.
A dedicated GitHub Actions workflow runs these tests without loading the
application-wide FastAPI test fixtures. The hurdle classifier probability is
not calibrated in v0.1.0 and must not be presented as a calibrated probability.

## 5. Limitations and deferred work

The first implementation does not yet provide calibrated occurrence probabilities or prediction intervals,
stockout-censoring correction, promotion/price/market-context covariates,
hierarchical reconciliation or inventory-policy backtesting. These must not be
claimed as implemented. They require verified fields and separate validation.

A daily sales panel alone cannot distinguish low demand from stockout-censored
sales. Where inventory availability is absent, the model estimates observed
sales, not latent unconstrained demand. This distinction is mandatory in the
report.

## 6. Acceptance criteria before thesis results are updated

1. Receive the exact dataset used for the reported WAPE comparison and its
   provenance manifest.
2. Reproduce the existing LightGBM, two-stage and XGBoost results under an
   identical cutoff, forecast horizon, aggregation and WAPE definition.
3. Inspect the 39.82% zero-sales share by shop/category and verify whether zeros
   are observed zero-sales days rather than missing/closed/stockout days.
4. Run rolling-origin development validation and publish per-shop, per-category
   and per-regime results, not only pooled WAPE.
5. Freeze model selection before a genuinely new untouched test or held-out
   business evaluation.
6. Update empirical thesis tables only from the immutable run manifest and
   generated artifacts.

## 7. Current conclusion

No new forecasting accuracy claim is made in this update. The repository now
has a reproducible, leakage-aware experiment entry point and tests, but the
research dataset is not present in the checkout. The next blocking input is the
frozen dataset plus its data dictionary/provenance. Until that arrives, a
world-class researcher should report the model design and verification status,
not invent a winning score.
