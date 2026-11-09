# Research dataset — current source and workflow

Status: 9 November 2026

## Dataset identity

The researcher supplied the Bangladesh data package through the project Google Drive folder. Its manifest claims real SME sales and people, in BDT, covering 1 January 2023 to 31 December 2025. The manifest also records a generation seed and describes validation as a “modeled world”. No independent source-system export, business-owner attestation, or source lineage was available for this review, so origin and representativeness remain unverified. Report results as conditional on the supplied package.

Manifest-level structure:

| Dataset component | Records / entities |
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

These are the counts declared by the Drive manifest. Research-specific prepared files have their own counts below.

## Research-question datasets

### RQ1 — Demand forecasting

The prepared SKU-level file contains 699,220 positive-sale records. It is a sparse observed-sales file: a missing SKU-date must not automatically be converted to zero. The SKU must be active and the relevant availability/exposure evidence must support a true zero-sales observation. Keep stockout, inactive-assortment, closed-shop and unknown-availability periods distinct.

### RQ2 — Customer prediction

The customer snapshot dataset contains 72,146 snapshots and 10,613 unique customers. It includes separate TRAIN and TEST assignments. Preserve the supplied split for the primary evaluation. Fit preprocessing, feature selection, calibration and model selection on TRAIN only; evaluate on TEST only after the pipeline is frozen.

### RQ3 — Replenishment

The policy dataset contains 2,500 scenarios. It supports controlled scenario-based policy evaluation. Scenario outcomes must be reported as scenario results; they do not replace a participating owner's documented current replenishment policy or prove observed business savings.

### RQ4 — Explanation evaluation

The explanation dataset contains 1,800 cases. A field named human_rating does not by itself establish that real participants supplied ratings. Treat the cases as prepared evaluation material and report an actual user study only after participant recruitment, consent, task completion and recorded responses have taken place.

## Research workflow

1. Read the Drive manifest and inspect every source file's actual columns, data types, keys, date coverage and row counts.
2. Keep a frozen copy of each source file and record its SHA-256 checksum before modelling.
3. Reconcile joins and totals across orders, sales lines, products, inventory movements and prepared analytical files.
4. For RQ1, construct exposure-aware SKU panels; never fill every missing SKU-date with zero.
5. For RQ2, preserve the supplied TRAIN/TEST split and prevent customer-level and time-based leakage.
6. For RQ3, compare policies on identical scenario inputs and separately obtain the participating owner's actual policy for a real-business comparison.
7. For RQ4, distinguish prepared explanation cases from feedback collected in a real participant study.
8. Save predictions, metrics, figures, configuration, split definitions, checksums and environment details for every model run.
9. Write the Implementation and Experimental Results chapters from saved, reproducible outputs. Do not invent model scores, policy outcomes or user-study findings.

## Data handling

Raw source files remain in the private project Google Drive folder. Do not commit raw customer records, contact details or other identifiable information to GitHub. Commit code, non-sensitive aggregate outputs, figures and run manifests needed to reproduce the research.

## Current research boundary — 9 November runs

- **RQ1:** Source joins and quantities reconcile internally. The new exposure-conditioned diagnostic covers 1,130,148 Q4 shop-SKU days, but the period was previously inspected; the 28-day exposed-sales mean (183.65% WAPE) slightly outperformed HistGradientBoosting (184.66%). No untouched test or independent physical-stock validation is available.
- **RQ2:** The 90-day labels were rebuilt from supplied orders with zero mismatches. On the supplied temporal split, HistGradientBoosting achieved PR-AUC 0.746 and ROC-AUC 0.830. Source provenance remains unverified; no causal retention effect was evaluated.
- **RQ3:** The trend policy lowered cost by 0.87% but increased scenario lost units from 45 to 100 across 2,500 generated-oracle scenarios. The participating owner's actual policy and realised outcomes remain unavailable.
- **RQ4:** All 1,800 prepared cases passed action, explanation and constraint checks. The supplied YES ratings have no participant provenance; validated participant responses remain zero.