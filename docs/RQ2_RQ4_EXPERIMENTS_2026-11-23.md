# RQ2–RQ4 experiment record — 23 November 2026

## Dataset version and provenance audit

The source files were exported from the project Google Drive folder. Raw business and customer-level files remain in controlled storage and are not included in this repository.

- **RQ1 panel:** the two `rq1_daily_shop_category` copies have identical SHA-256 `ab741f4d72c49706ba2abc8f096659324d862f758c4f171b84dd55a3ab6cbcbd`, matching the input hash in the existing RQ1 experiment manifest. The sales-line, sales-order and product-master hashes also match the recorded RQ1 manifest.
- **RQ2 snapshots:** three copies contain the same rows and values after normalising the target-column name. The selected export uses `inactive_next_90d_label`; the other copies call the same values `inactive_next_90d_synthetic_label`. The selected file contains 72,146 snapshots for 10,613 customers. The target was reconstructed from `sales_orders.csv` as no order in `(snapshot_date, horizon_end]`; agreement is 100% across all rows.
- **RQ4 cases:** the richer export contains the common fields in the shorter export plus `explanation` and `human_rating`. The common fields match. The richer export is used for the text audit.
- **RQ3 scenarios:** one 2,500-row scenario table is supplied. Its future-demand field is explicitly labelled synthetic oracle demand.

The supplied manifest describes the operational tables as real SME records. Derived scenario fields and constant review flags are treated according to their actual column definitions; they are not promoted to observed outcomes or participant responses.

## RQ2 — customer inactivity prediction

**Target:** 1 means that the customer places no order during the 90 days after the snapshot cutoff. This is a fixed-horizon no-repeat-purchase label, not permanent churn.

**Data and split:** 72,146 snapshots; 10,613 unique customers; 50,982 TRAIN rows and 21,164 TEST rows. TRAIN snapshots run from 31 December 2023 through 31 December 2024. TEST snapshots are 31 March 2025 and 30 June 2025. The supplied chronological split was preserved. Repeated customers appear in both periods (10,483 overlapping customers), so this measures temporal performance within the supplied population, not cold-start generalisation to unseen customers.

**Feature policy:** the final model uses only historical snapshot columns and deterministic transformations. Current customer-master attributes (`customer_type`, `loyalty_member`, `home_division`, `home_district`) are excluded because the source does not provide effective dates showing that their values were known at each historical cutoff. Customer ID and name are never predictors. The categorical feature is the snapshot's `home_shop_id`.

**Selection:** rolling-origin TRAIN validation at 30 June, 30 September and 31 December 2024. Recency rule, logistic regression, LightGBM and CatBoost were compared. Platt calibration and the F2 threshold were fitted from training-only out-of-time predictions. CatBoost was selected by validation PR-AUC with calibrated Brier as the tie-breaker; LightGBM remained a close challenger.

| Model | OOF PR-AUC | OOF ROC-AUC | Calibrated OOF Brier | TEST PR-AUC | TEST ROC-AUC | TEST Brier | TEST F2 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Recency rule | 0.6398 | 0.7418 | — | 0.6874 | 0.7559 | — | — |
| Logistic regression | 0.6963 | 0.8124 | 0.1714 | 0.7370 | 0.8234 | 0.1733 | 0.8235 |
| LightGBM | 0.6986 | 0.8143 | 0.1705 | 0.7452 | 0.8301 | 0.1659 | 0.8271 |
| CatBoost | **0.7005** | **0.8174** | **0.1692** | **0.7470** | **0.8313** | **0.1647** | **0.8300** |

Threshold-based classification measures were evaluated on TEST using the F2-maximising threshold selected separately for each classifier from calibrated, training-only rolling-origin predictions. The positive class is inactivity within the next 90 days.

| Model | Threshold | Precision | Recall | F1-score | ROC-AUC |
|---|---:|---:|---:|---:|---:|
| Logistic regression | 0.1911 | 0.5131 | 0.9703 | 0.6713 | 0.8234 |
| LightGBM | 0.1633 | 0.5220 | 0.9687 | 0.6784 | 0.8301 |
| CatBoost | **0.1539** | **0.5385** | **0.9598** | **0.6900** | **0.8313** |

For the selected CatBoost model, the TEST confusion matrix at threshold 0.1539 is:

| Actual class | Predicted active | Predicted inactive |
|---|---:|---:|
| Active (0) | 5,279 (TN) | 7,169 (FP) |
| Inactive (1) | 350 (FN) | 8,366 (TP) |

Thus, 8,366 of 8,716 actually inactive snapshots were detected (recall 95.98%). Of the 15,535 snapshots classified as inactive, 8,366 were actually inactive (precision 53.85%). The F1-score is 0.6900. The threshold favours recall, but it also produces 7,169 false positives; this error volume should be considered before using the scores to initiate retention contact. The ROC curve is stored as 21 aggregate points in \`roc_curve_points.csv\`; the confusion counts are stored in \`confusion_matrix.csv\`. No row-level customer predictions are exported.

Ranking the top 10% by risk gives precision 0.8465, recall 0.2056 and lift 2.055 over the test prevalence. The customer-cluster bootstrap (500 resamples) gives 95% intervals of 0.7364–0.7584 for PR-AUC, 0.8260–0.8370 for ROC-AUC and 0.1619–0.1673 for Brier score.

The final snapshot-only feature policy removes undated customer-master attributes. The selected CatBoost model therefore has a cleaner point-in-time information set than the earlier exploratory run. This is predictive evidence only; it does not estimate the causal effect of a retention message or campaign. The temporal test contains repeated customers from TRAIN, so it does not establish cold-start performance for new customers.

## RQ3 — replenishment policy scenarios

The supplied file contains 2,500 paired cases across 32 shops and 477 SKUs at a 31 July 2025 cutoff. The summed synthetic oracle demand is 8,330 units.

| Measure | Baseline total | Trend-policy total | Mean difference per case (trend − baseline) | Relative change |
|---|---:|---:|---:|---:|
| Scenario lost units | 45 | 100 | +0.0220 units | +122.2% |
| Average stock | 392,825.28 | 387,567.97 | −2.1029 units | −1.34% |
| Supplied scenario cost | BDT 2,227,690.07 | BDT 2,208,289.47 | −BDT 7.7602 | −0.87% |
| Order quantity | 7,356 | 654 | −2.6808 units | −91.1% |

A shop-cluster bootstrap (5,000 resamples) gives 95% intervals for the mean per-case differences: scenario cost −BDT 8.94 to −BDT 6.65; lost units +0.0127 to +0.0320; average stock −2.45 to −1.78 units; order quantity −3.13 to −2.27 units. Lost units are higher under the trend policy in 23 cases, equal in 2,477, and lower in none. The trend policy therefore trades lower supplied scenario cost and stock for more lost units.

Both order quantities are pack multiples in every case, and the supplied cost-gap field equals trend cost minus baseline cost to floating-point precision. The source does not document the scenario-cost formula and does not provide an owner's actual current policy. These results are a scenario audit, not realised savings or an empirical owner-policy comparison. RQ3, as worded against a participating owner's actual current policy, remains unevaluated.

## RQ4 — decision-rule and explanation audit

The richer case export contains 1,800 prepared cases across 32 shops and 467 SKUs, all dated 31 December 2025. Joining the product master confirms the reorder-point values. Recomputing inventory position, reorder trigger, pack-rounded target quantity and budget cap reproduces the suggested quantity, action and constraint reason in **100%** of cases. There are 199 `REORDER` cases and 1,601 `NO_ACTION` cases; one no-action case is blocked by insufficient budget.

The supplied explanation contains the numeric stock, reorder point, pack multiple and budget in all 1,800 cases. It contains numeric lead days in 108 cases, pending purchase quantity in 173, suggested order quantity in 3, and unit purchase cost in none. A new deterministic bilingual explanation generator states the branch-relevant stock, pending receipts, inventory position, reorder point, target, pack rounding, feasible quantity, cost, budget and lead-time evidence. The generated English and Bangla explanations include every required numeric field in 100% of cases within each decision branch.

The `human_rating` and `evidence_complete` fields are `YES` in every row. Because these fields are constant and no participant/task records are supplied, they are not evidence of user comprehension, confidence or usability. The RQ4 user study remains pending; see `docs/RQ4_USER_STUDY_PROTOCOL.md`.

## Reproducibility

The scripts in `research/experiments/` regenerate these aggregate outputs from controlled Drive exports. The scripts intentionally do not save customer-level predictions or copy raw business data into GitHub. See `research/experiments/README.md` for commands and required input filenames.