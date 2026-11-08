# RQ1 shop-category forecasting experiment

This code is the reproducible implementation used for the RQ1 development results in the main thesis report at `thesis_report/main.tex`. It is not a separate thesis/report format.

## Input

Use the controlled Google Drive export `rq1_daily_shop_category.csv`. Do not commit the raw business dataset to this public repository. The experiment manifest records the input SHA-256 so that a run can be matched to the source file.

The supplied dataset manifest declares the package as real SME sales or real people. The separate `simulated_unmet_demand` table is not used as observed sales or as the RQ1 target.

## Run

Install the pinned dependencies:

```bash
python -m pip install -r research/forecasting/requirements.txt
python research/forecasting/rq1_shop_category_experiment.py \
  --input /path/to/rq1_daily_shop_category.csv \
  --output /path/to/rq1_results
```

## Protocol

- Unit: shop-category-day; 32 shops, 16 categories, 512 series.
- Horizons: direct cumulative 1, 7, 14, and 28 days.
- Development origins: 1 July, 1 August, and 1 September 2025.
- Training origins: every 28 days; each training target window ends before its validation origin.
- Historical features only; minimum feature history 56 days.
- Candidates: LightGBM Tweedie, weekly seasonal naive, Croston-SBA, and TSB.
- Q4 2025 is excluded from model selection because it was previously inspected.
- No final untouched holdout is claimed.

## Outputs

The run writes forecast-level predictions, per-origin metrics, aggregate metrics, demand-regime metrics, a regime distribution summary, and a run manifest. The committed CSV files under `results/` are aggregate evidence only. The raw source data and full prediction rows remain outside the public repository.

## Interpretation boundary

The current result is for the aggregated shop-category panel, not an SKU-level forecast. Observed sales may be censored by stock-outs. Price, promotion, inventory, and purchase tables have not yet been joined with point-in-time availability checks. The development results must not be described as final test performance or as proof of generalization to all SME sectors.
