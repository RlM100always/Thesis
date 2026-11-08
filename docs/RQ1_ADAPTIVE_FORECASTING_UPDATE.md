# RQ1 research update — adaptive demand forecasting

Date: 8 November 2026

## Dataset

RQ1 uses the real Bangladesh SME dataset supplied by the researcher through the project Google Drive folder. The prepared SKU-level observed-sales file contains 699,220 positive-sale records. The complete shop-category panel used by the existing benchmark contains 561,152 rows, 512 series, 32 shops and 1,096 days.

The SKU-level export is sparse. Missing SKU-date rows are not automatically zero demand. SKU activity and stock availability must be established before a zero-sales label is assigned.

## Existing source reconciliation

- 365,447 sales orders and 736,683 sales lines are recorded in the Drive manifest.
- The existing audit aggregates sales lines by shop × SKU × date and records an exact match to the 699,220 prepared positive-sale SKU records, totalling 1,580,361 units.
- The complete shop-category panel contains 561,152 rows, 512 series, 1,096 dates and 1,580,361 observed units.
- The previous inventory-ledger audit recorded negative-balance events and positive-sale days with non-positive reconstructed intraday stock. These require reconciliation before SKU availability labels are used as ground truth.

These are previously recorded audit results; this documentation update did not rerun the full source audit or any model.

## Existing fixed-origin development benchmark

The saved benchmark compares LightGBM Tweedie, CatBoost Tweedie, a raw CatBoost hurdle model, weekly seasonal-naive, Croston-SBA and TSB. It uses development origins in July, August and September 2025, with 512 shop-category series and direct cumulative horizons of 1, 7, 14 and 28 days. Q4 2025 was excluded from model selection because it had already been inspected.

| Horizon | LightGBM | CatBoost | Hurdle (raw) | Croston-SBA | TSB | Weekly seasonal-naive |
|---:|---:|---:|---:|---:|---:|---:|
| 1 day | 79.80% | 79.98% | 79.23% | 84.01% | 84.78% | 92.21% |
| 7 days | 33.74% | 34.20% | 35.26% | 37.74% | 38.62% | 40.77% |
| 14 days | 24.11% | 24.78% | 24.54% | 30.27% | 32.10% | 33.97% |
| 28 days | 18.57% | 19.28% | 18.84% | 25.62% | 27.38% | 29.16% |

The hurdle model's one-day WAPE is accompanied by material under-forecast bias and uncalibrated occurrence probabilities. LightGBM remains the current fallback candidate for 7/14/28-day shop-category development forecasting; CatBoost remains a challenger.

## Remaining work

1. Complete the exposure-aware SKU panel and shop/branch–SKU evaluation.
2. Reconcile negative stock balances and affected positive-sale days before availability-based labels are used.
3. Reproduce and document all candidate results from frozen inputs and run manifests.
4. Calibrate occurrence probabilities and prediction intervals using development-only data.
5. Add point-in-time price and promotion features only after verifying their availability timestamps.
6. Freeze model selection and run a genuinely untouched final evaluation.

The current saved outputs are development results. No final untouched holdout has been evaluated.