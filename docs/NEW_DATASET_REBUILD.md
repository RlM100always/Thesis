# B-SMART thesis research data — current source

The active thesis research uses the real Bangladesh SME dataset supplied by the researcher through the project Google Drive folder. The package covers 2023–2025 and contains shop, product, customer, sales, payment, procurement, inventory, return, promotion and calendar data.

## Research datasets

- RQ1: 699,220 positive-sale SKU records. Missing SKU-date rows are not automatically zero.
- RQ2: 72,146 customer snapshots across 10,613 unique customers, with separate TRAIN and TEST assignments.
- RQ3: 2,500 replenishment policy scenarios. Scenario comparisons are separate from the participating owner's actual policy.
- RQ4: 1,800 explanation cases. The human_rating column is not, by itself, evidence of a completed participant study.

## Repository and data separation

- Raw source files remain in the private Google Drive folder.
- GitHub stores research code, model configurations, run manifests, non-sensitive aggregate outputs and figures.
- Do not commit raw customer identities, contact details or other personal records.
- Keep each RQ's data, target definition, split and evaluation protocol separate.

## Current work

RQ1 has existing development model outputs; exposure-aware SKU evaluation and a final untouched evaluation remain. RQ2 needs its reproducible classification pipeline and model comparison. RQ3 needs scenario evaluation and the participating owner's actual-policy comparison. RQ4 needs a real participant study before human-feedback claims can be reported.

Use the current research documentation in research/forecasting/README.md and docs/REAL_DATA_ONBOARDING.md. Do not use older reset notes as the description of the current dataset.