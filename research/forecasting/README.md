# RQ1 demand forecasting research module

This research-only package contains the demand-forecasting pipelines and their saved experiment outputs. It is separate from the operational B-SMART application and does not modify live business records.

## Dataset

The module uses the Bangladesh package supplied through the project Google Drive folder. Its manifest claims real source data, but a generation seed and “modeled world” wording leave provenance unverified. The prepared SKU-level observed-sales file contains 699,220 positive-sale records. The complete shop-category daily panel used by the existing benchmark contains 561,152 rows, 512 series, 32 shops and 1,096 dates.

The SKU export is sparse: a missing SKU-date is not automatically zero demand. A zero label is valid only when the SKU is active and availability evidence supports that it was in stock for the relevant period. Stockout, inactive assortment, closed-shop and unknown-availability periods must remain censored or unknown.

Raw source data stay in Drive. GitHub stores code, run manifests, non-sensitive aggregate results and figures.

## Existing experiments

The repository contains a fixed-origin benchmark comparing:

- LightGBM Tweedie
- CatBoost Tweedie
- CatBoost hurdle (raw, uncalibrated occurrence probability)
- Weekly seasonal-naive
- Croston-SBA
- TSB

It also contains a context-feature experiment and a historical price/activity feature ablation. Those outputs are development results. The exposure-conditioned SKU diagnostic is saved under `research/experiments/results/rq1_exposure_aware_20261109/`; its Q4 period had been inspected and is not an untouched holdout. The final untouched holdout has not been evaluated.

Recorded fixed-origin pooled WAPE:

| Horizon | LightGBM Tweedie | CatBoost Tweedie | Raw hurdle | Croston-SBA | TSB | Weekly seasonal-naive |
|---:|---:|---:|---:|---:|---:|---:|
| 1 day | 79.80% | 79.98% | 79.23% | 84.01% | 84.78% | 92.21% |
| 7 days | 33.74% | 34.20% | 35.26% | 37.74% | 38.62% | 40.77% |
| 14 days | 24.11% | 24.78% | 24.54% | 30.27% | 32.10% | 33.97% |
| 28 days | 18.57% | 19.28% | 18.84% | 25.62% | 27.38% | 29.16% |

The raw hurdle model's one-day WAPE is accompanied by material aggregate under-forecast bias and uncalibrated probabilities; it is not selected on WAPE alone. LightGBM is the current fallback candidate for 7/14/28-day shop-category development forecasting, with CatBoost retained as a challenger.

## Source audit

Run the source reconciliation against a frozen local export of the Drive files:

~~~powershell
python research/forecasting/audit_rq1_sources.py --data-dir path\to\frozen_drive_export --output-dir artifacts\source_audit
~~~

The audit checks sales-order/line joins, SKU aggregation, category aggregation, inventory SALE movements, purchase receipts and reconstructed stock exposure. It writes aggregate diagnostics and file checksums; do not place raw customer or transaction files in GitHub.

## Fixed-origin model benchmark

~~~powershell
python research/forecasting/rq1_shop_category_experiment.py --input path\to\rq1_daily_shop_category.csv --output artifacts\rq1_fixed_origin_v2 --evidence-status observed_unverified
~~~

## Context-aware experiment

~~~powershell
python research/forecasting/context_aware_experiment.py --input path\to\rq1_daily_shop_category.csv --output artifacts\context_aware_v1 --evidence-status observed_unverified
~~~

## Input contract

The daily panel requires one row per date × shop × category and the following fields:

- date
- shop_id
- category_id or category
- demand or units_sold_observed (non-negative units, not revenue)
- optional is_zero_observed_sales flag that must agree with the quantity

Missing dates are rejected by default. Use a zero only when the source supports a genuine zero-sales day. For SKU-level work, use verified active assortment and inventory exposure rather than filling all absent rows.

## Implemented pipeline components

- Panel validation and explicit missing-date policy
- ADI, CV², zero ratio and descriptive demand regimes
- Historical-only lag, rolling, recency and calendar features
- Direct 1/7/14/28-day cumulative-demand targets
- Seasonal-naive, Croston, SBA and TSB baselines
- Two-stage hurdle, HistGradientBoosting, LightGBM and CatBoost candidates
- Rolling-origin development metrics: WAPE, MAE, RMSE, horizon-scaled weekly MASE and signed bias
- Pooled, per-shop, per-category and demand-regime metrics
- Run manifests, figures and contract tests

## Exposure-conditioned SKU diagnostic and remaining work

The 9 November run reconstructs inventory and assigns zeros only on full-day positive-stock exposure. It quarantines 253 shop-SKU histories containing negative balances. On the previously inspected Q4 2025 period, the 28-day exposed-sales mean has WAPE 183.65%, compared with 184.66% for HistGradientBoosting and 190.28% for weekly seasonal naive. This evaluates observed sales conditional on reconstructed exposure, not latent demand during stock-outs.

1. Validate reconstructed exposure against physical stock or owner-approved inventory records.
2. Freeze model selection, then evaluate once on an untouched future period or held-out businesses.
3. Evaluate shortage costs and subgroups on validated evidence.
4. Calibrate occurrence probabilities and prediction intervals on development-only folds.
5. Add price/promotion features only when timestamps prove they were available at the forecast origin.

Do not describe the development outputs as final holdout performance.