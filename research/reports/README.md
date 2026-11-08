# RQ1 development evidence — 8 November 2026

This is a first empirical development pass on the supplied RQ1 daily shop-category panel. It is separate from the production application.

## Evidence status

**EXPLORATORY — PROVENANCE NOT VERIFIED.** The Drive manifest claims real SME data but records a fixed seed and a simulated-unmet-demand table. An earlier repository audit records a conflicting synthetic flag for a related SKU export; the current downloaded SKU CSV has no row-level flag. Obtain source-system extracts and a data-owner provenance statement before making real-world empirical claims.

## Data audit

- 561,152 daily rows; 32 shops; 16 categories; 512 series.
- 2023-01-01 through 2025-12-31; 1,580,361 observed units.
- 37.5962% zero-sales observations.
- No duplicate series-date keys, missing values, zero-flag mismatches or missing dates.
- SKU export: 699,220 positive observations; missing dates are not automatically zero.

## First development comparison

Three origins: 2025-07-01, 2025-08-01, 2025-09-01. Q4 2025 was excluded because previously inspected. Each horizon has 1,536 series-origin predictions.

| Horizon | LightGBM Tweedie WAPE | Seasonal naive WAPE | Croston classic WAPE |
|---:|---:|---:|---:|
| 1 day | 82.73% | 91.65% | 85.16% |
| 7 days | 33.84% | 40.88% | 38.62% |
| 14 days | 24.66% | 32.31% | 31.89% |
| 28 days | 18.84% | 25.57% | 27.06% |

These are development scores, not final holdout results. The training-origin stride is 90 days; there was no hyperparameter search, interval calibration or final model selection. Sales are not unconstrained demand when stock availability is unknown.

## Run

python research/forecasting/run_rq1_experiment.py --input path/to/panel.csv --output artifacts/rq1_development --evidence-status provenance_conflict

See RQ1_Empirical_Development_Report.tex for methods, detailed results, limitations and next research gates.

The earlier 83.98% WAPE figure has not been reproduced. Its exact script, target level, test rows, origin and metric implementation must be matched before comparison. The current 82.73% 1-day score is at shop-category level and is not directly comparable with a previously reported individual-level result.
