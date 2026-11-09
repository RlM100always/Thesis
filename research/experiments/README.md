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
python research/experiments/run_rq4_explanation_case_audit.py --data-dir /path/to/private/drive-export --figures-dir thesis_report/Figures
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

The file has 2,500 paired scenarios at the 31 July 2025 cutoff, across 32 shops and 477 SKUs. Its future-demand oracle field contains assumption-based scenario values; it is not realized future sales. The same scenario inputs were used to compare the baseline and trend policies. Costs and budgets are scenario assumptions, not observed business accounts.

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

## Multi-date validation and SME owner-impact analysis

The supplemental runner `run_multidate_business_impact.py` was executed against the same researcher-provided data export. It uses several dates so that one favourable or unfavourable cutoff does not decide the conclusion:

```bash
python research/experiments/run_multidate_business_impact.py \
  --data-dir /path/to/private/drive-export \
  --output-dir research/experiments/results/multidate_business_impact \
  --figures-dir thesis_report/Figures
```

### RQ1 — leakage-safe six-date actual-versus-predicted demand

Cutoffs: 30 April, 31 May, 30 June, 31 July, 31 August and 30 September 2025. At each cutoff, the model predicts the following seven days for all 512 shop--category series. Training origins are earlier than the cutoff and use a trailing 365-day window. The HistGradientBoosting model uses lag 1/7/14/28 demand, 7- and 28-day means and dispersion, series history and calendar encodings; the Poisson loss keeps the count target non-negative.

The earlier 32.40% figure came from a full-history series-mean feature and is no longer treated as valid primary evidence. The runner now uses a point-in-time series mean that stops strictly before each origin. The corrected six-date mean WAPE is **32.57%** for HistGradientBoosting, **39.33%** for the previous-28-day mean and **46.06%** for the weekly naive rule. Actual total demand over the six horizons is 60,982 units; the leakage-safe model predicts 58,981.02 (aggregate signed bias -3.29%). The reader-facing actual-versus-predicted graph is `thesis_report/Figures/rq1_simple_actual_vs_predicted.png`; the full two-panel diagnostic is retained as `rq1_multidate_actual_vs_predicted.png`. The per-date values and WAPE are in `rq1_multidate_metrics.csv`.

This is a seven-day shop--category validation. It must not be merged with the separate one-day SKU exposure diagnostic, where the target grain and stock-eligibility rule differ and the 28-day mean remains the strongest WAPE baseline.

### RQ1 — frozen Q4 tail stress check

`research/forecasting/run_final_holdout.py` fits the context-aware LightGBM once using data through 30 September 2025 and scores 13 weekly origins from 1 October to 24 December 2025. All rolling and cross-series features are point-in-time. The context model gives **33.45% WAPE**, MAE **6.037 units per shop-category seven-day forecast**, RMSE **8.234**, actual **120,127** units and predicted **119,369.62** units (bias **-0.63%**). The base model gives 33.58% WAPE, so context features improve the frozen-tail check by 0.13 percentage points.

The tail was inspected in earlier project work, so the output is named a **pre-inspected frozen-tail stress check**, not a blind final holdout. Its outputs are `research/forecasting/results/rq1_frozen_tail_v1/aggregate_metrics.csv`, `origin_metrics.csv`, `regime_metrics.csv`, and `run_manifest.json`; the reader-facing graphs are `thesis_report/Figures/rq1_final_holdout_actual_vs_predicted.png` and `rq1_final_holdout_regime_wape.png`. Regime-wise WAPE is reported separately because intermittent and lumpy series behave differently from smooth and erratic demand.

### RQ2 — six-date customer-inactivity stability, lift and uncertainty

Snapshot dates: 31 March and 30 June and 30 September 2024, then 31 December 2024, 31 March 2025 and 30 June 2025. Each date is scored using only earlier snapshots for fitting. The mean predicted probability is compared with the observed inactivity rate, average precision and Brier score. The highest-risk 10% is also measured against all customers.

The observed inactivity rate is 32.15--43.34% across dates, while the highest-risk 10% contains 69.91--86.06% inactive customers. That is a mean **2.06x targeting lift**; date-level bootstrap intervals average 1.98--2.14x across the six snapshots. The simple decision graph is `thesis_report/Figures/rq2_simple_targeting_lift.png`; the full rolling diagnostic remains `rq2_multidate_inactivity.png`. The mean probability is below the observed rate on every date, so the model is suitable for ranking and campaign prioritisation but needs probability calibration before a literal probability threshold is used. This does not prove that a retention message or discount causes a later purchase. Outputs: `rq2_multidate_metrics.csv` and both figures.

### RQ3 — eight-date observed-sales replenishment backtest

Cutoffs: month-end dates from 28 February through 30 September 2025. For each shop--SKU pair, the next 30 days of observed sales are the outcome. The baseline forecast is `30 * (D90 / 90)`. The trend forecast is `30 * (0.6 * D30 / 30 + 0.4 * D90 / 90)`. Orders are rounded up to the product case pack after covering the reorder point. The declared decision cost is:

```text
cost = order_quantity * purchase_cost
       + 0.02 * average_stock * purchase_cost
       + lost_units * max(retail_price - purchase_cost, 0)
```

The 2% holding factor is an assumption-based comparison term, not audited accounting profit. Across all eight dates, baseline cost is BDT 61.341m and trend-policy cost is BDT 61.675m: a weighted **+0.54%** change. Trend is cheaper at 3 dates and more expensive at 5. Both policies have zero lost units because reconstructed stock is high relative to observed demand in this sample; this is not evidence of universal stockout prevention. The new low-stock file isolates the bottom stock quartile, while `rq3_cost_sensitivity.csv` repeats the comparison at 0%, 2%, 5% and 10% holding-cost rates. Because lost units remain zero at every rate, this dataset does not identify a service-cost Pareto frontier; it identifies how the cost comparison changes when the declared holding assumption changes. The simple decision graph is `thesis_report/Figures/rq3_simple_cost_tradeoff.png`, the sensitivity graph is `rq3_cost_sensitivity.png`, and the full diagnostic remains `rq3_multidate_strategy_impact.png`. Outputs: `rq3_multidate_business_impact.csv`, `rq3_low_stock_metrics.csv`, `rq3_cost_sensitivity.csv` and the three figures.

### What this means for an SME owner

- RQ1 gives a date-specific planning signal: the owner can see the actual units, forecast units and WAPE for each cutoff, then review months with larger error rather than trusting one average score.
- RQ2 gives a manageable retention list: a small owner team can focus on the highest-risk decile, which contains about twice the inactivity rate of the full population in these snapshots.
- RQ3 exposes the cash/service trade-off: the trend rule is not automatically cheaper, and the historical backtest shows exactly which dates increase the decision-analysis cost.

These are decision-support findings, not audited profit or causal intervention results. The owner-policy replay still needs documented reorder rules, validated purchase/holding/lost-sales costs and realised outcomes from participating businesses.

## RQ4 — what is actually demonstrated

The RQ4 audit covers 1,800 prepared explanation cases dated 31 December 2025. The supplied action, constraint reason, case-pack quantity and budget checks all match at 100%; every explanation includes the stock, reorder point, pack multiple and budget evidence. The supplied `human_rating=YES` field is not treated as a participant response because it has no participant ID, consent, task completion record, timestamp or response provenance. Validated participant responses are therefore **0**.

The runner now creates `thesis_report/Figures/rq4_explanation_evidence.png`, which places the 100% mechanical pass rates beside the 0 validated participant responses. This makes the correct RQ4 conclusion visible: the explanation mechanism is computationally consistent, but usability, confidence, task accuracy and decision time remain unevaluated.

## Integrated result overview and thesis novelty

To build the one-page summary figure after the RQ1--RQ4 runners have run:

```bash
python research/experiments/build_thesis_results_overview.py
```

The output is `thesis_report/Figures/thesis_results_overview.png`. It shows actual-versus-forecast demand, the customer targeting lift, the replenishment cost trade-off and the RQ4 evidence boundary in one view.

The thesis contribution is decision-oriented rather than a claim of a new machine-learning algorithm. Its design contribution is the combination of exposure-aware demand targets, date-aware validation, top-decile customer targeting, constraint- and cost-linked replenishment, and an explanation audit that separates mechanical consistency from human usability. The data analysis determines the method: sparse/lumpy demand requires exposure and aggregation checks; imbalanced inactivity requires PR-AUC and lift; stock-rich replenishment requires cost decomposition; and prepared explanation cases cannot substitute for a participant study.

## Cross-RQ limits and saved outputs

- Source provenance is unverified; structural reconciliation does not establish origin.
- RQ1 lacks a blind final test and independent physical-stock validation.
- RQ3 includes an observed-sales backtest, but its cost terms are assumptions and owner-policy and audited realised-cost evidence remain missing; the separate 2,500-row scenario file uses assumption-based future-demand values.
- RQ4 is a rules audit, not a participant study.

Aggregate result folders:

- `research/forecasting/results/rq1_source_audit_20261109/`
- `research/experiments/results/rq1_exposure_aware_20261109/`
- `research/experiments/results/rq2_customer_prediction/`
- `research/experiments/results/rq3_scenario_comparison/`
- `research/experiments/results/rq4_explanation_case_audit/`
- `research/experiments/results/multidate_business_impact/`
