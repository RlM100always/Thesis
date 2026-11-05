# B-SMART evidence-aware research update (5 November 2026)

**Status:** preliminary, reproducible research; **not** independently validated merchant data, a multi-sector field test, or a deployed end-to-end ML system.

## Research question linkage
- **RQ1 (forecasting):** forecast observed shop–category–day sales using history-only features; evaluate at four aggregation levels without substituting aggregate WAPE for leaf WAPE.
- **RQ2 (inactivity risk):** 90-day customer inactivity ranking with temporal embargo; compare LightGBM, logistic regression and recency baseline; do not interpret risk as campaign uplift.
- **RQ3 (strategy):** compare policies under known inventory, budget and lead-time constraints; the current oracle-driven 2,500 scenarios are *simulations*, not realised BDT savings. Use credible historical stock ledger and outcomes for later replay.
- **RQ4 (explanation):** present recommendation reason, source, cutoff, evidence, constraints and abstention state; SHAP is a model attribution, not a causal explanation or a human usability result.

## Verified experimental findings (source exports supplied by researcher)
Existing RQ1 held-out period 1 October–31 December 2025; **47,104 rows**. A fresh refit from the same panel and fixed 2025 split reproduces:
- Original LightGBM WAPE **83.984%** (MAE 2.160).
- Seven-day trailing mean WAPE **89.698%**; seasonal-naive **110.447%**.
- New two-stage hurdle model WAPE **84.042%** and XGBoost **84.564%**. Neither improves on the refit LightGBM.
- Same LightGBM predictions, aggregated *before* absolute error: network/day **6.019%**, shop/day **31.426%**, category/day **16.547%**, shop–category/day **83.984%**.
- Aggregation cancels **92.833%** of the sum of leaf absolute errors when grouped by day. This does **not** imply 6.019% SKU/shop forecasting error or improved leaf decisions.
- The test panel includes **39.82% zero-recorded-sales rows**. A zero sale is not proof of zero *latent demand*: stockouts may censor sales.
- On the same held-out test, zero-sales observations have mean model forecast **1.708 units**; the positive-sales subset WAPE is **57.54%**. WAPE is *undefined* on the all-zero subset.
- Three exploratory earlier temporal folds yielded LightGBM WAPE **72.89%, 81.83%, 85.84%** vs trailing means **78.30%, 86.60%, 88.75%**. These show temporal variability.
- Because the October–December test has been previously reviewed, *new candidate-model comparisons on it are exploratory*. An untouched external/forward test is required for final model selection.

## Current RQ2, RQ3, RQ4 results and boundaries
- RQ2 LightGBM PR-AUC **0.7405**, logistic regression **0.7346**, recency rule **0.6528**. Training data after outcome embargo: 40,499 snapshots; test: 21,164. Model outputs are **offline**, not live API predictions.
- RQ3: 2,500 *synthetic-oracle scenario* cases; baseline scenario cost BDT 2,227,690.07, trend cost BDT 2,208,289.47; lost units **45 → 100**. In **97.68%** of cases initial stock already exceeds or equals the scenario future 30-day demand, so policy discrimination is poor. The trend policy should not be declared universally superior.
- RQ4: 1,800 structured cases; 199 REORDER, 1,601 NO_ACTION; 1,800 tagged evidence-complete. That tag was supplied in the file and is **not independently verified evidence** or human comprehension. Human-study data are unavailable.

## Dataset provenance and privacy
The 32 shops in the supplied catalogue are all labelled grocery/FMCG, not cross-sector; reported opening dates are identical. Earlier selected unflagged exports and later exports containing synthetic metadata markers conflict. Removing a flag does **not** prove authentic merchant origin. Before real-world or publication claims, obtain data-owner permission, secure access, independent extraction records, reconciliation from raw transactions and ethics approval where appropriate. Never commit customer-level records, model artifacts with identifying data, or row-level predictions to this public repository.

## Method implementation and links
1. Data validation, versioned source manifests, raw-transaction reconciliation.
2. Chronological training/validation/testing and three rolling-origin folds.
3. Aggregation-level evaluation, zero-sales diagnostics, shop/category heterogeneity, explicit error-cancellation analysis.
4. Refit LightGBM and compare with same-target XGBoost and two-stage hurdle model.
5. Evaluate RQ3 scenarios separately from observational outcomes.
6. Treat RQ4 structural evidence and human usability as distinct.
7. Integrate reviewed outputs into the original six-chapter LaTeX thesis and keep software code vs offline experimental model status explicit.

This branch is a **research revision proposal**; no software deployment or new ethics approval is implied.
