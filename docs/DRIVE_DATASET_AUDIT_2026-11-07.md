# RQ1 source audit — 8 November 2026

## Scope and evidence boundary

This audit uses the user-linked Google Drive package and the repository's prior data-onboarding record. It is a structural and internal-reconciliation audit, not an independent verification of business ownership, collection, consent, or real-world origin.

**Evidence status: `provenance_conflict`.** The current Drive `manifest.json` claims `100% real SME sales or real people`, but the repository's 2 November `docs/REAL_DATA_ONBOARDING.md` describes a package with the same seed (20261025), same 32 shops, 11,000 customers, 480 products, 56 suppliers, and same 2023-01-01 to 2025-12-31 period as `100% SYNTHETIC / simulated; NO observed SME sales or real people`. That earlier document also reports `synthetic_flag=YES` on inspected source rows. The current accessible SKU sheet has six populated columns and does not expose a `synthetic_flag` column. The current declaration therefore conflicts with the prior source record; this audit does not silently decide which declaration is correct.

Until the source owner supplies traceable POS/accounting exports or an auditable source statement, collection/consent basis, anonymisation method, data dictionary, and a versioned explanation of the prior synthetic classification, results from this package are controlled development/simulation evidence—not verified real-world Bangladeshi SME evidence.

## Current Drive manifest

- Current declaration: `100% real SME sales or real people`.
- Seed: `20261025`.
- Period: 2023-01-01 to 2025-12-31.
- Country scenario: Bangladesh; currency: BDT.
- Shops: 32; customers: 11,000; products: 480; suppliers: 56.
- Manifest row counts: 365,447 sales orders; 736,683 sales lines; 381,756 payments; 122,422 purchase orders and purchase lines; 994,808 inventory movements; 134,379 inventory lots; 32,852 simulated unmet-demand rows; 5,102 returns; 1,216 promotions; 1,096 calendar rows; 1,800 RQ4 explanation cases.

The `simulated_unmet_demand` table is explicitly simulated and is never treated as observed sales or real lost-sales ground truth.

## Transaction-to-SKU reconciliation

Files: `sales_orders`, `sales_lines`, `rq1_daily_sku_sales_observed`, `products`.

- Sales orders: 365,447 rows.
- Sales lines: 736,683 rows.
- Every sales line joins to exactly one order; no missing order references were found and line shop IDs agree with order shop IDs.
- Aggregating sales lines by `shop_id × sku_id × date` reproduces all 699,220 rows in the prepared SKU observed-sales sheet.
- All 699,220 quantities match exactly; total observed quantity is 1,580,361 units.
- The prepared SKU sales value also matches the transaction-line aggregation to floating-point precision.
- The SKU export contains positive-sale days only. Its field note says missing rows are not automatically zero demand.
- 32 shops and 480 SKUs are represented; 13,271 shop-SKU combinations have at least one recorded sale. Median positive-sale days per observed shop-SKU combination: 39 (10th percentile 12; 90th percentile 111).

This establishes internal reproducibility of the derived SKU table from the supplied transaction tables. It does not independently establish that the underlying transactions were collected from real businesses.

## SKU-to-category reconciliation

File: `rq1_daily_shop_category`.

- 561,152 rows = 32 shops × 16 categories × 1,096 dates.
- 512 shop-category series; every series covers 2023-01-01 to 2025-12-31 without gaps.
- Total quantity: 1,580,361 units, matching the SKU and sales-line totals.
- Zero-sales rows: 210,972 (37.5962%); zero flags match quantity on every row.
- Aggregating SKU observed sales to shop-category-date matches all 350,180 positive shop-category-date rows exactly.
- The remaining 210,972 category rows are zero-sales rows absent from the sparse SKU export; they are not missing SKU sales records to be blindly zero-filled.

Legacy Q4-2025 window (already inspected; not an untouched final test): 47,104 shop-category observations, 18,757 zero-sales rows (39.8204%), and 121,157 units.

## Inventory and procurement ledger reconciliation

Files: `inventory_movements`, `inventory_lots`, `purchase_orders`, `purchase_lines`.

Movement counts: 13,272 OPENING; 121,107 PURCHASE; 736,683 SALE; 118,673 EXPIRY_DISPOSAL; 5,073 DAMAGE (994,808 total).

- Every one of the 736,683 SALE movements matches one sales line by order, shop, SKU, lot, and quantity.
- The 121,107 PURCHASE movement groups match the 121,107 purchase-order/SKU groups with a non-null received quantity.
- 1,315 purchase lines have no final received quantity; the PO table labels these as pending at cutoff.
- Reconstructed stock balance contains 269 negative-balance movement events across 253 shop-SKU combinations. There are 330 positive-sale days on which the reconstructed intraday minimum balance is non-positive. These events must be quarantined or reconciled before SKU availability labels are treated as ground truth.
- Across the 13,272 inventory-tracked shop-SKU combinations and 1,096 days, the movement ledger reconstructs 13,781,575 fully in-stock days and 764,537 days with non-positive intraday balance. This is a derived ledger diagnostic, not an independently audited stock-out label.
- Every zero-sales shop-category day has at least one SKU in that shop-category with positive reconstructed stock during the day. This reduces concern that category-level zero rows are days when every recorded SKU in the category was out of stock; it does not rule out item-level stockouts or unrecorded assortment.

The 2,088 theoretical shop-SKU combinations without an opening inventory movement are not assumed to be active or zero-demand series.

## RQ1 development model comparison

The complete shop-category panel was evaluated at three development origins (2025-07-01, 2025-08-01, 2025-09-01), with 512 series at each origin and direct cumulative horizons 1, 7, 14, and 28 days. Q4-2025 was excluded from model selection because it had already been inspected. Each horizon contains 1,536 series-origin forecasts.

Features: lags 1/7/14/28/56; rolling mean, standard deviation, sum and zero ratio over 7/14/28/56 days; days since last sale; ADI; positive-demand mean and CV²; shop/category identifiers; weekday, day, month, ISO week and cyclical calendar encodings. All features use information strictly before the forecast origin. Training labels must finish before the validation origin.

Candidates: LightGBM Tweedie; CatBoost Tweedie; raw two-stage CatBoost occurrence × positive-quantity expectation; weekly seasonal-naive using up to four previous matching weekdays; Croston-SBA; and TSB. The hurdle classifier probabilities are not calibrated. Hyperparameters and all metrics are stored in the immutable run manifest and result CSVs.

| Horizon | LightGBM WAPE | CatBoost WAPE | Raw hurdle WAPE | Croston-SBA WAPE | TSB WAPE | Seasonal-naive WAPE |
|---:|---:|---:|---:|---:|---:|---:|
| 1 day | 79.80% | 79.98% | **79.23%** | 84.01% | 84.78% | 92.21% |
| 7 days | **33.74%** | 34.20% | 35.26% | 37.74% | 38.62% | 40.77% |
| 14 days | **24.11%** | 24.78% | 24.54% | 30.27% | 32.10% | 33.97% |
| 28 days | **18.57%** | 19.28% | 18.84% | 25.62% | 27.38% | 29.16% |

At one day, the raw hurdle has WAPE 79.23% but signed aggregate bias -28.18%, so its lower WAPE is not sufficient for selection. LightGBM has signed bias -21.69% at one day, -6.59% at seven days, -2.42% at fourteen days, and -2.10% at twenty-eight days. LightGBM ranks first at all three seven-day development origins (32.52%, 33.86%, 34.92% WAPE). A 2,000-replicate shop-category cluster bootstrap gives the seven-day WAPE difference (LightGBM minus CatBoost) median -0.45 percentage points, 95% interval [-0.85, -0.08] percentage points. This interval describes development-series variation only; it is not final-test uncertainty.

Demand regime from history through 2025-06-30: 342 lumpy, 153 erratic, 13 smooth, and only 4 intermittent series. The intermittent subset has 12 series-origin forecasts and 25 actual units at seven days. It is too small for automatic model switching. Croston-SBA has lower seven-day WAPE than LightGBM in that tiny subgroup, but this is exploratory and not a specialist-model superiority claim.

## Research design decision

1. Keep LightGBM Tweedie as the current shop-category fallback candidate.
2. Keep CatBoost Tweedie as a challenger; it did not outperform LightGBM consistently in this development run.
3. Keep the hurdle model experimental until occurrence probabilities are calibrated and aggregate bias is controlled.
4. Keep Croston-SBA and TSB as intermittent-demand challengers; do not route by ADI/CV² labels unless a regime has at least 20 independent series at each of at least three validation origins.
5. For SKU experiments, construct a daily exposure-aware panel from verified assortment and inventory events. A missing SKU-date is zero only if the SKU is active and demonstrably in stock throughout that day. Non-positive stock, negative-ledger anomalies, missing inventory coverage, closed-shop periods, and unknown assortment are censored/unknown—not zero.
6. Keep observed-sales forecasting separate from latent unconstrained-demand estimation. The simulated unmet-demand table is not empirical target data.
7. Add calibrated prediction intervals, hierarchical reconciliation, price/promotion effects and RQ3 inventory-policy replay only after point-in-time joins and a verified source record.
8. Reserve a genuinely untouched future period or held-out businesses after model design is frozen. Q4-2025 is not that holdout.

## Reproducibility and files

The source package remains in controlled Google Drive and is not committed to GitHub. Commit only code, schema, checksums, aggregate outputs and non-sensitive figures. Every run must record input SHA-256, evidence status, date cutoff, horizons, origins, training stride, model parameters, environment, warnings and whether a final holdout was evaluated.

No result in this document should be described as verified real-world SME accuracy while provenance remains unresolved.
