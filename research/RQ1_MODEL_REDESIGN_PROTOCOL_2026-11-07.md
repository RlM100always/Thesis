# RQ1 model redesign protocol — 7 November 2026

## Objective
Do not optimise the held-out October–December 2025 test set. The reported WAPE 83.98% is a serious result, not a score to hide. Select models using chronological validation only, then evaluate a frozen model once on a genuinely untouched forward test. Because the current test period has already been examined repeatedly, all further comparisons on it are exploratory.

## What the current evidence says
- 47,104 held-out shop × category × day rows; 39.82% have zero recorded sales.
- WAPE by aggregation of the same leaf predictions: network/day 6.02%; shop/day 31.43%; category/day 16.55%; shop × category/day 83.98%.
- The network WAPE is a portfolio-level total, not evidence of accurate replenishment for each shop/category. Opposite signed leaf errors cancel when summed.
- Refit LightGBM 83.98%; two-stage hurdle 84.04%; XGBoost 84.56%. These candidates did not improve the leaf-level score.
- Existing experiment is rolling one-day-ahead: each prediction can use the previous day's actual sale. It does not establish 7/14/28-day-ahead accuracy for inventory planning.

## Key modelling diagnosis to perform before tuning
1. **Target validity:** observed sales are not necessarily unconstrained demand. Zero sales can mean no demand or no available stock. Do not label zero as no-demand without stock availability / lost-sales evidence.
2. **Panel integrity:** verify each shop-category has a complete daily calendar; distinguish missing rows from explicit zero rows; check duplicates and category/shop mapping changes.
3. **Demand regime:** compute per series Average Demand Interval (ADI), squared coefficient of variation (CV²), zero fraction, non-zero mean/variance, run lengths, and seasonality. Classify smooth/intermittent/erratic/lumpy with stated thresholds, as a diagnostic rather than ground truth.
4. **Feature validity:** only information available at forecast origin is allowed. For multi-step horizons, do not feed actual sales from days after the origin as lag features.
5. **Business segmentation:** assess error per shop, category, and shop-category series; use paired block bootstrap by shop (and time blocks) for uncertainty.

## Candidate model architecture
Use a *regime-aware, partially pooled forecasting system*, not one universal regressor.

### A. Global regular-demand model
For series with enough non-zero observations and stable demand, fit CatBoost or LightGBM with:
- lags 1, 7, 14, 28, 56 and (only if history supports it) 364;
- rolling mean/median/std and zero fraction over 7/14/28/56 days, all shifted so they end before the forecast origin;
- recency since last non-zero sale; non-zero mean and demand interval;
- day-of-week and annual cyclic features;
- shop and category identifiers, plus static metadata only after provenance and stability checks.
Tune depth, leaf size, regularisation, objective (Poisson/Tweedie/Huber) and shrinkage on validation. Do not assume Tweedie or a deeper tree is automatically better.

### B. Intermittent-demand model
For intermittent/lumpy series compare Croston, SBA and TSB, plus a pooled occurrence/size model:
- occurrence classifier estimates P(sale > 0);
- conditional quantity model estimates E(quantity | sale > 0);
- expected sales = probability × conditional quantity.
Use calibrated probabilities and compare against simple Croston/SBA/TSB; the two-stage result already tested (84.04%) is not sufficient evidence that the family cannot work—its feature design, calibration and regime segmentation need audit.

### C. Hierarchical reconciliation
Produce forecasts at shop-category, shop-total, category-total and network-total levels. Compare:
- bottom-up sum of leaf forecasts;
- direct aggregate models;
- reconciliation (e.g. MinT only when covariance estimates are stable).
Report each level separately and verify arithmetic coherence. Never use network WAPE to claim leaf accuracy.

### D. Forecast horizon
Evaluate one-day rolling forecast separately from true 7-, 14- and 28-day forecasts. For the latter, create origin-based features and direct multi-horizon targets or recursive predictions without actual future lags. Inventory policy should use lead-time demand, not a one-day forecast relabelled as 30-day demand.

## Experiment design
- Keep October–December 2025 as a previously inspected exploratory test, not a tuning set.
- Use at least three rolling-origin validation windows before the final test, each with a fixed forecast horizon and an embargo where target windows overlap.
- Fit imputers, encoders, calibration and feature selection on training data only.
- Baselines: seasonal naive, trailing mean, zero forecast, Croston/SBA/TSB.
- Models: current LightGBM, regularised global LightGBM/CatBoost, Poisson/Tweedie, hurdle occurrence × size, regime-specific ensemble.
- Metrics: WAPE and MAE plus MASE/RMSSE, signed bias, zero-event precision/recall/Brier, quantile pinball loss and interval coverage. State that WAPE is unstable or undefined for all-zero segments.
- Use paired block bootstrap by shop and time to report confidence intervals. Report mean and dispersion across shops, not only pooled rows.
- Select model on validation with a predeclared business loss; freeze it before any new test.

## Success criterion
A candidate is better only if it improves the predeclared leaf-level and lead-time business metrics on multiple validation windows without materially worsening bias, high-volume categories, or service-level constraints. If no candidate beats the baseline reliably, report that as a valid finding and investigate data/target limitations rather than selecting a winner post hoc.

## Data required for a stronger claim
Daily on-hand stock / availability, stockout timestamps, lost-sales or demand proxy, price, promotions, opening hours, holidays, supplier lead time, order quantities and returns. Without these, call the target *observed sales*, not latent demand, and state the limits of inventory recommendations.

## Immediate next actions
1. Freeze source hashes and verify provenance, permission and ethical basis.
2. Reconcile daily panel against raw orders/lines; prove missing-vs-zero logic.
3. Generate demand-regime and shop/category error diagnostics.
4. Build origin-safe multi-horizon dataset.
5. Run validation-only candidate comparison; publish all results including failures.
6. Freeze final candidate and evaluate on a new untouched period or an external business cohort.
7. Update Chapter 3 (target, horizons, splits, feature timing), Chapter 4 (model implementation), Chapter 5 (all results and diagnostics), Chapter 6 (contribution and limitations), abstract and figures.

## Claim boundaries
This redesign is a research plan until the experiments are executed. It does not assert that any candidate will achieve a lower WAPE. Do not invent a target score or tune against the repeatedly viewed test set.
