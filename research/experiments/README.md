# RQ2-RQ4 research experiments

These scripts complement the RQ1 shop-category forecasting pipeline. Raw Drive exports, customer identifiers and row-level predictions are not committed to this repository. Keep the controlled source files in the project's Drive folder and pass their local export directory with `--data-dir`.

## RQ2 — 90-day customer inactivity prediction

Required controlled inputs:

- `rq2_customer_snapshots_90d_A.csv` (the selected export with `inactive_next_90d_label`; the script also accepts `inactive_next_90d_synthetic_label`)
- `sales_orders.csv`

Run:

```bash
python research/experiments/rq2_customer_prediction.py \
  --data-dir /path/to/controlled/exports \
  --snapshot-file rq2_customer_snapshots_90d_A.csv \
  --output-dir research/experiments/results/rq2_customer_prediction_v1 \
  --bootstrap-replicates 500
```

The script reconstructs the no-purchase-within-90-days target from order headers and stops unless it matches the supplied label exactly. It preserves the supplied chronological TRAIN/TEST split, uses rolling-origin validation inside TRAIN, compares a recency rule, logistic regression, LightGBM and CatBoost, calibrates with training-only out-of-time predictions, and selects the F2 threshold without using TEST. Only historical snapshot fields and deterministic transformations are used. Current customer-master attributes without effective-date history are excluded. Customer IDs and names are excluded from model features. The script writes aggregate metrics, date-level metrics, calibration bins, customer-cluster bootstrap intervals and feature importance.

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
