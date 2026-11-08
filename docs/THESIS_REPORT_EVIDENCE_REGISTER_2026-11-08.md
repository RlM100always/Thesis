# Thesis evidence register — 8 November 2026

## Active source and provenance
- Active dataset location: user-linked Google Drive folder SME datasets.
- Current manifest declares real SME sales or real people; the project owner confirms this is the intended source.
- An earlier repository onboarding note records a conflicting classification for a same-seed package. This report uses the current Drive snapshot as user-declared source data but does not claim independent verification of collection, ownership or consent.
- The empirical shop table contains 32 Grocery and FMCG Retail shops. Results should not be generalised to other SME sectors without additional data.

## RQ1 — branch--SKU forecasting
- Source files: rq1_daily_sku_sales_observed, inventory_movements, products, shops, calendar and promotions.
- Derived panel: 13,272 shop--SKU series, 1,096 dates, 699,220 observed daily sales rows.
- Primary run: LightGBM Tweedie, 45 trees, 80,000 training rows per horizon, 7/14/28-day horizons, three out-of-time test origins (July--September 2025).
- 7-day context-minus-history WAPE: -0.010845; 2,000 branch--SKU cluster bootstrap 95% interval [-0.012052, -0.009770].
- 7-day 80% empirical interval coverage: 82.70%; mean width 2.41 units.
- A separate 250-tree full-training challenger was evaluated. It improves WAPE at 7 and 14 days but does not beat seasonal naive on MASE; at 28 days it also loses on WAPE.
- Warning: 7-day pooled WAPE remains above 100%; model quality is not sufficient to claim universal forecast superiority.

## RQ2 — customer inactivity
- Source: rq2_customer_snapshots_90d.
- 72,146 snapshots; 10,613 customers; 21,164 test rows; 90-day outcome.
- LightGBM with Platt calibration: PR-AUC 0.731453; Lift@10% 2.031319; Brier 0.173161; ECE 0.050160; ROC-AUC 0.819752.
- Customer-cluster bootstrap (400 resamples): PR-AUC 95% interval [0.720232, 0.742776]; Lift@10% [1.985879, 2.076157]; Brier [0.170220, 0.176162]; ECE [0.044469, 0.055619].
- This is a temporal repeat-customer test, not a cold-start test.

## RQ3 — replenishment
- Historical procurement: 122,422 purchase orders and lines; 32 shops; 56 suppliers; median observed lead time 7 days; p90 13 days.
- Scenario file: 2,500 cases, one cutoff (31 July 2025), synthetic future oracle demand.
- Scenario baseline cost BDT 2,227,690.07; trend scenario BDT 2,208,289.47 (-0.87%); stock-out units rise from 45 to 100 (+122.2%).
- 2,000 shop-cluster bootstrap: cost change 95% interval [-1.009826%, -0.728477%]; stock-out difference [32, 82.025] units.
- No documented owner policy rule or decomposed validated cost components are present in the supplied scenario file.

## RQ4 — explanation evaluation
- 1,800 generated cases; 1,601 NO_ACTION; 199 REORDER; 100% action--quantity rule consistency.
- human_rating is YES for every row and is not a measured rating.
- No participant, consent, randomized condition, decision response, correctness, time, confidence or usability outcomes are supplied.
- Prepared 899 matched pairs, two counterbalanced forms of 1,798 tasks each, scoring key and data-collection template.
- Human study remains pending; no participant results are claimed.

## Report status
RQ1 and RQ2 have model-based results with stated limitations. RQ3 has historical procurement evidence and a scenario comparison, but not a validated owner-policy experiment. RQ4 has generated-case checks and study materials, but no human-participant results.
