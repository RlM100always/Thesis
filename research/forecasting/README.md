# Adaptive daily-demand forecasting research module

This research-only package is separate from the operational B-SMART application. It does not modify application databases, tenant records, serving APIs or live business decisions.

## Evidence status: provenance conflict

The current user-linked Drive manifest says `100% real SME sales or real people`. However, the repository's 2 November 2026 onboarding record describes a package with the same seed (20261025), same counts (32 shops, 11,000 customers, 480 products, 56 suppliers), and same 2023–2025 coverage as `100% SYNTHETIC / simulated`. The earlier record also reports a `synthetic_flag=YES` column. The currently accessible Drive SKU sheet has six populated fields and does not expose that flag. The two source declarations conflict.

The package is therefore `provenance_conflict` until the data owner provides source-system exports or a traceable source statement, collection/consent basis, anonymisation method, data dictionary, and a versioned explanation of the earlier synthetic classification. Structural reconciliation is not proof of real-world provenance. All scores remain controlled development evidence, not verified SME forecast accuracy.

See `docs/DRIVE_DATASET_AUDIT_2026-11-07.md` for the full 8 November source, transaction, inventory and forecasting audit.

## Verified internal structure

- Shop-category panel: 561,152 rows = 32 shops × 16 categories × 1,096 days; 512 complete series; 1,580,361 units; 37.5962% zero-sales rows.
- SKU observed-sales export: 699,220 positive-sale rows across 13,271 shop-SKU combinations; missing SKU-date rows are explicitly not automatically zero.
- All 736,683 sales lines reconcile one-to-one to orders and aggregate exactly to the 699,220 SKU daily records.
- SKU aggregation reproduces all positive shop-category daily rows. The 210,972 category zero-sales rows are present only in the complete category panel.
- The inventory ledger reproduces all sale quantities, but 269 negative-balance events across 253 shop-SKU combinations and 330 positive-sale days with non-positive reconstructed intraday stock require quarantine/reconciliation.
- Every zero-sales category-day has at least one recorded SKU in positive reconstructed stock. This does not rule out item-level stockouts or unrecorded assortment.

## Transaction-feature ablation

The nine-origin, seven-day LightGBM ablation tests whether lagged transaction-derived price, discount, order and customer-day summaries improve the historical-demand baseline. The exact source checksums, per-origin metrics and pooled comparison are under `results/transaction_feature_ablation_v1/`. The extended feature set did not improve pooled WAPE (33.84% versus 33.73%) and is therefore not adopted in the current model.

Run it with the controlled Drive CSV exports:

```bash
python research/forecasting/ablation_transaction_features.py --data-dir /path/to/source_csvs --output-dir /path/to/ablation_results
```

## Reproducible source and model experiments

A run may be labelled `verified_observed` only when a source-owner provenance JSON is supplied. The experiment runner checks the required source-system, owner, collection-period, collection-method, consent/licence, anonymisation, data-dictionary, prior synthetic-flag explanation, and exact input SHA-256 fields. A manifest label alone cannot promote a dataset to verified-observed status.

- `audit_rq1_sources.py` reconciles sales orders/lines, the prepared SKU daily export, the shop-category panel, inventory SALE movements, purchase receipts and intraday stock exposure. It writes aggregate audit outputs only; raw files are not committed.
- `rq1_shop_category_experiment.py` runs the fixed-origin LightGBM/CatBoost/hurdle/baseline benchmark and writes the complete prediction file, per-origin metrics, regime metrics, MASE, cluster-bootstrap intervals and a SHA-256 run manifest.
- The committed v2 aggregate outputs are under `research/forecasting/results/rq1_fixed_origin_v2/`.

Example source audit (run from the repository root):

```powershell
python research/forecasting/audit_rq1_sources.py --data-dir path\\to\\frozen_drive_export --output-dir artifacts\\source_audit --historical-onboarding docs\\REAL_DATA_ONBOARDING.md
```

Example fixed-origin candidate benchmark:

```powershell
python research/forecasting/rq1_shop_category_experiment.py --input path\\to\\rq1_daily_shop_category.csv --output artifacts\\rq1_fixed_origin_v2 --evidence-status provenance_conflict
```

## Input contract

The generic engine accepts CSV/XLSX with:

- `date`: daily date (ISO date or Excel serial)
- `shop_id`: shop identifier
- `category_id` or `category`: category identifier
- `demand` or `units_sold_observed`: non-negative quantity, not revenue
- optional `is_zero_observed_sales`: must match quantity exactly

One row per date × shop × category is required. Missing dates are rejected by default. Use `--fill-missing-dates-as-zero` only after source evidence confirms a genuine zero-sales day. A missing SKU date is not automatically a zero; SKU-level work must use verified active assortment and in-stock exposure.

## Install and run (PowerShell)

```powershell
python -m pip install -r requirements-research.txt
python -m pytest --confcutdir=research/forecasting research/forecasting/tests -q
python -m research.forecasting.adaptive_engine --input path\to\rq1_daily_shop_category.csv --output artifacts\adaptive_forecasting --development-end 2025-10-01 --evidence-status provenance_conflict
```

## Implemented

- Strict panel validation and explicit missing-date policy
- ADI, CV², zero ratio and descriptive demand regimes
- Historical-only lag, rolling, recency and calendar features
- Direct 1/7/14/28-day cumulative-demand targets
- Weekly seasonal-naive (matching weekday average over up to four prior cycles), Croston, SBA, TSB
- Two-stage hurdle, HistGradientBoosting, optional LightGBM and CatBoost
- LightGBM native categorical identifiers and Tweedie objective
- CatBoost Tweedie objective for non-negative, right-skewed demand
- Rolling-origin development metrics: WAPE, MAE, RMSE, horizon-scaled weekly MASE and signed bias
- Pooled, per-shop, per-category and demand-regime metrics
- Development-only regime selection requiring at least 3 origins and at least 20 series in each origin; smaller regimes remain unselected
- Figures, SHA-256 run manifest and contract tests

## Model-selection interpretation

The separately recorded 8 November fixed-origin candidate experiment compares LightGBM Tweedie, CatBoost Tweedie, a raw two-stage CatBoost hurdle, weekly seasonal-naive, Croston-SBA and TSB. LightGBM is the current fallback for 7/14/28-day category forecasting; CatBoost is a challenger. The raw hurdle's lower one-day WAPE is accompanied by material under-forecasting and uncalibrated probabilities, so it is not selected. Only four of 512 category series are intermittent; there is insufficient support for automatic regime routing.

Do not promote a specialist model solely because its ADI/CV² label matches. Use same-origin development validation, minimum independent-series support, bias and practical cost, and then a new untouched evaluation.

## Limitations and deferred work

- Q4-2025 has already been inspected and is excluded from model selection; it is not a final holdout.
- No calibrated hurdle probabilities or prediction intervals are currently claimed.
- No stockout-censoring correction, verified price/promotion features, hierarchical reconciliation or inventory-policy backtest is claimed as completed.
- A sales forecast is not latent unconstrained demand when availability is unknown.
- `simulated_unmet_demand` is simulation-only and never empirical lost-sales ground truth.
- The current package's provenance remains unresolved. Do not present the results as real-world SME accuracy.

## Next research gates

1. Resolve provenance and obtain source-owner documentation.
2. Freeze a verified source package and checksum.
3. Reconcile and quarantine negative inventory balances and stockout-censored days.
4. Build SKU panels only for verified active/in-stock exposure.
5. Reproduce prior 83.98%/84.04%/84.56% values from original scripts, exact target, split and WAPE definition.
6. Calibrate hurdle probabilities and prediction intervals on development-only calibration folds.
7. Add price/promotion and inventory features only with point-in-time availability checks.
8. Freeze model design, then evaluate on a genuinely untouched future period or held-out businesses.
9. Evaluate RQ3 policies separately from prediction metrics; RQ4 requires real owners using the actual application.
