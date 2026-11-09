# RQ1 research update — adaptive demand forecasting

Date: 9 November 2026

## Dataset

RQ1 uses the researcher-supplied Bangladesh data package. Its manifest claims real SME source data but records a generation seed and “modeled world” validation wording. Provenance has not been independently verified. The prepared SKU-level observed-sales file contains 699,220 positive-sale records. The complete shop-category panel used by the existing benchmark contains 561,152 rows, 512 series, 32 shops and 1,096 days.

The SKU-level export is sparse. Missing SKU-date rows are not automatically zero demand. SKU activity and stock availability must be established before a zero-sales label is assigned.

## Existing source reconciliation

- 365,447 sales orders and 736,683 sales lines are recorded in the Drive manifest.
- The existing audit aggregates sales lines by shop × SKU × date and records an exact match to the 699,220 prepared positive-sale SKU records, totalling 1,580,361 units.
- The complete shop-category panel contains 561,152 rows, 512 series, 1,096 dates and 1,580,361 observed units.
- The previous inventory-ledger audit recorded negative-balance events and positive-sale days with non-positive reconstructed intraday stock. These require reconciliation before SKU availability labels are used as ground truth.

The 9 November source audit reran these structural checks. It found 0 unmatched sales lines, 0 shop mismatches, 0 SKU quantity mismatches, 0 positive-category mismatches, 0 unmatched sale movements, and 0 unmatched purchase receipts. It also found 269 negative-balance events across 253 shop-SKU histories and 330 positive-sale days with non-positive reconstructed intraday stock. Reconciliation establishes internal consistency, not source authenticity or physical-stock accuracy.

## Existing fixed-origin development benchmark

The saved benchmark compares LightGBM Tweedie, CatBoost Tweedie, a raw CatBoost hurdle model, weekly seasonal-naive, Croston-SBA and TSB. It uses development origins in July, August and September 2025, with 512 shop-category series and direct cumulative horizons of 1, 7, 14 and 28 days. Q4 2025 was excluded from model selection because it had already been inspected.

| Horizon | LightGBM | CatBoost | Hurdle (raw) | Croston-SBA | TSB | Weekly seasonal-naive |
|---:|---:|---:|---:|---:|---:|---:|
| 1 day | 79.80% | 79.98% | 79.23% | 84.01% | 84.78% | 92.21% |
| 7 days | 33.74% | 34.20% | 35.26% | 37.74% | 38.62% | 40.77% |
| 14 days | 24.11% | 24.78% | 24.54% | 30.27% | 32.10% | 33.97% |
| 28 days | 18.57% | 19.28% | 18.84% | 25.62% | 27.38% | 29.16% |

The hurdle model's one-day WAPE is accompanied by material under-forecast bias and uncalibrated occurrence probabilities. LightGBM remains the current fallback candidate for 7/14/28-day shop-category development forecasting; CatBoost remains a challenger.

## 9 November exposure-conditioned SKU diagnostic

The ledger reconstruction retained 13,545,871 exposed shop-SKU days after quarantining all 253 histories with negative balances. It assigned zeros only to 12,860,044 full-day exposed records and retained 685,827 positive eligible records. The Q4 2025 diagnostic evaluated 1,130,148 exposed days from 13,019 series; these include 119,161 observed units and a 95.34% zero share. Q4 had been inspected in prior project work and is not an untouched holdout.

| Model | WAPE | MAE (units/day) | RMSE | Bias |
|---|---:|---:|---:|---:|
| Weekly seasonal naive | 190.28% | 0.201 | 0.853 | +1.19% |
| 28-day exposed-sales mean | 183.65% | 0.194 | 0.616 | +0.82% |
| HistGradientBoosting | 184.66% | 0.195 | 0.604 | +2.06% |

The 28-day mean has lower WAPE than HGB by 1.01 percentage points. A 2,000-resample shop bootstrap interval for HGB minus the mean is -0.21 to +2.25 points and includes zero. The HGB candidate improves on weekly naive but does not beat the strongest simple baseline on WAPE.

## Remaining RQ1 work

1. Verify source lineage and validate ledger-derived exposure against physical stock or an owner-approved inventory snapshot.
2. Evaluate once on an untouched future period or held-out businesses after model selection is frozen.
3. Evaluate business-relevant shortage costs and subgroup performance without treating observed sales as latent demand during stock-outs.
4. Reproduce the separate multi-horizon shop-category development results from frozen inputs if those outputs are to be treated as current.

The saved Q4 results are diagnostic evidence only; no final holdout has been evaluated.