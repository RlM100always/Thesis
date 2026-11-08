# RQ1 research update — adaptive demand forecasting

**Date:** 8 November 2026  
**Scope:** RQ1 forecasting and source-data reconciliation  
**Status:** transaction/SKU/category reconciliation completed; inventory ledger audited; fixed-origin model challengers tested; provenance remains unresolved; no final holdout evaluated.

## 1. Evidence classification

The current Drive manifest claims that the package contains real SME sales or real people. The repository's 2 November onboarding record classifies a package with the same seed, entity counts and coverage as fully synthetic. It also records a `synthetic_flag=YES` field; the current accessible SKU sheet no longer exposes that field. The mismatch is unresolved.

**Evidence class: `provenance_conflict`.** Results are reproducible controlled development evidence only. They must not be called verified real-world Bangladeshi SME accuracy until the source owner supplies traceable origin, consent/collection, anonymisation, data dictionary and explanation of the previous synthetic classification.

## 2. Source reconciliation results

- 365,447 sales orders; 736,683 sales lines.
- Every sales line joins one order; no missing order references or shop mismatches.
- Sales lines aggregated by shop × SKU × date reproduce all 699,220 prepared SKU observed-sales rows exactly, including 1,580,361 units and sales value to floating-point precision.
- SKU-to-category aggregation reproduces all 350,180 positive shop-category-date rows exactly.
- The complete shop-category panel has 561,152 rows, 512 series, 1,096 days, 1,580,361 units and 210,972 zero-sales rows (37.5962%).
- The already inspected 2025-Q4 period has 47,104 rows, 18,757 zero rows (39.8204%), and 121,157 units; it is not used for model selection or represented as an untouched test.
- 736,683 SALE inventory movements match sales lines one-to-one. 121,107 PURCHASE movement groups match received purchase-order/SKU quantities.
- The reconstructed inventory ledger has 269 negative-balance events in 253 shop-SKU combinations and 330 positive-sale days with non-positive intraday balance. These are quarantined for SKU availability analysis.
- Every zero-sales shop-category day has at least one SKU with positive reconstructed stock during that day. This supports category-level zero observations as observed category sales, but does not rule out item-level stockouts.

## 3. Development experiment

The fixed-origin benchmark used 1 July, 1 August and 1 September 2025, with 512 shop-category series and 1,536 series-origin forecasts per horizon. Q4-2025 was excluded. Each model used the same target definition and historical-only feature snapshot.

Feature set: lags 1/7/14/28/56; rolling mean, standard deviation, sum and zero ratio over 7/14/28/56 days; days since last sale; ADI; positive-demand mean/CV²; shop/category identifiers; weekday, day, month, ISO week and cyclical encodings.

Candidates: LightGBM Tweedie (100 trees, learning rate 0.035, 31 leaves, minimum child samples 80, row/column subsampling 0.85, L2 2.0, seed 42); CatBoost Tweedie (120 iterations, depth 6, learning rate 0.04, L2 5, seed 42); raw two-stage CatBoost occurrence and positive-quantity model (100 iterations each, depth 5, learning rate 0.04, balanced classifier weights); weekly seasonal-naive based on up to four prior matching weekdays; Croston-SBA and TSB (alpha/beta 0.1).

| Horizon | LightGBM | CatBoost | Hurdle (raw) | Croston-SBA | TSB | Weekly seasonal-naive |
|---:|---:|---:|---:|---:|---:|---:|
| 1 day | 79.80% | 79.98% | **79.23%** | 84.01% | 84.78% | 92.21% |
| 7 days | **33.74%** | 34.20% | 35.26% | 37.74% | 38.62% | 40.77% |
| 14 days | **24.11%** | 24.78% | 24.54% | 30.27% | 32.10% | 33.97% |
| 28 days | **18.57%** | 19.28% | 18.84% | 25.62% | 27.38% | 29.16% |

The hurdle model's one-day WAPE is lower, but its aggregate bias is -28.18%; its occurrence probabilities are uncalibrated. LightGBM bias is -21.69%, -6.59%, -2.42% and -2.10% across 1/7/14/28 days respectively. LightGBM is therefore the current fallback for 7/14/28-day category forecasting; CatBoost remains a challenger. No model is declared a real-world winner.

At seven days, LightGBM WAPE across the three origins is 32.52%, 33.86% and 34.92%. A 2,000-replicate shop-category cluster bootstrap estimates the WAPE difference (LightGBM minus CatBoost) at -0.45 percentage points, 95% interval [-0.85, -0.08] points. This is development-fold variation, not final-test uncertainty.

The 512 historical regimes are 342 lumpy, 153 erratic, 13 smooth and 4 intermittent. Four intermittent series are inadequate for automatic specialist routing. Regime labels are descriptive and cannot substitute for independent-series support.

## 4. Model architecture decision

The current evidence supports a conservative two-layer design:

1. **Forecast layer:** pooled LightGBM Tweedie fallback; CatBoost Tweedie challenger; raw hurdle remains experimental until probability calibration and bias correction pass; Croston-SBA/TSB remain intermittent challengers.
2. **Selection layer:** compare all candidates on identical rolling origins, horizon, targets and available rows. Require at least 3 development origins and at least 20 independent series per regime per origin before enabling a regime-specific selector. Otherwise retain the pooled fallback.
3. **SKU layer:** build only from verified assortment and inventory exposure. A missing SKU date is zero only when active assortment and positive stock throughout the day are established; stockout, negative-ledger, closed-shop and unknown-coverage periods are censored/unknown.
4. **Uncertainty and hierarchy:** next stage is calibrated intervals and reconciliation after source and target eligibility are frozen.
5. **Decision layer:** RQ3 inventory replay is separate from forecast accuracy and requires validated costs, lead times, pack/MOQ, budgets and stock state. RQ4 requires actual SME owners using B-SMART; generated explanation cases do not qualify.

## 5. Reproducibility and remaining gates

The generic adaptive engine includes explicit missing-date policy, direct horizons, baseline and tree/hurdle candidates, per-shop/category/regime metrics, horizon-scaled weekly MASE, run manifest, figures and tests. Its weekly seasonal-naive baseline now uses matching weekdays; LightGBM uses native categorical IDs; regime selection checks independent series support rather than counting repeated forecasts.

Remaining gates:
1. Resolve the provenance conflict.
2. Reconcile the 269 negative stock events and 330 affected positive-sale days.
3. Build and validate an exposure-aware SKU panel.
4. Reproduce prior WAPE claims from their original scripts and exact protocol.
5. Calibrate occurrence probabilities and prediction intervals.
6. Add point-in-time price/promotion features and hierarchical reconciliation.
7. Freeze selection before a new untouched future period or held-out businesses.
8. Evaluate RQ3 and RQ4 only with their own required evidence.

No final holdout has been evaluated. The 2025-Q4 legacy period is excluded from model selection and cannot be relabelled as untouched.
