# B-SMART context-aware forecasting experiment (v1)

## Why this experiment exists

The audited shop-category model uses only local-series history and calendar variables. The new challenger adds point-in-time cross-series context from the same observed-sales panel: shop totals, category totals, network totals, short-window trends, and the focal series' share of its shop/category/network. The purpose is to test whether information shared across related series reduces forecast error without using future observations.

## Data and evidence status

Input: controlled Drive file `rq1_daily_shop_category.csv`, SHA-256 recorded in `run_manifest.json`. It contains 561,152 daily rows, 512 shop-category series, 32 shops, 16 categories, 1,096 days, and 1,580,361 observed units. The zero-sales share is 37.5962%.

**Evidence status remains `provenance_conflict`.** The current Drive manifest says real SME data; the prior repository onboarding record classifies a same-seed/same-count package as synthetic. These results are controlled development evidence and must not be represented as verified real-world SME performance.

## Model design

- Target: direct cumulative observed units for the next 1, 7, 14, or 28 days.
- Feature minimum history: 56 days.
- Training origins: every 14 days; every training target window ends strictly before its validation origin.
- Seven-day validation origins: nine monthly origins, January–September 2025.
- 1-, 14-, and 28-day validation origins: July, August, and September 2025.
- Q4 2025 is excluded because it was previously inspected.
- Baseline and context models use identical LightGBM Tweedie parameters and identical origins.
- No SKU missing-date imputation is performed. The experiment is shop-category observed-sales only.

The context layer adds:
1. Shop-level observed sales sums and means over 7/28/56 days and 28-day trend.
2. Category-level observed sales sums and means over 7/28/56 days and 28-day trend.
3. Network-level observed sales sums over 7/28 days.
4. Focal series' 28-day share of shop and category totals.
5. Shop/category share of network 28-day sales.

Every contextual aggregate is calculated only from dates before the forecast origin.

## Results

Seven-day pooled WAPE decreases from 33.4699% (base) to 32.6627% (context), an absolute improvement of 0.8072 percentage points (2.41% relative). The context model wins 6 of 9 monthly origins. A paired 2,000-replicate shop-category cluster bootstrap estimates the WAPE difference (context minus base) at -0.8115 percentage points, 95% interval [-1.0907, -0.5170] points.

The context model's seven-day aggregate bias is -6.05%, versus -2.02% for the base model. Lower WAPE therefore comes with greater under-forecasting. A past-fold-only multiplicative adjustment reduces bias to -1.61% but raises pooled WAPE to 32.8959%; it is an optional business-loss trade-off, not the default forecast.

The context model improves pooled WAPE at all four tested horizons in this development experiment. The 1-, 14-, and 28-day comparisons use three origins each; only the seven-day result has nine origins. These are not final-test estimates.

## Uncertainty and hierarchy

Seven-day prequential scaled-residual intervals are calibrated using only earlier validation origins. Across April–September 2025, empirical coverage averages 79.43% for nominal 80% intervals and 89.55% for nominal 90% intervals. The 90% mean interval width is 26.69 units per shop-category seven-day target. Coverage varies by origin, so these intervals remain development diagnostics, not guaranteed future coverage.

Bottom-up aggregation of the same leaf forecasts is arithmetically coherent. Seven-day WAPE is 32.66% at shop-category, 14.95% at shop total, 10.98% at category total, and 7.85% at network total. The lower aggregate errors partly reflect cancellation and must not be used as evidence of leaf-level replenishment accuracy.

## Decision

Promote the context features as a validated development challenger, not yet as the production-selected model. Keep the original global LightGBM as fallback until the context model's bias, business costs, and performance on a genuinely untouched future period or held-out businesses are evaluated. Do not automatically route the four intermittent series to Croston/TSB. SKU-level forecasts remain blocked pending verified active-assortment and stock-exposure labels and resolution of the negative-stock anomalies recorded in the source audit.

## Reproduction

```bash
python -m pip install -r research/forecasting/requirements.txt
python research/forecasting/context_aware_experiment.py \
  --input /path/to/rq1_daily_shop_category.csv \
  --output /path/to/context_aware_v1 \
  --evidence-status provenance_conflict
```

Outputs include fold and aggregate metrics, paired bootstrap, prequential intervals, hierarchy roll-ups, prequential bias calibration, predictions, and a run manifest. Raw business records are not committed.
