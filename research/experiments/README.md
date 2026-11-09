# Cross-RQ experiments — 9 November 2026

This README records the experiments completed so far, their saved outputs, methods, and remaining evidence. The researcher confirms that the linked Drive folder is the real Bangladesh SME dataset source used for this thesis:

[Real project dataset folder](https://drive.google.com/drive/u/0/folders/1ET_on20yEu4z2_P-sRRECt1ZGUC6vphz)

The source package manifest records a generation seed and describes validation as a “modeled world”. The underlying source lineage has not been independently checked in this run, so results are reported as based on the researcher-provided real dataset. RQ3's generated future-demand scenario values are not realized future sales or an owner's actual policy; RQ4's prepared rule-test cases are not participant feedback.

Raw order, customer, inventory, and scenario CSVs remain outside Git. The committed result files contain aggregate metrics, run settings, and non-identifying diagnostics only. Each run manifest records input checksums, software versions, data splits or cutoffs, parameters, and evidence limits.

## Run the experiments

From the repository root, set `--data-dir` to a private folder containing the Drive exports:

```bash
python research/experiments/run_rq1_exposure_aware.py --data-dir /path/to/private/drive-export
python research/experiments/run_rq2_customer_prediction.py --data-dir /path/to/private/drive-export
python research/experiments/run_rq3_scenario_comparison.py --data-dir /path/to/private/drive-export
python research/experiments/run_rq4_explanation_case_audit.py --data-dir /path/to/private/drive-export
```

The scripts save outputs under `research/experiments/results/` unless `--output-dir` is supplied. Do not commit the input CSVs.

## RQ1 — Demand forecasting

**Files:** `inventory_movements.csv`, `rq1_daily_sku_sales_observed.csv`, and `products.csv`.

The source audit reconciled order-line joins, SKU quantities, category totals, sale movements, and purchase receipts with zero mismatches in those checks. It found 269 negative-balance events across 253 shop-SKU histories and 330 positive-sale days with non-positive reconstructed intraday stock. The exposure run quarantines all 253 affected histories, retains 13,545,871 full-day positive-stock records, assigns zero only to 12,860,044 eligible exposed no-sale records, and keeps 685,827 eligible positive-sale records.

The model comparison trains through 30 September 2025 and makes sequential one-day predictions for 1 October–31 December 2025. It evaluates 1,130,148 exposed days from 13,019 series, with 119,161 observed units and a 95.34% zero share. Q4 had already been inspected in prior project work, so it is a diagnostic period rather than an untouched final holdout. Ledger reconstruction is not independently validated against physical stock and does not estimate latent demand during stock-outs.

| Candidate | WAPE | MAE (units/day) | RMSE | Bias |
|---|---:|---:|---:|---:|
| Weekly seasonal naive | 190.28% | 0.201 | 0.853 | +1.19% |
| 28-day exposed-sales mean | **183.65%** | **0.194** | 0.616 | +0.82% |
| HistGradientBoosting | 184.66% | 0.195 | **0.604** | +2.06% |

The 28-day mean has 1.01 percentage points lower WAPE than HistGradientBoosting. The HGB-minus-mean shop-bootstrap 95% interval is -0.21 to +2.25 points and includes zero. HGB improves on weekly seasonal naive but does not beat the strongest simple baseline on WAPE. Do not call HGB the winner for this SKU diagnostic.

**Remaining:** validate ledger exposure against physical-stock or owner-approved records; freeze model selection and evaluate on one untouched future period or held-out businesses; assess shortage costs on validated outcomes.

## RQ2 — Customer inactivity prediction

**Files:** `rq2_customer_snapshots_90d.csv` and `sales_orders.csv`.

The 90-day inactivity label was independently rebuilt as “no customer order after the snapshot cutoff and on or before the 90-day horizon end”. All 72,146 supplied labels matched. The supplied temporal split has 50,982 TRAIN rows through 31 December 2024 and 21,164 TEST rows from 31 March–30 June 2025. Train prevalence is 36.39%; test prevalence is 41.18%. Customer and snapshot IDs were excluded from features. Repeated customers span both temporal partitions, so confidence intervals resample customer clusters.

Constant prevalence, logistic regression, random forest, and HistGradientBoosting were compared. Candidate and threshold selection used the final TRAIN cohort dated 31 December 2024; models were then refit on all TRAIN rows. At the selected HGB threshold of 0.222, TEST PR-AUC is 0.746, ROC-AUC 0.830, Brier score 0.168, precision 0.588, recall 0.913, and F1 0.716. The highest-scored 10% has precision 0.845 and lift 2.05. A 300-replicate customer-cluster bootstrap gives PR-AUC 95% CI 0.736–0.758 and paired AP improvement over the constant baseline CI 0.326–0.345.

These are predictive results for the supplied snapshots. They do not show that a retention action causes more purchases or validate source provenance.

## RQ3 — Replenishment comparison

**Files:** `rq3_offline_policy_comparison.csv` and `products.csv`.

The file has 2,500 paired scenarios at the 31 July 2025 cutoff, across 32 shops and 477 SKUs. Its future-demand oracle field contains generated scenario values; it is not realized future sales. The same scenario inputs were used to compare the baseline and trend policies. Costs and budgets are scenario assumptions, not observed business accounts.

| Outcome | Baseline | Trend policy | Difference |
|---|---:|---:|---:|
| Total scenario cost (BDT) | 2,227,690.07 | 2,208,289.47 | -19,400.60 (-0.87%) |
| Lost units | 45 | 100 | +55 |
| Mean average stock (units) | 157.13 | 155.03 | -2.10 |
| Budget breaches | 0 | 0 | 0 |

The paired scenario bootstrap estimates -BDT 7.76 cost per row (95% CI -9.26 to -6.30) and +0.022 lost units per row (95% CI 0.012 to 0.034). The lower assumed cost comes with more lost units. This is not realized savings and does not compare against a participating owner's documented actual policy.

**Remaining:** obtain the owner's current policy, validate costs and realized demand/outcomes, then replay both policies on the same observed periods.

## RQ4 — Explanation-case audit

**File:** `rq4_explanation_cases.csv`.

The file contains 1,800 prepared rule-test cases, all dated 31 December 2025. The audit recomputed the action and constraint reason from stock position, reorder point, pack size, and scenario budget. All 1,800 actions and reasons matched; all suggested quantities were case-pack multiples within budget; and every explanation mentioned stock, reorder point, pack multiple, and budget. Of 200 cases below the reorder point after pending orders, one no-action outcome was correctly attributed to a budget block.

The source has YES in `human_rating` for all rows, but provides no participant identity or linkage, consent record, completed task, timestamp, or response provenance. Validated participant responses: 0. No usability, confidence, task-correctness, or completion-time measure can be reported. The file also lacks the target order-up-to quantity, so quantity optimality was not evaluated.

**Remaining:** conduct a consented participant study with recorded tasks and measured accuracy, completion time, confidence, and usability. Do not treat the prefilled rating column as participant evidence.

## Cross-RQ limits and saved outputs

- Source provenance is unverified; structural reconciliation does not establish origin.
- RQ1 lacks a blind final test and independent physical-stock validation.
- RQ3 uses generated future-demand scenario inputs; owner-policy and realized outcome evidence remain missing.
- RQ4 is a rules audit, not a participant study.

Aggregate result folders:

- `research/forecasting/results/rq1_source_audit_20261109/`
- `research/experiments/results/rq1_exposure_aware_20261109/`
- `research/experiments/results/rq2_customer_prediction/`
- `research/experiments/results/rq3_scenario_comparison/`
- `research/experiments/results/rq4_explanation_case_audit/`
