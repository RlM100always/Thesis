# Google Drive dataset audit — current thesis package

Updated: 8 November 2026

## Dataset source

The thesis uses the real Bangladesh SME dataset supplied by the researcher through the project Google Drive folder. The Drive manifest identifies the data as real SME sales and real people data, with BDT currency and coverage from 1 January 2023 to 31 December 2025. The repository contains research code and non-sensitive aggregate outputs; the raw source package remains in Drive.

## Manifest inventory

| Dataset | Manifest count |
|---|---:|
| Shops | 32 |
| Customers | 11,000 |
| Products / SKUs | 480 |
| Suppliers | 56 |
| Sales orders | 365,447 |
| Sales lines | 736,683 |
| Payments | 381,756 |
| Purchase orders | 122,422 |
| Purchase lines | 122,422 |
| Inventory movements | 994,808 |
| Inventory lots | 134,379 |
| Returns | 5,102 |
| Promotions | 1,216 |
| Calendar records | 1,096 |

## Prepared research datasets

| Research question | Dataset size | Interpretation and current requirement |
|---|---:|---|
| RQ1 — Demand forecasting | 699,220 positive-sale SKU records | Sparse observed sales. Missing SKU-date rows are not automatically zero; evaluate active assortment and inventory exposure. |
| RQ2 — Customer prediction | 72,146 snapshots; 10,613 unique customers | Separate TRAIN/TEST assignments are supplied and must be preserved for the primary evaluation. |
| RQ3 — Replenishment | 2,500 policy scenarios | Supports scenario-based policy evaluation. A participating owner's actual policy is still needed for an observed business-policy comparison. |
| RQ4 — Explanation evaluation | 1,800 explanation cases | The human_rating column alone does not establish real participant feedback. A real user study is still required. |

## RQ1 transaction and panel reconciliation already recorded

The existing RQ1 audit records the following structural checks against the supplied Drive package:

- 365,447 sales orders and 736,683 sales lines.
- Sales lines were aggregated by shop, SKU and date to reproduce 699,220 prepared positive-sale SKU records, totalling 1,580,361 units.
- The prepared shop-category panel contains 561,152 rows, 512 shop-category series and 1,096 dates, with 1,580,361 observed units.
- The SKU-level export is sparse. Missing SKU-date records must not be blindly filled with zero.
- The inventory-ledger audit recorded negative-balance events and positive-sale days with non-positive reconstructed intraday stock. These require reconciliation before SKU availability labels are used as ground truth.

These are existing repository audit outputs; they are not a claim that a new audit or model run was executed during this documentation update.

## Existing RQ1 development experiments

The repository already contains fixed-origin development results comparing LightGBM Tweedie, CatBoost Tweedie, a CatBoost hurdle model, weekly seasonal-naive, Croston-SBA and TSB. It also contains a context-feature experiment and a historical price/activity ablation. Their recorded metrics are development results, not a final untouched holdout.

| Horizon | Best recorded pooled WAPE in the fixed-origin development run |
|---:|---:|
| 1 day | CatBoost hurdle: 79.23% (with material under-forecast bias; not selected) |
| 7 days | LightGBM Tweedie: 33.74% |
| 14 days | LightGBM Tweedie: 24.11% |
| 28 days | LightGBM Tweedie: 18.57% |

Q4 2025 was previously inspected and was excluded from model selection. It must not be described as an untouched final test. SKU-level exposure-aware evaluation, model calibration and a genuinely untouched final evaluation remain outstanding.

## RQ2 — Customer prediction

The supplied snapshot file has 72,146 rows and 10,613 unique customers, with separate TRAIN and TEST assignments. The next implementation step is a reproducible pipeline that validates the target definition, checks snapshot dates and customer overlap, fits preprocessing on TRAIN only, compares simple baselines with candidate classifiers, and reports PR-AUC, ROC-AUC, F1, recall/precision at an operational threshold, Lift@K and calibration where appropriate.

## RQ3 — Replenishment

The supplied 2,500 scenarios can be used to compare replenishment policies under common scenario inputs and explicit constraints. The evaluation must report the assumptions and scenario metrics. It must not present scenario results as the participating owner's observed policy or as realised savings. Obtain and encode the owner's actual policy for the real-policy comparison.

## RQ4 — Explanation evaluation

The supplied 1,800 cases can support structured explanation testing. The presence of a human_rating column is not sufficient evidence of a completed human study. A real study requires actual participants, consent, defined tasks, recorded answers, task correctness, completion time and feedback. Until then, report the cases as prepared evaluation material, not user-study results.

## Data and reporting rules

1. Use the Drive package as the real SME research dataset.
2. Preserve original source tables and checksums; never overwrite source files during cleaning.
3. Do not convert missing SKU dates into zero without active-assortment and availability evidence.
4. Preserve the provided customer TRAIN/TEST split.
5. Keep scenario evaluation separate from observed owner-policy evaluation.
6. Keep generated or prepared explanation cases separate from actual participant responses.
7. Record the exact model, features, target, split, cutoff, parameters, environment and metrics for each run.
8. Report final results only after the corresponding pipeline has actually run and its output files have been inspected.