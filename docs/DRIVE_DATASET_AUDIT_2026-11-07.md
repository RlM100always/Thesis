# Google Drive dataset audit — current thesis package

Updated: 9 November 2026

## Source and provenance

The researcher supplied the Bangladesh data package through the project Google Drive folder. The manifest claims real SME sales and people, in BDT, covering 1 January 2023 to 31 December 2025. It also records a generation seed and describes business validation as a “modeled world”. No independent source-system export, business-owner attestation, or source lineage was available for this audit. The data origin and representativeness therefore remain unverified. Results below are conditional on the supplied package.

Raw source files remain in Drive. The repository stores code and non-sensitive aggregate outputs; raw customer and transaction records are not committed.

## Manifest inventory

| Dataset | Manifest count |
|---|---:|
| Shops | 32 |
| Customers | 11,000 |
| Products / SKUs | 480 |
| Suppliers | 56 |
| Sales orders | 365,447 |
| Sales lines | 736,683 |
| Payments | 381,756 |
| Purchase orders | 122,422 |
| Purchase lines | 122,422 |
| Inventory movements | 994,808 |
| Inventory lots | 134,379 |
| Returns | 5,102 |
| Promotions | 1,216 |
| Calendar records | 1,096 |

## Research datasets

| Research question | Dataset size | Interpretation |
|---|---:|---|
| RQ1 — Demand forecasting | 699,220 positive-sale SKU records; 561,152 shop-category-day records | Sparse SKU file; a missing SKU date is not automatically zero demand. The SKU diagnostic labels only ledger-reconstructed full-day stock exposure. |
| RQ2 — Customer prediction | 72,146 snapshots; 10,613 customers | Supplied chronological TRAIN/TEST assignments preserved. Repeated customers appear across temporal partitions; cluster bootstrap used. |
| RQ3 — Replenishment | 2,500 scenarios | The future-oracle demand field contains generated scenario values, not realized future sales. No participating owner's actual policy is included. |
| RQ4 — Explanation evaluation | 1,800 cases | Prepared rule-test cases; their values are not live inventory records. The YES field has no participant or response provenance. |

## Source reconciliation and exposure audit

The 9 November audit found 0 unmatched order-line joins, 0 shop mismatches, 0 SKU quantity mismatches, 0 positive-category mismatches, 0 unmatched sale movements, and 0 unmatched purchase receipts. The prepared SKU and shop-category totals reconcile to 1,580,361 units. These checks establish internal consistency, not authenticity or physical-stock accuracy.

The inventory file contained 994,808 movements. The audit found 269 negative-balance events across 253 shop-SKU histories and 330 positive-sale days with non-positive reconstructed intraday stock. The exposure-conditioned panel quarantines all 253 affected histories, retains 13,545,871 positive-stock shop-SKU days, assigns zeros only to 12,860,044 eligible exposed zero records, and retains 685,827 eligible positive-sale records.

## Experimental results recorded 9 November

### RQ1 — SKU observed-sales diagnostic

The previously inspected Q4 2025 period contains 1,130,148 exposed shop-SKU days from 13,019 series, 119,161 observed units, and a 95.34% zero share. WAPE was 190.28% for weekly seasonal naive, 183.65% for the 28-day exposed-sales mean, and 184.66% for HistGradientBoosting. The HGB-minus-mean WAPE difference was +1.01 percentage points (2,000-resample shop-bootstrap 95% interval: -0.21 to +2.25). HGB did not beat the strongest simple baseline on WAPE. The period was previously inspected and is not a final blind holdout. Exposure is reconstructed from ledger records and has not been validated against physical stock.

### RQ2 — customer inactivity

The 90-day labels were independently rebuilt from order dates with 0 mismatches across all 72,146 snapshots. The supplied temporal split contains 50,982 training and 21,164 test rows. HistGradientBoosting achieved test PR-AUC 0.746, ROC-AUC 0.830, Brier score 0.168, precision 0.588, and recall 0.913 at a threshold selected on the final training cohort. Customer-cluster bootstrap 95% interval for PR-AUC: 0.736–0.758. These are predictive results on the supplied snapshots, not causal retention-effect estimates.

### RQ3 — replenishment scenarios

Across 2,500 scenarios, the trend policy reduced total scenario cost from BDT 2,227,690.07 to BDT 2,208,289.47 (-0.87%) while scenario lost units increased from 45 to 100. The paired bootstrap cost difference was -BDT 7.76 per scenario (95% interval -9.26 to -6.30); lost-unit change was +0.022 per scenario (0.012 to 0.034). This result uses generated future-demand scenario values; it is not realised savings or an owner-policy comparison.

### RQ4 — explanation cases

All 1,800 cases matched the recomputed action and constraint reason; all quantities were case-pack multiples within the stated scenario budget, and the explanation text mentioned the required inputs. The cases are prepared rule-test data, not participant observations. Validated participant responses: 0. No usability or task-performance outcome is available.

## Remaining evidence

1. Verify source lineage and independently validate stock exposure.
2. Freeze RQ1 model selection and run one untouched future or held-out-business evaluation.
3. Obtain a participating owner's actual replenishment policy and validated outcomes for policy replay.
4. Conduct a consented RQ4 participant study with recorded tasks and measured accuracy, completion time, confidence, and usability.
5. Keep all claims conditional until source provenance is established.
