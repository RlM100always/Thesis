# RQ2-RQ4 research experiments

These scripts complement the RQ1 shop-category forecasting pipeline. Raw Drive exports, customer identifiers and row-level predictions are not committed to this repository. Keep the controlled source files in the project's Drive folder and pass their local export directory with `--data-dir`.

## RQ2 — 90-day customer inactivity prediction

### Original classifier comparison (v1)

Required controlled inputs:

- `rq2_customer_snapshots_90d.csv` (Google Drive export with `inactive_next_90d_label`)
- `sales_orders.csv`

Run the original experiment to reproduce the initial Logistic Regression, LightGBM and CatBoost comparison:

```bash
python research/experiments/rq2_customer_prediction.py \
  --data-dir /path/to/controlled/exports \
  --snapshot-file rq2_customer_snapshots_90d.csv \
  --output-dir research/experiments/results/rq2_customer_prediction_v1 \
  --bootstrap-replicates 500
```

### Threshold refinement (v2)

Run the three stages in order. Each stage uses TRAIN only until the final scoring stage:

```bash
python research/experiments/rq2_customer_prediction_v2.py --stage select \
  --data-dir /path/to/controlled/exports \
  --snapshot-file rq2_customer_snapshots_90d.csv \
  --output-dir research/experiments/results/rq2_customer_prediction_v2

python research/experiments/rq2_customer_prediction_v2.py --stage threshold \
  --data-dir /path/to/controlled/exports \
  --snapshot-file rq2_customer_snapshots_90d.csv \
  --output-dir research/experiments/results/rq2_customer_prediction_v2

python research/experiments/rq2_customer_prediction_v2.py --stage score \
  --data-dir /path/to/controlled/exports \
  --snapshot-file rq2_customer_snapshots_90d.csv \
  --output-dir research/experiments/results/rq2_customer_prediction_v2 \
  --bootstrap-replicates 500
```

The v2 pipeline preserves the supplied chronological TRAIN/TEST split and independently reconstructs the 90-day no-repeat label from order headers. It compares the original CatBoost feature set with a past-only customer-trajectory extension on the first two rolling-origin TRAIN folds. The selected feature set is calibrated using those two folds. The final TRAIN origin (31 December 2024) is reserved for threshold selection: the primary threshold maximises precision subject to at least 85% recall. TEST is scored only after the model, calibrator and threshold are frozen.

The v2 outputs include TRAIN-only model and threshold selection tables, TEST operating-point comparisons, snapshot-level and latest-snapshot-per-customer metrics, confusion counts, ROC coordinates, calibration bins, date-level metrics, feature importance and customer-cluster bootstrap intervals. Only aggregate outputs are written; no customer IDs or row-level predictions are exported.

**Interpretation limit:** v2 changes the classification operating point; it does not materially improve ranking discrimination. The TEST set was already evaluated in v1, so v2 TEST results are a repeated-holdout diagnostic rather than a pristine independent confirmation. A later untouched period is needed for independent confirmation.

## RQ3 — replenishment policy scenario audit

Required controlled inputs:

- `rq3_offline_policy_comparison.csv`
- `products.csv`

Run:

```bash
python research/experiments/rq3_policy_scenario_audit.py \
  --data-dir /path/to/controlled/exports \
  --input-file rq3_offline_policy_comparison.csv \
  --products-file products.csv \
  --output-dir research/experiments/results/rq3_policy_scenario_audit_v1 \
  --bootstrap-replicates 5000
```

This is a paired scenario audit. The future-demand column is synthetic oracle demand, the scenario-cost formula is not documented, and the owner's actual current policy is not supplied. Do not interpret the result as realised savings or a causal policy comparison.

## RQ4 — decision-rule and explanation audit

Required controlled inputs:

- `rq4_explanation_cases_A.csv` (the richer export containing `explanation` and `human_rating`)
- `products.csv`

Run:

```bash
python research/experiments/rq4_explanation_audit.py \
  --data-dir /path/to/controlled/exports \
  --input-file rq4_explanation_cases_A.csv \
  --products-file products.csv \
  --output-dir research/experiments/results/rq4_explanation_audit_v1
```

The script independently recomputes inventory position, reorder trigger, pack-rounded quantity and budget cap; compares quantity, action and constraint reason; audits the supplied explanation text; and generates deterministic English/Bangla explanations with branch-specific numeric evidence coverage. The supplied `human_rating` value is constant across all rows, so it is not participant-study evidence. See `docs/RQ4_USER_STUDY_PROTOCOL.md` for the planned owner study.

## Reproducibility and claim limits

- Machine-readable aggregate outputs and run manifests are stored under `research/experiments/results/`.
- Dataset SHA-256 values and software versions are recorded in each run manifest.
- Do not commit raw Drive exports, customer-level records or row-level predictions.
- The research CI workflow runs contract tests, compile checks and CLI smoke tests. A separate workflow compiles the updated LaTeX report.
