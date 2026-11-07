# Drive dataset audit — 7 November 2026

## Scope and source

The user-provided Google Drive folder contains two child folders:

- `data`: source business tables and `manifest.json`
- `data-2`: RQ1–RQ4 derived research tables

The source files remain in Drive and are not copied into the public GitHub repository. This audit records structural findings only; it does not certify legal provenance or business ownership.

## Current manifest claim

The current `manifest.json` reports:

- `dataset_nature`: "100% real SME sales or real people"
- period: 2023-01-01 to 2025-12-31
- country scenario: Bangladesh
- currency: BDT
- shops: 32; customers: 11,000; products: 480; suppliers: 56
- fixed seed: 20261025
- raw row counts: sales_orders 365,447; sales_lines 736,683; payments 381,756; purchase_orders 122,422; purchase_lines 122,422; inventory_movements 994,808; inventory_lots 134,379; simulated_unmet_demand 32,852; returns 5,102; promotions 1,216; calendar 1,096; rq4_explanation_cases 1,800.

## RQ1 shop-category panel

File: `rq1_daily_shop_category`

- data rows: 561,152
- shops: 32
- categories: 16
- unique shop-category series: 512
- date range: 2023-01-01 through 2025-12-31 (1,096 consecutive days)
- each shop-category series: exactly 1,096 rows
- duplicate date × shop × category keys: 0
- total units sold: 1,580,361
- zero-sales rows: 210,972 (37.5962%)
- `is_zero_observed_sales` agrees with `units_sold_observed == 0` on every row.

Legacy test window (2025-10-01 through 2025-12-31):

- observations: 47,104 (= 32 × 16 × 92)
- zero-sales rows: 18,757
- zero-sales share: 39.8204%
- units sold: 121,157

The observation count and zero-sales share match the previously reported test-set size and 39.82% zero rate. The 2025-Q4 window has already been inspected and is excluded from new model selection.

## RQ1 SKU-level panel and provenance conflict

File: `rq1_daily_sku_sales_observed`

- data rows: 699,220
- shops: 32
- SKUs: 480
- total units sold: 1,580,361 (matches the shop-category panel)
- `synthetic_flag` distribution: YES = 699,220; no other value was present.

This is a direct contradiction with the current Drive manifest's "100% real SME sales or real people" statement. The repository's 2 November onboarding document also records an earlier version of the manifest as explicitly "100% SYNTHETIC / simulated; NO observed SME sales or real people". The current manifest appears to have changed, but the row-level synthetic flag remains YES. The fixed random seed and separate `simulated_unmet_demand` table add reasons to demand a source-level explanation; they are not, by themselves, proof of how every sales row was produced.

**Evidence classification: provenance_conflict.** Do not describe the dataset as verified real-world SME evidence until the source owner supplies the original POS/accounting exports or source-system statement, collection/consent basis, anonymisation method, field-level data dictionary and explanation/correction of `synthetic_flag`.

## Research implications

1. The RQ1 panel is structurally complete and is suitable for pipeline integration, schema tests and controlled model experiments.
2. If the rows are confirmed synthetic, all scores must be labelled simulation results, not real-world forecast accuracy.
3. If the flag is erroneous and the records are truly observed, the correction must be documented with a signed/traceable source statement and a versioned manifest. Do not simply change YES to NO in the data.
4. `simulated_unmet_demand` is explicitly simulated. It may support controlled inventory simulation only, not empirical lost-sales claims.
5. Sales-only forecasting estimates observed sales. Stockout-censored demand cannot be inferred without verified inventory availability/stockout labels.
6. The old 2025-Q4 test period is excluded from development selection. A new untouched future period or held-out business is still required for final evaluation.

## Pipeline changes

The research engine now:

- accepts the native RQ1 schema aliases `category` and `units_sold_observed`;
- converts Excel serial dates;
- validates `is_zero_observed_sales` against the demand values;
- constructs supervised lag/rolling features vectorially;
- uses a development cutoff exclusive at 2025-10-01 by default;
- selects three monthly spaced rolling origins before that cutoff;
- records `provenance_conflict` as the default evidence status and stores the provenance note in the run manifest.

No new WAPE or accuracy claim is made by this audit.
