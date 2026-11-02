# B-SMART empirical run — 2 November 2026

## Scope and provenance
The seven Google Sheets exports supplied in the researcher's `datasets` Drive folder were downloaded as spreadsheet exports. Independently audited merchant origin, consent, and original system exports have **not** been provided. All 32 shops in the `shops` table are labelled Grocery & FMCG Retail and have the identical opening date 2021-01-01. The original repository README describes fictional demo shops; this new research dataset is **not thereby proven to be live merchant data**.

The source includes an explicit `synthetic_future_30_day_oracle_demand_units` field in RQ3, as well as assumed budgets/lead times and `_scenario` outputs. These flags retain their meaning; they were not renamed, erased, or used to misrepresent simulated outcomes.

The similarly named `sales_lines` sheets show the same final line identifiers (ending in `SL0000736683`). Treat them as possible duplicate versions, never as independent partitions until row hashes are reconciled.

## Completed numerical experiments
These values were obtained from execution of the separately delivered, reproducible Python package, not entered as desired targets. Random seed 42.

| Experiment | Evaluation | Transparent baseline | Learning model |
| --- | --- | --- | --- |
| RQ1 daily shop-category units | 47,104 test rows; Oct–Dec 2025; rolling next-day | 7-day moving mean WAPE 89.70% | LightGBM WAPE 83.98%, MAE 2.160, RMSE 3.120 |
| RQ2 inactive in next 90 days | 21,164 test snapshots; embargoed labels; 10,613 customers | Logistic regression PR-AUC 0.7346, ROC-AUC 0.8211 | LightGBM PR-AUC 0.7405, ROC-AUC 0.8271, Brier 0.1681 |
| RQ3 2,500 **simulation** cases | Paired scenario cost and missed units | Baseline BDT 2,227,690.07, 45 lost units | Trend BDT 2,208,289.47, **100 lost units** |
| RQ4 1,800 **generated** cases | Recommendation audit only | 1,601 NO_ACTION | 199 REORDER; **no human usability outcomes** |

RQ1 shop-cluster bootstrap 95% interval for the LightGBM improvement over moving-mean WAPE: 5.36–6.07 percentage points. RQ2 customer-cluster bootstrap 95% interval for LightGBM minus logistic PR-AUC: 0.0022–0.0102.

## Reproduction artifacts delivered separately in the ChatGPT session
- `run_experiments.py` and `robustness.py`: time-aware modeling, metrics, prediction CSVs, checksums and uncertainty.
- `build_report.py` and `latex/`: independent six-chapter report with generated figures; PDF compiled and validated locally.
- `outputs/metrics.json`, model `.joblib` binaries, test predictions, research figures.
- The raw Drive exports were **not** committed or republished in GitHub to avoid disclosing pseudonymous customer-level source data.

## Mandatory work before calling the thesis fully complete
1. Verify source collection, merchant identities, rights and consent; if generated, classify data accurately.
2. Reconcile order-line versions and audit keys, timestamps and duplicate items.
3. Add shop-held-out, multicutoff, fixed-horizon forecasting and sector experiments.
4. Test prospective inventory decisions with a specified service-loss cost, actual stock, and real outcomes.
5. Conduct an ethics-approved Bangla explanatory UI task study with consenting humans.
6. Complete the university/supervisor's 40+ scholarly paper matrix, appendices and exact template review.
7. Test integration into the application without modifying demo/production records.

**Status:** rigorous reproducible research progress, **not** verified fully completed final thesis.